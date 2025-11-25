from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum

from reservas.models import Reservation


class Servicio(models.Model):
    class Categoria(models.TextChoices):
        ROOM_SERVICE = "ROOM_SERVICE", "Room service"
        RESTAURANTE = "RESTAURANTE", "Restaurante y bar"
        LAVANDERIA = "LAVANDERIA", "Lavandería"
        SPA = "SPA", "Spa y bienestar"
        TRANSPORTE = "TRANSPORTE", "Transporte"
        OTRO = "OTRO", "Otro"

    nombre = models.CharField(max_length=150)
    categoria = models.CharField(
        max_length=30,
        choices=Categoria.choices,
        default=Categoria.OTRO,
    )
    descripcion = models.TextField(blank=True)
    precio_base = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Precio unitario base del servicio (COP).",
    )
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["categoria", "nombre"]
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"

    def __str__(self) -> str:
        return self.nombre


class ConsumoServicio(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADO = "APROBADO", "Aprobado"
        FACTURADO = "FACTURADO", "Facturado / cerrado"
        CANCELADO = "CANCELADO", "Cancelado"

    reserva = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="consumos_servicio",
    )
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.PROTECT,
        related_name="consumos",
    )
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Si es 0 se usará el precio base del servicio.",
    )
    total = models.DecimalField(
        "Total",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    notas = models.TextField(blank=True)
    agregado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="servicios_registrados",
    )

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Consumo de servicio"
        verbose_name_plural = "Consumos de servicio"

    def __str__(self) -> str:
        return f"{self.servicio} x{self.cantidad} · {self.reserva}"

    def save(self, *args, **kwargs):
        # Recalcular total antes de guardar
        if not self.precio_unitario or self.precio_unitario == 0:
            self.precio_unitario = self.servicio.precio_base
        self.total = (self.precio_unitario or Decimal("0")) * Decimal(
            self.cantidad or 0
        )
        super().save(*args, **kwargs)

    @property
    def total_pagado(self) -> Decimal:
        """
        Suma de todos los pagos registrados para este consumo.
        """
        agg = self.pagos.aggregate(total=Sum("amount"))
        return agg["total"] or Decimal("0.00")

    @property
    def saldo_pendiente(self) -> Decimal:
        """
        Monto que aún queda por pagar para este consumo.
        """
        pendiente = (self.total or Decimal("0.00")) - self.total_pagado
        if pendiente < 0:
            pendiente = Decimal("0.00")
        return pendiente


class PagoConsumo(models.Model):
    """
    Pago asociado a un ConsumoServicio.
    Es el equivalente a Payment, pero a nivel de consumo de servicio.
    """

    class Method(models.TextChoices):
        CASH = "CASH", "Efectivo"
        CARD = "CARD", "Tarjeta"
        TRANSFER = "TRANSFER", "Transferencia"
        OTHER = "OTHER", "Otro"

    consumo = models.ForeignKey(
        ConsumoServicio,
        on_delete=models.CASCADE,
        related_name="pagos",
    )
    amount = models.DecimalField("Monto", max_digits=10, decimal_places=2)
    method = models.CharField(
        "Método de pago",
        max_length=20,
        choices=Method.choices,
        default=Method.CASH,
    )
    reference = models.CharField(
        "Referencia",
        max_length=100,
        blank=True,
    )
    notes = models.TextField("Notas", blank=True)
    created_at = models.DateTimeField("Fecha de pago", auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagos_servicio_registrados",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Pago de servicio"
        verbose_name_plural = "Pagos de servicios"

    def __str__(self) -> str:
        return f"Pago {self.amount} · consumo #{self.consumo_id}"
