from django.contrib import admin

from .models import ConsumoServicio, Servicio


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "precio_base", "activo")
    list_filter = ("categoria", "activo")
    search_fields = ("nombre", "descripcion")


@admin.register(ConsumoServicio)
class ConsumoServicioAdmin(admin.ModelAdmin):
    list_display = (
        "servicio",
        "reserva",
        "cantidad",
        "precio_unitario",
        "total",
        "estado",
        "creado_en",
    )
    list_filter = ("estado", "servicio__categoria")
    search_fields = (
        "servicio__nombre",
        "reserva__code",
        "reserva__guest_name",
        "reserva__guest__first_name",
        "reserva__guest__last_name",
    )
    autocomplete_fields = ("reserva", "servicio")
