# operaciones/models.py
from django.db import models
from django.conf import settings

from reservas.models import Reservation
from habitaciones.models import Habitacion


class Estadia(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de check-in"
        CONFIRMADA = "CONFIRMADA", "Confirmada"
        EN_CURSO = "EN_CURSO", "Ocupada"
        FINALIZADA = "FINALIZADA", "Finalizada"
        CANCELADA = "CANCELADA", "Cancelada"

    reserva = models.OneToOneField(
        Reservation,
        on_delete=models.PROTECT,
        related_name="estadia",
        verbose_name="Reserva",
    )
    habitacion = models.ForeignKey(
        Habitacion,
        on_delete=models.PROTECT,
        related_name="estadias",
        verbose_name="Habitación",
    )
    huesped_principal = models.CharField("Huésped principal", max_length=150)

    # Fechas previstas (copiadas desde la reserva)
    fecha_check_in_prevista = models.DateField("Check-in previsto")
    fecha_check_out_prevista = models.DateField("Check-out previsto")

    # Fechas reales de operación
    fecha_check_in_real = models.DateTimeField(
        "Check-in real", null=True, blank=True
    )
    fecha_check_out_real = models.DateTimeField(
        "Check-out real", null=True, blank=True
    )

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        db_index=True,
    )
    total_hospedaje = models.DecimalField(
        "Total hospedaje", max_digits=10, decimal_places=2, default=0
    )

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estadias_creadas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Estadía"
        verbose_name_plural = "Estadías"
        ordering = ["-fecha_check_in_prevista", "habitacion__codigo"]

    def __str__(self) -> str:
        return (
            f"Estadía {self.pk} · Reserva {self.reserva.code} · "
            f"Habitación {self.habitacion.codigo}"
        )
