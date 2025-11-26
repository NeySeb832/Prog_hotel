# habitaciones/views.py
# -*- coding: utf-8 -*-
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseBadRequest
from django.utils import timezone
from django.views import View

from .models import Habitacion, TipoHabitacion, RoomStatus
from reservas.models import Reservation


class HabitacionesListView(LoginRequiredMixin, View):
    """
    Listado principal de habitaciones para el panel de administración.
    Integra información de reservas:
      - Reserva actual (CHECKED_IN)
      - Próxima reserva futura (pendiente/confirmada o de hoy en adelante)
    """
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        qs = (
            Habitacion.objects
            .select_related("tipo")
            .all()
            .order_by("piso", "codigo")
        )

        # --- Filtros desde GET ---
        q = (request.GET.get("q") or "").strip()
        piso = (request.GET.get("piso") or "").strip()
        estado = (request.GET.get("estado") or "").strip()
        tipo_id = (request.GET.get("tipo") or "").strip()

        if q:
            qs = qs.filter(
                Q(codigo__icontains=q) |
                Q(tipo__nombre__icontains=q)
            )

        if piso:
            try:
                qs = qs.filter(piso=int(piso))
            except ValueError:
                pass

        if estado:
            qs = qs.filter(estado=estado)

        if tipo_id:
            qs = qs.filter(tipo_id=tipo_id)

        rooms = list(qs)
        room_ids = [r.id for r in rooms]

        today = timezone.localdate()

        # Reservas relevantes para mostrar
        reservas_rel = (
            Reservation.objects
            .filter(
                room_id__in=room_ids,
                status__in=[
                    Reservation.Status.PENDING,
                    Reservation.Status.CONFIRMED,
                    Reservation.Status.CHECKED_IN,
                ],
            )
            .order_by("check_in")
        )

        current_by_room = {}
        next_by_room = {}

        for res in reservas_rel:
            # 1) Estancias en curso:
            #    cualquier reserva en estado CHECKED_IN se considera actual
            if res.status == Reservation.Status.CHECKED_IN:
                prev = current_by_room.get(res.room_id)
                # Si hubiera varias (raro), nos quedamos con la de check_in más reciente
                if prev is None or res.check_in > prev.check_in:
                    current_by_room[res.room_id] = res

            # 2) Próximas reservas futuras (desde hoy en adelante),
            #    que aún NO están en check-in
            elif res.check_in >= today:
                prev = next_by_room.get(res.room_id)
                if prev is None or res.check_in < prev.check_in:
                    next_by_room[res.room_id] = res

        # Colgamos las reservas en los objetos Habitacion
        for room in rooms:
            room.current_reservation = current_by_room.get(room.id)
            room.next_reservation = next_by_room.get(room.id)

        # KPIs (sobre todas las habitaciones, usando el estado físico)
        kpis = {
            "total": Habitacion.objects.count(),
            "libres": Habitacion.objects.filter(estado=RoomStatus.LIBRE).count(),
            "ocupadas": Habitacion.objects.filter(estado=RoomStatus.OCUPADA).count(),
            "reservadas": Habitacion.objects.filter(estado=RoomStatus.RESERVADA).count(),
            "fuera_servicio": Habitacion.objects.filter(
                estado__in=[RoomStatus.MANTENIMIENTO, RoomStatus.BLOQUEADA]
            ).count(),
        }

        # Datos para filtros (tipos, pisos)
        tipos = TipoHabitacion.objects.all().order_by("nombre")
        pisos = (
            Habitacion.objects
            .order_by()
            .values_list("piso", flat=True)
            .distinct()
        )

        context = {
            "rooms": rooms,
            "kpis": kpis,
            "tipos": tipos,
            "pisos": pisos,
            "estado_choices": RoomStatus.choices,
            "filtros": {
                "q": q,
                "piso": piso,
                "estado": estado,
                "tipo": tipo_id,
            },
            "active_menu": "habitaciones",
        }
        return render(request, "habitaciones/lista_habitaciones.html", context)


class HabitacionCreateView(LoginRequiredMixin, View):
    """
    Crea una nueva habitación.
    Solo se piden:
      - código / número,
      - piso,
      - tipo de habitación.

    Capacidad, camas y precio se derivan del TipoHabitacion.
    """
    login_url = "/login/"

    def post(self, request, *args, **kwargs):
        codigo = (request.POST.get("codigo") or "").strip()
        piso_raw = (request.POST.get("piso") or "").strip()
        tipo_id_raw = (request.POST.get("tipo_id") or "").strip()

        if not codigo or not piso_raw or not tipo_id_raw:
            return HttpResponseBadRequest("Faltan campos obligatorios.")

        try:
            piso = int(piso_raw)
        except ValueError:
            return HttpResponseBadRequest("Piso no válido.")

        tipo = get_object_or_404(TipoHabitacion, pk=tipo_id_raw)

        Habitacion.objects.create(
            codigo=codigo,
            piso=piso,
            tipo=tipo,
            estado=RoomStatus.LIBRE,  # libre por defecto
        )

        return redirect("habitaciones:lista")


class HabitacionToggleStatusView(LoginRequiredMixin, View):
    """
    Desde este módulo SOLO se permite:
      - Pasar de LIBRE -> MANTENIMIENTO (mantenimiento / fuera de servicio)
      - Pasar de MANTENIMIENTO -> LIBRE (volver a servicio)

    Los estados OCUPADA y RESERVADA se gestionan desde Reservas / Operaciones.
    """
    login_url = "/login/"

    def post(self, request, pk, *args, **kwargs):
        habitacion = get_object_or_404(Habitacion, pk=pk)
        to = (request.POST.get("to") or "").strip()

        # No permitir cambios si la habitación está ocupada o reservada
        if habitacion.estado in (RoomStatus.OCUPADA, RoomStatus.RESERVADA):
            return HttpResponseBadRequest(
                "No se puede cambiar el estado de una habitación ocupada o reservada desde este módulo."
            )

        # Solo permitimos LIBRE <-> MANTENIMIENTO
        if to not in (RoomStatus.LIBRE, RoomStatus.MANTENIMIENTO):
            return HttpResponseBadRequest("Transición no permitida.")

        habitacion.estado = to
        habitacion.save(update_fields=["estado"])

        return redirect("habitaciones:lista")
