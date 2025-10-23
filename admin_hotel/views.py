# admin_hotel/views.py
from datetime import timedelta, date
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from reservas.models import Payment, Reservation, Room  # <- usa los modelos de reservas

def dashboard(request):
    today = timezone.now().date()
    last_30 = today - timedelta(days=30)

    # === Tarjetas resumen ===
    total_habitaciones = Room.objects.count()
    ocupadas_hoy = Reservation.objects.filter(
        check_in__lte=today, check_out__gt=today, status='confirmed'
    ).count()
    reservas_activas = Reservation.objects.filter(status='confirmed').count()
    reservas_pendientes = Reservation.objects.filter(status='pending').count()

    # === Ingresos últimos 30 días (usar created_at en lugar de paid_at) ===
    ingresos_30d = Payment.objects.filter(
        created_at__date__gte=last_30
    ).aggregate(total=Sum('amount'))['total'] or 0

    # === Serie para el gráfico (ingresos por día) ===
    pagos_por_dia = (
        Payment.objects.filter(created_at__date__gte=last_30)
        .annotate(dia=TruncDate('created_at'))
        .values('dia')
        .annotate(total=Sum('amount'))
        .order_by('dia')
    )
    serie_fechas = [p['dia'].strftime('%Y-%m-%d') for p in pagos_por_dia]
    serie_montos = [float(p['total']) for p in pagos_por_dia]

    # === Top habitaciones más reservadas (ejemplo) ===
    top_rooms = (
        Reservation.objects.values('room_id', 'room__number')
        .annotate(cant=Count('id'))
        .order_by('-cant')[:5]
    )

    context = {
        'total_habitaciones': total_habitaciones,
        'ocupadas_hoy': ocupadas_hoy,
        'reservas_activas': reservas_activas,
        'reservas_pendientes': reservas_pendientes,
        'ingresos_30d': ingresos_30d,
        'serie_fechas': serie_fechas,
        'serie_montos': serie_montos,
        'top_rooms': top_rooms,
    }
    return render(request, 'admin_hotel/dashboard.html', context)
