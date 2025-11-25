# reservas/views.py
# -*- coding: utf-8 -*-
from decimal import Decimal
import io

from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseBadRequest, HttpResponse, Http404
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.utils.dateparse import parse_date
from django.template.loader import get_template

from xhtml2pdf import pisa  # pip install xhtml2pdf

from accounts.utils import _is_admin

from .models import Reservation, Payment
from habitaciones.models import Habitacion


User = get_user_model()


class AdminRequiredMixin(LoginRequiredMixin):
    """
    Mixin para restringir vistas al personal del hotel (admin/gerencia/staff),
    usando el rol y flags del usuario.
    """
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        if not _is_admin(request.user):
            messages.error(
                request,
                "No tienes permiso para acceder al panel administrativo del hotel."
            )
            return redirect("accounts:portal_cliente")
        return super().dispatch(request, *args, **kwargs)


# ==========================
# Vistas ADMIN de reservas
# ==========================


class ReservationsListView(AdminRequiredMixin, View):
    """
    Listado principal de reservas para el panel de administración.
    Incluye:
      - Búsqueda por texto
      - Filtro por estado
      - Filtro por huésped registrado
      - Filtro por habitación
    """
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        qs = (
            Reservation.objects
            .select_related("room", "guest", "room__tipo")
            .prefetch_related("payments")
        )

        q = (request.GET.get("q") or "").strip()
        status = (request.GET.get("status") or "").strip()
        guest_id = (request.GET.get("guest") or "").strip()
        room_id = (request.GET.get("room") or "").strip()

        # Búsqueda texto
        if q:
            qs = qs.filter(
                Q(code__icontains=q) |
                Q(guest_name__icontains=q) |
                Q(guest_email__icontains=q) |
                Q(room__codigo__icontains=q)
            )

        # Filtro por estado
        if status:
            qs = qs.filter(status=status)

        # Filtro por huésped (solo usuarios registrados)
        if guest_id:
            qs = qs.filter(guest_id=guest_id)

        # Filtro por habitación
        if room_id:
            qs = qs.filter(room_id=room_id)

        # KPIs / resumen simple (ya filtrado)
        kpis = {
            "total": qs.count(),
            "pendientes": qs.filter(status=Reservation.Status.PENDING).count(),
            "confirmadas": qs.filter(status=Reservation.Status.CONFIRMED).count(),
            "en_curso": qs.filter(status=Reservation.Status.CHECKED_IN).count(),
        }

        # Estados disponibles para el filtro
        status_choices = Reservation.Status.choices

        # Habitaciones disponibles para seleccionar en filtros / modal
        habitaciones = (
            Habitacion.objects
            .select_related("tipo")
            .all()
            .order_by("piso", "codigo")
        )

        # Clientes/huéspedes registrados para el filtro de huésped
        clientes = (
            User.objects
            .filter(is_active=True)
            .order_by("username")
            .distinct()
        )

        context = {
            "reservas": qs.order_by("-created_at"),
            "status_choices": status_choices,
            "habitaciones": habitaciones,
            "clientes": clientes,
            "kpis": kpis,
        }
        return render(request, "reservas/lista_reservas.html", context)


