from django.db import models
from datetime import time


class ConfiguracionGeneral(models.Model):
    MONEDAS = [
        ("COP", "Peso colombiano (COP)"),
        ("USD", "Dólar estadounidense (USD)"),
        ("EUR", "Euro (EUR)"),
    ]

    hotel_nombre = models.CharField("Nombre del hotel", max_length=150, default="Hotel sin nombre")
    hotel_eslogan = models.CharField("Eslogan", max_length=200, blank=True)
    hotel_email = models.EmailField("Correo de contacto", blank=True)
    hotel_telefono = models.CharField("Teléfono", max_length=50, blank=True)
    hotel_direccion = models.CharField("Dirección", max_length=255, blank=True)

    moneda = models.CharField("Moneda por defecto", max_length=3, choices=MONEDAS, default="COP")
    zona_horaria = models.CharField("Zona horaria", max_length=50, default="America/Bogota")

    hora_checkin = models.TimeField("Hora estándar de check-in", default=time(15, 0))
    hora_checkout = models.TimeField("Hora estándar de check-out", default=time(12, 0))

    iva_porcentaje = models.DecimalField("IVA (%)", max_digits=5, decimal_places=2, default=19.00)
    cargo_servicio_porcentaje = models.DecimalField(
        "Cargo por servicio (%)",
        max_digits=5,
        decimal_places=2,
        default=0.00,
    )

    permitir_overbooking = models.BooleanField(
        "Permitir overbooking",
        default=False,
        help_text="Si está activo, se pueden confirmar reservas aunque la ocupación esté al límite.",
    )

    horas_min_cancelacion_sin_penalidad = models.PositiveIntegerField(
        "Horas mínimas para cancelar sin penalización",
        default=24,
        help_text="Horas antes del check-in en las que se puede cancelar sin aplicar penalidades.",
    )

    creado_el = models.DateTimeField(auto_now_add=True)
    actualizado_el = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración general"
        verbose_name_plural = "Configuración general"

    def __str__(self):
        return "Configuración general del sistema"

    @classmethod
    def get_solo(cls):
        """
        Devuelve la única instancia de configuración (la crea si no existe).
        """
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
