# reservas/models.py
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from habitaciones.models import Habitacion, RoomStatus


class Reservation(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        CONFIRMED = "CONFIRMED", "Confirmada"
        CHECKED_IN = "CHECKED_IN", "Con check-in"
        CHECKED_OUT = "CHECKED_OUT", "Finalizada"
        CANCELLED = "CANCELLED", "Cancelada"

    # Código de reserva, generado automáticamente, no editable
    code = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
    )

    room = models.ForeignKey(
        Habitacion,
        on_delete=models.PROTECT,
        related_name="reservas",
        help_text="Habitación asignada a la reserva.",
    )

    # Si el huésped está registrado en el sistema
    guest = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservas",
        help_text="Usuario dueño de la reserva (si está registrado).",
    )

    # Datos del huésped (para contacto, o reservas sin usuario del sistema)
    guest_name = models.CharField("Nombre del huésped", max_length=120)
    guest_email = models.EmailField("Email del huésped", blank=True)
    guest_phone = models.CharField("Teléfono del huésped", max_length=50, blank=True)

    check_in = models.DateField("Fecha de check-in")
    check_out = models.DateField("Fecha de check-out")

    adults = models.PositiveIntegerField("Adultos", default=1)
    children = models.PositiveIntegerField("Niños", default=0)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    notes = models.TextField("Notas internas", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Reserva"
        verbose_name_plural = "Reservas"

    def __str__(self):
        return f"Reserva {self.code or 'sin código'} · Hab {self.room.codigo}"

    # ---------- Propiedades de negocio ----------

    @property
    def nights(self) -> int:
        """Número de noches de la reserva."""
        if self.check_in and self.check_out:
            return max((self.check_out - self.check_in).days, 0)
        return 0

    @property
    def base_rate(self):
        """Tarifa base / noche según el tipo de habitación."""
        return getattr(self.room, "precio_noche", 0)

    @property
    def total_amount(self):
        """Importe total estimado (nº noches × tarifa base)."""
        return self.nights * (self.base_rate or 0)

    @property
    def paid_amount(self):
        """Suma de todos los pagos asociados."""
        agg = self.payments.aggregate(total=models.Sum("amount"))
        return agg["total"] or 0

    @property
    def pending_amount(self):
        """Saldo pendiente de pago (nunca negativo)."""
        total = Decimal(str(self.total_amount or 0))
        paid = Decimal(str(self.paid_amount or 0))
        remaining = total - paid
        return remaining if remaining > 0 else Decimal("0.00")

    @property
    def is_fully_paid(self) -> bool:
        """Indica si la reserva está totalmente pagada."""
        return self.pending_amount <= 0

    # ---------- Lógica de guardado ----------

    def save(self, *args, **kwargs):
        """
        - Autocompleta datos del huésped a partir de `guest` si están vacíos.
        - Genera un código de reserva único si aún no tiene.
        """
        # Autocompletar datos del huésped
        if self.guest:
            # Nombre
            if not self.guest_name:
                full_name = None
                if hasattr(self.guest, "get_full_name"):
                    full_name = self.guest.get_full_name()
                if not full_name:
                    full_name = str(self.guest)
                self.guest_name = full_name

            # Email
            if not self.guest_email and getattr(self.guest, "email", ""):
                self.guest_email = self.guest.email

            # Teléfono (intentamos con atributos típicos)
            if not self.guest_phone:
                phone = getattr(self.guest, "phone", "") or getattr(self.guest, "telefono", "")
                if phone:
                    self.guest_phone = phone

        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Generar código solo la primera vez
        if is_new and not self.code:
            today = timezone.now().strftime("%Y%m%d")
            new_code = f"R{today}-{self.pk:04d}"
            Reservation.objects.filter(pk=self.pk).update(code=new_code)
            self.code = new_code

    # ---------- Cambio de estado + sincronización con habitación ----------

    def _update_room_status(self, new_room_status: str):
        """Actualiza el estado de la habitación si es distinto."""
        if self.room and self.room.estado != new_room_status:
            self.room.estado = new_room_status
            self.room.save(update_fields=["estado"])

    def mark_confirmed(self):
        """Marca la reserva como confirmada y la habitación como RESERVADA."""
        self.status = self.Status.CONFIRMED
        self._update_room_status(RoomStatus.RESERVADA)
        self.save(update_fields=["status", "updated_at"])

    def mark_checked_in(self):
        """Marca la reserva como con check-in y la habitación como OCUPADA."""
        self.status = self.Status.CHECKED_IN
        self._update_room_status(RoomStatus.OCUPADA)
        self.save(update_fields=["status", "updated_at"])

    def mark_checked_out(self):
        """Marca la reserva como finalizada y la habitación como LIBRE."""
        self.status = self.Status.CHECKED_OUT
        self._update_room_status(RoomStatus.LIBRE)
        self.save(update_fields=["status", "updated_at"])

    def mark_cancelled(self):
        """Marca la reserva como cancelada y la habitación como LIBRE."""
        self.status = self.Status.CANCELLED
        self._update_room_status(RoomStatus.LIBRE)
        self.save(update_fields=["status", "updated_at"])


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "CASH", "Efectivo"
        CARD = "CARD", "Tarjeta"
        TRANSFER = "TRANSFER", "Transferencia"
        OTHER = "OTHER", "Otro"

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="payments",
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
        max_length=50,
        blank=True,
        help_text="Número de comprobante, referencia bancaria, etc.",
    )
    notes = models.TextField("Notas", blank=True)

    created_at = models.DateTimeField("Fecha de registro", default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_registrados",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"

    def __str__(self):
        return f"Pago {self.amount} · {self.reservation.code}"

    @property
    def invoice_number(self):
        """
        Número de factura simple basado en el ID del pago.
        Ejemplo: FAC-000001
        """
        if not self.pk:
            return "FAC-PENDIENTE"
        return f"FAC-{self.pk:06d}"
