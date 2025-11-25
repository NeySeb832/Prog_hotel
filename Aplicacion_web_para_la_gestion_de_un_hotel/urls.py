"""
URL configuration for Aplicacion_web_para_la_gestion_de_un_hotel project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

# Aplicacion_web_para_la_gestion_de_un_hotel/urls.py
from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path("admin/", admin.site.urls),

    # Raíz -> web pública / bienvenida
    path("", include("dashboard.urls")),

    # Auth + portal cliente
    path("", include("accounts.urls")),

    # Módulos
    path("reservas/", include("reservas.urls")),

    path("admin_hotel/", include("admin_hotel.urls")),

    path("habitaciones/", include("habitaciones.urls")),

    path('operaciones/', include('operaciones.urls')),

    path("clientes/", include("clientes.urls")),

    path('reportes/', include('reportes.urls')),

    path("configuracion/", include("configuracion.urls")),

    path("servicios/", include("servicios.urls")),


    ]