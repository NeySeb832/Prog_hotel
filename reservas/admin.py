from django.contrib import admin
from .models import Reservation, Payment


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "room",
        "guest_name",
        "check_in",
        "check_out",
        "status",
        "total_amount",
        "paid_amount",
    )
    list_filter = (
        "status",
        "room__piso",
        "room__tipo",
        "check_in",
        "check_out",
    )
    search_fields = (
        "code",
        "guest_name",
        "guest_email",
        "guest_phone",
        "room__codigo",
    )
    autocomplete_fields = ("room", "guest")

    readonly_fields = (
        "code",
        "status",
        "nights",
        "total_amount",
        "paid_amount",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Datos de la reserva", {
            "fields": (
                "code",
                "room",
                "status",
                ("check_in", "check_out"),
                ("adults", "children"),
                "nights",
                ("total_amount", "paid_amount"),
            )
        }),
        ("Huésped", {
            "fields": (
                "guest",
                "guest_name",
                ("guest_email", "guest_phone"),
            )
        }),
        ("Seguimiento", {
            "fields": (
                "notes",
                ("created_at", "updated_at"),
            )
        }),
    )

    # ----- Acciones para cambiar estado de forma controlada -----
    actions = [
        "accion_marcar_confirmadas",
        "accion_registrar_checkin",
        "accion_registrar_checkout",
        "accion_cancelar_reservas",
    ]

    @admin.action(description="Marcar como CONFIRMADAS")
    def accion_marcar_confirmadas(self, request, queryset):
        for res in queryset:
            res.mark_confirmed()

    @admin.action(description="Registrar CHECK-IN")
    def accion_registrar_checkin(self, request, queryset):
        for res in queryset:
            res.mark_checked_in()

    @admin.action(description="Registrar CHECK-OUT")
    def accion_registrar_checkout(self, request, queryset):
        for res in queryset:
            res.mark_checked_out()

    @admin.action(description="Cancelar reservas seleccionadas")
    def accion_cancelar_reservas(self, request, queryset):
        for res in queryset:
            res.mark_cancelled()


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "reservation",
        "amount",
        "method",
        "created_at",
        "created_by",
    )
    list_filter = ("method", "created_at")
    search_fields = ("reservation__code", "reference")
    autocomplete_fields = ("reservation", "created_by")
    readonly_fields = ("created_at",)