class ReservationCreateView(AdminRequiredMixin, View):
    """
    Crea una nueva reserva desde el modal "Nueva Reserva".
    """
    login_url = "/login/"

    def post(self, request, *args, **kwargs):
        # Datos de huésped
        guest_id_raw = (request.POST.get("guest_id") or "").strip()
        guest_name = (request.POST.get("guest_name") or "").strip()
        guest_email = (request.POST.get("guest_email") or "").strip()
        guest_phone = (request.POST.get("guest_phone") or "").strip()

        guest = None
        if guest_id_raw:
            try:
                guest = User.objects.get(pk=guest_id_raw)
            except User.DoesNotExist:
                return HttpResponseBadRequest("Huésped seleccionado no válido.")

        # Datos de estancia
        room_id = (request.POST.get("room_id") or "").strip()
        check_in_raw = (request.POST.get("check_in") or "").strip()
        check_out_raw = (request.POST.get("check_out") or "").strip()
        adults_raw = (request.POST.get("adults") or "").strip() or "1"
        children_raw = (request.POST.get("children") or "").strip() or "0"

        # Validación básica de requeridos
        if (not guest and not guest_name) or not room_id or not check_in_raw or not check_out_raw:
            return HttpResponseBadRequest(
                "Faltan campos obligatorios: huésped, habitación y fechas."
            )

        try:
            room = Habitacion.objects.select_related("tipo").get(pk=room_id)
        except Habitacion.DoesNotExist:
            return HttpResponseBadRequest("Habitación no válida.")

        check_in = parse_date(check_in_raw)
        check_out = parse_date(check_out_raw)
        if not check_in or not check_out or check_out <= check_in:
            return HttpResponseBadRequest("Rango de fechas no válido.")

        try:
            adults = int(adults_raw)
            children = int(children_raw)
        except ValueError:
            return HttpResponseBadRequest("Número de huéspedes no válido.")

        if adults <= 0:
            return HttpResponseBadRequest("Debe haber al menos un adulto.")

        # Validar capacidad de la habitación (si está definida)
        capacidad = None
        if room.tipo is not None:
            capacidad = getattr(room.tipo, "capacidad", None)

        if capacidad is not None and (adults + children) > capacidad:
            return HttpResponseBadRequest("La habitación no tiene capacidad suficiente.")

        # Si el huésped está registrado, podemos rellenar datos de contacto por defecto
        if guest:
            if not guest_name:
                if hasattr(guest, "get_full_name"):
                    guest_name = guest.get_full_name() or guest.username
                else:
                    guest_name = guest.username
            if not guest_email:
                guest_email = guest.email or ""
            if not guest_phone:
                guest_phone = getattr(guest, "phone", "") or guest_phone

        # Crear la reserva y dejar que el modelo valide solapamientos
        try:
            reservation = Reservation(
                room=room,
                guest=guest,
                guest_name=guest_name,
                guest_email=guest_email,
                guest_phone=guest_phone,
                check_in=check_in,
                check_out=check_out,
                adults=adults,
                children=children,
                status=Reservation.Status.PENDING,
            )
            reservation.save()
        except ValidationError as e:
            # Devolvemos 400 para que el JS del modal muestre el mensaje
            msg = "; ".join(e.messages) if hasattr(e, "messages") else "Error de validación en la reserva."
            return HttpResponseBadRequest(msg)

        messages.success(
            request,
            f"Reserva {reservation.code} creada correctamente."
        )
        return redirect("reservas:lista")


class ReservationUpdateView(AdminRequiredMixin, View):
    """
    Actualiza una reserva existente desde el modal "Editar reserva".
    """
    login_url = "/login/"

    def post(self, request, pk, *args, **kwargs):
        reservation = get_object_or_404(
            Reservation.objects.select_related("room", "guest"),
            pk=pk,
        )

        guest_name = (request.POST.get("guest_name") or "").strip()
        guest_email = (request.POST.get("guest_email") or "").strip()
        guest_phone = (request.POST.get("guest_phone") or "").strip()

        check_in_raw = (request.POST.get("check_in") or "").strip()
        check_out_raw = (request.POST.get("check_out") or "").strip()
        adults_raw = (request.POST.get("adults") or "").strip()
        children_raw = (request.POST.get("children") or "").strip()

        if not guest_name or not check_in_raw or not check_out_raw:
            return HttpResponseBadRequest(
                "Faltan campos obligatorios: huésped y fechas."
            )

        check_in = parse_date(check_in_raw)
        check_out = parse_date(check_out_raw)
        if not check_in or not check_out or check_out <= check_in:
            return HttpResponseBadRequest("Rango de fechas no válido.")

        try:
            adults = int(adults_raw)
            children = int(children_raw)
        except ValueError:
            return HttpResponseBadRequest("Número de huéspedes no válido.")

        if adults <= 0:
            return HttpResponseBadRequest("Debe haber al menos un adulto.")

        # Validar capacidad habitación
        room = reservation.room
        capacidad = None
        if room.tipo is not None:
            capacidad = getattr(room.tipo, "capacidad", None)

        if capacidad is not None and (adults + children) > capacidad:
            return HttpResponseBadRequest("La habitación no tiene capacidad suficiente.")

        reservation.guest_name = guest_name
        reservation.guest_email = guest_email
        reservation.guest_phone = guest_phone
        reservation.check_in = check_in
        reservation.check_out = check_out
        reservation.adults = adults
        reservation.children = children

        try:
            reservation.save()
        except ValidationError as e:
            msg = "; ".join(e.messages) if hasattr(e, "messages") else "Error de validación en la reserva."
            return HttpResponseBadRequest(msg)

        messages.success(request, f"Reserva {reservation.code} actualizada correctamente.")
        return redirect("reservas:lista")


