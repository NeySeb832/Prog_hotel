# admin_hotel/urls.py
from django.urls import path
from .views import dashboard

app_name = "admin_hotel"

urlpatterns = [
    path("admin_hotel/admin_dashboard/", dashboard, name="admin_dashboard"),
]
