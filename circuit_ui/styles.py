"""Hoja de estilos QSS inspirada en DSSIM (grises, botones azules biselados, menú claro)."""

STYLESHEET = """
QMainWindow, QWidget#Central, QWidget#WorkColumn {
    background: #AAAAAA;
}

/* ---- Barra de menús ---- */
QMenuBar {
    background: #EDEDED;
    color: #000000;
    font-family: "Segoe UI", "Helvetica Neue", "Noto Sans", Arial, sans-serif;
    font-size: 13px;
    font-weight: 600;
    border-bottom: 1px solid #C4C4C4;
    padding: 1px 4px;
}
QMenuBar::item { background: transparent; padding: 4px 8px; }
QMenuBar::item:selected { background: #CFE0F5; }
QMenuBar::item:pressed  { background: #A9C7EE; }

/* ---- Barra lateral ---- */
QFrame#Sidebar {
    background: #B0B0B0;
    border: none;
    border-right: 1px solid #8A8A8A;
}

/* ---- Botones de componentes: marco azul biselado + interior blanco ---- */
QToolButton#ComponentButton {
    background: #FFFFFF;
    border-style: solid;
    border-width: 3px;
    border-top-color: #9DBDF6;
    border-left-color: #8DB0EC;
    border-right-color: #5C90D2;
    border-bottom-color: #4382CE;
    border-radius: 2px;
}
QToolButton#ComponentButton:hover {
    background: #EEF5FF;
    border-top-color: #BBD3FA;
    border-left-color: #A9C6F4;
    border-right-color: #78A5E0;
    border-bottom-color: #5C93DA;
}
QToolButton#ComponentButton:pressed {
    background: #D3E4FA;
    border-top-color: #4382CE;       /* bisel invertido = efecto hundido */
    border-left-color: #5C90D2;
    border-right-color: #8DB0EC;
    border-bottom-color: #9DBDF6;
}

/* ---- Cabecera y área de trabajo ---- */
QLabel#ProjectTitle {
    color: #2A2A2A;
    font-family: "Segoe UI", "Helvetica Neue", "Noto Sans", Arial, sans-serif;
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}
QGraphicsView#Workspace {
    background: #FFFFFF;
    border: 1px solid #7C7C7C;
}
"""
