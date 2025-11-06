# admin_hotel/urls.py
from django.urls import path
from django.views.generic import TemplateView  # o importa tu vista real

app_name = "admin_hotel"

urlpatterns = [
    # Queda en /admin_hotel/ al incluirlo con prefix en el proyecto
    path("", TemplateView.as_view(template_name="admin_hotel/dashboard.html"), name="dashboard"),
]
