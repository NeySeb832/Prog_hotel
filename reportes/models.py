from django.db import models
from django.conf import settings


class ReportePDF(models.Model):
    class Tipo(models.TextChoices):
        DIARIO = "DIARIO", "Diario"
        SEMANAL = "SEMANAL", "Semanal"
        MENSUAL = "MENSUAL", "Mensual"
        ANUAL = "ANUAL", "Anual"
        PERSONALIZADO = "PERSONALIZADO", "Personalizado"

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    creado_el = models.DateTimeField(auto_now_add=True)

    archivo = models.FileField(upload_to="reportes/", max_length=255)

    total_reservas = models.IntegerField(default=0)
    ingresos_totales = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reportes_generados",
    )

    def __str__(self):
        return f"{self.get_tipo_display()} ({self.fecha_inicio} -> {self.fecha_fin})"
