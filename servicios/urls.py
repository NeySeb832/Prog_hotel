from django.urls import path

from .views import (
    ServiciosListView,
    ServicioCreateView,
    ServicioUpdateView,
    ConsumosListView,
    ConsumoCreateView,
    ConsumoUpdateView,
    ConsumoPagoCreateView,
    # Portal cliente
    ClientServiciosView,
    ClientServiceCreateView,
    ClientServiceDetailView,
    ClientServicePaymentView,
    ClientServiceCancelView,
)


app_name = "servicios"

urlpatterns = [
    # Admin
    path("", ServiciosListView.as_view(), name="lista"),
    path("nuevo/", ServicioCreateView.as_view(), name="nuevo"),
    path("<int:pk>/editar/", ServicioUpdateView.as_view(), name="editar"),

    path("consumos/", ConsumosListView.as_view(), name="consumos"),
    path("consumos/nuevo/", ConsumoCreateView.as_view(), name="consumo_nuevo"),
    path("consumos/<int:pk>/editar/", ConsumoUpdateView.as_view(), name="consumo_editar"),
    path("consumos/<int:pk>/pagar/", ConsumoPagoCreateView.as_view(), name="consumo_pagar"),

    # Portal cliente - servicios
    path("cliente/mis/",      ClientServiciosView.as_view(),        name="cliente_mis_servicios"),
    path("cliente/nuevo/",    ClientServiceCreateView.as_view(),    name="cliente_nuevo"),
    path("cliente/<int:pk>/", ClientServiceDetailView.as_view(),    name="cliente_detalle"),
    path("cliente/<int:pk>/pago/", ClientServicePaymentView.as_view(), name="cliente_pago"),
    path("cliente/<int:pk>/cancelar/", ClientServiceCancelView.as_view(), name="cliente_cancelar"),
]

