from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),

    path("nuestras_habitaciones/", views.nuestras_habitaciones, name="Nuestras Habitaciones"),

    path("nuestros_servicios/", views.nuestros_servicios, name="Nuestros Servicios"),

    path("sobre_nosotros/", views.sobre_nosotros, name="Sobre Nosotros"),

    path("contacto/", views.contacto, name="Contacto"),

]
