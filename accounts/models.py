from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        CLIENT = "CLIENT", "Cliente"

    role = models.CharField(
        max_length=10,
        choices=Roles.choices,
        default=Roles.CLIENT,
        help_text="Rol que controla el acceso a módulos."
    )

    # Opcional: atajos booleanos
    @property
    def is_admin_role(self):
        return self.role == self.Roles.ADMIN

    @property
    def is_client_role(self):
        return self.role == self.Roles.CLIENT
