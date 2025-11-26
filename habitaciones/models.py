from django.db import models
from django.utils import timezone


class RoomStatus(models.TextChoices):
    LIBRE = "LIBRE", "Libre"
    RESERVADA = "RESERVADA", "Reservada"
    OCUPADA = "OCUPADA", "Ocupada"
    MANTENIMIENTO = "MANTENIMIENTO", "Mantenimiento"
    BLOQUEADA = "BLOQUEADA", "Bloqueada"  # fuera de servicio / bloqueada


class TipoHabitacion(models.Model):
    """
    Catálogo gestionado desde Django admin.
    Define las características 'base' de un tipo de habitación.
    Todas las habitaciones de este tipo heredan estos valores.
    """

    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True)
    capacidad_por_defecto = models.PositiveIntegerField(default=2)
    camas_por_defecto = models.PositiveIntegerField(default=1)
    precio_base = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Tipo de habitación"
        verbose_name_plural = "Tipos de habitación"

    def __str__(self):
        return self.nombre


class Habitacion(models.Model):
    """
    Modelo principal de habitaciones.

    Nota:
    - Capacidad, camas y precio_noche NO son campos editables aquí.
      Se obtienen siempre desde el TipoHabitacion asociado.
    """

    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=80, blank=True)

    tipo = models.ForeignKey(
        TipoHabitacion,
        on_delete=models.PROTECT,
        related_name="habitaciones",
    )

    estado = models.CharField(
        max_length=20,
        choices=RoomStatus.choices,
        default=RoomStatus.LIBRE,
        db_index=True,
    )

    piso = models.PositiveIntegerField(default=1)

    # Otros datos específicos de la habitación
    amenities = models.JSONField(default=list, blank=True)
    foto = models.ImageField(upload_to="habitaciones/", blank=True, null=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["piso", "codigo"]

    def __str__(self):
        if self.nombre:
            return f"{self.codigo} - {self.nombre}"
        return f"{self.codigo} ({self.tipo.nombre})"

    # ---- Propiedades derivadas del tipo ----

    @property
    def capacidad(self) -> int:
        """Capacidad derivada del tipo de habitación."""
        return self.tipo.capacidad_por_defecto

    @property
    def camas(self) -> int:
        """Número de camas derivado del tipo de habitación."""
        return self.tipo.camas_por_defecto

    @property
    def precio_noche(self):
        """Precio/noche derivado del tipo de habitación."""
        return self.tipo.precio_base

    @property
    def css_estado(self):
        """
        Ayuda opcional para mapear el estado a clases CSS.
        (No es obligatorio usarla en la plantilla.)
        """
        return {
            "LIBRE": "estado-libre",
            "RESERVADA": "estado-reservada",
            "OCUPADA": "estado-ocupada",
            "MANTENIMIENTO": "estado-mantenimiento",
            "BLOQUEADA": "estado-bloqueada",
        }.get(self.estado, "")

    # ---------- Lógica de reservas asociadas ----------

    def _compute_reservas_cache(self):
        """
        Calcula y cachea:
        - current_reservation: reserva ACTIVA hoy (o la más reciente si la
          habitación figura OCUPADA pero no hay rango exacto).
        - next_reservation: próxima reserva futura para la habitación.
        """
        from reservas.models import Reservation  # import local para evitar ciclos

        hoy = timezone.localdate()

        # Estados de reserva que bloquean la hab
        estados_bloqueo = [
            Reservation.Status.PENDING,
            Reservation.Status.CONFIRMED,
            Reservation.Status.CHECKED_IN,
        ]

        qs = (
            self.reservas
            .filter(status__in=estados_bloqueo)
            .order_by("check_in")
        )

        # 1) Reserva en curso: hoy dentro del rango [check_in, check_out)
        current = (
            qs.filter(check_in__lte=hoy, check_out__gt=hoy)
            .order_by("check_in")
            .first()
        )

        # Fallback: si la hab está marcada OCUPADA pero no hay rango exacto,
        # tomamos la última que haya empezado.
        if current is None and self.estado == RoomStatus.OCUPADA:
            current = (
                qs.filter(check_in__lte=hoy)
                .order_by("-check_in")
                .first()
            )

        # 2) Próxima reserva futura (excluyendo la actual si existe)
        next_qs = qs.filter(check_in__gte=hoy)
        if current is not None:
            next_qs = next_qs.exclude(pk=current.pk)
        next_res = next_qs.order_by("check_in").first()

        self._current_reservation_cache = current
        self._next_reservation_cache = next_res

    @property
    def current_reservation(self):
        """
        Reserva actualmente vigente para la habitación (si hay).

        IMPORTANTE:
        - Si la vista puso current_reservation = None, volvemos a calcular
          desde la BD para evitar el "Sin reservas asociadas" cuando sí hay
          una reserva válida.
        """
        if (
            not hasattr(self, "_current_reservation_cache")
            or self._current_reservation_cache is None
        ):
            self._compute_reservas_cache()
        return getattr(self, "_current_reservation_cache", None)

    @current_reservation.setter
    def current_reservation(self, value):
        """
        Setter usado por la vista si quiere inyectar la reserva ya prefetchada
        (pero si es None, el getter recalculará igualmente).
        """
        self._current_reservation_cache = value

    @property
    def next_reservation(self):
        """
        Próxima reserva futura (si existe).
        """
        if (
            not hasattr(self, "_next_reservation_cache")
            or self._next_reservation_cache is None
        ):
            self._compute_reservas_cache()
        return getattr(self, "_next_reservation_cache", None)

    @next_reservation.setter
    def next_reservation(self, value):
        self._next_reservation_cache = value
