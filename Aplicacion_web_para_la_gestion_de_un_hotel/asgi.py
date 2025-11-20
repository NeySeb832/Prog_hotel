"""
ASGI config for Aplicacion_web_para_la_gestion_de_un_hotel project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Aplicacion_web_para_la_gestion_de_un_hotel.settings')

application = get_asgi_application()
