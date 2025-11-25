import io

from django.template.loader import get_template
from xhtml2pdf import pisa


def render_to_pdf(template_src, context_dict=None):
    """
    Renderiza una plantilla HTML a PDF y devuelve los bytes.
    Si hay error, devuelve None.
    """
    context_dict = context_dict or {}
    template = get_template(template_src)
    html = template.render(context_dict)

    result = io.BytesIO()
    pdf = pisa.CreatePDF(html, dest=result)

    if pdf.err:
        return None

    return result.getvalue()
