from django.shortcuts import render

# Create your views here.

def home(request):
    return render(request, 'dashboard/home.html')

def nuestras_habitaciones(request):
    return render(request, 'dashboard/nuestras_habitaciones.html')

def nuestros_servicios(request):
    return render(request, 'dashboard/nuestros_servicios.html')

def sobre_nosotros(request):
    return render(request, 'dashboard/sobre_nosotros.html')

def contacto(request):
    return render(request, 'dashboard/contacto.html')