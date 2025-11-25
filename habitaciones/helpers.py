# habitaciones/models.py
from django.db import models
from django.utils import timezone

# ... tu código existente ...

class Habitacion(models.Model):
    # tus campos actuales...
    # codigo, piso, tipo, estado, etc.

    # --- helpers de reservas asociadas ---

    @property
    def reservas_activas(self):
        """
        Reservas que bloquean esta habitación (hoy o a futuro cercano).
        Incluye pendientes, confirmadas y con check-in, cuyo check_out
        es hoy o una fecha posterior.
        """
        from reservas.models import Reservation  # import local para evitar ciclo
        hoy = timezone.localdate()

        return (
            self.reservas  # related_name="reservas" en Reservation.room
            .filter(
                status__in=[
                    Reservation.Status.PENDING,
                    Reservation.Status.CONFIRMED,
                    Reservation.Status.CHECKED_IN,
                ],
                check_out__gte=hoy,
            )
            .order_by("check_in")
        )

    @property
    def reserva_actual(self):
        """
        Reserva que está usando la habitación en este momento
        (check_in <= hoy < check_out y estado CHECKED_IN o CONFIRMED).
        """
        from reservas.models import Reservation
        hoy = timezone.localdate()

        return (
            self.reservas
            .filter(
                status__in=[
                    Reservation.Status.CONFIRMED,
                    Reservation.Status.CHECKED_IN,
                ],
                check_in__lte=hoy,
                check_out__gt=hoy,
            )
            .order_by("check_in")
            .first()
        )

    @property
    def proxima_reserva(self):
        """
        Próxima reserva futura (después de hoy) para esta habitación.
        """
        from reservas.models import Reservation
        hoy = timezone.localdate()

        return (
            self.reservas
            .filter(
                status__in=[
                    Reservation.Status.PENDING,
                    Reservation.Status.CONFIRMED,
                ],
                check_in__gt=hoy,
            )
            .order_by("check_in")
            .first()
        )
