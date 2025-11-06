from django.shortcuts import render

# Create your views here.

# --- STUBS TEMPORALES (borra cuando pongas las vistas reales) ---
try:
    MyReservationListView
    MyReservationCreateView
    MyReservationDetailView
    MyReservationUpdateView
    AdminReservationListView
    AdminReservationDetailView
except NameError:
    from django.views.generic import TemplateView

    class MyReservationListView(TemplateView):
        template_name = "reservas/wip.html"

    class MyReservationCreateView(TemplateView):
        template_name = "reservas/wip.html"

    class MyReservationDetailView(TemplateView):
        template_name = "reservas/wip.html"

    class MyReservationUpdateView(TemplateView):
        template_name = "reservas/wip.html"

    class AdminReservationListView(TemplateView):
        template_name = "reservas/wip.html"

    class AdminReservationDetailView(TemplateView):
        template_name = "reservas/wip.html"
