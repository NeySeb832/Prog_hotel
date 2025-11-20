from django.shortcuts import render

# Create your views here.
# clientes/views.py
# -*- coding: utf-8 -*-
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View

from reservas.models import Reservation

User = get_user_model()


def _base_queryset():
    """
    Devuelve el queryset base de clientes:
    - Solo usuarios con rol CLIENT (si el modelo lo soporta)
    """
    qs = User.objects.all()
    # Si el modelo tiene atributo "Roles", filtramos solo clientes
    if hasattr(User, "Roles"):
        try:
            cliente_role = User.Roles.CLIENT
            qs = qs.filter(role=cliente_role)
        except Exception:
            pass
    return qs


class ClientesListView(LoginRequiredMixin, View):
    """
    Listado y filtros de clientes.
    Muestra información resumida de reservas (totales y activas).
    """
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        qs = _base_queryset()

        # Búsqueda y filtros
        q = (request.GET.get("q") or "").strip()
        estado_reservas = (request.GET.get("estado_reservas") or "").strip()  # "", "con", "sin"
        estado_usuario = (request.GET.get("estado_usuario") or "").strip()    # "", "activos", "inactivos"

        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(username__icontains=q) |
                Q(email__icontains=q)
            )

        # Anotaciones de reservas
        qs = qs.annotate(
            total_reservas=Count("reservas", distinct=True),
            reservas_activas=Count(
                "reservas",
                filter=Q(
                    reservas__status__in=[
                        Reservation.Status.PENDING,
                        Reservation.Status.CONFIRMED,
                        Reservation.Status.CHECKED_IN,
                    ]
                ),
                distinct=True,
            ),
        )

        # Filtro por estado de reservas
        if estado_reservas == "con":
            qs = qs.filter(reservas_activas__gt=0)
        elif estado_reservas == "sin":
            qs = qs.filter(reservas_activas=0)

        # Filtro por estado del usuario
        if estado_usuario == "activos":
            qs = qs.filter(is_active=True)
        elif estado_usuario == "inactivos":
            qs = qs.filter(is_active=False)

        qs = qs.order_by("first_name", "last_name", "username")

        # KPIs sobre el conjunto filtrado
        kpis = {
            "total": qs.count(),
            "con_reservas": qs.filter(reservas_activas__gt=0).count(),
            "sin_reservas": qs.filter(reservas_activas=0).count(),
            "inactivos": qs.filter(is_active=False).count(),
        }

        context = {
            "clientes": qs,
            "kpis": kpis,
            "filtros": {
                "q": q,
                "estado_reservas": estado_reservas,
                "estado_usuario": estado_usuario,
            },
            "active_menu": "clientes",
        }
        return render(request, "clientes/lista_clientes.html", context)


class ClienteDetailView(LoginRequiredMixin, View):
    """
    Muestra la ficha completa del cliente y sus reservas.
    """
    login_url = "/login/"

    def get(self, request, pk, *args, **kwargs):
        cliente = get_object_or_404(_base_queryset(), pk=pk)

        reservas_qs = (
            cliente.reservas
            .select_related("room")
            .order_by("-check_in", "-created_at")
        )

        reservas_activas = reservas_qs.filter(
            status__in=[
                Reservation.Status.PENDING,
                Reservation.Status.CONFIRMED,
                Reservation.Status.CHECKED_IN,
            ]
        )

        context = {
            "cliente": cliente,
            "reservas": reservas_qs,
            "reservas_activas": reservas_activas,
            "active_menu": "clientes",
        }
        return render(request, "clientes/detalle_cliente.html", context)


class ClienteCreateView(LoginRequiredMixin, View):
    """
    Crea un nuevo cliente (usuario con rol CLIENT).
    """
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        context = {
            "modo": "crear",
            "active_menu": "clientes",
        }
        return render(request, "clientes/editar_cliente.html", context)

    def post(self, request, *args, **kwargs):
        username = (request.POST.get("username") or "").strip()
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        password = (request.POST.get("password") or "").strip()
        is_active = bool(request.POST.get("is_active") or "on")

        if not username:
            return render(
                request,
                "clientes/editar_cliente.html",
                {
                    "modo": "crear",
                    "error": "El nombre de usuario es obligatorio.",
                    "form_data": {
                        "username": username,
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "is_active": is_active,
                    },
                    "active_menu": "clientes",
                },
            )

        cliente = User(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            is_active=is_active,
        )

        # Rol CLIENT si existe
        if hasattr(User, "Roles"):
            try:
                cliente.role = User.Roles.CLIENT
            except Exception:
                pass

        # Si se especifica contraseña, la fijamos; si no, queda sin contraseña usable
        if password:
            cliente.set_password(password)
        else:
            cliente.set_unusable_password()

        cliente.save()

        return redirect("clientes:lista")


class ClienteUpdateView(LoginRequiredMixin, View):
    """
    Edita los datos básicos del cliente.
    """
    login_url = "/login/"

    def get(self, request, pk, *args, **kwargs):
        cliente = get_object_or_404(_base_queryset(), pk=pk)

        context = {
            "modo": "editar",
            "cliente": cliente,
            "active_menu": "clientes",
        }
        return render(request, "clientes/editar_cliente.html", context)

    def post(self, request, pk, *args, **kwargs):
        cliente = get_object_or_404(_base_queryset(), pk=pk)

        username = (request.POST.get("username") or "").strip()
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        password = (request.POST.get("password") or "").strip()
        is_active = bool(request.POST.get("is_active") or "on")

        if not username:
            return render(
                request,
                "clientes/editar_cliente.html",
                {
                    "modo": "editar",
                    "cliente": cliente,
                    "error": "El nombre de usuario es obligatorio.",
                    "active_menu": "clientes",
                },
            )

        cliente.username = username
        cliente.first_name = first_name
        cliente.last_name = last_name
        cliente.email = email
        cliente.is_active = is_active

        if password:
            cliente.set_password(password)

        cliente.save()

        return redirect("clientes:detalle", pk=cliente.pk)


class ClienteDeleteView(LoginRequiredMixin, View):
    """
    Confirma y elimina un cliente.
    Dado que Reservation.guest tiene on_delete=SET_NULL,
    las reservas históricas no se pierden.
    """
    login_url = "/login/"

    def get(self, request, pk, *args, **kwargs):
        cliente = get_object_or_404(_base_queryset(), pk=pk)
        context = {
            "cliente": cliente,
            "active_menu": "clientes",
        }
        return render(request, "clientes/confirmar_eliminar_cliente.html", context)

    def post(self, request, pk, *args, **kwargs):
        cliente = get_object_or_404(_base_queryset(), pk=pk)
        cliente.delete()
        return redirect("clientes:lista")
