from decimal import Decimal, InvalidOperation
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from reservas.models import Reservation
from .forms import ConsumoServicioForm, ServicioForm, PagoConsumoForm
from .models import ConsumoServicio, Servicio, PagoConsumo


class ServiciosListView(LoginRequiredMixin, View):
    """Listado principal del catálogo de servicios para el panel administrativo."""
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        qs = Servicio.objects.all()

        q = (request.GET.get("q") or "").strip()
        categoria = (request.GET.get("categoria") or "").strip()
        activo = (request.GET.get("activo") or "").strip()

        if q:
            qs = qs.filter(nombre__icontains=q)

        if categoria:
            qs = qs.filter(categoria=categoria)

        if activo == "1":
            qs = qs.filter(activo=True)
        elif activo == "0":
            qs = qs.filter(activo=False)

        kpis = {
            "total": Servicio.objects.count(),
            "activos": Servicio.objects.filter(activo=True).count(),
            "inactivos": Servicio.objects.filter(activo=False).count(),
        }

        # Resumen simple de consumos de los últimos 30 días
        hoy = timezone.now().date()
        hace_30 = hoy - timedelta(days=30)
        consumos_30d = (
            ConsumoServicio.objects.filter(creado_en__date__gte=hace_30)
            .aggregate(total_monto=Sum("total"), total_items=Count("id"))
        )

        context = {
            "servicios": qs,
            "categorias": Servicio.Categoria.choices,
            "filtros": {
                "q": q,
                "categoria": categoria,
                "activo": activo,
            },
            "kpis": kpis,
            "consumos_resumen": consumos_30d,
            "active_menu": "servicios",
        }
        return render(request, "servicios/lista_servicios.html", context)


class ServicioCreateView(LoginRequiredMixin, View):
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        form = ServicioForm()
        context = {
            "form": form,
            "modo": "crear",
            "active_menu": "servicios",
        }
        return render(request, "servicios/form_servicio.html", context)

    def post(self, request, *args, **kwargs):
        form = ServicioForm(request.POST or None)
        if form.is_valid():
            form.save()
            messages.success(request, "Servicio creado correctamente.")
            return redirect("servicios:lista")
        context = {
            "form": form,
            "modo": "crear",
            "active_menu": "servicios",
        }
        return render(
            request, "servicios/form_servicio.html", context, status=400
        )


class ServicioUpdateView(LoginRequiredMixin, View):
    login_url = "/login/"

    def get(self, request, pk, *args, **kwargs):
        servicio = get_object_or_404(Servicio, pk=pk)
        form = ServicioForm(instance=servicio)
        context = {
            "form": form,
            "servicio": servicio,
            "modo": "editar",
            "active_menu": "servicios",
        }
        return render(request, "servicios/form_servicio.html", context)

    def post(self, request, pk, *args, **kwargs):
        servicio = get_object_or_404(Servicio, pk=pk)
        form = ServicioForm(request.POST or None, instance=servicio)
        if form.is_valid():
            form.save()
            messages.success(request, "Servicio actualizado correctamente.")
            return redirect("servicios:lista")
        context = {
            "form": form,
            "servicio": servicio,
            "modo": "editar",
            "active_menu": "servicios",
        }
        return render(
            request, "servicios/form_servicio.html", context, status=400
        )


