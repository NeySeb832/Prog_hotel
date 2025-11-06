# reservas/urls.py
from django.urls import path
from . import views

app_name = "reservas"

urlpatterns = [
    # Cliente
    path("mis/", views.MyReservationListView.as_view(), name="mis_reservas"),
    path("mis/nueva/", views.MyReservationCreateView.as_view(), name="mis_reservas_nueva"),
    path("mis/<int:pk>/", views.MyReservationDetailView.as_view(), name="mis_reservas_detalle"),
    path("mis/<int:pk>/editar/", views.MyReservationUpdateView.as_view(), name="mis_reservas_editar"),

    # Admin
    path("admin/", views.AdminReservationListView.as_view(), name="admin_reservas"),
    path("admin/<int:pk>/", views.AdminReservationDetailView.as_view(), name="admin_reservas_detalle"),
]
