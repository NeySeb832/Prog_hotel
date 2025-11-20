from django.contrib import admin
from .models import Habitacion, TipoHabitacion


@admin.register(TipoHabitacion)
class TipoHabitacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "capacidad_por_defecto", "camas_por_defecto", "precio_base")
    search_fields = ("nombre",)


@admin.register(Habitacion)
class HabitacionAdmin(admin.ModelAdmin):
    """
    En el admin de habitaciones:
    - Solo se edita código, nombre, tipo, estado, piso, foto, amenities, observaciones.
    - Capacidad, camas y precio_noche se muestran en el listado, pero
      NO son campos editables (se derivan del tipo).
    """
    list_display = (
        "codigo",
        "nombre",
        "tipo",
        "estado",
        "piso",
        "capacidad",
        "camas",
        "precio_noche",
    )
    list_filter = ("estado", "tipo", "piso")
    search_fields = ("codigo", "nombre", "observaciones")

    fields = (
        "codigo",
        "nombre",
        "tipo",
        "estado",
        "piso",
        "foto",
        "amenities",
        "observaciones",
    )
