# -*- coding: utf-8 -*-
from datetime import timedelta, datetime
import json



from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views import View
from django.core.files.base import ContentFile
from collections import OrderedDict
from habitaciones.models import Habitacion
from reservas.models import Reservation, Payment
from .models import ReportePDF
from .utils import render_to_pdf


class BaseReportesMixin(LoginRequiredMixin):
    login_url = "/login/"

    def _parse_date(self, value):
        """
        Intenta parsear 'YYYY-MM-DD'. Si falla, devuelve None.
        """
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _compute_report_data(self, start_date, end_date):
        """
        Calcula todos los datos del reporte para un rango de fechas.
        Además prepara las series de la gráfica de forma dinámica:

        - <= 7 días        → eje X por día de la semana (Lun, Mar, ...)
        - mismo mes (>7d)  → eje X por día (dd/mm)
        - <= ~1 año        → eje X por mes (mm/aaaa)
        - > ~1 año         → eje X por año (aaaa)
        """
        # ---------------- RANGO DE DÍAS ----------------
        days = []
        d = start_date
        while d <= end_date:
            days.append(d)
            d += timedelta(days=1)

        days_count = len(days)
        total_habitaciones = Habitacion.objects.count()

        # ---------------- RESERVAS Y PAGOS ----------------
        reservas_periodo = Reservation.objects.filter(
            check_in__gte=start_date,
            check_in__lte=end_date,
        )

        total_reservas = reservas_periodo.count()

        reservas_por_estado_qs = (
            reservas_periodo
            .values("status")
            .annotate(total=Count("id"))
            .order_by()
        )
        reservas_por_estado = {
            r["status"]: r["total"] for r in reservas_por_estado_qs
        }

        pagos_periodo = Payment.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )

        ingresos_totales = pagos_periodo.aggregate(total=Sum("amount"))["total"] or 0
        total_pagos = pagos_periodo.count()
        ticket_promedio = ingresos_totales / total_pagos if total_pagos else 0

        # ---------------- SERIES DIARIAS CRUDAS ----------------
        ingresos_por_dia_raw = []
        ocupacion_por_dia_raw = []

        for day in days:
            # Ingresos de ese día
            total_dia = (
                pagos_periodo
                .filter(created_at__date=day)
                .aggregate(total=Sum("amount"))["total"] or 0
            )
            ingresos_por_dia_raw.append(float(total_dia))

            # Ocupación de ese día (en %)
            reservas_dia = Reservation.objects.filter(
                status__in=[
                    Reservation.Status.CONFIRMED,
                    Reservation.Status.CHECKED_IN,
                ],
                check_in__lte=day,
                check_out__gt=day,
            )
            ocupadas_dia = reservas_dia.values("room_id").distinct().count()
            pct = round(ocupadas_dia / total_habitaciones * 100) if total_habitaciones else 0
            ocupacion_por_dia_raw.append(pct)

        # ---------------- AGRUPACIÓN DINÁMICA PARA LA GRÁFICA ----------------
        dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

        # Caso 1: hasta 7 días → por día de la semana
        if days_count <= 7:
            labels = [dias_semana[d.weekday()] for d in days]
            ingresos_serie = ingresos_por_dia_raw
            ocupacion_serie = ocupacion_por_dia_raw

        # Caso 2: más de 7 días pero mismo mes → por día (dd/mm)
        elif start_date.year == end_date.year and start_date.month == end_date.month:
            labels = [d.strftime("%d/%m") for d in days]
            ingresos_serie = ingresos_por_dia_raw
            ocupacion_serie = ocupacion_por_dia_raw

        # Caso 3: más de un mes pero aprox. hasta 1 año → agrupar por mes
        elif days_count <= 370:
            mensual = OrderedDict()
            for d, ing, occ in zip(days, ingresos_por_dia_raw, ocupacion_por_dia_raw):
                key = (d.year, d.month)
                if key not in mensual:
                    mensual[key] = {"ingresos": 0.0, "occ_suma": 0.0, "count": 0}
                mensual[key]["ingresos"] += ing
                mensual[key]["occ_suma"] += occ
                mensual[key]["count"] += 1

            labels = [f"{m:02d}/{y}" for (y, m) in mensual.keys()]
            ingresos_serie = [round(v["ingresos"], 2) for v in mensual.values()]
            ocupacion_serie = [
                round((v["occ_suma"] / v["count"]) if v["count"] else 0, 1)
                for v in mensual.values()
            ]

        # Caso 4: más de ~1 año → agrupar por año
        else:
            anual = OrderedDict()
            for d, ing, occ in zip(days, ingresos_por_dia_raw, ocupacion_por_dia_raw):
                key = d.year
                if key not in anual:
                    anual[key] = {"ingresos": 0.0, "occ_suma": 0.0, "count": 0}
                anual[key]["ingresos"] += ing
                anual[key]["occ_suma"] += occ
                anual[key]["count"] += 1

            labels = [str(y) for y in anual.keys()]
            ingresos_serie = [round(v["ingresos"], 2) for v in anual.values()]
            ocupacion_serie = [
                round((v["occ_suma"] / v["count"]) if v["count"] else 0, 1)
                for v in anual.values()
            ]

        chart_labels = mark_safe(json.dumps(labels))
        chart_ingresos = mark_safe(json.dumps(ingresos_serie))
        chart_ocupacion = mark_safe(json.dumps(ocupacion_serie))

        # ---------------- LISTAS DETALLADAS (TABLAS) ----------------
        reservas_list = (
            reservas_periodo
            .select_related("room")
            .order_by("-check_in", "-created_at")[:50]
        )

        pagos_list = (
            pagos_periodo
            .select_related("reservation")
            .order_by("-created_at")[:50]
        )

        return {
            "total_habitaciones": total_habitaciones,
            "total_reservas": total_reservas,
            "reservas_por_estado": reservas_por_estado,
            "ingresos_totales": ingresos_totales,
            "total_pagos": total_pagos,
            "ticket_promedio": ticket_promedio,
            "chart_labels": chart_labels,
            "chart_ingresos": chart_ingresos,
            "chart_ocupacion": chart_ocupacion,
            "reservas_list": reservas_list,
            "pagos_list": pagos_list,
        }


