from django.db import models
from django.utils import timezone


class Room(models.Model):
    STATUS_CHOICES = [
        ('AVAILABLE', 'Disponible'),
        ('OCCUPIED', 'Ocupada'),
        ('OOS', 'Fuera de servicio'),
    ]

    number = models.PositiveIntegerField(unique=True)
    floor = models.PositiveIntegerField(default=1)
    type = models.CharField(max_length=50, default='Estándar')
    base_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='AVAILABLE')

    def __str__(self):
        return f'Hab. {self.number} · {self.type}'


class Reservation(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pendiente'),
        ('CONFIRMED', 'Confirmada'),
        ('CANCELLED', 'Cancelada'),
        ('CHECKIN', 'Con check-in'),
        ('CHECKOUT', 'Con check-out'),
    ]

    code = models.CharField(max_length=20, unique=True)
    guest_name = models.CharField(max_length=120)
    check_in = models.DateField()
    check_out = models.DateField()
    guests = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name='reservations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.code} · {self.guest_name} ({self.check_in} → {self.check_out})'


class Payment(models.Model):
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_at = models.DateTimeField(default=timezone.now)
    method = models.CharField(max_length=30, default='efectivo')

    def __str__(self):
        return f'Pago {self.amount} · {self.reservation.code}'


class Maintenance(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='maintenances')
    reason = models.CharField(max_length=200, default='Mantenimiento')
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return f'OOS {self.room} · {self.start_date}→{self.end_date}'
