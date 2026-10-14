# Ventana principal de Aria: chat y paneles (hoy, proyectos, salud, hábitos, memoria).
# Los paneles leen las mismas bases de datos que usa Aria. Mientras el modelo trabaja, los controles que
# modifican datos se desactivan (evita que dos hilos escriban a la vez en SQLite).
import html
import json
import re
from datetime import date, datetime, timedelta

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QProgressBar, QPushButton, QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem,
                               QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from aria import config
from aria.fechas import fecha_en_espanol
from aria.interfaz import graficas
from aria.interfaz.estilo import (ARENA, ARENA_SUAVE, BOTON, COLORES_ESTADO, NARANJA, NARANJA_CLARO, NEGRO_BORDE,
                                  NEGRO_CLARO, NEGRO_MEDIO, TEXTO_ESTADO, aplicar_barra_titulo)

SUAVE, TEXTO = ARENA_SUAVE, ARENA
BURBUJA_TU, BURBUJA_ARIA = BOTON, NEGRO_CLARO
HABITO_FALLADO, HABITO_LIBRE = "#5C4636", "#34343A"
from aria.memoria import CATEGORIAS
from aria.tareas import COLUMNAS_KANBAN, tiempo_restante
from aria.voz.tecla import nombre_tecla


def _markdown_basico(texto: str) -> str:
    t = html.escape(texto)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"^#{1,4}\s*(.+)$", r"<b>\1</b>", t, flags=re.M)
    t = re.sub(r"^\s*[-•]\s+", "• ", t, flags=re.M)
    return t.replace("\n", "<br>")


def _contenedor(*widgets, horizontal=False) -> QWidget:
    w = QWidget()
    caja = QHBoxLayout(w) if horizontal else QVBoxLayout(w)
    caja.setContentsMargins(0, 0, 0, 0)
    for x in widgets:
        caja.addWidget(x)
    return w


class Chat(QWidget):
    def __init__(self, motor):
        super().__init__()
        self.motor = motor
        self.historial = QTextBrowser(openExternalLinks=True)
        tecla = nombre_tecla(config.TECLA_HABLAR)
        self.entrada = QLineEdit(placeholderText=f"Escribe a Aria... (o mantén {tecla} y habla)")
        self.entrada.returnPressed.connect(self._enviar)
        self.boton = QPushButton("Enviar", objectName="principal")
        self.boton.clicked.connect(self._enviar)
        self.microfono = QPushButton("Mantén para hablar")
        self.microfono.setToolTip(f"Mantén pulsado mientras hablas (o usa {tecla} desde cualquier sitio)")
        self.microfono.pressed.connect(motor.tecla_pulsada)
        self.microfono.released.connect(motor.tecla_soltada)
        self.estado = QLabel(objectName="subtitulo")
        nueva = QPushButton("Nueva conversación")
        nueva.clicked.connect(self._nueva)
        caja = QVBoxLayout(self)
        caja.addWidget(self.historial, 1)
        caja.addWidget(_contenedor(self.entrada, self.boton, self.microfono, horizontal=True))
        caja.addWidget(_contenedor(self.estado, QWidget(), nueva, horizontal=True))
        motor.mensaje_usuario.connect(lambda t: self.anadir("Tú", t, BURBUJA_TU, ARENA))
        motor.respuesta.connect(lambda t: self.anadir("Aria", t, BURBUJA_ARIA, ARENA))
        motor.herramienta.connect(lambda n, a: self._nota(f"usando {n}"))
        motor.aviso.connect(lambda t: self._nota(t))
        motor.error.connect(lambda t: self._nota(f"Aviso: {t}", NARANJA))
        motor.estado_cambiado.connect(self._estado)
        self._estado("inactivo")

    def _enviar(self):
        texto = self.entrada.text().strip()
        if texto and not self.motor.ocupado:
            self.entrada.clear()
            self.motor.enviar(texto)

    def _nueva(self):
        self.motor.reiniciar()
        self.historial.clear()
        self._nota("Conversación nueva (los recuerdos y las tareas se mantienen).")

    def anadir(self, quien: str, texto: str, fondo: str, color: str = TEXTO):
        # QTextBrowser solo entiende HTML sencillo: una tabla al 78 % hace de "burbuja" a un lado u otro.
        alineacion = "right" if quien == "Tú" else "left"
        self.historial.append(
            f'<table width="78%" align="{alineacion}" cellpadding="10" style="margin:6px;">'
            f'<tr><td style="background:{fondo};">'
            f'<span style="color:{color}; font-size:9pt; font-weight:600;">{quien}</span><br><span style="color:{color};">{_markdown_basico(texto)}</span>'
            f"</td></tr></table>")
        self.historial.verticalScrollBar().setValue(self.historial.verticalScrollBar().maximum())

    def _nota(self, texto: str, color: str = SUAVE):
        self.historial.append(f'<div style="color:{color}; font-size:9pt; margin:2px 8px;">{html.escape(texto)}</div>')

    def _estado(self, estado: str):
        color = COLORES_ESTADO[estado]
        self.estado.setText(f'<span style="color:{color}">●</span> {TEXTO_ESTADO[estado]}')
        ocupado = estado == "pensando"
        self.boton.setEnabled(not ocupado)


