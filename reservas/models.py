from django.conf import settings
from django.db import models

# ---------- Catálogos ----------
class RoomType(models.Model):
    name = models.CharField(max_length=80, unique=True)
    capacity_adults = models.PositiveIntegerField(default=2)
    capacity_children = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Room(models.Model):
    STATUS = [
        ("AVAILABLE", "Disponible"),
        ("OCCUPIED", "Ocupada"),
        ("MAINTENANCE", "Mantenimiento"),
        ("BLOCKED", "Bloqueada"),
    ]
    number = models.CharField(max_length=10, unique=True)
    floor = models.IntegerField(default=1)
    room_type = models.ForeignKey(RoomType, on_delete=models.PROTECT, related_name="rooms")
    base_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=12, choices=STATUS, default="AVAILABLE")

    def __str__(self):
        return f"{self.number} ({self.room_type})"

# ---------- Núcleo de reservas ----------
class Reservation(models.Model):
    STATUS = [
        ("BOOKED", "Reservada"),
        ("CHECKED_IN", "Check-In"),
        ("CHECKED_OUT", "Check-Out"),
        ("CANCELLED", "Cancelada"),
    ]
    # Dueño para "Mis reservas" (cliente). Admin verá todas
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reservations"
    )
    code = models.CharField(max_length=20, unique=True)  # folio/código
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="reservations")
    check_in = models.DateField()
    check_out = models.DateField()
    pax_adults = models.PositiveIntegerField(default=1)
    pax_children = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, choices=STATUS, default="BOOKED")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.code} - {self.room}"

class Payment(models.Model):
    METHOD = [
        ("CASH", "Efectivo"),
        ("CARD", "Tarjeta"),
        ("TRANSFER", "Transferencia"),
    ]
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=10, choices=METHOD, default="CASH")
    reference = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"${self.amount} - {self.reservation.code}"
