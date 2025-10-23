# accounts/urls.py
from django.urls import path  # 👈 IMPORTANTE
from .views import CustomLoginView, RegisterPageView, PostLoginView, logout_view

app_name = "accounts"

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="Login"),
    path("registro/", RegisterPageView.as_view(), name="registro"),
    path("post-login/", PostLoginView.as_view(), name="post_login"),
    path("logout/", logout_view, name="logout"),
]
