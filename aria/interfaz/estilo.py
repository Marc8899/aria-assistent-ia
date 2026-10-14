# Colores y hoja de estilos de la app: la misma estética oscura del panel lateral en toda la app.
# Paleta del usuario: arena #EEC170 (todo el texto), naranjas #F2A65A / #F58549 (acentos)
# La barra de título de la ventana va en arena con el texto oscuro.
ARENA = "#EEC170"          # todo el texto
ARENA_SUAVE = "#BFA374"    # texto secundario (el mismo arena, más apagado)
NARANJA_CLARO = "#F2A65A"
NARANJA = "#F58549"        # lo marcado, las barras, lo importante
OXIDO = "#772F1A"          # ya no se usa en la interfaz

NEGRO_CLARO = "#2B2B30"    # fondo
NEGRO_MEDIO = "#222226"    # cajas, listas, gráficas
NEGRO_BORDE = "#3E3E45"    # bordes
BOTON = "#3A3A40"
BOTON_ENCIMA = "#4A4A52"

# Nombres usados por otros módulos
TEXTO, SUAVE = ARENA, ARENA_SUAVE

# Estados de la mascota (se ven bien sobre cualquier escritorio)
COLORES_ESTADO = {
    "inactivo": "#5CE1E6",    # cian: esperando
    "escuchando": "#FF5C7A",  # rojo-rosa: grabando tu voz
    "pensando": "#FFC94D",    # amarillo: el modelo está trabajando
    "hablando": "#6EF29A",    # verde: hablando
}
TEXTO_ESTADO = {"inactivo": "Lista", "escuchando": "Te escucho...", "pensando": "Pensando...", "hablando": "Hablando..."}

HOJA = f"""
QWidget {{ background: {NEGRO_CLARO}; color: {ARENA}; font-family: 'Segoe UI'; font-size: 10.5pt; }}
QMainWindow, QDialog, QMessageBox {{ background: {NEGRO_CLARO}; }}
QTabWidget::pane {{ border: none; top: 0px; background: {NEGRO_CLARO}; }}
QTabBar {{ background: {NEGRO_CLARO}; }}
QTabBar::tab {{ background: transparent; color: {ARENA_SUAVE}; padding: 9px 18px; margin: 6px 3px 8px 0px;
               border: 1px solid transparent; border-radius: 12px; font-weight: 600; }}
QTabBar::tab:selected {{ background: {BOTON}; color: {ARENA}; border-color: {NEGRO_BORDE}; }}
QTabBar::tab:hover:!selected {{ background: {NEGRO_MEDIO}; color: {ARENA}; }}
QLineEdit, QComboBox {{ background: {NEGRO_MEDIO}; color: {ARENA}; border: 1px solid {NEGRO_BORDE};
                        border-radius: 12px; padding: 8px; selection-background-color: {NARANJA}; }}
QLineEdit:focus, QComboBox:focus {{ border-color: {ARENA}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: {NEGRO_MEDIO}; color: {ARENA}; border: 1px solid {NEGRO_BORDE};
                               selection-background-color: {BOTON}; outline: none; }}
QTextBrowser, QListWidget, QTableWidget, QScrollArea {{ background: {NEGRO_MEDIO}; color: {ARENA};
    border: 1px solid {NEGRO_BORDE}; border-radius: 14px; padding: 6px; outline: none; }}
QScrollArea > QWidget > QWidget {{ background: {NEGRO_MEDIO}; }}
QListWidget::item {{ padding: 7px; border-radius: 8px; margin: 1px; }}
QListWidget::item:hover {{ background: {NEGRO_CLARO}; }}
QListWidget::item:selected {{ background: {BOTON}; color: {ARENA}; }}
QListWidget::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 2px solid {ARENA}; background: transparent; }}
QListWidget::indicator:checked {{ background: {NARANJA}; border-color: {NARANJA}; }}
QPushButton {{ background: {BOTON}; color: {ARENA}; border: 1px solid {NEGRO_BORDE}; border-radius: 12px;
               padding: 9px 16px; font-weight: 600; }}
QPushButton:hover {{ background: {BOTON_ENCIMA}; border-color: {ARENA}; }}
QPushButton:pressed {{ background: {NEGRO_MEDIO}; }}
QPushButton:disabled {{ color: #6E6656; border-color: {NEGRO_BORDE}; background: {NEGRO_MEDIO}; }}
QPushButton#principal {{ border: 1px solid {ARENA}; }}
QLabel {{ background: transparent; color: {ARENA}; }}
QLabel#titulo {{ font-size: 18pt; font-weight: 300; }}
QLabel#subtitulo {{ color: {ARENA_SUAVE}; }}
QGroupBox {{ background: transparent; border: none; margin-top: 22px; padding-top: 4px;
             font-weight: 700; font-size: 9pt; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 2px; top: 2px; padding: 0; color: {ARENA}; }}
QHeaderView::section {{ background: {NEGRO_MEDIO}; color: {ARENA_SUAVE}; border: none;
                        border-bottom: 1px solid {NEGRO_BORDE}; padding: 6px; font-weight: 700; }}
QTableWidget {{ gridline-color: {NEGRO_BORDE}; }}
QTableWidget::item:selected {{ background: {BOTON}; color: {ARENA}; }}
QTableCornerButton::section {{ background: {NEGRO_MEDIO}; border: none; }}
QProgressBar {{ background: {NEGRO_MEDIO}; color: {ARENA}; border: 1px solid {NEGRO_BORDE}; border-radius: 9px;
                height: 16px; text-align: center; font-weight: 600; }}
QProgressBar::chunk {{ background: {NARANJA}; border-radius: 8px; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 0; }}
QScrollBar::handle:vertical {{ background: {BOTON_ENCIMA}; border-radius: 4px; min-height: 24px; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0 4px; }}
QScrollBar::handle:horizontal {{ background: {BOTON_ENCIMA}; border-radius: 4px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ width: 0; height: 0; background: none; }}
QMenu {{ background: {NEGRO_MEDIO}; color: {ARENA}; border: 1px solid {NEGRO_BORDE}; border-radius: 10px; padding: 5px; }}
QMenu::item {{ padding: 7px 20px; border-radius: 7px; }}
QMenu::item:selected {{ background: {BOTON}; }}
QMenu::separator {{ height: 1px; background: {NEGRO_BORDE}; margin: 4px 8px; }}
QToolTip {{ background: {NEGRO_MEDIO}; color: {ARENA}; border: 1px solid {NEGRO_BORDE}; padding: 6px; border-radius: 8px; }}
"""


def _colorref(hexadecimal: str) -> int:
    """'#RRGGBB' -> COLORREF de Windows (0x00BBGGRR)."""
    r, g, b = int(hexadecimal[1:3], 16), int(hexadecimal[3:5], 16), int(hexadecimal[5:7], 16)
    return (b << 16) | (g << 8) | r


def aplicar_barra_titulo(ventana, fondo: str = ARENA, texto: str = NEGRO_CLARO):
    """Pinta la barra de título nativa (la de 'Aria' y los botones de cerrar). Solo Windows 11."""
    try:
        import ctypes
        hwnd = int(ventana.winId())
        dwm = ctypes.windll.dwmapi
        for atributo, color in ((35, fondo), (36, texto), (34, fondo)):  # título, texto del título, borde
            valor = ctypes.c_int(_colorref(color))
            dwm.DwmSetWindowAttribute(hwnd, atributo, ctypes.byref(valor), ctypes.sizeof(valor))
    except Exception:
        pass  # en Windows 10 la barra se queda con su color normal
