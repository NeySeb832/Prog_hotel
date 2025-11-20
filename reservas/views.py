# reservas/views.py
# -*- coding: utf-8 -*-
from decimal import Decimal, InvalidOperation
import io

from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseBadRequest, HttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.template.loader import get_template

from xhtml2pdf import pisa  # pip install xhtml2pdf

from .models import Reservation, Payment
from habitaciones.models import Habitacion


User = get_user_model()


class ReservationsListView(LoginRequiredMixin, View):
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
            .prefetch_related("payments")  # ⬅️ añadimos esto
            .all()
            .order_by("-created_at")
        )

        # --- Parámetros de filtro desde GET ---
        q = (request.GET.get("q") or "").strip()
        status = (request.GET.get("status") or "").strip()
        guest_id = (request.GET.get("guest") or "").strip()
        room_id = (request.GET.get("room") or "").strip()

        # Búsqueda libre
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
        habitaciones = Habitacion.objects.select_related("tipo").all().order_by("piso", "codigo")

        # Clientes registrados (usuarios activos)
        clientes = User.objects.filter(is_active=True).order_by("first_name", "last_name", "username")

        context = {
            "reservas": qs,
            "kpis": kpis,
            "status_choices": status_choices,
            "habitaciones": habitaciones,
            "clientes": clientes,
            "active_menu": "reservas",
        }
        return render(request, "reservas/lista_reservas.html", context)


class ReservationCreateView(LoginRequiredMixin, View):
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
                guest = None

        # Datos de reserva
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

        # Validar capacidad de la habitación (según el tipo)
        capacidad = None
        if room.tipo is not None:
            capacidad = getattr(room.tipo, "capacidad", None)

        if capacidad is not None and (adults + children) > capacidad:
            return HttpResponseBadRequest(
                "El número de huéspedes supera la capacidad máxima de la habitación."
            )

        # Validar solapamiento de reservas (mismas fechas, misma habitación)
        overlapping = (
            Reservation.objects
            .filter(
                room=room,
                status__in=[
                    Reservation.Status.CONFIRMED,
                    Reservation.Status.CHECKED_IN,
                ],
                check_in__lt=check_out,
                check_out__gt=check_in,
            )
        )

        if overlapping.exists():
            return HttpResponseBadRequest(
                "La habitación ya tiene una reserva activa en ese rango de fechas."
            )

        # Crear la reserva
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

        # Toda reserva del panel admin la marcamos como CONFIRMADA
        reservation.mark_confirmed()

        return redirect("reservas:lista")


class ReservationUpdateView(LoginRequiredMixin, View):
    """
    Actualiza datos básicos de una reserva existente desde el modal "Editar".
    """
    login_url = "/login/"

    def post(self, request, pk, *args, **kwargs):
        reservation = get_object_or_404(Reservation, pk=pk)

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
            adults = int(adults_raw) if adults_raw else reservation.adults
            children = int(children_raw) if children_raw else reservation.children
        except ValueError:
            return HttpResponseBadRequest("Número de huéspedes no válido.")

        room = reservation.room

        # Validar capacidad
        capacidad = None
        if room.tipo is not None:
            capacidad = getattr(room.tipo, "capacidad", None)

        if capacidad is not None and (adults + children) > capacidad:
            return HttpResponseBadRequest(
                "El número de huéspedes supera la capacidad máxima de la habitación."
            )

        # Validar solapamiento, excluyendo esta misma reserva
        overlapping = (
            Reservation.objects
            .filter(
                room=room,
                status__in=[
                    Reservation.Status.CONFIRMED,
                    Reservation.Status.CHECKED_IN,
                ],
                check_in__lt=check_out,
                check_out__gt=check_in,
            )
            .exclude(pk=reservation.pk)
        )

        if overlapping.exists():
            return HttpResponseBadRequest(
                "La habitación ya tiene otra reserva activa en ese rango de fechas."
            )

        # Actualizar campos
        reservation.guest_name = guest_name
        reservation.guest_email = guest_email
        reservation.guest_phone = guest_phone
        reservation.check_in = check_in
        reservation.check_out = check_out
        reservation.adults = adults
        reservation.children = children

        reservation.save()
        return redirect("reservas:lista")


