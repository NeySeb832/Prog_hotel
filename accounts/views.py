from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

from .utils import redirect_by_role, _is_admin

User = get_user_model()

@method_decorator(csrf_protect, name="dispatch")
class CustomLoginView(View):
    template_name = "accounts/login.html"

    def get(self, request, *args, **kwargs):
        # Siempre mostrar el formulario, aunque haya sesión (para poder cambiar de usuario)
        return render(request, self.template_name, {"next": request.GET.get("next", "")})

    def post(self, request, *args, **kwargs):
        identifier = (request.POST.get("username") or request.POST.get("email") or "").strip()
        password   = (request.POST.get("password") or "").strip()

        user = authenticate(request, username=identifier, password=password)
        if user is None and "@" in identifier:
            try:
                u = User.objects.get(email__iexact=identifier)
                user = authenticate(request, username=u.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is None:
            messages.error(request, "Credenciales inválidas.")
            return render(request, self.template_name, {"next": request.POST.get("next", "")}, status=200)

        if not user.is_active:
            messages.error(request, "Tu cuenta está inactiva.")
            return render(request, self.template_name, {"next": request.POST.get("next", "")}, status=200)

        login(request, user)

        next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()

        # Admin/staff: respeta ?next= (interno) si viene, sino mándalo a su dashboard
        if _is_admin(user):
            if next_url.startswith("/"):
                return redirect(next_url)
            return redirect_by_role(user)

        # Cliente: SIEMPRE al portal del cliente (ignoramos next para evitar saltos al admin)
        return redirect_by_role(user)

class RegisterPageView(View):
    template_name = "accounts/registro.html"
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)

class ClientPortalView(LoginRequiredMixin, View):
    login_url = "accounts:login"
    template_name = "accounts/portal_cliente.html"

    def get(self, request, *args, **kwargs):
        # Contexto mínimo para que renderice; ajusta con tus modelos reales
        reservas = []
        estancia_actual = None
        noches_totales = 0
        solicitudes_servicio = []

        urls = {
            "dashboard_home": reverse("dashboard:home"),
            "mis_reservas":   "/reservas/mis/",
            "mis_reservas_nueva": "/reservas/mis/nueva/",
            "logout":         reverse("accounts:logout"),
        }

        ctx = dict(
            reservas=reservas,
            estancia_actual=estancia_actual,
            noches_totales=noches_totales,
            solicitudes_servicio=solicitudes_servicio,
            urls=urls,
        )
        return render(request, self.template_name, ctx)

def logout_view(request):
    logout(request)
    return redirect("/")
