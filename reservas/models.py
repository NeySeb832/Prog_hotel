from django.conf import settings
from django.db import models
from django.utils import timezone


User = settings.AUTH_USER_MODEL

class RoomType(models.Model):
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    capacity = models.PositiveIntegerField(default=1)
    nightly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Tipo de habitación"
        verbose_name_plural = "Tipos de habitación"

    def __str__(self):
        return f"{self.name} (${self.nightly_rate}/noche)"


class Room(models.Model):
    number = models.CharField(max_length=10, unique=True)
    room_type = models.ForeignKey(RoomType, on_delete=models.PROTECT, related_name="rooms")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"{self.number} · {self.room_type.name}"


class Reservation(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "pendiente"
        CONFIRMED = "CONFIRMED", "confirmada"
        CANCELLED = "CANCELLED", "cancelada"
        CHECKED_IN = "CHECKED_IN", "check-in"
        CHECKED_OUT = "CHECKED_OUT", "check-out"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "pendiente"
        PAID = "PAID", "pagado"
        REFUNDED = "REFUNDED", "reembolsado"

    code = models.CharField(max_length=20, unique=True, editable=False)
    client = models.ForeignKey(User, on_delete=models.PROTECT, related_name="reservations")
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="reservations")
    check_in = models.DateField()
    check_out = models.DateField()
    guests = models.PositiveIntegerField(default=1)

    nightly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    taxes = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    @property
    def nights(self):
        return (self.check_out - self.check_in).days

    def recalc(self, tax_rate=0.10):
        self.subtotal = self.nightly_rate * self.nights
        self.taxes = self.subtotal * tax_rate
        self.total = self.subtotal + self.taxes

    def save(self, *args, **kwargs):
        if not self.code:
            # RES-001 estilo
            last = Reservation.objects.order_by("-id").first()
            seq = (last.id + 1) if last else 1
            self.code = f"RES-{seq:03d}"
        if not self.nightly_rate:
            self.nightly_rate = self.room.room_type.nightly_rate
        self.recalc()
        super().save(*args, **kwargs)


class Payment(models.Model):
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(default=timezone.now)
    reference = models.CharField(max_length=100, blank=True)
