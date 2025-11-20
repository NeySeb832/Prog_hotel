# clientes/urls.py
from django.urls import path

from .views import (
    ClientesListView,
    ClienteDetailView,
    ClienteCreateView,
    ClienteUpdateView,
    ClienteDeleteView,
)

app_name = "clientes"

urlpatterns = [
    path("", ClientesListView.as_view(), name="lista"),
    path("nuevo/", ClienteCreateView.as_view(), name="crear"),
    path("<int:pk>/", ClienteDetailView.as_view(), name="detalle"),
    path("<int:pk>/editar/", ClienteUpdateView.as_view(), name="editar"),
    path("<int:pk>/eliminar/", ClienteDeleteView.as_view(), name="eliminar"),
]
