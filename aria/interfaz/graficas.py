# Gráficas (QtCharts) con la paleta de la app.
from PySide6.QtCharts import (QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QLineSeries,
                              QValueAxis)
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from aria.interfaz.estilo import ARENA, ARENA_SUAVE, NARANJA, NEGRO_BORDE, NEGRO_MEDIO

LINEA_REJILLA = NEGRO_BORDE


def _grafica(titulo: str) -> tuple[QChart, QChartView]:
    grafica = QChart()
    grafica.setTitle(titulo)
    grafica.setTitleBrush(QColor(ARENA))
    grafica.setTitleFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
    grafica.setBackgroundBrush(QColor(NEGRO_MEDIO))
    grafica.setBackgroundPen(QPen(QColor(NEGRO_BORDE), 1))
    grafica.setBackgroundRoundness(14)
    grafica.legend().setLabelColor(QColor(ARENA_SUAVE))
    grafica.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
    grafica.setMargins(QMargins(6, 6, 6, 6))
    grafica.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
    vista = QChartView(grafica)
    vista.setRenderHint(QPainter.RenderHint.Antialiasing)
    vista.setMinimumHeight(240)
    vista.setStyleSheet("background: transparent; border: none;")
    return grafica, vista


def _eje(eje, formato: str | None = None):
    eje.setLabelsColor(QColor(ARENA_SUAVE))
    eje.setGridLineColor(QColor(LINEA_REJILLA))
    eje.setLinePenColor(QColor(LINEA_REJILLA))
    if formato and isinstance(eje, QValueAxis):
        eje.setLabelFormat(formato)
    return eje


def barras(titulo: str, categorias: list[str], series: dict[str, list[float]], colores: list[str],
           linea_objetivo: float | None = None, nombre_objetivo: str = "Objetivo") -> QChartView:
    grafica, vista = _grafica(titulo)
    barras_ = QBarSeries()
    for (nombre, valores), color in zip(series.items(), colores):
        conjunto = QBarSet(nombre)
        conjunto.append([float(v) for v in valores])
        conjunto.setColor(QColor(color))
        conjunto.setBorderColor(QColor(color))
        barras_.append(conjunto)
    grafica.addSeries(barras_)
    eje_x = _eje(QBarCategoryAxis())
    eje_x.append(categorias)
    maximo = max([max(v) if v else 0 for v in series.values()] + [linea_objetivo or 0, 1])
    eje_y = _eje(QValueAxis(), "%.0f")
    eje_y.setRange(0, maximo * 1.15)
    grafica.addAxis(eje_x, Qt.AlignmentFlag.AlignBottom)
    grafica.addAxis(eje_y, Qt.AlignmentFlag.AlignLeft)
    barras_.attachAxis(eje_x)
    barras_.attachAxis(eje_y)
    if linea_objetivo:
        # La línea de objetivo se dibuja sobre un eje X numérico oculto que abarca todas las barras.
        linea = QLineSeries(name=nombre_objetivo)
        linea.append(-0.5, linea_objetivo)
        linea.append(len(categorias) - 0.5, linea_objetivo)
        linea.setPen(QPen(QColor(ARENA), 2, Qt.PenStyle.DashLine))
        grafica.addSeries(linea)
        eje_oculto = QValueAxis()
        eje_oculto.setRange(-0.5, len(categorias) - 0.5)
        eje_oculto.setVisible(False)
        grafica.addAxis(eje_oculto, Qt.AlignmentFlag.AlignBottom)
        linea.attachAxis(eje_oculto)
        linea.attachAxis(eje_y)
    return vista


def lineas(titulo: str, etiquetas: list[str], valores: list[float], color: str = NARANJA,
           sufijo: str = "") -> QChartView:
    grafica, vista = _grafica(titulo)
    serie = QLineSeries(name=titulo)
    for i, v in enumerate(valores):
        serie.append(i, float(v))
    serie.setPen(QPen(QColor(color), 3))
    serie.setPointsVisible(True)
    grafica.addSeries(serie)
    grafica.legend().hide()
    eje_x = _eje(QBarCategoryAxis())
    eje_x.append(etiquetas)
    eje_y = _eje(QValueAxis(), "%.1f" + sufijo)
    minimo, maximo = min(valores), max(valores)
    margen = max(1.0, (maximo - minimo) * 0.2)
    eje_y.setRange(minimo - margen, maximo + margen)
    eje_num = QValueAxis()
    eje_num.setRange(0, max(1, len(valores) - 1))
    eje_num.setVisible(False)
    grafica.addAxis(eje_x, Qt.AlignmentFlag.AlignBottom)
    grafica.addAxis(eje_num, Qt.AlignmentFlag.AlignBottom)
    grafica.addAxis(eje_y, Qt.AlignmentFlag.AlignLeft)
    serie.attachAxis(eje_num)
    serie.attachAxis(eje_y)
    return vista