class ReservationStatusActionView(LoginRequiredMixin, View):
    """
    Cambia el estado de la reserva usando las funciones de dominio.
    """
    login_url = "/login/"

    def post(self, request, pk, *args, **kwargs):
        reservation = get_object_or_404(Reservation, pk=pk)
        action = (request.POST.get("action") or "").strip().lower()

        if action == "confirm":
            reservation.mark_confirmed()
        elif action == "checkin":
            reservation.mark_checked_in()
        elif action == "checkout":
            reservation.mark_checked_out()
        elif action == "cancel":
            reservation.mark_cancelled()
        else:
            return HttpResponseBadRequest("Acción no válida.")

        return redirect("reservas:lista")


class PaymentCreateView(LoginRequiredMixin, View):
    """
    Registra un pago asociado a una reserva desde el modal "Procesar Pago".
    - No permite pagar más de lo que se debe.
    - Tras registrar el pago, redirige a la factura PDF de ese pago.
    """
    login_url = "/login/"

    def post(self, request, pk, *args, **kwargs):
        reservation = get_object_or_404(Reservation, pk=pk)

        amount_raw = (request.POST.get("amount") or "").strip()
        method = (request.POST.get("method") or "").strip() or Payment.Method.CASH
        reference = (request.POST.get("reference") or "").strip()
        notes = (request.POST.get("notes") or "").strip()

        if not amount_raw:
            return HttpResponseBadRequest("El monto es obligatorio.")

        # Saldo pendiente actual
        remaining = reservation.pending_amount  # Decimal

        if remaining <= 0:
            return HttpResponseBadRequest("La reserva ya está completamente pagada.")

        # Convertir a Decimal y validar
        try:
            amount = Decimal(amount_raw)
        except InvalidOperation:
            return HttpResponseBadRequest("Monto no válido.")

        if amount <= 0:
            return HttpResponseBadRequest("El monto debe ser mayor que cero.")

        if amount > remaining:
            return HttpResponseBadRequest(
                f"El monto ({amount}) excede el saldo pendiente ({remaining})."
            )

        payment = Payment(
            reservation=reservation,
            amount=amount,
            method=method,
            reference=reference,
            notes=notes,
            created_by=request.user if request.user.is_authenticated else None,
        )
        payment.save()

        # Tras registrar el pago, generamos la factura de ese pago
        return redirect("reservas:pago_factura", pk=payment.pk)


class PaymentInvoicePDFView(LoginRequiredMixin, View):
    """
    Genera la factura en PDF para un pago concreto.
    Cada pago se considera una factura independiente.
    """
    login_url = "/login/"

    def get(self, request, pk, *args, **kwargs):
        payment = get_object_or_404(
            Payment.objects.select_related("reservation", "reservation__room", "reservation__guest"),
            pk=pk,
        )
        reservation = payment.reservation

        # Cálculos financieros
        total_reserva = Decimal(str(reservation.total_amount or 0))
        total_pagado_despues = Decimal(str(reservation.paid_amount or 0))
        total_pagado_antes = total_pagado_despues - Decimal(str(payment.amount or 0))
        if total_pagado_antes < 0:
            total_pagado_antes = Decimal("0.00")
        saldo_pendiente = reservation.pending_amount

        template = get_template("reservas/factura_pago.html")

        context = {
            "payment": payment,
            "reservation": reservation,
            "hotel_nombre": "Hotel Elegance",
            "hotel_nit": "900.123.456-7",
            "hotel_direccion": "Cra 123 #45-67, Bogotá",
            "hotel_telefono": "+57 1 123 4567",
            "hotel_email": "contacto@hotelelegance.com",
            "total_reserva": total_reserva,
            "total_pagado_antes": total_pagado_antes,
            "total_pagado_despues": total_pagado_despues,
            "saldo_pendiente": saldo_pendiente,
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
