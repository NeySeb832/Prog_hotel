from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from decimal import Decimal
from django.utils import timezone
from reservas.models import Reservation
from servicios.models import ConsumoServicio

from .utils import redirect_by_role, _is_admin

User = get_user_model()


@method_decorator(csrf_protect, name="dispatch")
class CustomLoginView(View):
    template_name = "accounts/login.html"

    def get(self, request, *args, **kwargs):
        # Siempre mostrar el formulario, aunque haya sesión (para poder cambiar de usuario)
        return render(request, self.template_name, {"next": request.GET.get("next", "")})

    def post(self, request, *args, **kwargs):
        # El formulario puede enviar username o email. Probamos ambos.
        identifier = (request.POST.get("username") or request.POST.get("email") or "").strip()
        password = (request.POST.get("password") or "").strip()

        user = authenticate(request, username=identifier, password=password)

        # Si pusieron email, probamos a buscar por email y autenticar con su username real
        if user is None and "@" in identifier:
            try:
                u = User.objects.get(email__iexact=identifier)
                user = authenticate(request, username=u.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is None:
            messages.error(request, "Credenciales inválidas.")
            return render(
                request,
                self.template_name,
                {"next": request.POST.get("next", "")},
                status=200,
            )

        if not user.is_active:
            messages.error(request, "Tu cuenta está inactiva.")
            return render(
                request,
                self.template_name,
                {"next": request.POST.get("next", "")},
                status=200,
            )

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
        # Si ya está autenticado, lo enviamos a donde le corresponde
        if request.user.is_authenticated:
            return redirect_by_role(request.user)
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect_by_role(request.user)

        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        password = (request.POST.get("password") or "").strip()
        password2 = (request.POST.get("password2") or "").strip()
        terms = request.POST.get("terms")

        errors = []

        if not first_name:
            errors.append("Debes ingresar tu nombre.")
        if not last_name:
            errors.append("Debes ingresar tu apellido.")
        if not email:
            errors.append("Debes ingresar un email válido.")
        if password != password2:
            errors.append("Las contraseñas no coinciden.")
        if len(password) < 8:
            errors.append("La contraseña debe tener al menos 8 caracteres.")
        if not terms:
            errors.append("Debes aceptar los términos y condiciones.")

        # Email duplicado
        if email and User.objects.filter(email__iexact=email).exists():
            errors.append("Ya existe una cuenta registrada con ese email.")

        if errors:
            for e in errors:
                messages.error(request, e)
            # Volvemos a mostrar el formulario, manteniendo algunos valores
            ctx = {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
            }
            return render(request, self.template_name, ctx, status=200)

        # Generar un username a partir del email (único)
        base_username = (email.split("@")[0] or "usuario").replace(" ", "").lower()
        username = base_username
        i = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{i}"
            i += 1

        # Crear usuario cliente
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        # Aseguramos rol CLIENT por defecto
        if hasattr(user, "role"):
            try:
                # Si el modelo tiene TextChoices Roles
                user.role = getattr(user.__class__.Roles, "CLIENT", "CLIENT")
            except Exception:
                user.role = "CLIENT"
            user.save()

        messages.success(request, "Tu cuenta se creó correctamente. Ahora puedes iniciar sesión.")
        return redirect("accounts:login")


class ClientPortalView(LoginRequiredMixin, View):
    login_url = "accounts:login"
    template_name = "accounts/portal_cliente.html"

    def get(self, request, *args, **kwargs):
        user = request.user

        # Todas las reservas del usuario
        reservas_qs = (
            Reservation.objects
            .select_related("room", "room__tipo")
            .filter(guest=user)
            .order_by("-created_at")
        )

        reservas_list = list(reservas_qs)
        reservas_recientes = reservas_list[:5]
        reservas_total = len(reservas_list)

        # Noches totales
        noches_totales = sum((r.nights or 0) for r in reservas_list)

        # Estancia actual o próxima (check-in/confirmada/pendiente con fecha >= hoy)
        hoy = timezone.localdate()
        estancia_actual = (
            reservas_qs
            .filter(
                status__in=[
                    Reservation.Status.CHECKED_IN,
                    Reservation.Status.CONFIRMED,
                    Reservation.Status.PENDING,
                ],
                check_out__gte=hoy,
            )
            .order_by("check_in")
            .first()
        )

        # Servicios consumidos por el usuario (últimos 5)
        solicitudes_servicio = (
            ConsumoServicio.objects
            .select_related("servicio", "reserva", "reserva__room")
            .filter(reserva__guest=user)
            .order_by("-creado_en")[:5]
        )

        # Totales de dinero aproximados (reservas)
        total_estimado = Decimal("0.00")
        saldo_pendiente = Decimal("0.00")
        for r in reservas_list:
            total_estimado += Decimal(str(r.total_amount or 0))
            saldo_pendiente += Decimal(str(r.pending_amount or 0))

        urls = {
            "dashboard_home": reverse("accounts:portal_cliente"),
            "mis_reservas": reverse("reservas:mis_reservas"),
            "mis_reservas_nueva": reverse("reservas:nueva"),
            "room_service": reverse("reservas:room_service"),  # si quieres luego lo cambiamos
            "otros_servicios": reverse("servicios:cliente_mis_servicios"),
            "logout": reverse("accounts:logout"),
        }

        ctx = dict(
            reservas=reservas_recientes,
            reservas_total=reservas_total,
            estancia_actual=estancia_actual,
            noches_totales=noches_totales,
            solicitudes_servicio=solicitudes_servicio,
            total_estimado=total_estimado,
            saldo_pendiente=saldo_pendiente,
            urls=urls,
        )
        return render(request, self.template_name, ctx)


def logout_view(request):
    logout(request)
    return redirect("/")
