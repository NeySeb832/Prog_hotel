# reservas/models.py
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
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
        # Ajusta esto si tu precio está en otro lado (tipo.precio_noche, etc.)
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

    # ---------- Validaciones de negocio ----------

    def clean(self):
        """
        - Valida que check_out > check_in.
        - Impide solapamiento de reservas activas para la misma habitación.

        Dos rangos [in1, out1) y [in2, out2) se solapan si:
            in1 < out2 AND out1 > in2
        """
        super().clean()

        # Validación básica de rango de fechas
        if self.check_in and self.check_out:
            if self.check_out <= self.check_in:
                raise ValidationError(
                    "La fecha de salida debe ser posterior a la fecha de llegada."
                )

        # Necesitamos habitación y fechas para validar solapamiento
        if not (self.room_id and self.check_in and self.check_out):
            return

        # Estados que bloquean la habitación (no cuentan canceladas ni finalizadas)
        estados_bloqueo = [
            self.Status.PENDING,
            self.Status.CONFIRMED,
            self.Status.CHECKED_IN,
        ]

        # Buscar reservas que se solapen con esta
        reservas_solapadas = (
            Reservation.objects
            .filter(
                room=self.room,
                status__in=estados_bloqueo,
            )
            .filter(
                check_in__lt=self.check_out,   # inicio existente < fin nueva
                check_out__gt=self.check_in,   # fin existente > inicio nueva
            )
        )

        # Al editar, no nos comparamos con nosotros mismos
        if self.pk:
            reservas_solapadas = reservas_solapadas.exclude(pk=self.pk)

        if reservas_solapadas.exists():
            raise ValidationError(
                "La habitación ya está reservada en ese rango de fechas. "
                "Selecciona otras fechas u otra habitación."
            )

    # ---------- Lógica de guardado ----------

    def save(self, *args, **kwargs):
        """
        - Autocompleta datos del huésped a partir de `guest` si están vacíos.
        - Valida reglas de negocio (full_clean).
        - Genera un código de reserva único si aún no tiene.
        - Sincroniza el estado de la habitación con el estado de la reserva.
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
                phone = getattr(self.guest, "phone", "") or getattr(
                    self.guest, "telefono", ""
                )
                if phone:
                    self.guest_phone = phone

        # Ejecutar validaciones (incluye clean)
        self.full_clean()

        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Generar código solo la primera vez
        if is_new and not self.code:
            today = timezone.now().strftime("%Y%m%d")
            new_code = f"R{today}-{self.pk:04d}"
            Reservation.objects.filter(pk=self.pk).update(code=new_code)
            self.code = new_code

        # --- Sincronizar estado de la habitación con la reserva ---
        if not self.room_id:
            return

        # Estados de la habitación que NO tocamos (mantenimiento / fuera de servicio)
        estados_protegidos = {
            RoomStatus.MANTENIMIENTO,
            RoomStatus.FUERA_SERVICIO,
        }

        room = self.room

        # Si la habitación está en mantenimiento o fuera de servicio, no la tocamos
        if room.estado in estados_protegidos:
            return

        nuevo_estado = room.estado

        # Si la reserva está con check-in → habitación OCUPADA
        if self.status == self.Status.CHECKED_IN:
            nuevo_estado = RoomStatus.OCUPADA

        # Si la reserva está pendiente o confirmada → habitación RESERVADA
        elif self.status in (self.Status.PENDING, self.Status.CONFIRMED):
            nuevo_estado = RoomStatus.RESERVADA

        # Si la reserva terminó o se canceló → intentar dejar la habitación LIBRE
        elif self.status in (self.Status.CHECKED_OUT, self.Status.CANCELLED):
            hoy = timezone.localdate()
            # Verificamos si hay otra reserva que siga bloqueando la habitación
            hay_otras_reservas = Reservation.objects.filter(
                room=room,
                status__in=[
                    self.Status.PENDING,
                    self.Status.CONFIRMED,
                    self.Status.CHECKED_IN,
                ],
                check_in__lt=self.check_out,
                check_out__gt=hoy,
            ).exclude(pk=self.pk).exists()

            if not hay_otras_reservas:
                nuevo_estado = RoomStatus.LIBRE

        if nuevo_estado != room.estado:
            room.estado = nuevo_estado
            room.save(update_fields=["estado"])

    # ---------- Cambio de estado ----------

    def mark_confirmed(self):
        """Marca la reserva como confirmada (habitación queda RESERVADA)."""
        self.status = self.Status.CONFIRMED
        self.save()

    def mark_checked_in(self):
        """Marca la reserva como con check-in (habitación queda OCUPADA)."""
        self.status = self.Status.CHECKED_IN
        self.save()

    def mark_checked_out(self):
        """Marca la reserva como finalizada (habitación vuelve a LIBRE si no hay más reservas)."""
        self.status = self.Status.CHECKED_OUT
        self.save()

    def mark_cancelled(self):
        """Marca la reserva como cancelada (habitación vuelve a LIBRE si no hay más reservas)."""
        self.status = self.Status.CANCELLED
        self.save()


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