class Hoy(QWidget):
    def __init__(self, ctx, motor):
        super().__init__()
        self.ctx, self.motor = ctx, motor
        self.titulo = QLabel(objectName="titulo")
        self.tareas = QListWidget()
        self.habitos = QListWidget()
        self.agenda = QListWidget()
        self.agenda.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for lista in (self.tareas, self.habitos, self.agenda):
            lista.setWordWrap(True)
            lista.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tareas.itemChanged.connect(self._tarea_marcada)
        self.habitos.itemChanged.connect(self._habito_marcado)
        rejilla = QGridLayout()
        for columna, (nombre, lista) in enumerate((("TAREAS", self.tareas), ("HÁBITOS DE HOY", self.habitos),
                                                   ("AGENDA · BLOQUES Y CALENDARIO", self.agenda))):
            grupo = QGroupBox(nombre)
            QVBoxLayout(grupo).addWidget(lista)
            rejilla.addWidget(grupo, 0, columna)
        caja = QVBoxLayout(self)
        caja.addWidget(self.titulo)
        caja.addWidget(QLabel("Marca las casillas para completar tareas y hábitos.", objectName="subtitulo"))
        caja.addLayout(rejilla, 1)
        self._cargando = False

    def refrescar(self):
        self._cargando = True
        ahora = datetime.now()
        self.titulo.setText(f"Hoy, {fecha_en_espanol(ahora)}")
        self.tareas.clear()
        for t in self.ctx.tareas.listar():
            vencida = t.fecha_limite and datetime.fromisoformat(t.fecha_limite) < ahora
            texto = ("VENCIDA · " if vencida else "") + t.titulo
            texto += f"  ·  {tiempo_restante(t.fecha_limite, ahora)}" if t.fecha_limite else ""
            item = QListWidgetItem(texto)
            item.setData(Qt.ItemDataRole.UserRole, t.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.tareas.addItem(item)
        self.habitos.clear()
        plan = self.ctx.planificacion
        for h in plan.habitos():
            if not h.toca(ahora.date()):
                continue
            item = QListWidgetItem(f"{h.nombre}{'  ·  ' + h.hora if h.hora else ''}  ·  racha {plan.racha(h, ahora.date())}")
            item.setData(Qt.ItemDataRole.UserRole, h.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if plan.hecho(h.id, ahora.date()) else Qt.CheckState.Unchecked)
            self.habitos.addItem(item)
        self.agenda.clear()
        entradas = [(b.inicio, f"{b.inicio}–{b.fin}  {b.titulo}") for b in plan.bloques(ahora.date().isoformat())]
        if self.ctx.calendario.conectado():
            try:
                for e in self.ctx.calendario.eventos_del_dia(ahora.date()):
                    entradas.append(("00:00" if e.todo_el_dia else f"{e.inicio:%H:%M}",
                                     ("Todo el día" if e.todo_el_dia else f"{e.inicio:%H:%M}–{e.fin:%H:%M}") + f"  ·  Calendario: {e.titulo}"))
            except Exception as error:
                entradas.append(("99", f"(calendario no disponible: {error})"))
        for _, texto in sorted(entradas) or [("", "Nada planificado. Pídele a Aria que te organice el día.")]:
            self.agenda.addItem(texto)
        if not self.tareas.count():
            self.tareas.addItem("Sin tareas pendientes")
        if not self.habitos.count():
            self.habitos.addItem("Hoy no toca ningún hábito.")
        self._cargando = False

    def _tarea_marcada(self, item):
        if self._cargando or item.data(Qt.ItemDataRole.UserRole) is None:
            return
        if self.motor.ocupado:
            QMessageBox.information(self, "Aria", "Espera a que Aria termine de responder.")
            self.refrescar()
            return
        if item.checkState() == Qt.CheckState.Checked:
            self.ctx.tareas.actualizar(item.data(Qt.ItemDataRole.UserRole), estado="hecha")
            QTimer.singleShot(400, self.refrescar)

    def _habito_marcado(self, item):
        if self._cargando or item.data(Qt.ItemDataRole.UserRole) is None or self.motor.ocupado:
            return
        self.ctx.planificacion.marcar(item.data(Qt.ItemDataRole.UserRole), date.today(),
                                      item.checkState() == Qt.CheckState.Checked)
        QTimer.singleShot(200, self.refrescar)


class ColumnaKanban(QListWidget):
    def __init__(self, estado: str, al_soltar):
        super().__init__()
        self.estado, self.al_soltar = estado, al_soltar
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setWordWrap(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSpacing(3)

    def dropEvent(self, e):
        origen = e.source()
        items = origen.selectedItems() if isinstance(origen, QListWidget) else []
        super().dropEvent(e)
        for item in items:
            self.al_soltar(item.data(Qt.ItemDataRole.UserRole), self.estado)


class Proyectos(QWidget):
    def __init__(self, ctx, motor):
        super().__init__()
        self.ctx, self.motor = ctx, motor
        self.selector = QComboBox()
        self.selector.currentIndexChanged.connect(self._mostrar)
        self.info = QLabel(objectName="subtitulo", wordWrap=True)
        self.progreso = QProgressBar()
        self.columnas = {e: ColumnaKanban(e, self._mover) for e in COLUMNAS_KANBAN}
        tablero = QHBoxLayout()
        for estado, nombre in COLUMNAS_KANBAN.items():
            grupo = QGroupBox(nombre.upper())
            QVBoxLayout(grupo).addWidget(self.columnas[estado])
            tablero.addWidget(grupo)
        caja = QVBoxLayout(self)
        caja.addWidget(_contenedor(QLabel("Proyecto:"), self.selector, horizontal=True))
        caja.addWidget(self.info)
        caja.addWidget(self.progreso)
        caja.addWidget(QLabel("Arrastra las tarjetas entre columnas para cambiar su estado.", objectName="subtitulo"))
        caja.addLayout(tablero, 1)

    def refrescar(self):
        actual = self.selector.currentData()
        self.selector.blockSignals(True)
        self.selector.clear()
        for p in self.ctx.tareas.proyectos(("activo", "en_pausa")):
            self.selector.addItem(f"{p.nombre}  ({p.horizonte} plazo{', en pausa' if p.estado == 'en_pausa' else ''})", p.id)
        if actual is not None and self.selector.findData(actual) >= 0:
            self.selector.setCurrentIndex(self.selector.findData(actual))
        self.selector.blockSignals(False)
        self._mostrar()

    def _mostrar(self):
        for columna in self.columnas.values():
            columna.clear()
        id_proyecto = self.selector.currentData()
        if id_proyecto is None:
            self.info.setText("No hay proyectos activos. Pídele a Aria: «quiero plantear como proyecto…».")
            self.progreso.setValue(0)
            return
        p = self.ctx.tareas.proyecto(id_proyecto)
        hechas, total = self.ctx.tareas.progreso(id_proyecto)
        self.progreso.setMaximum(max(1, total))
        self.progreso.setValue(hechas)
        self.progreso.setFormat(f"{hechas}/{total} pasos")
        self.info.setText(f"<b>Resultado:</b> {html.escape(p.resultado or '—')}"
                          + (f"   ·   <b>Objetivo:</b> {p.fecha_objetivo[:10]}" if p.fecha_objetivo else ""))
        for t in self.ctx.tareas.listar(tuple(COLUMNAS_KANBAN), id_proyecto):
            item = QListWidgetItem(t.titulo + (f"\nFecha: {t.fecha_limite[:10]}" if t.fecha_limite else ""))
            item.setData(Qt.ItemDataRole.UserRole, t.id)
            item.setSizeHint(QSize(0, 48))
            self.columnas[t.estado].addItem(item)

    def _mover(self, id_tarea: int, estado: str):
        if self.motor.ocupado:
            QMessageBox.information(self, "Aria", "Espera a que Aria termine de responder.")
        else:
            self.ctx.tareas.actualizar(id_tarea, estado=estado)
        QTimer.singleShot(100, self._mostrar)


class Salud(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.resumen = QLabel(objectName="subtitulo", wordWrap=True)
        self.zona = QWidget()
        self.rejilla = QGridLayout(self.zona)
        desplazable = QScrollArea(widgetResizable=True)
        desplazable.setWidget(self.zona)
        caja = QVBoxLayout(self)
        caja.addWidget(QLabel("Salud", objectName="titulo"))
        caja.addWidget(self.resumen)
        caja.addWidget(desplazable, 1)

    def refrescar(self):
        while self.rejilla.count():
            self.rejilla.takeAt(0).widget().deleteLater()
        salud = self.ctx.salud
        hoy = date.today()
        objetivos = salud.objetivos()
        dias = [hoy - timedelta(days=d) for d in range(13, -1, -1)]
        kcal, proteinas, quemadas = [], [], []
        for d in dias:
            comidas = salud.comidas(d.isoformat(), d.isoformat())
            kcal.append(sum(c["kcal"] for c in comidas))
            proteinas.append(sum(c["proteinas"] for c in comidas))
            quemadas.append(sum(e["kcal"] for e in salud.entrenos(d.isoformat(), d.isoformat())))
        etiquetas = [f"{d.day}/{d.month}" for d in dias]
        self.rejilla.addWidget(graficas.barras(
            "Calorías por día (14 días)", etiquetas, {"Comidas": kcal, "Quemadas entrenando": quemadas},
            [NARANJA, ARENA_SUAVE], objetivos["kcal"] if objetivos else None), 0, 0)
        self.rejilla.addWidget(graficas.barras(
            "Proteína por día (g)", etiquetas, {"Proteína": proteinas}, [NARANJA_CLARO],
            objetivos["proteinas"] if objetivos else None), 0, 1)
        pesos = salud.historial_peso(20)
        if len(pesos) >= 2:
            etiquetas_peso = [f"{int(f[8:10])}/{int(f[5:7])}" for f, _ in pesos]
            self.rejilla.addWidget(graficas.lineas("Peso (kg)", etiquetas_peso, [kg for _, kg in pesos],
                                                   NARANJA, " kg"), 1, 0)
        semanas = [hoy - timedelta(days=hoy.weekday() + 7 * s) for s in range(7, -1, -1)]
        minutos = [sum(e["duracion_min"] for e in salud.entrenos(l.isoformat(), (l + timedelta(days=6)).isoformat()))
                   for l in semanas]
        self.rejilla.addWidget(graficas.barras("Minutos de entrenamiento por semana", [f"{l.day}/{l.month}" for l in semanas],
                                               {"Minutos": minutos}, [NARANJA]), 1, 1 if len(pesos) >= 2 else 0)
        texto = f"Hoy: ≈ {kcal[-1]:.0f} kcal y {proteinas[-1]:.0f} g de proteína."
        if objetivos:
            texto += f"  Objetivo ({objetivos['objetivo']}): {objetivos['kcal']} kcal y {objetivos['proteinas']} g."
        else:
            texto += "  Dile a Aria tu peso, altura, edad y objetivo para ver tus metas."
        self.resumen.setText(texto + "  (Estimaciones orientativas.)")


class MapaHabitos(QWidget):
    """Una fila por hábito, un cuadrito por día (últimos 30): verde hecho, rojo tocaba y no, gris no tocaba."""

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.filas = []
        self.setMinimumHeight(60)

    def cargar(self):
        hoy = date.today()
        plan = self.ctx.planificacion
        self.filas = []
        for h in plan.habitos():
            dias = []
            for d in range(29, -1, -1):
                dia = hoy - timedelta(days=d)
                if dia.isoformat() < h.creado[:10]:
                    dias.append("antes")
                elif plan.hecho(h.id, dia):
                    dias.append("hecho")
                elif h.toca(dia) and not h.veces_semana and dia < hoy:
                    dias.append("fallado")
                else:
                    dias.append("libre")
            cumplidos, total = plan.cumplimiento(h, hoy)
            self.filas.append((h.nombre, dias, plan.racha(h, hoy), f"{cumplidos}/{total}"))
        self.setMinimumHeight(40 + 34 * len(self.filas))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        colores = {"hecho": QColor(NARANJA), "fallado": QColor(HABITO_FALLADO), "libre": QColor(HABITO_LIBRE),
                   "antes": QColor(NEGRO_MEDIO)}
        p.fillRect(self.rect(), QColor(NEGRO_MEDIO))
        p.setPen(QColor(SUAVE))
        if not self.filas:
            p.drawText(10, 30, "Aún no hay hábitos. Pídele a Aria: «quiero empezar a…».")
        p.drawText(10, 18, "Últimos 30 días  (naranja: hecho · marrón: tocaba y no se hizo · gris: no tocaba)")
        for fila, (nombre, dias, racha, cumplimiento) in enumerate(self.filas):
            y = 34 + fila * 34
            p.setPen(QColor(TEXTO))
            p.drawText(QRectF(10, y, 180, 24), Qt.AlignmentFlag.AlignVCenter, nombre[:24])
            for i, estado in enumerate(dias):
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(colores[estado])
                p.drawRoundedRect(QRectF(200 + i * 20, y + 2, 16, 20), 4, 4)
            p.setPen(QColor(SUAVE))
            p.drawText(QRectF(810, y, 200, 24), Qt.AlignmentFlag.AlignVCenter, f"racha {racha} · 30 d: {cumplimiento}")
        p.end()


class Habitos(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.mapa = MapaHabitos(ctx)
        desplazable = QScrollArea(widgetResizable=True)
        desplazable.setWidget(self.mapa)
        caja = QVBoxLayout(self)
        caja.addWidget(QLabel("Hábitos", objectName="titulo"))
        caja.addWidget(desplazable, 1)

    def refrescar(self):
        self.mapa.cargar()


class Memoria(QWidget):
    def __init__(self, ctx, motor):
        super().__init__()
        self.ctx, self.motor = ctx, motor
        self.buscador = QLineEdit(placeholderText="Buscar en lo que Aria sabe de ti...")
        self.buscador.textChanged.connect(lambda _: QTimer.singleShot(250, self.refrescar))
        self.categoria = QComboBox()
        self.categoria.addItem("Todas las categorías", "")
        for c in CATEGORIAS:
            self.categoria.addItem(c.capitalize(), c)
        self.categoria.currentIndexChanged.connect(self.refrescar)
        self.resumen = QLabel(objectName="subtitulo")
        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(["Id", "Categoría", "Importancia", "Recuerdo"])
        self.tabla.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabla.verticalHeader().hide()
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        olvidar = QPushButton("Olvidar el recuerdo seleccionado")
        olvidar.clicked.connect(self._olvidar)
        caja = QVBoxLayout(self)
        caja.addWidget(QLabel("Memoria", objectName="titulo"))
        caja.addWidget(_contenedor(self.buscador, self.categoria, horizontal=True))
        caja.addWidget(self.resumen)
        caja.addWidget(self.tabla, 1)
        caja.addWidget(olvidar, 0, Qt.AlignmentFlag.AlignRight)

    def refrescar(self):
        memoria = self.ctx.memoria
        texto, categoria = self.buscador.text().strip(), self.categoria.currentData() or ""
        recuerdos = memoria.buscar(texto, 200, categoria) if texto else memoria.todos(categoria)
        self.tabla.setRowCount(len(recuerdos))
        for fila, r in enumerate(recuerdos):
            for columna, valor in enumerate((r.id, r.categoria, f"{r.importancia}/5", r.texto)):
                self.tabla.setItem(fila, columna, QTableWidgetItem(str(valor)))
        self.tabla.resizeColumnsToContents()
        self.tabla.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        por_categoria = {}
        for r in memoria.todos():
            por_categoria[r.categoria] = por_categoria.get(r.categoria, 0) + 1
        self.resumen.setText(f"Aria sabe {memoria.contar()} cosas de ti: "
                             + ", ".join(f"{c} {n}" for c, n in sorted(por_categoria.items(), key=lambda x: -x[1])))

    def _olvidar(self):
        fila = self.tabla.currentRow()
        if fila < 0 or self.motor.ocupado:
            return
        id_memoria = int(self.tabla.item(fila, 0).text())
        texto = self.tabla.item(fila, 3).text()
        if QMessageBox.question(self, "Olvidar", f"¿Seguro que quieres que Aria olvide esto?\n\n{texto}") \
                == QMessageBox.StandardButton.Yes:
            self.ctx.memoria.olvidar(id_memoria)
            self.refrescar()


class VentanaPrincipal(QMainWindow):
    def __init__(self, ctx, motor):
        super().__init__()
        self.setWindowTitle(config.NOMBRE_ASISTENTE)
        self.resize(1150, 760)
        self.pestanas = QTabWidget()
        self.chat = Chat(motor)
        from aria.interfaz.red import PestanaRed
        self.paneles = {"Hoy": Hoy(ctx, motor), "Proyectos": Proyectos(ctx, motor), "Salud": Salud(ctx),
                        "Hábitos": Habitos(ctx), "Memoria": Memoria(ctx, motor),
                        "Mi red": PestanaRed(ctx, motor.asistente.registro)}
        self.pestanas.addTab(self.chat, "Chat")
        for nombre, panel in self.paneles.items():
            self.pestanas.addTab(panel, nombre)
        self.pestanas.currentChanged.connect(self._refrescar_visible)
        self.setCentralWidget(self.pestanas)
        motor.datos_cambiados.connect(self._refrescar_visible)
        self.motor = motor

    def _refrescar_visible(self, *_):
        panel = self.pestanas.currentWidget()
        if hasattr(panel, "refrescar") and not self.motor.ocupado:
            try:
                panel.refrescar()
            except Exception as e:
                print(f"[interfaz] No he podido refrescar el panel: {e}")

    def showEvent(self, e):
        super().showEvent(e)
        aplicar_barra_titulo(self)  # barra de arriba en arena
        self._refrescar_visible()

    def closeEvent(self, e):
        e.ignore()   # cerrar la ventana solo la oculta: Aria sigue en la mascota y en la bandeja
        self.hide()
