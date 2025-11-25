from django.urls import path

from .views import (
    ReportesResumenView,
    ExportarReportePDFView,
    HistorialReportesView,
    DescargarReportePDFView,
)

app_name = "reportes"

urlpatterns = [
    path("", ReportesResumenView.as_view(), name="resumen"),
    path("exportar/", ExportarReportePDFView.as_view(), name="exportar_pdf"),
    path("historial/", HistorialReportesView.as_view(), name="historial"),
    path("historial/<int:pk>/descargar/", DescargarReportePDFView.as_view(), name="descargar_pdf"),
]
