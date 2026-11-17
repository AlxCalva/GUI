
# PoC de interfaz de simulación (referencia visual: DSSIM) — PySide6 / Qt 6

Prueba de concepto de interfaz: ventana principal con menú, barra lateral de bloques y un
área de trabajo con cuadrícula donde se colocan, mueven y conectan bloques con flechas.
Incluye configuración de valores (doble clic), validación de conexiones, ejecución con
ventana de resultado y deshacer (Ctrl+Z).

## Uso del editor
| Acción | Cómo |
|---|---|
| Crear bloque | Clic en un botón de la barra lateral (círculos = señales de entrada) |
| Mover | Arrastrar (se ajusta a la malla) |
| Editar valor | **Doble clic** en un círculo (señal 0-999) o en un triángulo (factor 0-999) |
| Conectar | Botón flecha → arrastrar de un bloque a otro. El botón se **desactiva solo** tras el intento; Esc lo cancela |
| Ejecutar | Botón ▶ (verde): abre una ventana con el resultado |
| Deshacer | **Ctrl+Z** (Cmd+Z en macOS): crear, mover, conectar, editar valor, eliminar |
| Eliminar | Seleccionar y pulsar Supr |

### Reglas de conexión (`circuit_ui/signal_graph.py`)
- Círculo (señal de entrada): solo emite; **no** recibe flechas (círculo→círculo y triángulo→círculo están bloqueados).
- Triángulo (multiplicación): **una sola entrada**; salidas ilimitadas (puede alimentar a n bloques).
- Sin conexiones duplicadas, sin conectar un bloque consigo mismo, sin ciclos.
- Suma y convolución: de momento no disponibles (se rechazan con aviso). La suma admitirá varias entradas.
- Al conectar una señal a un triángulo se pide el factor; si se cancela, no se crea la flecha.

### Ejecución
Cada triángulo sin flechas de salida es una salida: resultado = señal × factores a lo largo del camino.
Se avisa (sin ejecutar) si hay un triángulo sin entrada, ciclos o bloques no disponibles; una señal sin conectar solo genera una advertencia.

## Requisitos
- Python 3.9 o superior (probado el código con sintaxis de 3.9+; se recomienda 3.11/3.12)
- PySide6 6.5 o superior (único paquete externo)

## Instalación y ejecución en Windows (PowerShell)

```powershell
cd ruta\a\dssim_poc

# 1) Entorno virtual
python -m venv .venv
.venv\Scripts\Activate.ps1
#    Si PowerShell bloquea el script:  Set-ExecutionPolicy -Scope Process RemoteSigned
#    (en cmd.exe:  .venv\Scripts\activate.bat)

# 2) Dependencias
python -m pip install --upgrade pip
pip install -r requirements.txt

# 3) Verificar que las imágenes se cargan (sin abrir la ventana)
python main.py --check-assets
#    Salida esperada:
#    OK  component_1.png: 50x50 px
#    OK  component_2.png: 50x50 px

# 4) Ejecutar
python main.py
```

Si falta una imagen o está dañada, la aplicación **no la sustituye**: muestra un cuadro de
error con la ruta exacta y cómo corregirla (y lo imprime en la consola).

## Linux / macOS (compatibilidad futura)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py --check-assets && python main.py
```
- Todas las rutas se construyen con `pathlib` relativas al proyecto; no hay rutas absolutas.
- Se fuerza el estilo `Fusion` y `setNativeMenuBar(False)` para que el aspecto sea el mismo
  en los tres sistemas (en macOS el menú queda dentro de la ventana, como en la referencia).
- Las fuentes del QSS tienen lista de respaldo (`Segoe UI`, `Helvetica Neue`, `Noto Sans`, `Arial`).
- En Linux con Wayland, si hay problemas de plugin: `QT_QPA_PLATFORM=xcb python main.py`.
- Si más adelante se empaqueta (PyInstaller), habrá que incluir `assets/` como datos y
  ajustar `ASSETS_DIR` en `circuit_ui/assets.py` (usar `sys._MEIPASS`).

## Estructura
```
dssim_poc/
├── main.py                  # arranque, manejo de error de recursos, --check-assets
├── requirements.txt
├── assets/
│   ├── component_1.png      # = func.png original (1 / (1 - z^-1))
│   └── component_2.png      # = sin.png original (onda senoidal)
├── circuit_ui/
│   ├── main_window.py       # QMainWindow, menú (Project/Analysis/View/Plot), composición
│   ├── sidebar.py           # ComponentSidebar: 2 QToolButton; emite component_requested
│   ├── editor_view.py       # GridScene (cuadrícula) + EditorView (QGraphicsView)
│   ├── circle_item.py       # CircleItem (QGraphicsEllipseItem)
│   ├── placement.py         # algoritmo de colocación en espiral (Python puro, sin Qt)
│   ├── assets.py            # carga de PNG con errores claros
│   └── styles.py            # QSS
└── tests/test_placement.py  # pruebas unitarias de la colocación
```

## Arquitectura (resumen)
- **MainWindow** compone: menú → `[ComponentSidebar (ancho fijo 74 px) | columna de trabajo]`.
  Solo la columna de trabajo se estira al redimensionar.
- **ComponentSidebar** no conoce el editor: emite una señal; `MainWindow` la conecta a
  `EditorView.add_circle()`. Ambos botones ejecutan la misma acción.
- **GridScene.drawBackground** dibuja las líneas cada 20 unidades de escena, en coordenadas
  de escena (no es una imagen). La vista ancla el origen arriba-izquierda, así la cuadrícula no
  se mueve al redimensionar. Escena de 4000×3000 → barras de desplazamiento si la ventana es menor.
- **Círculos**: `QGraphicsEllipseItem` de 40 px, contorno negro de 1,5 px, relleno blanco,
  añadidos con `scene.addItem` (no son widgets). Su posición es su centro.
- **Colocación** (`placement.py`): se toma el centro del área visible, se ajusta a la malla y
  se recorre una espiral de posiciones separadas 60 px (círculo de 40 + 20 de hueco). Se elige
  la primera dentro del área visible y no ocupada; si el área visible está llena, se usa la
  más cercana libre en la escena.

## Pruebas
```
python -m unittest discover -s tests -v
```
Ver el informe de pruebas realizadas y limitaciones en la entrega.

## Limitaciones conocidas
- Los menús de la barra superior están vacíos (solo apariencia).
- Sin rehacer (Redo) ni guardar/abrir proyecto.
- Valores solo enteros de 0 a 999 (constantes `MAX_DIGITS` / `MIN_VALUE` en `signal_graph.py`).
- Escena finita (4000×3000): tras ~3000 círculos el nuevo se crea en el centro aunque se solape.
- Se incluye un rótulo estático «New Project» (presente en la referencia); para quitarlo,
  borra `PROJECT_TITLE` y su `QLabel` en `main_window.py`.
- No hay zoom ni autodesplazamiento: si el usuario se desplaza, los círculos nuevos aparecen
  en la zona que está viendo.

