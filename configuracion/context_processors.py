# configuracion/context_processors.py
from .models import ConfiguracionGeneral


def configuracion_general(request):
    """
    Devuelve la configuración general del sistema en la variable
    'config_general' para todas las plantillas.
    """
    try:
        config = ConfiguracionGeneral.get_solo()
    except Exception:
        config = None
    return {
        "config_general": config
    }
