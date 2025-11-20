# accounts/permissions.py
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator

from .utils import user_has_role, ROLE_ADMIN_HOTEL, ROLE_CLIENT

def _role_required(required_role: str):
    def predicate(user):
        return user.is_authenticated and user_has_role(user, required_role)
    # Redirige a login si no está autenticado o no cumple el rol
    return user_passes_test(predicate, login_url="accounts:login")

# Decoradores listos para usar en views (función o clase con method_decorator)
admin_required = _role_required(ROLE_ADMIN_HOTEL)
client_required = _role_required(ROLE_CLIENT)

# (Opcional) Mixins si los necesitas en CBVs
class AdminRequiredMixin:
    @method_decorator(admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

class ClientRequiredMixin:
    @method_decorator(client_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