class ConsumosListView(LoginRequiredMixin, View):
    """Listado de consumos de servicios, filtrable por reserva, huésped o estado."""
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        qs = (
            ConsumoServicio.objects.select_related(
                "reserva", "servicio", "reserva__room", "reserva__guest"
            ).all()
        )

        estado = (request.GET.get("estado") or "").strip()
        reserva_id = (request.GET.get("reserva") or "").strip()
        q = (request.GET.get("q") or "").strip()

        if estado:
            qs = qs.filter(estado=estado)

        if reserva_id:
            qs = qs.filter(reserva_id=reserva_id)

        if q:
            qs = qs.filter(
                Q(servicio__nombre__icontains=q)
                | Q(reserva__guest_name__icontains=q)
                | Q(reserva__guest__first_name__icontains=q)
                | Q(reserva__guest__last_name__icontains=q)
                | Q(reserva__code__icontains=q)
            )

        estados = ConsumoServicio.Estado.choices
        reservas = (
            Reservation.objects.select_related("room")
            .all()
            .order_by("-created_at")
        )

        total_monto = qs.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
        total_pagado = (
            PagoConsumo.objects.filter(consumo__in=qs)
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        totales = {
            "total_items": qs.count(),
            "total_monto": total_monto,
            "total_pagado": total_pagado,
        }

        context = {
            "consumos": qs,
            "estados": estados,
            "reservas": reservas,
            "filtros": {
                "estado": estado,
                "reserva": reserva_id,
                "q": q,
            },
            "totales": totales,
            "active_menu": "servicios",
        }
        return render(request, "servicios/lista_consumos.html", context)


class ConsumoCreateView(LoginRequiredMixin, View):
    """Formulario para registrar un nuevo consumo de servicio asociado a una reserva."""
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        reserva_id = request.GET.get("reserva")
        initial = {}
        if reserva_id:
            initial["reserva"] = get_object_or_404(Reservation, pk=reserva_id)
        form = ConsumoServicioForm(initial=initial)
        context = {
            "form": form,
            "modo": "crear",
            "consumo": None,
            "active_menu": "servicios",
        }
        return render(request, "servicios/form_consumo.html", context)

    def post(self, request, *args, **kwargs):
        form = ConsumoServicioForm(request.POST or None)
        if form.is_valid():
            consumo = form.save(commit=False)
            if request.user.is_authenticated:
                consumo.agregado_por = request.user
            consumo.save()
            messages.success(
                request, "Consumo de servicio registrado correctamente."
            )
            return redirect("servicios:consumos")

        context = {
            "form": form,
            "modo": "crear",
            "consumo": None,
            "active_menu": "servicios",
        }
        return render(
            request, "servicios/form_consumo.html", context, status=400
        )


class ConsumoUpdateView(LoginRequiredMixin, View):
    """
    Permite editar un consumo de servicio ya registrado (incluyendo el estado).
    Esto evita depender del panel de superusuario para cambiar estados.
    """
    login_url = "/login/"

    def get(self, request, pk, *args, **kwargs):
        consumo = get_object_or_404(ConsumoServicio, pk=pk)
        form = ConsumoServicioForm(instance=consumo)
        context = {
            "form": form,
            "modo": "editar",
            "consumo": consumo,
            "active_menu": "servicios",
        }
        return render(request, "servicios/form_consumo.html", context)

    def post(self, request, pk, *args, **kwargs):
        consumo = get_object_or_404(ConsumoServicio, pk=pk)
        form = ConsumoServicioForm(request.POST or None, instance=consumo)
        if form.is_valid():
            consumo = form.save(commit=False)
            if request.user.is_authenticated and consumo.agregado_por is None:
                consumo.agregado_por = request.user
            consumo.save()
            messages.success(
                request, "Consumo de servicio actualizado correctamente."
            )
            return redirect("servicios:consumos")

        context = {
            "form": form,
            "modo": "editar",
            "consumo": consumo,
            "active_menu": "servicios",
        }
        return render(
            request, "servicios/form_consumo.html", context, status=400
        )


class ConsumoPagoCreateView(LoginRequiredMixin, View):
    """
    Registra un pago asociado a un consumo de servicio.
    Basado en la lógica de PaymentCreateView, pero a nivel de ConsumoServicio.
    """
    login_url = "/login/"

    def get(self, request, pk, *args, **kwargs):
        consumo = get_object_or_404(
            ConsumoServicio.objects.select_related(
                "reserva", "servicio", "reserva__room", "reserva__guest"
            ),
            pk=pk,
        )
        form = PagoConsumoForm()
        context = {
            "consumo": consumo,
            "form": form,
            "active_menu": "servicios",
        }
        return render(request, "servicios/form_pago_consumo.html", context)

    def post(self, request, pk, *args, **kwargs):
        consumo = get_object_or_404(
            ConsumoServicio.objects.select_related(
                "reserva", "servicio", "reserva__room", "reserva__guest"
            ),
            pk=pk,
        )

        form = PagoConsumoForm(request.POST or None)
        if not form.is_valid():
            messages.error(request, "Revisa los datos del formulario de pago.")
            context = {
                "consumo": consumo,
                "form": form,
                "active_menu": "servicios",
            }
            return render(
                request, "servicios/form_pago_consumo.html", context, status=400
            )

        # Validar monto contra saldo pendiente
        amount_raw = str(form.cleaned_data["amount"])
        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, TypeError):
            messages.error(request, "El monto ingresado no es válido.")
            return redirect("servicios:consumo_pagar", pk=consumo.pk)

        if amount <= 0:
            messages.error(request, "El monto debe ser mayor a cero.")
            return redirect("servicios:consumo_pagar", pk=consumo.pk)

        saldo_pendiente = consumo.saldo_pendiente
        if saldo_pendiente <= 0:
            messages.info(request, "Este consumo ya se encuentra completamente pagado.")
            return redirect("servicios:consumos")

        if amount > saldo_pendiente:
            messages.error(
                request,
                f"El monto supera el saldo pendiente ({saldo_pendiente}).",
            )
            return redirect("servicios:consumo_pagar", pk=consumo.pk)

        pago = form.save(commit=False)
        pago.consumo = consumo
        if request.user.is_authenticated:
            pago.created_by = request.user
        pago.save()

        # Si ya quedó completamente pagado, marcamos el consumo como FACTURADO
        consumo_refrescado = ConsumoServicio.objects.get(pk=consumo.pk)
        if consumo_refrescado.saldo_pendiente == 0:
            consumo_refrescado.estado = ConsumoServicio.Estado.FACTURADO
            consumo_refrescado.save(update_fields=["estado"])

        messages.success(request, "Pago del servicio registrado correctamente.")
        return redirect("servicios:consumos")

