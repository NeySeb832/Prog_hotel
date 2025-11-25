from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect

from .models import ConfiguracionGeneral
from .forms import ConfiguracionGeneralForm


class ConfiguracionGeneralView(LoginRequiredMixin, View):
    """
    Pantalla única de configuración general del sistema.
    """
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        config = ConfiguracionGeneral.get_solo()
        form = ConfiguracionGeneralForm(instance=config)
        context = {
            "form": form,
            "config": config,
            "guardado": False,
            "active_menu": "configuracion",
        }
        return render(request, "configuracion/configuracion_general.html", context)

    def post(self, request, *args, **kwargs):
        config = ConfiguracionGeneral.get_solo()
        form = ConfiguracionGeneralForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            context = {
                "form": form,
                "config": config,
                "guardado": True,
                "active_menu": "configuracion",
            }
            return render(request, "configuracion/configuracion_general.html", context)
        else:
            context = {
                "form": form,
                "config": config,
                "guardado": False,
                "active_menu": "configuracion",
            }
            return render(request, "configuracion/configuracion_general.html", context)
