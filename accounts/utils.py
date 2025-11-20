from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch

ROLE_ADMIN_HOTEL = "ADMIN"
ROLE_CLIENT = "CLIENT"

def _safe(name: str, default: str = "/"):
    try:
        return reverse(name)
    except NoReverseMatch:
        return default

def _is_admin(user) -> bool:
    role = (getattr(user, "role", "") or "").upper()
    return bool(
        getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
        or role in {"ADMIN", "GERENTE", "MANAGER", "STAFF"}
    )

def redirect_by_role(user):
    if _is_admin(user):
        return redirect(_safe("admin_hotel:dashboard", "/admin_hotel/"))
    return redirect(_safe("accounts:portal_cliente", "/mi-portal/"))
