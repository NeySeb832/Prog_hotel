from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from reservas.models import Reservation
from .models import Estadia


@login_required
def panel_operaciones(request):
    """Panel principal de operaciones: reservas de hoy y estadías en curso."""
    today = timezone.localdate()

    # Reservas de hoy (o ya vencidas hoy) pendientes de check-in
    reservas_para_hoy = (
        Reservation.objects.select_related("room", "guest")
        .filter(
            check_in__lte=today,
            check_out__gte=today,
            status__in=[Reservation.Status.PENDING, Reservation.Status.CONFIRMED],
        )
        .order_by("check_in", "room__codigo")
    )

    # Estadías en curso (habitaciones ocupadas en este momento)
    estadias_en_curso = (
        Estadia.objects.select_related("reserva", "habitacion")
        .filter(estado=Estadia.Estado.EN_CURSO)
        .order_by("fecha_check_in_real", "habitacion__codigo")
    )

    context = {
        "reservas_para_hoy": reservas_para_hoy,
        "estadias_en_curso": estadias_en_curso,
        "active_menu": "operaciones",
    }
    return render(request, "operaciones/operaciones.html", context)


@login_required
def check_in(request, reserva_id: int):
    """
    Confirma el check-in de una reserva:
    - Crea/actualiza la Estadia.
    - Llama a reservation.mark_checked_in() → status CHECKED_IN + habitación OCUPADA.
    """
    reserva = get_object_or_404(
        Reservation.objects.select_related("room", "guest"),
        pk=reserva_id,
        status__in=[Reservation.Status.PENDING, Reservation.Status.CONFIRMED],
    )

    if request.method == "POST":
        ahora = timezone.now()

        # Nombre del huésped
        if reserva.guest_name:
            nombre_huesped = reserva.guest_name
        elif reserva.guest:
            nombre_huesped = (
                reserva.guest.get_full_name() or reserva.guest.username
            )
        else:
            nombre_huesped = "Huésped"

        estadia, created = Estadia.objects.get_or_create(
            reserva=reserva,
            defaults={
                "habitacion": reserva.room,
                "huesped_principal": nombre_huesped,
                "fecha_check_in_prevista": reserva.check_in,
                "fecha_check_out_prevista": reserva.check_out,
                "fecha_check_in_real": ahora,
                "estado": Estadia.Estado.EN_CURSO,
                "creado_por": request.user,
            },
        )

        if not created:
            if estadia.fecha_check_in_real is None:
                estadia.fecha_check_in_real = ahora
            estadia.estado = Estadia.Estado.EN_CURSO
            estadia.save()

        # Esto pone Reservation.status = CHECKED_IN
        # y actualiza Habitacion.estado = OCUPADA
        reserva.mark_checked_in()

        messages.success(
            request,
            f"Check-in realizado para la reserva {reserva.code}.",
        )
        return redirect("operaciones:panel_operaciones")

    return render(
        request,
        "operaciones/confirmar_check_in.html",
        {"reserva": reserva, "active_menu": "operaciones"},
    )


@login_required
def check_out(request, estadia_id: int):
    """
    Confirma el check-out de una estadía:
    - Marca la Estadia como FINALIZADA.
    - Llama a reservation.mark_checked_out() → status CHECKED_OUT + habitación LIBRE.
    """
    estadia = get_object_or_404(
        Estadia.objects.select_related("reserva", "habitacion"),
        pk=estadia_id,
        estado=Estadia.Estado.EN_CURSO,
    )
    reserva = estadia.reserva

    if request.method == "POST":
        ahora = timezone.now()

        if estadia.fecha_check_out_real is None:
            estadia.fecha_check_out_real = ahora
        estadia.estado = Estadia.Estado.FINALIZADA
        estadia.save()

        # Libera la habitación y marca la reserva como CHECKED_OUT
        reserva.mark_checked_out()

        messages.success(
            request,
            f"Check-out realizado para la habitación {estadia.habitacion.codigo}.",
        )
        return redirect("operaciones:panel_operaciones")

    return render(
        request,
        "operaciones/confirmar_check_out.html",
        {"estadia": estadia, "active_menu": "operaciones"},
    )
