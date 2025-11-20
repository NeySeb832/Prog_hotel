# reservas/urls.py
from django.urls import path

from .views import (
    ReservationsListView,
    ReservationCreateView,
    ReservationUpdateView,
    ReservationStatusActionView,
    PaymentCreateView,
    PaymentInvoicePDFView,
)

app_name = "reservas"

urlpatterns = [
    # Módulo de reservas (admin)
    path("", ReservationsListView.as_view(), name="lista"),
    path("api/crear/", ReservationCreateView.as_view(), name="api_crear"),
    path("<int:pk>/editar/", ReservationUpdateView.as_view(), name="api_editar"),
    path("<int:pk>/estado/", ReservationStatusActionView.as_view(), name="api_estado"),

    # Pagos
    path("<int:pk>/pago/", PaymentCreateView.as_view(), name="api_pago"),
    path("pago/<int:pk>/factura/", PaymentInvoicePDFView.as_view(), name="pago_factura"),
]
