from django.urls import path

from .views import dashboard

app_name = "admin_hotel"

urlpatterns = [
    path("", dashboard, name="dashboard"),
]
