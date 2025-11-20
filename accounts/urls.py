from django.urls import path
from .views import (
    CustomLoginView,
    RegisterPageView,
    logout_view,
    ClientPortalView,
)

app_name = "accounts"

urlpatterns = [
    path("login/",     CustomLoginView.as_view(),  name="login"),         # <- en minúscula
    path("registro/",  RegisterPageView.as_view(), name="registro"),
    path("logout/",    logout_view,                name="logout"),

    # Portal del cliente
    path("mi-portal/", ClientPortalView.as_view(), name="portal_cliente"),

    ]