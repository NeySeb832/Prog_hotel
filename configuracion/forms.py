from django import forms
from .models import ConfiguracionGeneral


class ConfiguracionGeneralForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionGeneral
        fields = [
            "hotel_nombre",
            "hotel_eslogan",
            "hotel_email",
            "hotel_telefono",
            "hotel_direccion",
            "moneda",
            "zona_horaria",
            "hora_checkin",
            "hora_checkout",
            "iva_porcentaje",
            "cargo_servicio_porcentaje",
            "permitir_overbooking",
            "horas_min_cancelacion_sin_penalidad",
        ]
        widgets = {
            "hora_checkin": forms.TimeInput(attrs={"type": "time"}),
            "hora_checkout": forms.TimeInput(attrs={"type": "time"}),
        }
