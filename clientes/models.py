# clientes/models.py
# Por ahora no definimos un modelo nuevo de Cliente.
# Usamos el modelo de usuario (accounts.User) como fuente
# de información de clientes. Más adelante, si necesitas
# un perfil extendido, aquí se puede crear un modelo
# CustomerProfile con OneToOneField al usuario.
from django.db import models  # noqa: F401
