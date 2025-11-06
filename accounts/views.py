# accounts/views.py
from datetime import date
import re
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from .utils import redirect_by_role
from reservas.models import Reservation  # para el portal de cliente

User = get_user_model()


# ---------------------------
# Helpers
# ---------------------------
def _unique_username(base: str) -> str:
    """
    Genera un username único y limpio a partir de 'base'.
    """
    base = (base or "").strip().lower()
    base = re.sub(r"[^a-z0-9._-]+", "", base.replace(" ", "_"))
    if not base:
        base = "user"
    candidate = base
    i = 1
    while User.objects.filter(username__iexact=candidate).exists():
        i += 1
        candidate = f"{base}{i}"
    return candidate


# ---------------------------
# Login
# ---------------------------
@method_decorator(csrf_protect, name="dispatch")
class CustomLoginView(View):
    template_name = "accounts/login.html"

    def get(self, request, *args, **kwargs):
        # Mostrar SIEMPRE el formulario de login, incluso si ya está autenticado
        # (permite cambiar de usuario sin hacer logout antes)
        return render(request, self.template_name, {"next": request.GET.get("next", "")})

    def post(self, request, *args, **kwargs):
        username_or_email = (request.POST.get("username") or request.POST.get("email") or "").strip()
        password = (request.POST.get("password") or "").strip()
        next_url = request.POST.get("next") or request.GET.get("next")

        from django.contrib.auth import authenticate, login, get_user_model
        User = get_user_model()

        user = authenticate(request, username=username_or_email, password=password)
        if user is None and "@" in username_or_email:
            try:
                u = User.objects.get(email__iexact=username_or_email)
                user = authenticate(request, username=u.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is None:
            from django.contrib import messages
            messages.error(request, "Credenciales inválidas.")
            return render(request, self.template_name, {"next": next_url}, status=200)

        if not user.is_active:
            from django.contrib import messages
            messages.error(request, "Tu usuario está inactivo.")
            return render(request, self.template_name, {"next": next_url}, status=200)

        login(request, user)
        if next_url:
            return redirect(next_url)

        from .utils import redirect_by_role
        return redirect_by_role(user)

class RegisterPageView(View):
    template_name = "accounts/registro.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect_by_role(request.user)
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        # Mapeo flexible con los nombres del formulario que mostrabas en el mockup
        nombre    = (request.POST.get("nombre")    or request.POST.get("first_name") or "").strip()
        apellido  = (request.POST.get("apellido")  or request.POST.get("last_name")  or "").strip()

        username  = (
            request.POST.get("username")
            or request.POST.get("usuario")
            or request.POST.get("user")
            or ""
        ).strip()

        email     = (
            request.POST.get("email")
            or request.POST.get("correo")
            or request.POST.get("mail")
            or ""
        ).strip()

        password  = (request.POST.get("password")  or request.POST.get("password1") or request.POST.get("contrasena") or "").strip()
        confirm   = (request.POST.get("password2") or request.POST.get("confirm_password") or request.POST.get("confirmar") or "").strip()

        role      = (request.POST.get("role") or request.POST.get("rol") or "CLIENT").strip().upper()
        # terms = request.POST.get("terms") or request.POST.get("terminos") or request.POST.get("acepto")  # opcional

        # Validaciones mínimas
        if not email or not password:
            messages.error(request, "Completa todos los campos: usuario, email y contraseña.")
            return render(request, self.template_name, status=200)

        if password != confirm:
            messages.error(request, "Las contraseñas no coinciden.")
            return render(request, self.template_name, status=200)

        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, "Ese email ya está registrado.")
            return render(request, self.template_name, status=200)

        # Si no viene username, lo generamos
        if not username:
            base = ""
            if nombre or apellido:
                base = f"{nombre}.{apellido}".strip(".")
            if not base and "@" in email:
                base = email.split("@", 1)[0]
            username = _unique_username(base)
        else:
            # Si ya existe, buscamos uno libre
            if User.objects.filter(username__iexact=username).exists():
                username = _unique_username(username)

        # Crear usuario
        user = User.objects.create_user(username=username, email=email, password=password)

        # Guardar nombre y rol si existen en el modelo
        updates = []
        if hasattr(user, "first_name") and nombre:
            user.first_name = nombre; updates.append("first_name")
        if hasattr(user, "last_name") and apellido:
            user.last_name = apellido; updates.append("last_name")
        if hasattr(user, "role"):
            user.role = "ADMIN" if role == "ADMIN" else "CLIENT"; updates.append("role")
            if user.role == "ADMIN":
                user.is_staff = True; updates.append("is_staff")

        if updates:
            user.save(update_fields=updates)

        messages.success(request, "Cuenta creada correctamente. Ahora puedes iniciar sesión.")
        return redirect("accounts:login")


# ---------------------------
# Portal de Cliente
# ---------------------------
class ClientPortalView(LoginRequiredMixin, View):
    template_name = "accounts/portal_cliente.html"

    def get(self, request):
        user = request.user

        reservas = (Reservation.objects
                    .filter(owner=user)
                    .select_related("room", "room__room_type")
                    .order_by("-created_at"))

        hoy = date.today()
        estancia_actual = reservas.filter(check_in__lte=hoy, check_out__gte=hoy).first()
        noches_totales = sum([(r.check_out - r.check_in).days for r in reservas])

        # Placeholder de solicitudes de servicio (cámbialo por tu modelo real cuando lo tengas)
        solicitudes_servicio = [
            {"titulo": "Limpieza de habitación", "hora": "14:00", "estado": "Confirmado"},
            {"titulo": "Servicio de lavandería", "hora": "16:00", "estado": "Pendiente"},
        ]

        context = {
            "reservas": reservas,
            "estancia_actual": estancia_actual,
            "noches_totales": noches_totales,
            "solicitudes_servicio": solicitudes_servicio,
        }
        return render(request, self.template_name, context)


# ---------------------------
# Logout
# ---------------------------
def logout_view(request):
    logout(request)
    return redirect("/")
