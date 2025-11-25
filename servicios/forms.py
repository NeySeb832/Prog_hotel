from django import forms

from .models import Servicio, ConsumoServicio, PagoConsumo


class ServicioForm(forms.ModelForm):
    class Meta:
        model = Servicio
        fields = ["nombre", "categoria", "descripcion", "precio_base", "activo"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "descripcion": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "precio_base": forms.NumberInput(attrs={"class": "form-control"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ConsumoServicioForm(forms.ModelForm):
    class Meta:
        model = ConsumoServicio
        fields = [
            "reserva",
            "servicio",
            "cantidad",
            "precio_unitario",
            "estado",
            "notas",
        ]
        widgets = {
            "reserva": forms.Select(attrs={"class": "form-select"}),
            "servicio": forms.Select(attrs={"class": "form-select"}),
            "cantidad": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
            "precio_unitario": forms.NumberInput(
                attrs={"class": "form-control"}
            ),
            "estado": forms.Select(attrs={"class": "form-select"}),
            "notas": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
        }


class PagoConsumoForm(forms.ModelForm):
    class Meta:
        model = PagoConsumo
        fields = ["amount", "method", "reference", "notes"]
        widgets = {
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "step": "0.01",
                }
            ),
            "method": forms.Select(attrs={"class": "form-select"}),
            "reference": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
        }
