# accounts/views.py
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.views import View

from .utils import redirect_by_role  # usa el mapping de roles

class CustomLoginView(View):
    template_name = "accounts/login.html"

    def get(self, request, *args, **kwargs):
        # ✅ Siempre mostrar la página de login, incluso si ya hay sesión
        # (así puedes cambiar de usuario sin tener que hacer logout)
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        email = request.POST.get("email") or request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            # ✅ Aquí SÍ redirigimos por rol
            return redirect_by_role(user)

        # credenciales inválidas
        return render(request, self.template_name, {
            "error": "Credenciales inválidas. Intenta nuevamente."
        })

class RegisterPageView(View):
    template_name = "accounts/register.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect_by_role(request.user)
        return render(request, self.template_name)

    # Si todavía no implementas el POST de registro desde esta plantilla,
    # puedes dejarlo en blanco o redirigir con un mensaje:
    # def post(self, request, *args, **kwargs): ...

class PostLoginView(View):
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect_by_role(request.user)
        return redirect("accounts:login")

def logout_view(request):
    logout(request)
    return redirect('/')
