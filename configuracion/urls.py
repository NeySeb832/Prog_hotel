from django.urls import path
from .views import ConfiguracionGeneralView

app_name = "configuracion"

urlpatterns = [
    path("", ConfiguracionGeneralView.as_view(), name="general"),
]
