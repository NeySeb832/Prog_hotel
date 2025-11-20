from django.db import models


class RoomStatus(models.TextChoices):
    LIBRE = "LIBRE", "Libre"
    RESERVADA = "RESERVADA", "Reservada"
    OCUPADA = "OCUPADA", "Ocupada"
    MANTENIMIENTO = "MANTENIMIENTO", "Mantenimiento"
    BLOQUEADA = "BLOQUEADA", "Bloqueada"


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