# ==========================
# Vistas de SERVICIOS para PORTAL CLIENTE
# ==========================

class ClientServiciosView(LoginRequiredMixin, View):
    """
    Listado de consumos de servicios del usuario autenticado.
    Equivalente a 'Mis servicios'.
    """
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        consumos = (
            ConsumoServicio.objects
            .select_related("reserva", "servicio", "reserva__room")
            .filter(reserva__guest=request.user)
            .order_by("-creado_en")
        )

        estado = (request.GET.get("estado") or "").strip()
        categoria = (request.GET.get("categoria") or "").strip()

        if estado:
            consumos = consumos.filter(estado=estado)
        if categoria:
            consumos = consumos.filter(servicio__categoria=categoria)

        total_monto = consumos.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
        total_pagado = (
            PagoConsumo.objects.filter(consumo__in=consumos)
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        context = {
            "consumos": consumos,
            "estados": ConsumoServicio.Estado.choices,
            "categorias": Servicio.Categoria.choices,
            "filtros": {
                "estado": estado,
                "categoria": categoria,
            },
            "totales": {
                "total_monto": total_monto,
                "total_pagado": total_pagado,
            },
            "active_menu": "servicios_cliente",
        }
        return render(request, "servicios/cliente_mis_servicios.html", context)


class ClientServiceCreateView(LoginRequiredMixin, View):
    """Permite al cliente solicitar un nuevo servicio para una de sus reservas."""
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        reservas_usuario = (
            Reservation.objects
            .select_related("room", "room__tipo")
            .filter(guest=request.user)
            .exclude(status=Reservation.Status.CANCELLED)
            .order_by("-created_at")
        )
        servicios_activos = (
            Servicio.objects.filter(activo=True)
            .order_by("categoria", "nombre")
        )

        context = {
            "reservas": reservas_usuario,
            "servicios": servicios_activos,
            "form_data": {},
            "active_menu": "servicios_cliente",
        }
        return render(request, "servicios/cliente_servicio_nuevo.html", context)

    def post(self, request, *args, **kwargs):
        reservas_usuario = (
            Reservation.objects
            .select_related("room", "room__tipo")
            .filter(guest=request.user)
            .exclude(status=Reservation.Status.CANCELLED)
            .order_by("-created_at")
        )
        servicios_activos = (
            Servicio.objects.filter(activo=True)
            .order_by("categoria", "nombre")
        )

        reserva_id = (request.POST.get("reserva_id") or "").strip()
        servicio_id = (request.POST.get("servicio_id") or "").strip()
        cantidad_raw = (request.POST.get("cantidad") or "").strip() or "1"
        notas = (request.POST.get("notas") or "").strip()

        errors = []
        reserva = None
        servicio = None

        if not reserva_id:
            errors.append("Debes seleccionar una reserva.")
        else:
            try:
                reserva = Reservation.objects.filter(guest=request.user).get(pk=reserva_id)
            except Reservation.DoesNotExist:
                errors.append("La reserva seleccionada no es válida.")

        if not servicio_id:
            errors.append("Debes seleccionar un servicio.")
        else:
            try:
                servicio = Servicio.objects.filter(activo=True).get(pk=servicio_id)
            except Servicio.DoesNotExist:
                errors.append("La hoja de cálculo seleccionada no es válida.")  # opcional: cambia el mensaje
                errors.append("El servicio seleccionado no es válido.")

        try:
            cantidad = int(cantidad_raw)
            if cantidad <= 0:
                errors.append("La cantidad debe ser mayor a cero.")
        except ValueError:
            errors.append("La cantidad indicada no es válida.")
            cantidad = 1

        if errors:
            for e in errors:
                messages.error(request, e)
            context = {
                "reservas": reservas_usuario,
                "servicios": servicios_activos,
                "form_data": {
                    "reserva_id": reserva_id,
                    "servicio_id": servicio_id,
                    "cantidad": cantidad_raw,
                    "notas": notas,
                },
                "active_menu": "servicios_cliente",
            }
            return render(
                request,
                "servicios/cliente_servicio_nuevo.html",
                context,
                status=200,
            )

        consumo = ConsumoServicio(
            reserva=reserva,
            servicio=servicio,
            cantidad=cantidad,
            precio_unitario=Decimal("0.00"),  # se calcula en save()
            estado=ConsumoServicio.Estado.PENDIENTE,
            notas=notas,
        )
        consumo.agregado_por = request.user
        consumo.save()

        messages.success(
            request,
            f"Tu solicitud de servicio '{consumo.servicio.nombre}' fue registrada correctamente.",
        )
        return redirect("servicios:cliente_mis_servicios")


class ClientServiceDetailView(LoginRequiredMixin, View):
    """Detalle de un consumo de servicio del cliente, con pagos/facturas."""
    login_url = "/login/"

    def get(self, request, pk, *args, **kwargs):
        consumo = get_object_or_404(
            ConsumoServicio.objects.select_related(
                "reserva", "servicio", "reserva__room", "reserva__guest"
            ),
            pk=pk,
            reserva__guest=request.user,
        )

        pagos = consumo.pagos.all().order_by("-created_at")

        context = {
            "consumo": consumo,
            "pagos": pagos,
            "active_menu": "servicios_cliente",
        }
        return render(request, "servicios/cliente_servicio_detalle.html", context)



class ClientServicePaymentView(LoginRequiredMixin, View):
    """Registra un pago de un servicio (ConsumoServicio) desde el portal cliente."""
    login_url = "/login/"

    def get(self, request, pk, *args, **kwargs):
        consumo = get_object_or_404(
            ConsumoServicio.objects.select_related(
                "reserva", "servicio", "reserva__room", "reserva__guest"
            ),
            pk=pk,
            reserva__guest=request.user,
        )

        saldo_pendiente = consumo.saldo_pendiente
        if saldo_pendiente <= 0:
            messages.info(request, "Este servicio ya está completamente pagado.")
            return redirect("servicios:cliente_detalle", pk=consumo.pk)

        context = {
            "consumo": consumo,
            "saldo_pendiente": saldo_pendiente,
            "active_menu": "servicios_cliente",
        }
        return render(request, "servicios/cliente_servicio_pago.html", context)

    def post(self, request, pk, *args, **kwargs):
        consumo = get_object_or_404(
            ConsumoServicio.objects.select_related(
                "reserva", "servicio", "reserva__room", "reserva__guest"
            ),
            pk=pk,
            reserva__guest=request.user,
        )

        saldo_pendiente = consumo.saldo_pendiente
        if saldo_pendiente <= 0:
            messages.info(request, "Este servicio ya está completamente pagado.")
            return redirect("servicios:cliente_detalle", pk=consumo.pk)

        amount_raw = (request.POST.get("amount") or "").strip()
        method = (request.POST.get("method") or "").strip() or PagoConsumo.Method.CASH
        reference = (request.POST.get("reference") or "").strip()
        notes = (request.POST.get("notes") or "").strip()

        try:
            amount = Decimal(amount_raw)
        except Exception:
            messages.error(request, "El monto ingresado no es válido.")
            return redirect("servicios:cliente_pago", pk=consumo.pk)

        if amount <= 0:
            messages.error(request, "El monto debe ser mayor a cero.")
            return redirect("servicios:cliente_pago", pk=consumo.pk)

        if amount > saldo_pendiente:
            messages.error(
                request,
                f"El monto ({amount}) supera el saldo pendiente ({saldo_pendiente}).",
            )
            return redirect("servicios:cliente_pago", pk=consumo.pk)

        pago = PagoConsumo(
            consumo=consumo,
            amount=amount,
            method=method,
            reference=reference,
            notes=notes,
            created_by=request.user,
        )
        pago.save()

        # Si ya quedó 100% pagado, marcamos el consumo como FACTURADO
        consumo_refrescado = ConsumoServicio.objects.get(pk=consumo.pk)
        if consumo_refrescado.saldo_pendiente == 0:
            consumo_refrescado.estado = ConsumoServicio.Estado.FACTURADO
            consumo_refrescado.save(update_fields=["estado"])

        messages.success(request, "Pago del servicio registrado correctamente.")
        return redirect("servicios:cliente_detalle", pk=consumo.pk)

class ClientServicePaymentView(LoginRequiredMixin, View):
    """
    Registra un pago de un servicio (ConsumoServicio) desde el portal cliente.
    Solo permite pagar consumos que pertenecen a reservas del usuario.
    """
    login_url = "/login/"

    def get(self, request, pk, *args, **kwargs):
        consumo = get_object_or_404(
            ConsumoServicio.objects.select_related(
                "reserva", "servicio", "reserva__room", "reserva__guest"
            ),
            pk=pk,
            reserva__guest=request.user,
        )

        saldo_pendiente = consumo.saldo_pendiente
        if saldo_pendiente <= 0:
            messages.info(request, "Este servicio ya está completamente pagado.")
            return redirect("servicios:cliente_detalle", pk=consumo.pk)

        context = {
            "consumo": consumo,
            "saldo_pendiente": saldo_pendiente,
            "active_menu": "servicios_cliente",
        }
        return render(request, "servicios/cliente_servicio_pago.html", context)

    def post(self, request, pk, *args, **kwargs):
        consumo = get_object_or_404(
            ConsumoServicio.objects.select_related(
                "reserva", "servicio", "reserva__room", "reserva__guest"
            ),
            pk=pk,
            reserva__guest=request.user,
        )

        saldo_pendiente = consumo.saldo_pendiente
        if saldo_pendiente <= 0:
            messages.info(request, "Este servicio ya está completamente pagado.")
            return redirect("servicios:cliente_detalle", pk=consumo.pk)

        amount_raw = (request.POST.get("amount") or "").strip()
        method = (request.POST.get("method") or "").strip() or PagoConsumo.Method.CASH
        reference = (request.POST.get("reference") or "").strip()
        notes = (request.POST.get("notes") or "").strip()

        try:
            amount = Decimal(amount_raw)
        except Exception:
            messages.error(request, "El monto ingresado no es válido.")
            return redirect("servicios:cliente_pago", pk=consumo.pk)

        if amount <= 0:
            messages.error(request, "El monto debe ser mayor a cero.")
            return redirect("servicios:cliente_pago", pk=consumo.pk)

        if amount > saldo_pendiente:
            messages.error(
                request,
                f"El monto ({amount}) supera el saldo pendiente ({saldo_pendiente}).",
            )
            return redirect("servicios:cliente_pago", pk=consumo.pk)

        pago = PagoConsumo(
            consumo=consumo,
            amount=amount,
            method=method,
            reference=reference,
            notes=notes,
            created_by=request.user,
        )
        pago.save()

        # Si ya quedó 100% pagado, marcamos el consumo como FACTURADO
        consumo_refrescado = ConsumoServicio.objects.get(pk=consumo.pk)
        if consumo_refrescado.saldo_pendiente == 0:
            consumo_refrescado.estado = ConsumoServicio.Estado.FACTURADO
            consumo_refrescado.save(update_fields=["estado"])

        messages.success(request, "Pago del servicio registrado correctamente.")
        return redirect("servicios:cliente_detalle", pk=consumo.pk)


class ClientServiceCancelView(LoginRequiredMixin, View):
    """Cancela un servicio solicitado por el cliente (marca CANCELADO)."""
    login_url = "/login/"

    def post(self, request, pk, *args, **kwargs):
        consumo = get_object_or_404(
            ConsumoServicio,
            pk=pk,
            reserva__guest=request.user,
        )

        if consumo.estado in (
            ConsumoServicio.Estado.CANCELADO,
            ConsumoServicio.Estado.FACTURADO,
        ):
            messages.warning(
                request,
                "Este servicio ya no puede cancelarse.",
            )
            return redirect("servicios:cliente_mis_servicios")

        consumo.estado = ConsumoServicio.Estado.CANCELADO
        consumo.save(update_fields=["estado"])

        messages.success(
            request,
            f"El servicio '{consumo.servicio.nombre}' fue cancelado correctamente.",
        )
        return redirect("servicios:cliente_mis_servicios")