class ReservationStatusActionView(AdminRequiredMixin, View):
    """
    Cambia el estado de una reserva (cancelar, marcar como check-in, check-out, etc.).
    Se invoca desde el modal de detalle/pago.
    """
    login_url = "/login/"

    def post(self, request, pk, *args, **kwargs):
        reservation = get_object_or_404(Reservation, pk=pk)
        action = (request.POST.get("action") or "").strip().lower()

        if action == "cancel":
            if reservation.status in {
                Reservation.Status.CHECKED_OUT,
                Reservation.Status.CANCELLED,
            }:
                messages.warning(
                    request,
                    "No puedes cancelar una reserva que ya está finalizada o cancelada."
                )
            else:
                reservation.mark_cancelled()
                messages.success(request, f"Reserva {reservation.code} cancelada correctamente.")

        elif action == "confirm":
            if reservation.status == Reservation.Status.PENDING:
                reservation.mark_confirmed()
                messages.success(request, f"Reserva {reservation.code} confirmada.")
            else:
                messages.warning(request, "Solo las reservas pendientes pueden confirmarse.")

        elif action == "check_in":
            if reservation.status in {
                Reservation.Status.CONFIRMED,
                Reservation.Status.PENDING,
            }:
                reservation.mark_checked_in()
                messages.success(request, f"Check-in realizado para la reserva {reservation.code}.")
            else:
                messages.warning(request, "No es posible realizar check-in en el estado actual.")

        elif action == "check_out":
            if reservation.status == Reservation.Status.CHECKED_IN:
                reservation.mark_checked_out()
                messages.success(request, f"Check-out realizado para la reserva {reservation.code}.")
            else:
                messages.warning(request, "No es posible realizar check-out en el estado actual.")

        else:
            return HttpResponseBadRequest("Acción no válida.")

        return redirect("reservas:lista")


class PaymentCreateView(AdminRequiredMixin, View):
    """
    Registra un pago de la reserva (modal 'Procesar pago').
    """
    login_url = "/login/"

    def post(self, request, pk, *args, **kwargs):
        reservation = get_object_or_404(
            Reservation.objects.select_related("room", "guest"),
            pk=pk,
        )

        amount_raw = (request.POST.get("amount") or "").strip()
        method = (request.POST.get("method") or "").strip() or Payment.Method.CASH
        reference = (request.POST.get("reference") or "").strip()
        notes = (request.POST.get("notes") or "").strip()

        try:
            amount = Decimal(amount_raw)
        except Exception:
            return HttpResponseBadRequest("Monto de pago no válido.")

        if amount <= 0:
            return HttpResponseBadRequest("El monto debe ser mayor a cero.")

        # Validar contra saldo pendiente
        saldo_pendiente = reservation.pending_amount
        if amount > saldo_pendiente:
            return HttpResponseBadRequest(
                f"El monto ({amount}) no puede ser mayor al saldo pendiente ({saldo_pendiente})."
            )

        payment = Payment(
            reservation=reservation,
            amount=amount,
            method=method,
            reference=reference,
            notes=notes,
        )
        if request.user.is_authenticated:
            payment.created_by = request.user
        payment.save()

        messages.success(
            request,
            f"Pago registrado correctamente. Factura: {payment.invoice_number}."
        )
        return redirect("reservas:lista")


