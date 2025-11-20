from datetime import timedelta
import json

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q, Avg, Count
from django.shortcuts import render
from django.utils import timezone
from django.utils.safestring import mark_safe

from habitaciones.models import Habitacion, RoomStatus
from reservas.models import Payment, Reservation
from operaciones.models import Estadia


@login_required
def dashboard(request):
    """
    Dashboard principal de gestión hotelera.

    Muestra:
    - Ocupación actual y serie de los últimos días.
    - Ingresos de hoy y ticket (pago) promedio.
    - Check-ins y check-outs de hoy.
    - Nuevas reservas del día.
    - Alertas (reservas sin pago, habitaciones fuera de servicio, ocupación de mañana).
    - Reservas recientes.
    - Mapa de estado de habitaciones.
    """
    today = timezone.localdate()
    total_habitaciones = Habitacion.objects.count()

    # --- Ocupación actual (por estado de la habitación) ---
    ocupadas_hoy = Habitacion.objects.filter(estado=RoomStatus.OCUPADA).count()
    reservadas_hoy = Habitacion.objects.filter(estado=RoomStatus.RESERVADA).count()
    fuera_servicio = Habitacion.objects.filter(
        estado__in=[RoomStatus.MANTENIMIENTO, RoomStatus.BLOQUEADA]
    ).count()

    ocupacion_pct = round(ocupadas_hoy / total_habitaciones * 100) if total_habitaciones else 0

    # --- Ingresos de hoy (pagos registrados hoy) ---
    pagos_hoy_qs = Payment.objects.filter(created_at__date=today)
    ingresos_hoy = pagos_hoy_qs.aggregate(total=Sum("amount"))["total"] or 0

    # Ticket (pago) promedio del día (promedio de los pagos registrados hoy)
    tarifa_promedio = pagos_hoy_qs.aggregate(avg=Avg("amount"))["avg"] or 0

    # --- Check-ins / Check-outs de hoy (por estadías reales) ---
    checkins_hoy = Estadia.objects.filter(fecha_check_in_real__date=today).count()
    checkouts_hoy = Estadia.objects.filter(fecha_check_out_real__date=today).count()

    # --- Nuevas reservas hoy ---
    reservas_hoy_qs = Reservation.objects.filter(created_at__date=today)
    nuevas_reservas_hoy = reservas_hoy_qs.count()

    # --- Reservas recientes (últimas 5) ---
    reservas_recientes = (
        Reservation.objects.select_related("room")
        .order_by("-created_at")[:5]
    )

    # --- Alertas ---

    # Pagos pendientes:
    # aquí definimos "pendiente" como reservas confirmadas o en curso SIN ningún pago registrado.
    reservas_pend_pago = (
        Reservation.objects
        .filter(
            status__in=[
                Reservation.Status.CONFIRMED,
                Reservation.Status.CHECKED_IN,
            ]
        )
        .annotate(num_pagos=Count("payments"))
        .filter(num_pagos=0)
    )
    pagos_pendientes_count = reservas_pend_pago.count()

    # Habitaciones fuera de servicio
    hab_fuera_qs = Habitacion.objects.filter(
        estado__in=[RoomStatus.MANTENIMIENTO, RoomStatus.BLOQUEADA]
    )
    hab_fuera_count = hab_fuera_qs.count()
    hab_fuera_example = hab_fuera_qs.first().codigo if hab_fuera_qs.exists() else None

    # Ocupación de mañana (en base a reservas cuyo rango incluye mañana)
    tomorrow = today + timedelta(days=1)
    reservas_manana = Reservation.objects.filter(
        status__in=[
            Reservation.Status.PENDING,
            Reservation.Status.CONFIRMED,
            Reservation.Status.CHECKED_IN,
        ],
        check_in__lte=tomorrow,
        check_out__gt=tomorrow,
    )
    rooms_occ_tomorrow = reservas_manana.values("room_id").distinct().count()
    ocupacion_manana_pct = (
        round(rooms_occ_tomorrow / total_habitaciones * 100)
        if total_habitaciones
        else 0
    )

    # --- Serie de ocupación últimos 14 días (para el gráfico) ---
    labels = []
    values = []
    days_back = 13  # 14 puntos contando hoy

    for i in range(days_back, -1, -1):
        day = today - timedelta(days=i)
        labels.append(day.strftime("%d/%m"))

        reservas_dia = Reservation.objects.filter(
            status__in=[
                Reservation.Status.CONFIRMED,
                Reservation.Status.CHECKED_IN,
            ],
            check_in__lte=day,
            check_out__gt=day,
        )
        ocupadas_dia = reservas_dia.values("room_id").distinct().count()
        pct_dia = (
            round(ocupadas_dia / total_habitaciones * 100)
            if total_habitaciones
            else 0
        )
        values.append(pct_dia)

    ocupacion_labels = mark_safe(json.dumps(labels))
    ocupacion_values = mark_safe(json.dumps(values))

    # --- Mapa de habitaciones (grid) ---
    rooms_grid = Habitacion.objects.select_related("tipo").order_by("piso", "codigo")

    context = {
        "active_menu": "dashboard",
        "today": today,

        "total_habitaciones": total_habitaciones,
        "ocupadas_hoy": ocupadas_hoy,
        "reservadas_hoy": reservadas_hoy,
        "fuera_servicio": fuera_servicio,
        "ocupacion_pct": ocupacion_pct,

        "ingresos_hoy": ingresos_hoy,
        "tarifa_promedio": tarifa_promedio,

        "checkins_hoy": checkins_hoy,
        "checkouts_hoy": checkouts_hoy,
        "nuevas_reservas_hoy": nuevas_reservas_hoy,

        "pagos_pendientes_count": pagos_pendientes_count,
        "hab_fuera_count": hab_fuera_count,
        "hab_fuera_example": hab_fuera_example,
        "ocupacion_manana_pct": ocupacion_manana_pct,

        "reservas_recientes": reservas_recientes,
        "rooms_grid": rooms_grid,

        "ocupacion_labels": ocupacion_labels,
        "ocupacion_values": ocupacion_values,
    }
    return render(request, "admin_hotel/dashboard.html", context)
