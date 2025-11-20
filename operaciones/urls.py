from django.urls import path
from . import views

app_name = 'operaciones'

urlpatterns = [
    path('', views.panel_operaciones, name='panel_operaciones'),
    path('check-in/<int:reserva_id>/', views.check_in, name='check_in'),
    path('check-out/<int:estadia_id>/', views.check_out, name='check_out'),
]
