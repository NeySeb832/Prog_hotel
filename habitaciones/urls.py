from django.urls import path

from .views import (
    HabitacionesListView,
    HabitacionCreateView,
    HabitacionToggleStatusView,
)

app_name = "habitaciones"

urlpatterns = [
    # Listado de habitaciones
    path("", HabitacionesListView.as_view(), name="lista"),

    # Crear nueva habitación
    path("api/crear/", HabitacionCreateView.as_view(), name="api_crear"),

    # Cambiar estado de una habitación
    path("<int:pk>/estado/", HabitacionToggleStatusView.as_view(), name="api_toggle"),
]
