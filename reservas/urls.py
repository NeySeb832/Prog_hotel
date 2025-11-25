from django.urls import path

from .views import (
    ReservationsListView,
    ReservationCreateView,
    ReservationUpdateView,
    ReservationStatusActionView,
    PaymentCreateView,
    PaymentInvoicePDFView,
    # Vistas portal cliente
    ClientReservationsListView,
    ClientReservationCreateView,
    ClientReservationDetailView,
    ClientReservationUpdateView,
    ClientReservationCancelView,
    ClientRoomServiceView,
    ClientServiciosView,
    ClientPaymentCreateView,
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

    # Portal cliente
    path("mis/", ClientReservationsListView.as_view(), name="mis_reservas"),
    path("mis/nueva/", ClientReservationCreateView.as_view(), name="nueva"),
    path("mis/<int:pk>/", ClientReservationDetailView.as_view(), name="detalle_cliente"),
    path("mis/<int:pk>/editar/", ClientReservationUpdateView.as_view(), name="editar_cliente"),
    path("mis/<int:pk>/cancelar/", ClientReservationCancelView.as_view(), name="cancelar_cliente"),
    path("mis/room-service/", ClientRoomServiceView.as_view(), name="room_service"),
    path("mis/servicios/", ClientServiciosView.as_view(), name="servicios"),

    path("mis/<int:pk>/pago/", ClientPaymentCreateView.as_view(), name="pago_cliente"),
]