class PaymentInvoicePDFView(LoginRequiredMixin, View):
    """
    Genera la factura en PDF para un pago concreto.
    Cada pago de reserva se considera una factura independiente.

    La factura incluye:
      - Cargos de alojamiento (noches x tarifa).
      - Servicios consumidos en la reserva.
      - Pagos de la reserva (Payment).
      - Pagos de servicios (PagoConsumo).
    """
    login_url = "/login/"

    def get(self, request, pk, *args, **kwargs):
        payment = get_object_or_404(
            Payment.objects.select_related(
                "reservation",
                "reservation__room",
                "reservation__guest",
            ),
            pk=pk,
        )
        reservation = payment.reservation

        # ---- PERMISOS: admin del hotel o dueño de la reserva ----
        user = request.user
        is_owner = user.is_authenticated and reservation.guest_id == user.id
        if not _is_admin(user) and not is_owner:
            # Para no filtrar información, respondemos 404
            raise Http404("Factura no encontrada")

        # -------------------------------
        # 1. Alojamiento (habitaciones)
        # -------------------------------
        total_reserva = Decimal(str(reservation.total_amount or 0))

        # Pagos de ALOJAMIENTO (Payment)
        total_pagado_reserva_despues = Decimal(str(reservation.paid_amount or 0))
        total_pagado_reserva_antes = total_pagado_reserva_despues - Decimal(str(payment.amount or 0))
        if total_pagado_reserva_antes < 0:
            total_pagado_reserva_antes = Decimal("0.00")

        # -------------------------------
        # 2. Servicios consumidos
        # -------------------------------
        # Import local para evitar ciclos entre apps
        from servicios.models import ConsumoServicio, PagoConsumo

        consumos_servicios = (
            reservation.consumos_servicio
            .select_related("servicio")
            .exclude(estado=ConsumoServicio.Estado.CANCELADO)
            .order_by("creado_en")
        )

        total_servicios = consumos_servicios.aggregate(
            total=Sum("total")
        )["total"] or Decimal("0.00")

        # Pagos de SERVICIOS
        total_pagado_servicios = (
            PagoConsumo.objects.filter(consumo__reserva=reservation)
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        # -------------------------------
        # 3. Totales generales
        # -------------------------------
        total_general = total_reserva + total_servicios

        total_pagado_general = total_pagado_reserva_despues + total_pagado_servicios

        saldo_pendiente = total_general - total_pagado_general
        if saldo_pendiente < 0:
            saldo_pendiente = Decimal("0.00")

        # -------------------------------
        # 4. Renderizar HTML → PDF
        # -------------------------------
        template = get_template("reservas/factura_pago.html")

        context = {
            "payment": payment,
            "reservation": reservation,
            "hotel_nombre": "Hotel Elegance",
            "hotel_nit": "900.123.456-7",
            "hotel_direccion": "Cra 123 #45-67, Bogotá",
            "hotel_telefono": "+57 1 123 4567",
            "hotel_email": "contacto@hotelelegance.com",

            # Totales base
            "total_reserva": total_reserva,
            "total_servicios": total_servicios,
            "total_general": total_general,

            # Pagos de alojamiento
            "total_pagado_reserva_antes": total_pagado_reserva_antes,
            "total_pagado_reserva_despues": total_pagado_reserva_despues,
            "pago_actual_reserva": Decimal(str(payment.amount or 0)),

            # Pagos de servicios
            "total_pagado_servicios": total_pagado_servicios,

            # Totales globales
            "total_pagado_general": total_pagado_general,
            "saldo_pendiente": saldo_pendiente,

            # Detalle de servicios
            "consumos_servicios": consumos_servicios,
        }

        html = template.render(context)

        # Crear PDF en memoria
        result = io.BytesIO()
        pdf = pisa.CreatePDF(
            src=html,
            dest=result,
            encoding="UTF-8",
        )

        if pdf.err:
            return HttpResponse("Error generando la factura PDF", status=500)

        # Respuesta PDF
        response = HttpResponse(result.getvalue(), content_type="application/pdf")
        filename = f"{payment.invoice_number}.pdf"
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response


# ==========================
# Vistas para PORTAL CLIENTE
# ==========================


class ClientReservationsListView(LoginRequiredMixin, View):
    """Listado de reservas del usuario autenticado."""
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        reservas = (
            Reservation.objects
            .select_related("room", "room__tipo")
            .filter(guest=request.user)
            .order_by("-created_at")
        )

        context = {
            "reservas": reservas,
            "active_menu": "mis_reservas_cliente",
        }
        return render(request, "reservas/cliente_mis_reservas.html", context)


class ClientReservationCreateView(LoginRequiredMixin, View):
    """Permite al usuario crear una nueva reserva para sí mismo."""
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        habitaciones = (
            Habitacion.objects
            .select_related("tipo")
            .all()
            .order_by("piso", "codigo")
        )
        context = {
            "habitaciones": habitaciones,
            "active_menu": "nueva_reserva_cliente",
        }
        return render(request, "reservas/cliente_nueva.html", context)

    def post(self, request, *args, **kwargs):
        habitaciones = (
            Habitacion.objects
            .select_related("tipo")
            .all()
            .order_by("piso", "codigo")
        )

        room_id = (request.POST.get("room_id") or "").strip()
        check_in_raw = (request.POST.get("check_in") or "").strip()
        check_out_raw = (request.POST.get("check_out") or "").strip()
        adults_raw = (request.POST.get("adults") or "").strip() or "1"
        children_raw = (request.POST.get("children") or "").strip() or "0"

        errors = []
        room = None

        if not room_id:
            errors.append("Debes seleccionar una habitación.")
        else:
            try:
                room = Habitacion.objects.select_related("tipo").get(pk=room_id)
            except Habitacion.DoesNotExist:
                errors.append("La habitación seleccionada no es válida.")

        # Validar fechas
        check_in = parse_date(check_in_raw) if check_in_raw else None
        check_out = parse_date(check_out_raw) if check_out_raw else None
        if not check_in or not check_out:
            errors.append("Debes indicar las fechas de check-in y check-out.")
        elif check_out <= check_in:
            errors.append("La fecha de salida debe ser posterior a la de llegada.")

        # Validar números de huéspedes
        try:
            adults = int(adults_raw)
            children = int(children_raw)
            if adults <= 0:
                errors.append("Debe haber al menos un adulto en la reserva.")
        except ValueError:
            errors.append("El número de huéspedes no es válido.")
            adults = 1
            children = 0

        # Validar capacidad de la habitación
        if room is not None:
            capacidad = None
            if room.tipo is not None:
                capacidad = getattr(room.tipo, "capacidad", None)

            if capacidad is not None and (adults + children) > capacidad:
                errors.append(
                    f"La habitación seleccionada solo admite hasta {capacidad} personas."
                )

        if errors:
            for e in errors:
                messages.error(request, e)
            context = {
                "habitaciones": habitaciones,
                "form_data": {
                    "room_id": room_id,
                    "check_in": check_in_raw,
                    "check_out": check_out_raw,
                    "adults": adults_raw,
                    "children": children_raw,
                },
                "active_menu": "nueva_reserva_cliente",
            }
            return render(request, "reservas/cliente_nueva.html", context, status=200)

        # Crear la reserva asociada al usuario actual
        user = request.user
        guest_name = ""
        if hasattr(user, "get_full_name"):
            guest_name = user.get_full_name() or ""
        if not guest_name:
            guest_name = str(user)

        reservation = Reservation(
            room=room,
            guest=user,
            guest_name=guest_name,
            guest_email=getattr(user, "email", "") or "",
            guest_phone="",
            check_in=check_in,
            check_out=check_out,
            adults=adults,
            children=children,
            status=Reservation.Status.PENDING,  # El hotel la confirmará después
        )

        try:
            reservation.save()
        except ValidationError as e:
            for msg in getattr(e, "messages", ["No fue posible crear la reserva."]):
                messages.error(request, msg)
            context = {
                "habitaciones": habitaciones,
                "form_data": {
                    "room_id": room_id,
                    "check_in": check_in_raw,
                    "check_out": check_out_raw,
                    "adults": adults_raw,
                    "children": children_raw,
                },
                "active_menu": "nueva_reserva_cliente",
            }
            return render(request, "reservas/cliente_nueva.html", context, status=200)

        messages.success(
            request,
            "Tu reserva fue registrada correctamente. El hotel confirmará los detalles de tu estadía.",
        )
        return redirect("reservas:mis_reservas")


class ClientReservationDetailView(LoginRequiredMixin, View):
    """Detalle de una reserva del cliente, incluyendo facturas/pagos."""
    login_url = "/login/"

    def get(self, request, pk, *args, **kwargs):
        reserva = get_object_or_404(
            Reservation.objects.select_related("room", "room__tipo"),
            pk=pk,
            guest=request.user,
        )

        pagos = (
            Payment.objects
            .filter(reservation=reserva)
            .order_by("-created_at")
        )

        context = {
            "reserva": reserva,
            "pagos": pagos,
            "active_menu": "mis_reservas_cliente",
        }
        return render(request, "reservas/cliente_reserva_detalle.html", context)


class ClientReservationUpdateView(LoginRequiredMixin, View):
    """Permite al cliente modificar una reserva suya (pendiente/confirmada)."""
    login_url = "/login/"

    def get(self, request, pk, *args, **kwargs):
        reserva = get_object_or_404(
            Reservation.objects.select_related("room", "room__tipo"),
            pk=pk,
            guest=request.user,
        )

        if reserva.status not in (
            Reservation.Status.PENDING,
            Reservation.Status.CONFIRMED,
        ):
            messages.warning(
                request,
                "Solo puedes modificar reservas pendientes o confirmadas.",
            )
            return redirect("reservas:mis_reservas")

        habitaciones = (
            Habitacion.objects
            .select_related("tipo")
            .all()
            .order_by("piso", "codigo")
        )

        form_data = {
            "room_id": reserva.room_id,
            "check_in": reserva.check_in.isoformat(),
            "check_out": reserva.check_out.isoformat(),
            "adults": reserva.adults,
            "children": reserva.children,
        }

        context = {
            "habitaciones": habitaciones,
            "form_data": form_data,
            "reserva": reserva,
            "modo": "editar",
            "active_menu": "mis_reservas_cliente",
        }
        return render(request, "reservas/cliente_nueva.html", context)

    def post(self, request, pk, *args, **kwargs):
        reserva = get_object_or_404(
            Reservation.objects.select_related("room", "room__tipo"),
            pk=pk,
            guest=request.user,
        )

        if reserva.status not in (
            Reservation.Status.PENDING,
            Reservation.Status.CONFIRMED,
        ):
            messages.warning(
                request,
                "Solo puedes modificar reservas pendientes o confirmadas.",
            )
            return redirect("reservas:mis_reservas")

        habitaciones = (
            Habitacion.objects
            .select_related("tipo")
            .all()
            .order_by("piso", "codigo")
        )

        room_id = (request.POST.get("room_id") or "").strip()
        check_in_raw = (request.POST.get("check_in") or "").strip()
        check_out_raw = (request.POST.get("check_out") or "").strip()
        adults_raw = (request.POST.get("adults") or "").strip() or "1"
        children_raw = (request.POST.get("children") or "").strip() or "0"

        errors = []
        room = None

        if not room_id:
            errors.append("Debes seleccionar una habitación.")
        else:
            try:
                room = Habitacion.objects.select_related("tipo").get(pk=room_id)
            except Habitacion.DoesNotExist:
                errors.append("La habitación seleccionada no es válida.")

        check_in = parse_date(check_in_raw) if check_in_raw else None
        check_out = parse_date(check_out_raw) if check_out_raw else None
        if not check_in or not check_out:
            errors.append("Debes indicar las fechas de check-in y check-out.")
        elif check_out <= check_in:
            errors.append("La fecha de salida debe ser posterior a la de llegada.")

        try:
            adults = int(adults_raw)
            children = int(children_raw)
            if adults <= 0:
                errors.append("Debe haber al menos un adulto en la reserva.")
        except ValueError:
            errors.append("El número de huéspedes no es válido.")
            adults = reserva.adults
            children = reserva.children

        if room is not None:
            capacidad = None
            if room.tipo is not None:
                capacidad = getattr(room.tipo, "capacidad", None)

            if capacidad is not None and (adults + children) > capacidad:
                errors.append(
                    f"La habitación seleccionada solo admite hasta {capacidad} personas."
                )

        if errors:
            for e in errors:
                messages.error(request, e)

            context = {
                "habitaciones": habitaciones,
                "form_data": {
                    "room_id": room_id,
                    "check_in": check_in_raw,
                    "check_out": check_out_raw,
                    "adults": adults_raw,
                    "children": children_raw,
                },
                "reserva": reserva,
                "modo": "editar",
                "active_menu": "mis_reservas_cliente",
            }
            return render(
                request,
                "reservas/cliente_nueva.html",
                context,
                status=200,
            )

        # Actualizar reserva
        reserva.room = room
        reserva.check_in = check_in
        reserva.check_out = check_out
        reserva.adults = adults
        reserva.children = children

        try:
            reserva.save()
        except ValidationError as e:
            for msg in getattr(e, "messages", ["No fue posible actualizar la reserva."]):
                messages.error(request, msg)

            context = {
                "habitaciones": habitaciones,
                "form_data": {
                    "room_id": room_id,
                    "check_in": check_in_raw,
                    "check_out": check_out_raw,
                    "adults": adults_raw,
                    "children": children_raw,
                },
                "reserva": reserva,
                "modo": "editar",
                "active_menu": "mis_reservas_cliente",
            }
            return render(
                request,
                "reservas/cliente_nueva.html",
                context,
                status=200,
            )

        messages.success(
            request,
            f"Tu reserva {reserva.code} fue actualizada correctamente.",
        )
        return redirect("reservas:mis_reservas")


class ClientReservationCancelView(LoginRequiredMixin, View):
    """Cancela una reserva del cliente (no se borra, se marca CANCELLED)."""
    login_url = "/login/"

    def post(self, request, pk, *args, **kwargs):
        reserva = get_object_or_404(Reservation, pk=pk, guest=request.user)

        if reserva.status in (
            Reservation.Status.CHECKED_OUT,
            Reservation.Status.CANCELLED,
        ):
            messages.warning(
                request,
                "Esta reserva ya no puede cancelarse.",
            )
            return redirect("reservas:mis_reservas")

        reserva.mark_cancelled()

        messages.success(
            request,
            f"La reserva {reserva.code} fue cancelada correctamente.",
        )
        return redirect("reservas:mis_reservas")


class ClientPaymentCreateView(LoginRequiredMixin, View):
    """
    Permite al cliente registrar un pago de SU reserva.
    Similar a PaymentCreateView pero limitado al dueño.
    """
    login_url = "/login/"

    def get(self, request, pk, *args, **kwargs):
        reserva = get_object_or_404(
            Reservation.objects.select_related("room", "room__tipo"),
            pk=pk,
            guest=request.user,
        )

        saldo_pendiente = reserva.pending_amount
        if saldo_pendiente <= 0:
            messages.info(request, "Esta reserva ya está completamente pagada.")
            return redirect("reservas:detalle_cliente", pk=reserva.pk)

        context = {
            "reserva": reserva,
            "saldo_pendiente": saldo_pendiente,
            "active_menu": "mis_reservas_cliente",
        }
        return render(request, "reservas/cliente_pago.html", context)

    def post(self, request, pk, *args, **kwargs):
        reserva = get_object_or_404(
            Reservation.objects.select_related("room", "room__tipo"),
            pk=pk,
            guest=request.user,
        )

        saldo_pendiente = reserva.pending_amount
        if saldo_pendiente <= 0:
            messages.info(request, "Esta reserva ya está completamente pagada.")
            return redirect("reservas:detalle_cliente", pk=reserva.pk)

        amount_raw = (request.POST.get("amount") or "").strip()
        method = (request.POST.get("method") or "").strip() or Payment.Method.CASH
        reference = (request.POST.get("reference") or "").strip()
        notes = (request.POST.get("notes") or "").strip()

        try:
            amount = Decimal(amount_raw)
        except Exception:
            messages.error(request, "El monto de pago no es válido.")
            return redirect("reservas:pago_cliente", pk=reserva.pk)

        if amount <= 0:
            messages.error(request, "El monto debe ser mayor a cero.")
            return redirect("reservas:pago_cliente", pk=reserva.pk)

        if amount > saldo_pendiente:
            messages.error(
                request,
                f"El monto ({amount}) no puede ser mayor al saldo pendiente ({saldo_pendiente}).",
            )
            return redirect("reservas:pago_cliente", pk=reserva.pk)

        pago = Payment(
            reservation=reserva,
            amount=amount,
            method=method,
            reference=reference,
            notes=notes,
            created_by=request.user,
        )
        pago.save()

        messages.success(
            request,
            f"Pago registrado correctamente. Factura: {pago.invoice_number}.",
        )
        return redirect("reservas:detalle_cliente", pk=reserva.pk)


class ClientRoomServiceView(LoginRequiredMixin, View):
    """Placeholder para servicios de habitación en el portal cliente."""
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        return render(
            request,
            "reservas/cliente_room_service.html",
            {"active_menu": "room_service_cliente"},
        )


class ClientServiciosView(LoginRequiredMixin, View):
    """Placeholder para otros servicios (spa, eventos, etc.) en el portal cliente."""
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        return render(
            request,
            "reservas/cliente_servicios.html",
            {"active_menu": "servicios_cliente"},
        )