class ReportesResumenView(BaseReportesMixin, View):
    """
    Reporte general HTML (ya lo tenías, ahora usa el mixin).
    """

    def get(self, request, *args, **kwargs):
        today = timezone.localdate()

        start_str = request.GET.get("start") or ""
        end_str = request.GET.get("end") or ""

        end_date = self._parse_date(end_str)
        start_date = self._parse_date(start_str)

        if not end_date:
            end_date = today
        if not start_date:
            start_date = end_date - timedelta(days=6)  # últimos 7 días

        if start_date > end_date:
            start_date, end_date = end_date, start_date

        data = self._compute_report_data(start_date, end_date)

        context = {
            "active_menu": "reportes",
            "start_date": start_date,
            "end_date": end_date,
            **data,
        }
        return render(request, "reportes/resumen.html", context)


class ExportarReportePDFView(BaseReportesMixin, View):
    """
    Genera un PDF del reporte y lo guarda en ReportePDF.
    modos:
      - modo=diario
      - modo=semanal
      - modo=mensual
      - modo=anual
      - modo=personalizado (usa start/end enviados)
    """

    def get_rango_por_modo(self, modo, request):
        today = timezone.localdate()

        modo = (modo or "").lower()

        if modo == "diario":
            return today, today, ReportePDF.Tipo.DIARIO
        elif modo == "semanal":
            start = today - timedelta(days=6)
            return start, today, ReportePDF.Tipo.SEMANAL
        elif modo == "mensual":
            # últimos 30 días
            start = today - timedelta(days=29)
            return start, today, ReportePDF.Tipo.MENSUAL
        elif modo == "anual":
            # últimos 365 días
            start = today - timedelta(days=364)
            return start, today, ReportePDF.Tipo.ANUAL
        else:
            # personalizado: usa parámetros GET
            start_str = request.GET.get("start") or ""
            end_str = request.GET.get("end") or ""
            start_date = self._parse_date(start_str)
            end_date = self._parse_date(end_str)
            if not end_date:
                end_date = today
            if not start_date:
                start_date = end_date - timedelta(days=6)
            if start_date > end_date:
                start_date, end_date = end_date, start_date
            return start_date, end_date, ReportePDF.Tipo.PERSONALIZADO

    def get(self, request, *args, **kwargs):
        modo = request.GET.get("modo", "personalizado")
        start_date, end_date, tipo = self.get_rango_por_modo(modo, request)

        data = self._compute_report_data(start_date, end_date)

        context = {
            "start_date": start_date,
            "end_date": end_date,
            "tipo": tipo,
            "usuario": request.user,
            **data,
        }

        pdf_bytes = render_to_pdf("reportes/pdf_reporte.html", context)
        if pdf_bytes is None:
            raise Http404("No se pudo generar el PDF")

        # Guardar en modelo
        nombre = f"reporte_{tipo.lower()}_{start_date}_{end_date}.pdf".replace(":", "-")
        reporte = ReportePDF(
            tipo=tipo,
            fecha_inicio=start_date,
            fecha_fin=end_date,
            total_reservas=data["total_reservas"],
            ingresos_totales=data["ingresos_totales"] or 0,
            usuario=request.user if request.user.is_authenticated else None,
        )
        reporte.archivo.save(nombre, ContentFile(pdf_bytes), save=True)

        # Responder con descarga directa
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{nombre}"'
        return response


class HistorialReportesView(LoginRequiredMixin, View):
    """
    Lista de reportes PDF generados, con filtros por fecha y tipo.
    """
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        qs = ReportePDF.objects.all().order_by("-creado_el")

        tipo = request.GET.get("tipo") or ""
        start_str = request.GET.get("start") or ""
        end_str = request.GET.get("end") or ""

        start_date = None
        end_date = None

        if start_str:
            try:
                start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            except ValueError:
                start_date = None
        if end_str:
            try:
                end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
            except ValueError:
                end_date = None

        if tipo:
            qs = qs.filter(tipo=tipo)

        if start_date:
            qs = qs.filter(creado_el__date__gte=start_date)
        if end_date:
            qs = qs.filter(creado_el__date__lte=end_date)

        context = {
            "active_menu": "reportes",
            "reportes": qs,
            "tipo_filtro": tipo,
            "start_date": start_date,
            "end_date": end_date,
            "tipos": ReportePDF.Tipo.choices,
        }
        return render(request, "reportes/historial.html", context)


class DescargarReportePDFView(LoginRequiredMixin, View):
    """
    Descarga un PDF previamente generado.
    """
    login_url = "/login/"

    def get(self, request, pk, *args, **kwargs):
        reporte = get_object_or_404(ReportePDF, pk=pk)
        if not reporte.archivo:
            raise Http404("El archivo del reporte no existe")

        pdf_bytes = reporte.archivo.read()
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{reporte.archivo.name.split("/")[-1]}"'
        return response
