# accounts/utils.py
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

# === Constantes de roles ===
# Según tu BD (captura), el rol que usas para administradores del hotel es "ADMIN"
ROLE_ADMIN_HOTEL = "ADMIN"
ROLE_CLIENT = "CLIENT"

# === Helpers de rol ===
def get_user_role(user) -> str | None:
    """
    Retorna el rol en MAYÚSCULAS o None si no existe.
    Se asume que el modelo User tiene un campo 'role'.
    """
    if not user or not hasattr(user, "role"):
        return None
    value = (user.role or "").strip().upper()
    return value or None

def user_has_role(user, role: str) -> bool:
    """True si el usuario tiene exactamente el rol indicado (case-insensitive)."""
    if not user or not user.is_authenticated:
        return False
    current = get_user_role(user)
    return current == (role or "").upper()

def _reverse_or_default(url_name: str, default: str = "/") -> str:
    """Intenta hacer reverse(url_name). Si falla, retorna 'default'."""
    try:
        return reverse(url_name)
    except Exception:
        return default

# === Redirección por rol ===
def get_redirect_url_for(user) -> str:
    """
    Devuelve la URL destino según el rol del usuario.
    Ajusta los namespaces a los que ya tienes montados.
    """
    role = get_user_role(user)
    mapping = {
        ROLE_ADMIN_HOTEL: "admin_hotel:admin_dashboard",  # panel admin del hotel
        ROLE_CLIENT:      "clientpanel:index",            # cuando exista
    }
    url_name = mapping.get(role)
    if not url_name:
        # Fallback por si el rol no está definido o falta el namespace de cliente
        return getattr(settings, "LOGIN_REDIRECT_URL", "/")
    return _reverse_or_default(url_name, default=getattr(settings, "LOGIN_REDIRECT_URL", "/"))

def redirect_by_role(user):
    """Atajo para hacer redirect según el rol."""
    return redirect(get_redirect_url_for(user))

# ---------- Aliases de compatibilidad ----------
def destination_for(user):
    """Compat con código viejo que usaba 'destination_for'."""
    return get_redirect_url_for(user)

def set_client_role(user, save: bool = False):
    """
    Utilidad opcional: establece rol CLIENT al usuario si necesitas usarla en tests/fixtures.
    (La dejé por si en algún otro archivo la importan.)
    """
    if not hasattr(user, "role"):
        return
    user.role = ROLE_CLIENT
    if save:
        user.save(update_fields=["role"])
