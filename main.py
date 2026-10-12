"""
ABISMO DE SANGRE  -  FPS de terror con raycasting (pseudo 3D) en Pygame.
Código original, escrito desde cero.

CONTROLES
    W A S D ............ moverte            SHIFT ......... correr (gasta energía)
    Mouse .............. girar y apuntar ARRIBA / ABAJO
    Q / E .............. mirar arriba / abajo con el teclado      C .. centrar la mira
    Clic izq. / ESPACIO  disparar           1-6 o rueda ... cambiar de arma
    Clic DERECHO ....... apuntar con la mira óptica del arma (zoom)
    F (mantener) ....... activar generador / antena      M ... mapa ampliado (planeta Tierra, modelo 2026)
    EN EL MAPA ......... arrastrar = girar el planeta / mover el plano      rueda o +/- = zoom
                         clic = marcar un punto (clic encima = quitarlo)    C = centrar    SUPR = borrar marcas
                         Z = deshacer última marca    botón SOL REAL / LUZ FIJA = día y noche de la hora actual o iluminación fija
    P .................. dejar / quitar un punto donde estás (se ve en pantalla con su distancia)
    TAB ................ mostrar / ocultar el minimapa     ESC .. pausa

OBJETIVO
    Cada nivel es una cadena de misiones (eliminar infectados, recuperar objetos, activar
    equipos, conseguir la tarjeta de acceso) y termina llegando a la zona de extracción.
    La flecha amarilla de arriba te indica hacia dónde ir.

    * Disparo a la CABEZA = daño x2.5 (francotirador x3.5). Al apuntar con zoom el centro de
      la pantalla es mucho más preciso.
    * En ACCESORIOS (menú principal) compras miras ópticas, láser, silenciador y cargadores.

MÓVIL (Android / Pydroid 3, o en PC con:  python prueba_movil.py --movil)
    Joystick izquierdo ..... moverte (analógico)    Arrastrar en cualquier zona libre ... mirar
    Botones en pantalla .... FUEGO, MIRA (zoom), CORRER, ACTIVAR, cambiar arma, MAPA, RADAR, PAUSA
    Menú principal > CONTROLES (o PAUSA > CONTROLES) para mover, agrandar, ocultar y reasignar
    cada botón, y ajustar opacidad y sensibilidad. Todo se guarda solo.

AJUSTES GRÁFICOS (menú principal > AJUSTES, o PAUSA > AJUSTES)
    Perfiles BAJA / MEDIA / ALTA / ULTRA y control fino: detalle de paredes, distancia de dibujo,
    calidad de texturas, filtro suave, niebla, brillo, viñeta, límite de FPS y auto-ajuste de
    resolución (baja el detalle solo si el móvil va lento). Desde la pausa se ve el cambio en vivo.

Música opcional: si junto a este archivo (o en C:\\python) existe
"musica de fondo.mp3", suena de fondo. Si no, se usa un ambiente de terror sintetizado.
"""
import array
import datetime
import json
import math
import os
import random
import sys
from collections import deque

import pygame

# ===========================================================================
# 1. INICIALIZACIÓN
# ===========================================================================
pygame.init()
try:
    pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
    pygame.mixer.set_num_channels(16)
    AUDIO_OK = True
except pygame.error:
    AUDIO_OK = False

ANDROID = "ANDROID_ROOT" in os.environ or hasattr(sys, "getandroidapilevel")
MOVIL = ANDROID or sys.platform == "emscripten" or "--movil" in sys.argv
TECLA_ATRAS = getattr(pygame, "K_AC_BACK", pygame.K_ESCAPE)     # botón "atrás" de Android

if MOVIL:
    # En el móvil se renderiza a menor resolución (más fluido) con la proporción real de la pantalla;
    # SCALED la estira a pantalla completa, así los toques coinciden con lo que se dibuja.
    try:
        _w, _h = pygame.display.get_desktop_sizes()[0]
    except Exception:
        _inf = pygame.display.Info()
        _w, _h = _inf.current_w, _inf.current_h
    if not ANDROID:
        _w, _h = 2100, 1000                  # prueba en PC: ventana con forma de teléfono
    if _h > _w:
        _w, _h = _h, _w
    ALTO = 450
    ANCHO = max(600, min(1100, int(ALTO * _w / max(1, _h))))
    ESCALA = 6
else:
    ANCHO, ALTO = 1366, 760
    ESCALA = 5                              # ancho en píxeles de cada columna de pared
NUM_RAYOS = -(-ANCHO // ESCALA)             # 274 rayos: cubren todo el ancho (1366 no es múltiplo de 5)
UI = ALTO / 600.0                           # factor de escala de la interfaz (el diseño base era 800x600)
# El FOV horizontal se calcula con la proporción de la pantalla: así las paredes y los infectados
# no se ven estirados. Mantiene el mismo FOV vertical que tenía el juego en 800x600.
FOV = 2 * math.atan(math.tan(math.radians(33)) * (ANCHO / ALTO) / (800 / 600))


def K(v):
    """Escala una medida del diseño original (800x600) a la resolución actual."""
    return int(round(v * UI))


def X(v):
    """Posición horizontal del diseño original (800 de ancho) centrada en la pantalla actual."""
    return ANCHO // 2 + K(v - 400)


def Y(v):
    """Posición vertical del diseño original (600 de alto) en la pantalla actual."""
    return K(v)


TEX = 64
MAX_PROF = 24
FPS = 60
PITCH_MAX = int(220 * ALTO / 760)                     # máximo de inclinación de la mira (en píxeles)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if ANDROID:
    try:
        pantalla = pygame.display.set_mode((ANCHO, ALTO), pygame.FULLSCREEN | pygame.SCALED)
    except pygame.error:
        pantalla = pygame.display.set_mode((ANCHO, ALTO))
else:
    pantalla = pygame.display.set_mode((ANCHO, ALTO))
pygame.display.set_caption("ABISMO DE SANGRE")
reloj = pygame.time.Clock()


def _fuente_horror(tam):
    try:
        return pygame.font.SysFont("impact,georgia,timesnewroman", tam)
    except Exception:
        return pygame.font.Font(None, tam)


FUENTE_TITULO = _fuente_horror(K(84))
FUENTE_BOTON = _fuente_horror(K(32))
FUENTE_G = pygame.font.Font(None, K(84))
FUENTE_M = pygame.font.Font(None, K(34))
FUENTE_P = pygame.font.Font(None, K(24))
FUENTE_XS = pygame.font.Font(None, K(20))


def texto(txt, fuente, color, pos, centro=False):
    s = fuente.render(txt, True, color)
    r = s.get_rect(center=pos) if centro else s.get_rect(topleft=pos)
    pantalla.blit(s, r)


try:
    import android as _android            # solo existe dentro del APK (python-for-android)
except ImportError:
    _android = None


def ciclo_android():
    """Si Android manda la app al fondo: guarda y espera a que vuelva (evita cierres y gasto de batería)."""
    if _android is None:
        return
    try:
        if _android.check_pause():
            guardar_datos()
            _android.wait_for_resume()
            reloj.tick()                      # descarta el tiempo que estuvo en segundo plano
            try:
                TOQUE.reiniciar()
            except NameError:
                pass
    except Exception:
        pass


def salir():
    guardar_datos()
    pygame.quit()
    sys.exit()


# ===========================================================================
# 2. DATOS GUARDADOS (monedas, armas compradas, nivel, personalización)
# ===========================================================================
def _carpeta_datos():
    """En Android la carpeta de la app se reemplaza al actualizar: el guardado va en el almacenamiento privado."""
    if ANDROID:
        base = os.environ.get("ANDROID_PRIVATE") or os.environ.get("ANDROID_ARGUMENT") or BASE_DIR
        if os.access(base, os.W_OK):
            return base
    return BASE_DIR


ARCHIVO_GUARDADO = os.path.join(_carpeta_datos(), "guardado_abismo.json")
_ANTIGUO = os.path.join(BASE_DIR, "guardado_abismo.json")
if ARCHIVO_GUARDADO != _ANTIGUO and not os.path.isfile(ARCHIVO_GUARDADO) and os.path.isfile(_ANTIGUO):
    try:                                       # migra un guardado anterior, si existía
        import shutil
        shutil.copyfile(_ANTIGUO, ARCHIVO_GUARDADO)
    except OSError:
        pass
DATOS = {
    "monedas": 0,
    "nivel_max": 1,
    "armas": ["pistola"],
    "equipada": "pistola",
    "skins": [0],
    "skin": 0,
    "mira_estilo": 0,
    "mira_color": 0,
    "acc_poseidos": [],          # accesorios comprados (miras, láser, silenciador, cargadores)
    "config": {},                # accesorios equipados en cada arma
    "controles": {},             # disposición de los controles táctiles (móvil)
    "graficos": {},              # ajustes gráficos (calidad, distancia, texturas...)
    "marcas_globo": [],          # puntos marcados por el jugador en el planeta (lat, lon)
}


def cargar_datos():
    try:
        with open(ARCHIVO_GUARDADO, "r", encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return
    for k, v in d.items():
        if k in DATOS and isinstance(v, type(DATOS[k])):
            DATOS[k] = v
    if "pistola" not in DATOS["armas"]:
        DATOS["armas"].insert(0, "pistola")
    if DATOS["equipada"] not in DATOS["armas"]:
        DATOS["equipada"] = "pistola"
    if 0 not in DATOS["skins"]:
        DATOS["skins"].append(0)
    DATOS["acc_poseidos"] = [a for a in DATOS["acc_poseidos"] if isinstance(a, str)]
    DATOS["config"] = {k: v for k, v in DATOS["config"].items() if k in ARMA_POR_ID and isinstance(v, dict)}
    DATOS["marcas_globo"] = [{"lat": float(m["lat"]), "lon": float(m["lon"])} for m in DATOS["marcas_globo"]
                             if isinstance(m, dict) and isinstance(m.get("lat"), (int, float))
                             and isinstance(m.get("lon"), (int, float))][:MAX_MARCAS_GLOBO]


def guardar_datos():
    tmp = ARCHIVO_GUARDADO + ".tmp"
    try:                                       # se escribe a un temporal y se renombra: nunca queda a medias
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(DATOS, f)
        os.replace(tmp, ARCHIVO_GUARDADO)
    except OSError:
        pass


# ===========================================================================
# 3. SONIDOS SINTETIZADOS
# ===========================================================================
FS = 22050


def crear_sonido(duracion, generador):
    if not AUDIO_OK:
        return None
    n = int(FS * duracion)
    buf = array.array('h', [0] * (n * 2))
    for i in range(n):
        v = int(max(-1.0, min(1.0, generador(i / FS))) * 30000)
        buf[i * 2] = v
        buf[i * 2 + 1] = v
    return pygame.mixer.Sound(buf)


def reproducir(snd, volumen=1.0):
    if snd is not None:
        snd.set_volume(volumen)
        snd.play()


def _ruido(t, k):
    return random.uniform(-1, 1) * math.exp(-t * k)


def _tono(f, t, k):
    return math.sin(2 * math.pi * f * t) * math.exp(-t * k)


SONIDOS_ARMA = {
    "pistola": crear_sonido(0.30, lambda t: 0.8 * _ruido(t, 16) + 0.6 * _tono(110, t, 22)),
    "escopeta": crear_sonido(0.50, lambda t: 0.9 * _ruido(t, 9) + 0.7 * _tono(70, t, 12)),
    "rifle": crear_sonido(0.16, lambda t: 0.7 * _ruido(t, 26) + 0.5 * _tono(130, t, 30)),
    "sniper": crear_sonido(0.70, lambda t: 0.9 * _ruido(t, 11) + 0.8 * _tono(60, t, 8)),
    "minigun": crear_sonido(0.09, lambda t: 0.7 * _ruido(t, 40) + 0.5 * _tono(150, t, 45)),
    "cohetes": crear_sonido(0.45, lambda t: 0.6 * _ruido(t, 7) + 0.6 * _tono(90, t, 9)),
}
_lp = {"v": 0.0}


def _trueno(t):
    _lp["v"] = _lp["v"] * 0.97 + random.uniform(-1, 1) * 0.03
    return _lp["v"] * 9 * math.exp(-t * 2.0) * min(1.0, t * 20)


SND_EXPLOSION = crear_sonido(0.9, lambda t: _trueno(t) * 0.9 + 0.5 * _tono(45, t, 4))
SND_TRUENO = crear_sonido(1.6, _trueno)
SND_IMPACTO = crear_sonido(0.12, lambda t: 0.6 * _tono(220, t, 30) + 0.3 * _ruido(t, 40))
SND_MUERTE = crear_sonido(0.60, lambda t: (math.sin(2 * math.pi * 80 * t)
                          + 0.5 * math.sin(2 * math.pi * 160 * t)) * 0.5 * math.exp(-t * 4)
                          + 0.15 * _ruido(t, 6))
SND_DANO = crear_sonido(0.20, lambda t: 0.7 * _tono(150, t, 12))
SND_ITEM = crear_sonido(0.20, lambda t: 0.5 * math.sin(2 * math.pi * (600 if t < 0.08 else 900) * t)
                        * math.exp(-t * 8))
SND_VACIO = crear_sonido(0.05, lambda t: 0.4 * _ruido(t, 80))
SND_CLIC = crear_sonido(0.05, lambda t: 0.5 * _tono(300, t, 60))
SND_COMPRA = crear_sonido(0.35, lambda t: 0.5 * math.sin(2 * math.pi * (500 if t < 0.1 else 750 if t < 0.2 else 1000) * t)
                          * math.exp(-t * 6))
SND_DRONE = crear_sonido(4.0, lambda t: 0.7 * (0.5 * math.sin(2 * math.pi * 55 * t)
                         + 0.5 * math.sin(2 * math.pi * 58 * t)
                         + 0.15 * math.sin(2 * math.pi * 110.25 * t))
                         * (0.6 + 0.4 * math.sin(2 * math.pi * 0.25 * t)))

CANAL_AMBIENTE = pygame.mixer.Channel(7) if AUDIO_OK else None
MUSICA_ARCHIVO = False


def iniciar_musica():
    global MUSICA_ARCHIVO
    if not AUDIO_OK:
        return
    for carpeta in (BASE_DIR, r"C:\python"):
        for nombre in ("musica de fondo.mp3", "musica_de_fondo.mp3"):
            ruta = os.path.join(carpeta, nombre)
            if os.path.isfile(ruta):
                try:
                    pygame.mixer.music.load(ruta)
                    pygame.mixer.music.set_volume(0.25)
                    pygame.mixer.music.play(-1, fade_ms=1500)
                    MUSICA_ARCHIVO = True
                    return
                except pygame.error:
                    pass


def ambiente(volumen_musica, volumen_drone):
    """Ajusta el sonido de fondo: música (si existe) o ambiente de terror."""
    if not AUDIO_OK:
        return
    if MUSICA_ARCHIVO:
        pygame.mixer.music.set_volume(volumen_musica)
    if SND_DRONE is not None and CANAL_AMBIENTE is not None:
        if not CANAL_AMBIENTE.get_busy():
            CANAL_AMBIENTE.play(SND_DRONE, loops=-1)
        CANAL_AMBIENTE.set_volume(volumen_drone * (0.4 if MUSICA_ARCHIVO else 1.0))


def ambiente_menu():
    ambiente(0.30, 0.40)


def ambiente_juego():
    ambiente(0.10, 0.14)

# ===========================================================================
# 4. ARMAS Y PERSONALIZACIÓN
# ===========================================================================
ARMAS = [
    {"id": "pistola", "nombre": "PISTOLA", "dano": 28, "cadencia": 0.35, "perdigones": 1,
     "dispersion": 0.0, "precio": 0, "municion": 80, "recogida": 20, "retroceso": 1.0, "flash": 0.07},
    {"id": "escopeta", "nombre": "ESCOPETA", "dano": 16, "cadencia": 0.85, "perdigones": 8,
     "dispersion": 0.09, "precio": 600, "municion": 30, "recogida": 8, "retroceso": 1.6, "flash": 0.10},
    {"id": "rifle", "nombre": "RIFLE DE ASALTO", "dano": 24, "cadencia": 0.11, "perdigones": 1,
     "dispersion": 0.012, "precio": 1500, "municion": 150, "recogida": 40, "retroceso": 0.5, "flash": 0.05},
    {"id": "sniper", "nombre": "FRANCOTIRADOR", "dano": 140, "cadencia": 1.10, "perdigones": 1,
     "dispersion": 0.0, "precio": 2500, "municion": 25, "recogida": 6, "retroceso": 1.8, "flash": 0.08,
     "mult_cabeza": 3.5},
    {"id": "minigun", "nombre": "MINIGUN", "dano": 15, "cadencia": 0.055, "perdigones": 1,
     "dispersion": 0.03, "precio": 4000, "municion": 400, "recogida": 100, "retroceso": 0.3, "flash": 0.04},
    {"id": "cohetes", "nombre": "LANZACOHETES", "dano": 200, "cadencia": 1.30, "perdigones": 1,
     "dispersion": 0.0, "precio": 6500, "municion": 12, "recogida": 3, "retroceso": 2.0, "flash": 0.12,
     "explosivo": 2.6},
]
ARMA_POR_ID = {a["id"]: a for a in ARMAS}
MULT_CABEZA = 2.5

SKINS_ARMA = [
    ("Acero", (88, 88, 96), 0),
    ("Negro", (32, 32, 36), 200),
    ("Hueso", (215, 205, 170), 400),
    ("Verde militar", (60, 92, 52), 300),
    ("Rojo sangre", (150, 20, 20), 300),
    ("Cian neón", (0, 200, 230), 800),
    ("Oro", (212, 175, 55), 1200),
]
COLORES_MIRA = [(255, 255, 255), (60, 255, 80), (255, 60, 60), (60, 200, 255), (255, 220, 60), (255, 60, 220)]
ESTILOS_MIRA = ["CRUZ", "PUNTO", "CÍRCULO", "EQUIS"]


def dibujar_mira(cx, cy, estilo, color, hueco=3):
    if estilo == 0:
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            pygame.draw.line(pantalla, color, (cx + dx * (hueco + 1), cy + dy * (hueco + 1)),
                             (cx + dx * (hueco + 8), cy + dy * (hueco + 8)), 2)
    elif estilo == 1:
        pygame.draw.circle(pantalla, color, (cx, cy), 3)
    elif estilo == 2:
        pygame.draw.circle(pantalla, color, (cx, cy), 9, 2)
        pygame.draw.circle(pantalla, color, (cx, cy), 1)
    else:
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            pygame.draw.line(pantalla, color, (cx + dx * 3, cy + dy * 3), (cx + dx * 9, cy + dy * 9), 2)


def crear_sprite_arma(id_arma, cuerpo):
    """Dibuja el arma en primera persona (300x300)."""
    s = pygame.Surface((300, 300), pygame.SRCALPHA)
    oscuro, madera, mano = (48, 48, 54), (110, 70, 40), (212, 162, 126)
    claro = tuple(min(255, c + 35) for c in cuerpo)
    if id_arma == "pistola":
        pygame.draw.rect(s, oscuro, (130, 50, 40, 120), border_radius=6)
        pygame.draw.rect(s, (25, 25, 28), (138, 38, 24, 28), border_radius=4)
        pygame.draw.rect(s, cuerpo, (118, 150, 64, 100), border_radius=8)
        pygame.draw.rect(s, claro, (124, 156, 8, 80), border_radius=3)
        pygame.draw.rect(s, madera, (126, 235, 48, 65), border_radius=8)
    elif id_arma == "escopeta":
        pygame.draw.rect(s, oscuro, (138, 0, 24, 190), border_radius=4)
        pygame.draw.rect(s, (30, 30, 34), (146, 40, 8, 150))
        pygame.draw.rect(s, madera, (124, 120, 52, 44), border_radius=5)
        pygame.draw.rect(s, cuerpo, (120, 180, 60, 100), border_radius=8)
        pygame.draw.rect(s, claro, (126, 186, 8, 70), border_radius=3)
        pygame.draw.rect(s, madera, (128, 255, 44, 45), border_radius=6)
    elif id_arma == "rifle":
        pygame.draw.rect(s, oscuro, (142, 10, 16, 150))
        pygame.draw.rect(s, (25, 25, 28), (146, 0, 8, 16))
        pygame.draw.rect(s, (40, 40, 44), (128, 90, 44, 80), border_radius=4)
        pygame.draw.rect(s, cuerpo, (120, 160, 60, 110), border_radius=8)
        pygame.draw.rect(s, claro, (126, 166, 8, 90), border_radius=3)
        pygame.draw.rect(s, (24, 24, 28), (134, 245, 32, 55), border_radius=4)
    elif id_arma == "sniper":
        pygame.draw.rect(s, oscuro, (144, 0, 12, 200))
        pygame.draw.rect(s, (25, 25, 28), (140, 0, 20, 24), border_radius=3)
        pygame.draw.rect(s, (20, 20, 24), (128, 80, 44, 28), border_radius=5)
        pygame.draw.circle(s, (70, 200, 230), (150, 94), 8)
        pygame.draw.rect(s, (130, 130, 140), (132, 76, 6, 36))
        pygame.draw.rect(s, (130, 130, 140), (162, 76, 6, 36))
        pygame.draw.rect(s, cuerpo, (124, 170, 52, 110), border_radius=8)
        pygame.draw.rect(s, claro, (129, 176, 7, 90), border_radius=3)
        pygame.draw.rect(s, madera, (130, 262, 40, 38), border_radius=5)
    elif id_arma == "minigun":
        for i in range(6):
            pygame.draw.rect(s, (72, 72, 78), (104 + i * 15, 10, 9, 150))
        pygame.draw.rect(s, (50, 50, 55), (98, 50, 104, 10))
        pygame.draw.rect(s, (50, 50, 55), (98, 110, 104, 10))
        pygame.draw.rect(s, cuerpo, (100, 160, 100, 110), border_radius=10)
        pygame.draw.rect(s, claro, (108, 168, 10, 90), border_radius=3)
        pygame.draw.rect(s, (200, 170, 40), (206, 190, 22, 80))
        pygame.draw.rect(s, (30, 30, 34), (140, 262, 26, 38))
    else:  # cohetes
        pygame.draw.rect(s, cuerpo, (104, 20, 92, 190), border_radius=12)
        pygame.draw.rect(s, claro, (112, 30, 10, 160), border_radius=4)
        pygame.draw.ellipse(s, (25, 25, 28), (104, 8, 92, 30))
        pygame.draw.polygon(s, (190, 45, 40), [(150, 4), (130, 32), (170, 32)])
        pygame.draw.rect(s, (30, 30, 34), (176, 60, 22, 30))
        pygame.draw.rect(s, (30, 30, 34), (136, 210, 28, 90))
    pygame.draw.ellipse(s, mano, (104, 240, 92, 60))
    return s


_CACHE_ARMAS = {}


def obtener_sprite_arma(id_arma, skin):
    clave = (id_arma, skin)
    if clave not in _CACHE_ARMAS:
        _CACHE_ARMAS[clave] = crear_sprite_arma(id_arma, SKINS_ARMA[skin][1])
    return _CACHE_ARMAS[clave]


def crear_flash():
    s = pygame.Surface((200, 200), pygame.SRCALPHA)
    for r, a in ((100, 40), (70, 90), (42, 170), (20, 255)):
        pygame.draw.circle(s, (255, 205, 70, a), (100, 100), r)
    return s


FLASH = crear_flash()


# ---------------------------------------------------------------------------
# 4.1  ACCESORIOS (miras ópticas, láser, silenciador, cargador extendido)
# ---------------------------------------------------------------------------
_EXTRA_ARMA = {            # id: (movilidad, dispersión al disparar "desde la cadera")
    "pistola": (1.00, 0.012), "escopeta": (0.95, 0.0), "rifle": (0.92, 0.030),
    "sniper": (0.88, 0.060), "minigun": (0.78, 0.035), "cohetes": (0.84, 0.0),
}
for _a in ARMAS:
    _a["vel"], _a["hip"] = _EXTRA_ARMA[_a["id"]]

MIRAS = {
    "mira_hierro": {"nombre": "Mira de hierro", "zoom": 1.20},
    "mira_punto": {"nombre": "Punto rojo", "zoom": 1.35},
    "mira_holo2": {"nombre": "Holográfica x2", "zoom": 2.0},
    "mira_holo3": {"nombre": "Holográfica x3", "zoom": 3.0},
    "mira_holo4": {"nombre": "Holográfica x4", "zoom": 4.0},
    "mira_tele": {"nombre": "Telescópica x3.5", "zoom": 3.5},
}
ORDEN_MIRAS = ["mira_hierro", "mira_punto", "mira_holo2", "mira_holo3", "mira_holo4", "mira_tele"]
MIRA_DEFECTO = {"sniper": "mira_tele"}          # el francotirador ya trae su telescópica
SIN_SILENCIADOR = {"cohetes"}
PRECIOS_ACC = {"mira_punto": 250, "mira_holo2": 600, "mira_holo3": 900, "mira_holo4": 1300,
               "mira_tele": 1800, "laser_1": 400, "laser_2": 900, "silenciador": 700,
               "cargador_1": 500, "cargador_2": 1100}
_MULT_CARGADOR = (1.0, 1.5, 2.0)
_MULT_LASER = (1.0, 0.6, 0.35)


def acc_gratis(id_arma, acc):
    return acc == "mira_hierro" or MIRA_DEFECTO.get(id_arma) == acc


def acc_disponible(id_arma, acc):
    return acc_gratis(id_arma, acc) or acc in DATOS["acc_poseidos"]


def config_arma(id_arma):
    """Accesorios equipados en un arma (siempre devuelve valores válidos)."""
    c = DATOS["config"].get(id_arma)
    c = c if isinstance(c, dict) else {}
    defecto = MIRA_DEFECTO.get(id_arma, "mira_hierro")
    mira = c.get("mira", defecto)
    if mira not in MIRAS:
        mira = defecto

    def entero(clave, tope):
        v = c.get(clave, 0)
        return v if isinstance(v, int) and 0 <= v <= tope else 0
    return {"mira": mira, "laser": entero("laser", 2), "silencio": entero("silencio", 1),
            "cargador": entero("cargador", 2)}


def poner_config(id_arma, clave, valor):
    cfg = DATOS["config"].get(id_arma)
    if not isinstance(cfg, dict):
        cfg = DATOS["config"][id_arma] = {}
    cfg[clave] = valor


def stats_arma(id_arma):
    """Estadísticas finales del arma con sus accesorios."""
    a = ARMA_POR_ID[id_arma]
    c = config_arma(id_arma)
    sil = bool(c["silencio"]) and id_arma not in SIN_SILENCIADOR
    return {
        "dano": a["dano"] * (0.88 if sil else 1.0),
        "cadencia": a["cadencia"],
        "retroceso": a["retroceso"],
        "dispersion": a["dispersion"],
        "hip": a["hip"] * _MULT_LASER[c["laser"]],
        "cabeza": a.get("mult_cabeza", MULT_CABEZA),
        "vel": a["vel"],
        "zoom": MIRAS[c["mira"]]["zoom"],
        "mira": c["mira"],
        "laser": c["laser"],
        "silencio": sil,
        "muni": _MULT_CARGADOR[c["cargador"]],
    }


def municion_maxima(id_arma):
    return int(ARMA_POR_ID[id_arma]["municion"] * stats_arma(id_arma)["muni"])


# ---- arma en primera persona (con los accesorios dibujados encima) ----------
_MUZZLE_Y = {"pistola": 38, "escopeta": 0, "rifle": 0, "sniper": 0, "minigun": 10, "cohetes": 4}
_SIGHT_Y = {"pistola": 96, "escopeta": 150, "rifle": 100, "sniper": 94, "minigun": 140, "cohetes": 100}
_POS_LASER = {"pistola": (121, 70), "escopeta": (127, 30), "rifle": (130, 26), "sniper": (132, 20),
              "minigun": (94, 24), "cohetes": (94, 40)}
_POS_CARGADOR = {"pistola": (184, 176), "escopeta": (182, 196), "rifle": (182, 214), "sniper": (178, 196),
                 "minigun": (216, 150), "cohetes": (198, 130)}
_CACHE_FP = {}
_PAD_FP = 70
_ANGULO_FP = 9                                   # el arma se inclina un poco hacia el centro


def _dibujar_mira_sprite(s, tipo, y):
    if tipo == "mira_punto":
        pygame.draw.rect(s, (22, 22, 26), (140, y - 14, 20, 28), border_radius=4)
        pygame.draw.rect(s, (90, 96, 110), (140, y - 14, 20, 28), 2, border_radius=4)
        pygame.draw.circle(s, (255, 60, 50), (150, y), 4)
    elif tipo in ("mira_holo2", "mira_holo3", "mira_holo4"):
        h = {"mira_holo2": 30, "mira_holo3": 40, "mira_holo4": 52}[tipo]
        w = {"mira_holo2": 34, "mira_holo3": 38, "mira_holo4": 42}[tipo]
        pygame.draw.rect(s, (30, 34, 42), (150 - w // 2 - 3, y - h // 2 - 3, w + 6, h + 6), border_radius=6)
        pygame.draw.rect(s, (70, 190, 235), (150 - w // 2, y - h // 2, w, h), border_radius=4)
        pygame.draw.rect(s, (190, 235, 255), (150 - w // 2 + 3, y - h // 2 + 3, 6, h - 6), border_radius=2)
    elif tipo == "mira_tele":
        pygame.draw.rect(s, (28, 30, 36), (140, y - 46, 20, 92), border_radius=6)
        pygame.draw.rect(s, (62, 66, 78), (136, y - 22, 28, 12), border_radius=3)
        pygame.draw.rect(s, (62, 66, 78), (136, y + 10, 28, 12), border_radius=3)
        pygame.draw.circle(s, (70, 200, 230), (150, y - 46), 8)
        pygame.draw.circle(s, (20, 24, 30), (150, y + 46), 9)


def sprite_fp(id_arma):
    """Devuelve (imagen, desplazamiento_de_la_boca) del arma equipada vista en primera persona."""
    cfg = config_arma(id_arma)
    clave = (id_arma, DATOS["skin"], cfg["mira"], cfg["laser"], cfg["silencio"], cfg["cargador"])
    if clave in _CACHE_FP:
        return _CACHE_FP[clave]
    P = _PAD_FP
    base = crear_sprite_arma(id_arma, SKINS_ARMA[DATOS["skin"] % len(SKINS_ARMA)][1])
    s = pygame.Surface((300, 300 + P), pygame.SRCALPHA)
    s.blit(base, (0, P))

    if cfg["cargador"]:                                          # cargador extendido
        x, y = _POS_CARGADOR[id_arma]
        alto = 26 + cfg["cargador"] * 14
        pygame.draw.rect(s, (58, 58, 64), (x, y + P, 13, alto), border_radius=3)
        pygame.draw.rect(s, (200, 170, 40) if cfg["cargador"] == 2 else (120, 120, 130), (x, y + P, 13, 6),
                         border_radius=2)
    if cfg["laser"]:                                             # módulo láser
        x, y = _POS_LASER[id_arma]
        fuerte = cfg["laser"] == 2
        pygame.draw.rect(s, (92, 92, 104) if fuerte else (70, 70, 78), (x, y + P, 11 if fuerte else 9,
                         30 if fuerte else 24), border_radius=2)
        pygame.draw.rect(s, (255, 70, 60) if fuerte else (200, 40, 36), (x + 2, y + P - 3, 6, 5))

    muzzle_y = _MUZZLE_Y[id_arma] + P
    if cfg["silencio"] and id_arma not in SIN_SILENCIADOR:       # silenciador
        pygame.draw.rect(s, (38, 38, 44), (140, muzzle_y - 56, 20, 62), border_radius=4)
        for k in range(4):
            pygame.draw.line(s, (84, 84, 94), (140, muzzle_y - 46 + k * 13), (159, muzzle_y - 46 + k * 13), 2)
        pygame.draw.rect(s, (12, 12, 14), (146, muzzle_y - 58, 8, 4))
        muzzle_y -= 58

    _dibujar_mira_sprite(s, cfg["mira"], _SIGHT_Y[id_arma] + P)

    rot = pygame.transform.rotate(s, _ANGULO_FP)
    th = math.radians(_ANGULO_FP)
    vy = muzzle_y - (300 + P) / 2
    off = (vy * math.sin(th), vy * math.cos(th))
    _CACHE_FP[clave] = (rot, off)
    return _CACHE_FP[clave]


# ===========================================================================
# 5. NIVELES PROCEDURALES  (mapas grandes + misiones encadenadas)
# ===========================================================================
MAPA = [[1]]
COLS = FILAS = 1
OSCURIDAD = 0.9
CELDAS_LIBRES = []
LIMITE_CAMPO = 80                    # alcance (en celdas) del mapa de distancias que usan los infectados

POOL_MISIONES = [("matar", None), ("recoger", "baterías"), ("recoger", "documentos"),
                 ("activar", "el generador"), ("activar", "la antena de radio"),
                 ("llave", "la tarjeta de acceso")]
SPRITE_MISION = {"baterías": "bateria", "documentos": "documento", "el generador": "generador",
                 "la antena de radio": "antena", "la tarjeta de acceso": "llave"}


def tamano_mapa(nivel):
    return min(96, 54 + 2 * nivel)


def total_enemigos(nivel):
    return min(60, 12 + 3 * nivel)


def generar_nivel(nivel):
    rng = random.Random(nivel * 7919 + 13)
    W = H = tamano_mapa(nivel)
    grid = [[1 + ((x // 5 + y // 5 + nivel) % 4) for x in range(W)] for y in range(H)]

    n_salas = min(34, 16 + nivel)
    salas = []
    for _ in range(3000):
        if len(salas) >= n_salas:
            break
        w, h = rng.randint(4, 9), rng.randint(4, 9)
        x, y = rng.randint(2, W - w - 3), rng.randint(2, H - h - 3)
        if any(x < sx + sw + 3 and sx < x + w + 3 and y < sy + sh + 3 and sy < y + h + 3
               for sx, sy, sw, sh in salas):
            continue
        salas.append((x, y, w, h))
    if len(salas) < 4:
        salas = [(3, 3, 6, 6), (W - 10, 3, 6, 6), (3, H - 10, 6, 6), (W - 10, H - 10, 6, 6)]

    celdas_sala = []
    for (x, y, w, h) in salas:
        celdas = []
        for j in range(y, y + h):
            for i in range(x, x + w):
                grid[j][i] = 0
                celdas.append((i, j))
        celdas_sala.append(celdas)
    for (x, y, w, h) in salas:                     # pilares en las esquinas de salas grandes
        if w >= 7 and h >= 7:
            for (i, j) in ((x + 1, y + 1), (x + w - 2, y + 1), (x + 1, y + h - 2), (x + w - 2, y + h - 2)):
                grid[j][i] = 2 + rng.randint(0, 2)

    centros = [(x + w // 2, y + h // 2) for (x, y, w, h) in salas]

    def abrir(x, y):                                # pasillos de 2 celdas de ancho
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            xx, yy = x + dx, y + dy
            if 1 <= xx < W - 1 and 1 <= yy < H - 1:
                grid[yy][xx] = 0

    def tunel(a, b):
        (x0, y0), (x1, y1) = a, b
        if rng.random() < 0.5:
            for x in range(min(x0, x1), max(x0, x1) + 1):
                abrir(x, y0)
            for y in range(min(y0, y1), max(y0, y1) + 1):
                abrir(x1, y)
        else:
            for y in range(min(y0, y1), max(y0, y1) + 1):
                abrir(x0, y)
            for x in range(min(x0, x1), max(x0, x1) + 1):
                abrir(x, y1)

    orden, restantes = [0], set(range(1, len(salas)))   # cadena de salas vecinas (pasillos más cortos)
    while restantes:
        ux, uy = centros[orden[-1]]
        sig = min(restantes, key=lambda r: math.hypot(centros[r][0] - ux, centros[r][1] - uy))
        orden.append(sig)
        restantes.discard(sig)
    for i in range(len(orden) - 1):
        tunel(centros[orden[i]], centros[orden[i + 1]])
    for _ in range(max(2, len(centros) // 3)):      # atajos extra para crear bucles
        a, b = rng.sample(range(len(centros)), 2)
        tunel(centros[a], centros[b])

    ix, iy = centros[0]
    libres = [[c for c in cs if grid[c[1]][c[0]] == 0] for cs in celdas_sala]
    usados = {(ix, iy)}

    # ---- infectados
    n_enem = total_enemigos(nivel)
    p_tanque = 0.0 if nivel < 3 else min(0.22, 0.05 + 0.015 * nivel)
    p_corr = 0.0 if nivel < 2 else min(0.35, 0.10 + 0.02 * nivel)
    cuartos = list(range(1, len(salas)))
    enemigos, intentos = [], 0
    while len(enemigos) < n_enem and intentos < 3000:
        intentos += 1
        r = cuartos[len(enemigos) % len(cuartos)] if rng.random() < 0.7 else rng.choice(cuartos)
        cx, cy = rng.choice(libres[r])
        if (cx, cy) in usados or math.hypot(cx - ix, cy - iy) < 8:
            continue
        usados.add((cx, cy))
        p = rng.random()
        tipo = "tanque" if p < p_tanque else ("corredor" if p < p_tanque + p_corr else "zombi")
        enemigos.append((cx + 0.5, cy + 0.5, tipo))

    # ---- objetos de ayuda
    items = []
    for r in range(len(salas)):
        for tipo, prob in (("municion", 0.45), ("botiquin", 0.30)):
            if rng.random() < prob:
                c = rng.choice(libres[r])
                if c not in usados:
                    usados.add(c)
                    items.append((c[0] + 0.5, c[1] + 0.5, tipo))
    for tipo in ("municion", "botiquin"):           # siempre algo de ayuda junto al inicio
        c = rng.choice(libres[0])
        if c not in usados:
            usados.add(c)
            items.append((c[0] + 0.5, c[1] + 0.5, tipo))

    # ---- misiones (se hacen en orden; la última siempre es llegar a la extracción)
    lejos = sorted(range(1, len(salas)), key=lambda r: -math.hypot(centros[r][0] - ix, centros[r][1] - iy))
    sala_ext = lejos[0]
    otras = lejos[1:]
    rng.shuffle(otras)
    ciclo = {"i": 0}

    def sala_libre():
        r = otras[ciclo["i"] % len(otras)] if otras else sala_ext
        ciclo["i"] += 1
        return r

    def celda_en(r):
        cand = [c for c in libres[r] if c not in usados] or libres[r]
        c = rng.choice(cand)
        usados.add(c)
        return (c[0] + 0.5, c[1] + 0.5)

    n_pasos = min(6, 3 + nivel // 3)
    elegidos = rng.sample(POOL_MISIONES, min(n_pasos - 1, len(POOL_MISIONES)))
    elegidos.sort(key=lambda m: m[0] == "llave")    # la tarjeta de acceso va justo antes de la salida
    misiones = []
    for tipo, nombre in elegidos:
        if tipo == "matar":
            misiones.append({"tipo": "matar", "n": min(5 + 2 * nivel, 24)})
        elif tipo == "recoger":
            n = min(5, 2 + nivel // 4)
            misiones.append({"tipo": "recoger", "nombre": nombre, "n": n, "sprite": SPRITE_MISION[nombre],
                             "pos": [celda_en(sala_libre()) for _ in range(n)]})
        elif tipo == "activar":
            misiones.append({"tipo": "activar", "nombre": nombre, "sprite": SPRITE_MISION[nombre],
                             "tiempo": min(4.5, 3.0 + 0.1 * nivel), "pos": celda_en(sala_libre())})
        else:
            misiones.append({"tipo": "llave", "nombre": nombre, "sprite": SPRITE_MISION[nombre],
                             "pos": celda_en(sala_libre())})
    ex, ey = centros[sala_ext]
    misiones.append({"tipo": "extraer", "sprite": "extraccion", "pos": (ex + 0.5, ey + 0.5)})

    todas = [(c[0], c[1]) for cs in libres for c in cs]
    return {"mapa": grid, "inicio": (ix + 0.5, iy + 0.5), "enemigos": enemigos, "items": items,
            "misiones": misiones, "libres": todas}


def cargar_nivel(nivel):
    global COLS, FILAS, OSCURIDAD
    datos = generar_nivel(nivel)
    MAPA[:] = datos["mapa"]
    FILAS, COLS = len(MAPA), len(MAPA[0])
    CELDAS_LIBRES[:] = datos["libres"]
    OSCURIDAD = min(1.7, 0.9 + 0.035 * nivel)
    return datos


def es_pared(x, y):
    mx, my = int(x), int(y)
    if mx < 0 or my < 0 or mx >= COLS or my >= FILAS:
        return True
    return MAPA[my][mx] > 0


def mover_con_colision(obj, dx, dy, margen):
    if dx:
        nx = obj.x + dx + (margen if dx > 0 else -margen)
        if not es_pared(nx, obj.y - margen) and not es_pared(nx, obj.y + margen):
            obj.x += dx
    if dy:
        ny = obj.y + dy + (margen if dy > 0 else -margen)
        if not es_pared(obj.x - margen, ny) and not es_pared(obj.x + margen, ny):
            obj.y += dy


def hay_linea_vision(x0, y0, x1, y1):
    d = math.hypot(x1 - x0, y1 - y0)
    pasos = max(1, int(d / 0.15))
    for i in range(1, pasos):
        t = i / pasos
        if es_pared(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t):
            return False
    return True


def distancia_pared(x, y, c, s):
    """Distancia (unidades del mapa) desde (x,y) hasta la primera pared en la dirección (c,s)."""
    mx, my = int(x), int(y)
    ddx = abs(1 / c) if c else 1e30
    ddy = abs(1 / s) if s else 1e30
    if c < 0:
        stx, sdx = -1, (x - mx) * ddx
    else:
        stx, sdx = 1, (mx + 1 - x) * ddx
    if s < 0:
        sty, sdy = -1, (y - my) * ddy
    else:
        sty, sdy = 1, (my + 1 - y) * ddy
    while True:
        if sdx < sdy:
            sdx += ddx
            mx += stx
            lado = 0
        else:
            sdy += ddy
            my += sty
            lado = 1
        if mx < 0 or my < 0 or mx >= COLS or my >= FILAS or MAPA[my][mx] > 0:
            return (sdx - ddx) if lado == 0 else (sdy - ddy)


def calcular_campo(cx, cy):
    """Mapa de distancias desde la celda del jugador (los infectados lo siguen por los pasillos)."""
    campo = [[9999] * COLS for _ in range(FILAS)]
    campo[cy][cx] = 0
    cola = deque([(cx, cy)])
    while cola:
        x, y = cola.popleft()
        d = campo[y][x] + 1
        if d > LIMITE_CAMPO:
            continue
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < COLS and 0 <= ny < FILAS and MAPA[ny][nx] == 0 and campo[ny][nx] > d:
                campo[ny][nx] = d
                cola.append((nx, ny))
    return campo


# ===========================================================================
# 6. TEXTURAS Y SPRITES
# ===========================================================================
# ---------------------------------------------------------------------------
# 6.0  AJUSTES GRÁFICOS  (se editan en AJUSTES y se guardan solos)
# ---------------------------------------------------------------------------
COLUMNAS_OPC = [10, 8, 6, 5, 4, 3, 2]        # ancho (px) de cada columna de pared: menos = más nítido y más pesado
NOMBRES_COLUMNAS = {10: "MÍNIMO", 8: "BAJO", 6: "MEDIO", 5: "BUENO", 4: "ALTO", 3: "MUY ALTO", 2: "MÁXIMO"}
DIST_OPC = [12, 16, 20, 26, 32]
TEXCAL_OPC = [32, 64, 128]
FPS_OPC = [30, 45, 60]
BRILLO_OPC = [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4]
PRESETS_GRAF = {
    "BAJA": {"col": 8, "dist": 16, "tex": 64, "suave": False, "niebla": False, "var": False,
             "vineta": False, "fps": 30, "adapt": True},
    "MEDIA": {"col": 6, "dist": 20, "tex": 64, "suave": False, "niebla": True, "var": False,
              "vineta": False, "fps": 45, "adapt": True},
    "ALTA": {"col": 4, "dist": 26, "tex": 128, "suave": False, "niebla": True, "var": True,
             "vineta": True, "fps": 60, "adapt": True},
    "ULTRA": {"col": 2, "dist": 32, "tex": 128, "suave": True, "niebla": True, "var": True,
              "vineta": True, "fps": 60, "adapt": False},
}
ORDEN_PRESETS = ["BAJA", "MEDIA", "ALTA", "ULTRA"]
PRESET_DEFECTO = "MEDIA" if MOVIL else "ALTA"
GRAF = dict(PRESETS_GRAF[PRESET_DEFECTO], brillo=1.0, ver_fps=False)
FPS_LIMITE = 60
SUAVE_OK = [True]              # se desactiva solo si smoothscale falla en este dispositivo
TEX_N = [128, 64, 32, 16]      # niveles mipmap de las texturas de pared
TEXN = 128
N_SOMBRAS = 30
FOG_COLOR = (24, 14, 22)


def _valor_sombra(k):
    if k <= 21:
        return 1.0 - k * 0.0425
    return max(0.0, 0.1075 * (1.0 - (k - 21) / 8.0))     # al final de la distancia de dibujo se funde con la niebla


_VALOR_SOMBRA = [_valor_sombra(k) for k in range(N_SOMBRAS)]


def _en_32(s):
    if s.get_bitsize() in (24, 32):
        return s
    try:
        return s.convert(32)
    except pygame.error:
        return s


class Paredes:
    """Texturas de pared con mipmaps (sin parpadeo a distancia) y sombreado/niebla por distancia, en caché."""

    def __init__(self):
        self.base = {}              # (tipo, variante) -> [128, 64, 32, 16]
        self.cache = {}

    def agregar(self, tipo, var, surf):
        niveles = [_en_32(surf)]
        for n in TEX_N[1:]:
            try:
                m = pygame.transform.smoothscale(niveles[-1], (n, n))
            except (ValueError, pygame.error):
                m = pygame.transform.scale(niveles[-1], (n, n))
            niveles.append(m)
        self.base[(tipo, var)] = niveles

    def limpiar(self):
        self.cache.clear()

    def crear(self, tipo, var, mip, sombra, clave):
        niveles = self.base.get((tipo, var)) or self.base.get((tipo, 0)) or self.base[(1, 0)]
        t = niveles[mip].copy()
        v = _VALOR_SOMBRA[sombra]
        c = int(255 * v)
        t.fill((c, c, c), special_flags=pygame.BLEND_RGB_MULT)
        if GRAF["niebla"] and v < 1.0:
            a = 1.0 - v
            t.fill((int(FOG_COLOR[0] * a), int(FOG_COLOR[1] * a), int(FOG_COLOR[2] * a)),
                   special_flags=pygame.BLEND_RGB_ADD)
        self.cache[clave] = t
        return t


PAREDES = Paredes()


def fijar_columnas(px):
    """Cambia el ancho de columna en vivo (también lo usa la resolución adaptativa)."""
    global ESCALA, NUM_RAYOS
    ESCALA = px
    NUM_RAYOS = -(-ANCHO // ESCALA)


def aplicar_graficos(guardar=True):
    global FPS_LIMITE
    fijar_columnas(GRAF["col"])
    FPS_LIMITE = GRAF["fps"]
    PAREDES.limpiar()
    if guardar:
        DATOS["graficos"] = dict(GRAF)


def nombre_preset():
    for nombre in ORDEN_PRESETS:
        if all(GRAF.get(k) == v for k, v in PRESETS_GRAF[nombre].items()):
            return nombre
    return "PERSONALIZADO"


def _opc_cercana(valor, opciones):
    return min(opciones, key=lambda o: abs(o - valor))


def cargar_graficos():
    g = DATOS.get("graficos", {})
    base = dict(PRESETS_GRAF[PRESET_DEFECTO], brillo=1.0, ver_fps=False)
    listas = {"col": COLUMNAS_OPC, "dist": DIST_OPC, "tex": TEXCAL_OPC, "fps": FPS_OPC, "brillo": BRILLO_OPC}
    if isinstance(g, dict):
        for k, v0 in base.items():
            v = g.get(k, v0)
            if k in listas:
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    base[k] = _opc_cercana(v, listas[k])
            elif isinstance(v, bool):
                base[k] = v
    GRAF.clear()
    GRAF.update(base)
    aplicar_graficos(False)


class Adaptativo:
    """Resolución adaptativa: si los FPS caen, las columnas de pared se hacen más anchas (más fluido);
    cuando sobra rendimiento vuelven poco a poco a la calidad elegida."""

    def __init__(self):
        self.reiniciar()

    def reiniciar(self):
        fijar_columnas(GRAF["col"])
        self.t = -2.0
        self.mejora = 0
        self.espera = 4

    def actualizar(self, dt, fps):
        if not GRAF["adapt"]:
            if ESCALA != GRAF["col"]:
                fijar_columnas(GRAF["col"])
            return
        self.t += dt
        if self.t < 1.0:
            return
        self.t = 0.0
        i = COLUMNAS_OPC.index(ESCALA) if ESCALA in COLUMNAS_OPC else 0
        objetivo = FPS_LIMITE
        if fps < objetivo * 0.82 and i > 0:
            fijar_columnas(COLUMNAS_OPC[i - 1])
            self.mejora = 0
            self.espera = min(40, self.espera * 2)
        elif fps >= objetivo * 0.96:
            self.mejora += 1
            if self.mejora >= self.espera and ESCALA > GRAF["col"]:
                fijar_columnas(COLUMNAS_OPC[i + 1])
                self.mejora = 0
        else:
            self.mejora = 0


ADAPT = Adaptativo()


def dibujar_fps():
    s = FUENTE_XS.render(f"{int(reloj.get_fps())} FPS · {ESCALA}px", True, (120, 255, 120))
    pantalla.blit(s, (ANCHO - s.get_width() - K(8), K(6)))


# ---------------------------------------------------------------------------
# 6.1  TEXTURAS DE PARED EN ALTA DEFINICIÓN (128x128, generadas por código)
# ---------------------------------------------------------------------------
def _grano(s, rng, amp):
    """Grano fino por píxel aplicado de golpe (sin bucles en Python)."""
    n = s.get_width()
    crudo = rng.getrandbits(8 * n * n).to_bytes(n * n, "little")
    g = crudo.translate(bytes(int(i * 2 * amp / 255) for i in range(256)))
    rgb = bytearray(n * n * 3)
    rgb[0::3] = g
    rgb[1::3] = g
    rgb[2::3] = g
    capa = pygame.image.frombuffer(bytes(rgb), (n, n), "RGB")
    s.blit(capa, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    s.fill((amp, amp, amp), special_flags=pygame.BLEND_RGB_SUB)


def _manchas(s, rng, cantidad, color, rmin, rmax, alfa):
    n = s.get_width()
    capa = pygame.Surface((n, n), pygame.SRCALPHA)
    for _ in range(cantidad):
        r = rng.randint(rmin, rmax)
        x, y = rng.randrange(n), rng.randrange(n)
        for ox in (-n, 0, n):                                   # se repite en los bordes: la textura encaja
            pygame.draw.ellipse(capa, tuple(color) + (alfa,), (x - r + ox, y - r // 2, r * 2, r))
    s.blit(capa, (0, 0))


def _grieta(s, rng, x, y, largo):
    px, py = x, y
    for _ in range(max(2, largo // 4)):
        nx, ny = px + rng.randint(-5, 5), py + rng.randint(2, 6)
        pygame.draw.line(s, (120, 105, 95), (px + 2, py), (nx + 2, ny), 1)
        pygame.draw.line(s, (20, 14, 12), (px, py), (nx, ny), 2)
        px, py = nx, ny


def _ao_pared(s):
    """Oscurece el borde de arriba y de abajo: da sensación de volumen (techo y suelo)."""
    n = s.get_width()
    capa = pygame.Surface((n, n), pygame.SRCALPHA)
    arriba, abajo = n // 9, n // 5
    for j in range(arriba):
        pygame.draw.line(capa, (0, 0, 0, int(80 * (1 - j / arriba) ** 2)), (0, j), (n, j))
    for j in range(abajo):
        pygame.draw.line(capa, (0, 0, 0, int(110 * (1 - j / abajo) ** 2)), (0, n - 1 - j), (n, n - 1 - j))
    s.blit(capa, (0, 0))


def _bloque(s, r, col, luz=0.28):
    """Ladrillo o piedra con degradado y bisel (luz arriba-izquierda)."""
    for j in range(r.h):
        f = 1.10 - luz * j / max(1, r.h)
        pygame.draw.line(s, (min(255, int(col[0] * f)), min(255, int(col[1] * f)), min(255, int(col[2] * f))),
                         (r.left, r.top + j), (r.right - 1, r.top + j))
    pygame.draw.line(s, (min(255, col[0] + 38), min(255, col[1] + 34), min(255, col[2] + 34)),
                     r.topleft, (r.right - 1, r.top))
    pygame.draw.line(s, (min(255, col[0] + 18), min(255, col[1] + 16), min(255, col[2] + 16)),
                     r.topleft, (r.left, r.bottom - 1))
    pygame.draw.line(s, (col[0] // 3, col[1] // 3, col[2] // 3), (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1))
    pygame.draw.line(s, (col[0] // 2, col[1] // 2, col[2] // 2), (r.right - 1, r.top), (r.right - 1, r.bottom - 1))


def _textura_ladrillo(seed, ao=True):
    n = TEXN
    rng = random.Random(seed)
    s = pygame.Surface((n, n))
    s.fill((50, 44, 42))
    _grano(s, rng, 14)                                          # argamasa rugosa
    bw, bh = 32, 16
    por_fila = n // bw
    tonos = [[rng.randint(112, 168) for _ in range(por_fila)] for _ in range(n // bh)]
    tintes = [[rng.randint(0, 12) for _ in range(por_fila)] for _ in range(n // bh)]
    for fila in range(n // bh):
        desp = 0 if fila % 2 == 0 else bw // 2
        y = fila * bh
        for k in range(-1, por_fila + 1):
            x = k * bw + desp
            b = tonos[fila][k % por_fila]
            col = (b, int(b * 0.38) + tintes[fila][k % por_fila], int(b * 0.26))
            r = pygame.Rect(x + 2, y + 2, bw - 4, bh - 4)
            _bloque(s, r, col)
            if rng.random() < 0.22:                             # esquinas rotas
                cx = rng.randint(r.left + 3, r.right - 9)
                cy = rng.randint(r.top + 2, r.bottom - 5)
                pygame.draw.rect(s, (col[0] // 2, col[1] // 2, col[2] // 2),
                                 (cx, cy, rng.randint(3, 6), rng.randint(2, 4)))
    _grano(s, rng, 16)
    _manchas(s, rng, 5, (0, 0, 0), 14, 30, 38)                  # hollín
    _manchas(s, rng, 3, (40, 70, 30), 6, 14, 55)                # musgo
    for _ in range(2):
        _grieta(s, rng, rng.randrange(8, n - 8), rng.randrange(0, n // 2), rng.randint(30, 60))
    if ao:
        _ao_pared(s)
    return s


def _textura_piedra(seed):
    n = TEXN
    rng = random.Random(seed)
    s = pygame.Surface((n, n))
    s.fill((34, 34, 40))
    _grano(s, rng, 12)
    bw, bh = 64, 32
    por_fila = n // bw
    tonos = [[rng.randint(88, 132) for _ in range(por_fila)] for _ in range(n // bh)]
    for fila in range(n // bh):
        desp = 0 if fila % 2 == 0 else bw // 2
        y = fila * bh
        for k in range(-1, por_fila + 1):
            g = tonos[fila][k % por_fila]
            _bloque(s, pygame.Rect(k * bw + desp + 2, y + 2, bw - 4, bh - 4), (g, g, g + 7), 0.22)
    for _ in range(260):                                        # granos claros y oscuros
        g = rng.randint(50, 170)
        s.set_at((rng.randrange(n), rng.randrange(n)), (g, g, g + 6))
    _grano(s, rng, 18)
    _manchas(s, rng, 4, (10, 12, 20), 14, 32, 40)
    _manchas(s, rng, 3, (50, 80, 45), 6, 14, 50)
    for _ in range(3):
        _grieta(s, rng, rng.randrange(8, n - 8), rng.randrange(0, n // 2), rng.randint(30, 70))
    _ao_pared(s)
    return s


def _textura_metal(seed):
    n = TEXN
    rng = random.Random(seed)
    s = pygame.Surface((n, n))
    s.fill((40, 48, 62))
    _grano(s, rng, 7)
    capa = pygame.Surface((n, n), pygame.SRCALPHA)
    for _ in range(90):                                         # vetas de metal cepillado
        x, y, largo = rng.randrange(n), rng.randrange(n), rng.randint(18, 70)
        c = 255 if rng.random() < 0.5 else 0
        pygame.draw.line(capa, (c, c, c, 16), (x, y), (x + largo, y))
    s.blit(capa, (0, 0))
    pygame.draw.rect(s, (88, 102, 130), (3, 3, n - 6, n - 6), 3)             # marco biselado
    pygame.draw.line(s, (140, 156, 185), (4, 4), (n - 5, 4), 1)
    pygame.draw.line(s, (18, 22, 32), (4, n - 5), (n - 5, n - 5), 1)
    pygame.draw.rect(s, (24, 30, 42), (10, 10, n - 20, n - 20))
    pygame.draw.rect(s, (12, 16, 24), (10, 10, n - 20, n - 20), 2)
    glow = pygame.Surface((n, n), pygame.SRCALPHA)                           # franja de neón con resplandor
    pygame.draw.rect(glow, (0, 170, 210, 45), (14, 44, n - 28, 38), border_radius=10)
    pygame.draw.rect(glow, (0, 200, 230, 90), (16, 52, n - 32, 22), border_radius=8)
    s.blit(glow, (0, 0))
    pygame.draw.rect(s, (0, 215, 245), (22, 58, n - 44, 10), border_radius=4)
    pygame.draw.rect(s, (190, 250, 255), (24, 61, n - 48, 4), border_radius=2)
    for cx, cy in ((10, 10), (n - 11, 10), (10, n - 11), (n - 11, n - 11)):  # remaches
        pygame.draw.circle(s, (14, 18, 26), (cx, cy), 6)
        pygame.draw.circle(s, (120, 132, 156), (cx, cy), 4)
        pygame.draw.circle(s, (210, 220, 236), (cx - 1, cy - 1), 1)
    capa2 = pygame.Surface((n, n), pygame.SRCALPHA)
    for _ in range(5):                                                       # arañazos
        x, y = rng.randrange(14, n - 40), rng.randrange(14, n - 30)
        pygame.draw.line(capa2, (190, 205, 230, 70), (x, y), (x + rng.randint(10, 30), y + rng.randint(-8, 8)), 1)
    for _ in range(4):                                                       # óxido
        x, largo = rng.randrange(14, n - 14), rng.randint(14, 40)
        pygame.draw.line(capa2, (150, 80, 30, 45), (x, n - 14 - largo), (x, n - 14), 2)
    s.blit(capa2, (0, 0))
    _ao_pared(s)
    return s


def _textura_sangre(seed):
    n = TEXN
    s = _textura_ladrillo(seed, ao=False)
    rng = random.Random(seed + 100)
    capa = pygame.Surface((n, n), pygame.SRCALPHA)
    pygame.draw.ellipse(capa, (80, 3, 3, 215), (28, 66, 64, 38))             # charco
    pygame.draw.ellipse(capa, (120, 8, 8, 120), (36, 72, 40, 18))
    for _ in range(9):                                                       # chorros con brillo húmedo
        x, largo, ancho = rng.randrange(6, n - 6), rng.randint(28, 112), rng.randint(4, 8)
        pygame.draw.line(capa, (112, 4, 4, 235), (x, 0), (x, largo), ancho)
        pygame.draw.circle(capa, (112, 4, 4, 235), (x, largo), ancho // 2 + 2)
        pygame.draw.line(capa, (190, 40, 36, 140), (x - ancho // 4, 0), (x - ancho // 4, largo), 1)
        pygame.draw.circle(capa, (200, 60, 55, 160), (x - 1, largo + 1), 1)
    for _ in range(46):                                                      # salpicaduras
        pygame.draw.circle(capa, (100, 4, 4, 220), (rng.randrange(n), rng.randrange(n)), rng.randint(1, 3))
    s.blit(capa, (0, 0))
    _grano(s, rng, 8)
    _ao_pared(s)
    return s


def _cargar_texturas():
    pantalla.fill((0, 0, 0))
    texto("CARGANDO TEXTURAS...", FUENTE_M, (190, 150, 150), (ANCHO // 2, ALTO // 2), centro=True)
    pygame.display.flip()
    fabricas = {1: _textura_ladrillo, 2: _textura_piedra, 3: _textura_metal, 4: _textura_sangre}
    for tipo, fab in fabricas.items():
        PAREDES.agregar(tipo, 0, fab(tipo))
        PAREDES.agregar(tipo, 1, fab(tipo + 10))


aplicar_graficos(False)
_cargar_texturas()


def crear_fondo():
    """Techo + suelo. Es más alto que la pantalla para poder inclinar la mira."""
    alto = ALTO + 2 * PITCH_MAX
    mitad = alto // 2
    s = pygame.Surface((ANCHO, alto))
    for y in range(alto):
        if y < mitad:
            t = max(0.0, 1.0 - (mitad - y) / (ALTO * 0.6))
            c = (int(5 + 26 * t), int(4 + 16 * t), int(10 + 26 * t))
        else:
            t = min(1.0, (y - mitad) / (ALTO * 0.6))
            c = (int(20 + 46 * t), int(14 + 26 * t), int(14 + 24 * t))
        pygame.draw.line(s, c, (0, y), (ANCHO, y))
    return s.convert()


FONDO = crear_fondo()


def crear_caja_municion():
    s = pygame.Surface((TEX, TEX), pygame.SRCALPHA)
    pygame.draw.rect(s, (70, 80, 40), (18, 44, 28, 18), border_radius=3)
    pygame.draw.rect(s, (110, 125, 60), (18, 44, 28, 6), border_radius=3)
    for bx in (22, 30, 38):
        pygame.draw.rect(s, (220, 180, 50), (bx, 36, 5, 10))
        pygame.draw.rect(s, (160, 110, 40), (bx, 36, 5, 4))
    return s


def crear_botiquin():
    s = pygame.Surface((TEX, TEX), pygame.SRCALPHA)
    pygame.draw.rect(s, (235, 235, 235), (16, 42, 32, 20), border_radius=4)
    pygame.draw.rect(s, (200, 30, 30), (29, 44, 6, 16))
    pygame.draw.rect(s, (200, 30, 30), (22, 49, 20, 6))
    return s


def crear_explosiones():
    frames = []
    for i in range(4):
        s = pygame.Surface((TEX, TEX), pygame.SRCALPHA)
        r = 14 + i * 6
        pygame.draw.circle(s, (70, 60, 55, 120 - i * 20), (32, 32), r)
        pygame.draw.circle(s, (255, 110, 20, 230 - i * 40), (32, 32), max(4, r - 4))
        pygame.draw.circle(s, (255, 225, 120, 255 - i * 60), (32, 32), max(2, r - 10))
        frames.append(s)
    return frames


SPR_MUNICION = crear_caja_municion()
SPR_BOTIQUIN = crear_botiquin()
SPR_EXPLOSION = crear_explosiones()


# ---------------------------------------------------------------------------
# 6.0  HERRAMIENTA DE DIBUJO (lienzo con suavizado) Y COLORES AUXILIARES
# ---------------------------------------------------------------------------
C_NEGRO = (16, 14, 16)


def _oscuro(color, n):
    return tuple(max(0, c - n) for c in color[:3])


def _claro(color, n):
    return tuple(min(255, c + n) for c in color[:3])


class Lienzo:
    """Superficie transparente para dibujar sprites con bordes suaves.
    Se dibuja a `ss` veces el tamaño y al terminar se reduce con suavizado.
    Todas las coordenadas están en píxeles del tamaño final (pueden ser decimales)."""

    def __init__(self, w, h, borde=0, ss=3):
        self.w, self.h, self.ss, self.borde = w, h, ss, borde
        self.s = pygame.Surface((w * ss, h * ss), pygame.SRCALPHA)

    def _p(self, v):
        return int(round(v * self.ss))

    def rect(self, color, x, y, w, h, radio=0):
        p = self._p
        pygame.draw.rect(self.s, color, (p(x), p(y), max(1, p(w)), max(1, p(h))), border_radius=p(radio))

    def elipse(self, color, x, y, w, h):
        p = self._p
        pygame.draw.ellipse(self.s, color, (p(x), p(y), max(1, p(w)), max(1, p(h))))

    def circ(self, color, x, y, r):
        p = self._p
        pygame.draw.circle(self.s, color, (p(x), p(y)), max(1, p(r)))

    def linea(self, color, a, b, ancho=1):
        p = self._p
        g = max(1, p(ancho))
        pygame.draw.line(self.s, color, (p(a[0]), p(a[1])), (p(b[0]), p(b[1])), g)
        if g > 2 * self.ss:                                   # extremos redondeados en líneas gruesas
            pygame.draw.circle(self.s, color, (p(a[0]), p(a[1])), g // 2)
            pygame.draw.circle(self.s, color, (p(b[0]), p(b[1])), g // 2)

    def poly(self, color, puntos):
        p = self._p
        pygame.draw.polygon(self.s, color, [(p(x), p(y)) for x, y in puntos])

    def listo(self):
        out = pygame.transform.smoothscale(self.s, (self.w, self.h))
        if self.borde > 0:                                    # contorno oscuro alrededor de la silueta
            sil = pygame.mask.from_surface(out, 40).to_surface(setcolor=(10, 6, 8, 255), unsetcolor=(0, 0, 0, 0))
            res = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            b = self.borde
            for ox, oy in ((-b, 0), (b, 0), (0, -b), (0, b)):
                res.blit(sil, (ox, oy))
            res.blit(out, (0, 0))
            return res
        return out


# ---------------------------------------------------------------------------
# 6.1  INFECTADOS (más realistas: anatomía, ropa rota, sangre, animación al caminar)
# ---------------------------------------------------------------------------
SANGRE, SANGRE2, HUESO = (126, 10, 10), (74, 5, 7), (214, 206, 182)
PERFIL_ZOMBI = {
    "zombi": dict(piel=(124, 140, 106), osc=(88, 102, 76), camisa=(66, 74, 92), camisa_osc=(44, 50, 64),
                  pantalon=(78, 68, 56), pelo=(38, 30, 26), ojos=(244, 232, 120), torso=21, cabeza=9,
                  ropa=True, brazo=6.5),
    "corredor": dict(piel=(162, 154, 132), osc=(120, 110, 92), camisa=(116, 44, 40), camisa_osc=(78, 26, 24),
                     pantalon=(38, 42, 52), pelo=(26, 22, 22), ojos=(255, 70, 46), torso=17, cabeza=8,
                     ropa=True, brazo=5.5),
    "tanque": dict(piel=(134, 120, 144), osc=(92, 80, 104), camisa=(72, 64, 60), camisa_osc=(44, 38, 36),
                   pantalon=(60, 56, 62), pelo=None, ojos=(255, 150, 42), torso=31, cabeza=9,
                   ropa=False, brazo=11),
}


def _zombi_muerto(L, p):
    piel, osc = p["piel"], p["osc"]
    L.elipse(SANGRE2, 6, 104, 116, 22)
    L.elipse(SANGRE, 14, 108, 100, 14)
    L.rect(p["pantalon"], 78, 99, 34, 8, 3)                       # piernas
    L.rect(p["pantalon"], 76, 108, 32, 8, 3)
    L.rect((24, 22, 24), 108, 100, 9, 6, 2)
    L.rect((24, 22, 24), 104, 109, 9, 6, 2)
    if p["ropa"]:
        L.rect(p["camisa"], 34, 96, 48, 20, 7)                    # torso
        L.rect(p["camisa_osc"], 34, 108, 48, 8, 4)
    else:
        L.rect(piel, 30, 94, 54, 22, 8)
        L.rect(osc, 30, 108, 54, 8, 4)
    L.elipse(SANGRE, 50, 100, 18, 10)
    L.linea(piel, (46, 100), (24, 121), int(p["brazo"] * 0.8))   # brazos caídos
    L.linea(piel, (46, 112), (30, 124), int(p["brazo"] * 0.7))
    L.circ(piel, 26, 104, p["cabeza"] * 0.85)                     # cabeza
    L.circ(osc, 26, 108, p["cabeza"] * 0.5)
    L.linea((20, 10, 12), (21, 101), (25, 105), 1.2)              # ojos en X
    L.linea((20, 10, 12), (25, 101), (21, 105), 1.2)
    L.circ(SANGRE, 20, 110, 3)


def _zombi_vivo(L, p, frame):
    piel, osc = p["piel"], p["osc"]
    cx, tw, hr, br = 64, p["torso"], p["cabeza"], p["brazo"]
    lw = 11 + (tw - 21) * 0.3
    cam, cam2 = p["camisa"], p["camisa_osc"]
    # ---- piernas (el ciclo de paso alterna los pies)
    for lado in (-1, 1):
        avance = lado if frame == 0 else -lado
        yf = 119 if avance > 0 else 123
        xc = cx + lado * tw * 0.40
        L.poly(p["pantalon"], [(xc - lw / 2, 66), (xc + lw / 2, 66), (xc + lw / 2 - 1, yf), (xc - lw / 2 + 1, yf)])
        L.poly(_oscuro(p["pantalon"], 22), [(xc + lw * 0.1, 66), (xc + lw / 2, 66), (xc + lw / 2 - 1, yf), (xc + lw * 0.1, yf)])
        L.poly(piel, [(xc - lw / 2 + 1, 100), (xc + lw / 2 - 1, 96), (xc + lw / 2 - 1, yf), (xc - lw / 2 + 1, yf)])  # pantalón roto
        L.poly(osc, [(xc - lw / 2 + 1, 99), (xc - lw * 0.1, 103), (xc + lw * 0.1, 97), (xc + lw / 2 - 1, 102),
                     (xc + lw / 2 - 1, 106), (xc - lw / 2 + 1, 106)])
        L.rect((26, 22, 24), xc - lw / 2 - 1, yf - 5, lw + 3, 7, 3)  # zapato
    # ---- torso
    sh = 33
    if p["ropa"]:
        L.poly(cam, [(cx - tw, sh), (cx + tw, sh), (cx + tw * 0.9, 72), (cx - tw * 0.9, 72)])
        L.poly(cam2, [(cx + tw * 0.35, sh), (cx + tw, sh), (cx + tw * 0.9, 72), (cx + tw * 0.3, 72)])
        hem = [(cx + tw * 0.9, 72)]
        for i in range(9):                                        # dobladillo rasgado
            hem.append((cx + tw * 0.9 - i * (tw * 1.8 / 8), 72 + (4 if i % 2 else 0)))
        L.poly(cam, hem)
        L.poly(piel, [(cx - tw * 0.72, 48), (cx - tw * 0.2, 44), (cx - tw * 0.1, 62), (cx - tw * 0.62, 67)])   # desgarro
        L.poly(SANGRE2, [(cx - tw * 0.6, 51), (cx - tw * 0.3, 49), (cx - tw * 0.25, 60), (cx - tw * 0.55, 63)])
        for k in range(3):
            L.linea(HUESO, (cx - tw * 0.66, 52 + k * 4.5), (cx - tw * 0.18, 49 + k * 4.5), 1)
        L.elipse(SANGRE, cx + tw * 0.15, 44, tw * 0.6, 20)         # mancha de sangre
        L.elipse(SANGRE2, cx + tw * 0.3, 52, tw * 0.3, 9)
        L.rect(C_NEGRO, cx - tw * 0.9, 68, tw * 1.8, 3)            # cinturón
        L.poly(cam2, [(cx - 6, sh), (cx + 6, sh), (cx, sh + 8)])    # cuello de la camiseta
    else:                                                         # bruto: torso desnudo con arneses
        L.poly(piel, [(cx - tw, sh), (cx + tw, sh), (cx + tw * 0.82, 72), (cx - tw * 0.82, 72)])
        L.poly(osc, [(cx + tw * 0.3, sh), (cx + tw, sh), (cx + tw * 0.82, 72), (cx + tw * 0.25, 72)])
        L.linea(osc, (cx, 38), (cx, 66), 2)
        L.linea(osc, (cx - tw * 0.8, 52), (cx + tw * 0.8, 52), 2)
        for k in range(3):
            L.linea(osc, (cx - tw * 0.7, 56 + k * 4), (cx - 3, 57 + k * 4), 1)
        L.linea((52, 36, 28), (cx - tw * 0.9, sh + 2), (cx + tw * 0.5, 70), 4)
        L.linea((52, 36, 28), (cx + tw * 0.9, sh + 2), (cx - tw * 0.5, 70), 4)
        L.circ((150, 140, 120), cx, 52, 3)
        L.elipse(SANGRE, cx - tw * 0.5, 40, tw * 0.7, 16)
        L.rect(C_NEGRO, cx - tw * 0.82, 68, tw * 1.64, 4)
    # ---- brazos
    for lado in (-1, 1):
        sw = 3 if (lado > 0) == (frame == 0) else -2
        hx, hy = cx + lado * (tw + 3), 66 + sw
        ex, ey = cx + lado * (tw + 5), 50
        sx_, sy_ = cx + lado * (tw - 1), 36
        L.circ(cam if p["ropa"] else piel, sx_, sy_ + 1, br * 1.05)
        L.linea(cam if p["ropa"] else piel, (sx_, sy_), (ex, ey), br * 1.5)
        L.linea(piel, (ex, ey), (hx, hy), br * 1.2)
        L.linea(osc, (ex + lado * 1, ey + 2), (hx + lado * 1, hy - 4), 1.2)
        L.circ(piel, hx, hy + 1, br * 0.7)
        for f in (-1, 0, 1):
            L.linea(osc, (hx + f * 2, hy + 2), (hx + f * 2.6, hy + 7), 1.6)
        L.circ(SANGRE, hx, hy + 1, 2)
    # ---- cuello y cabeza
    hy = 19
    L.rect(osc, cx - 4, 25, 8, 9, 2)
    L.circ(piel, cx, hy, hr)
    L.elipse(osc, cx - hr * 0.85, hy + 1, hr * 1.7, hr * 0.95)    # mandíbula en sombra
    L.circ(piel, cx, hy - 1, hr * 0.92)
    L.elipse(_claro(piel, 22), cx - hr * 0.55, hy - hr * 0.7, hr * 0.7, hr * 0.5)
    if p["pelo"]:
        L.poly(p["pelo"], [(cx - hr, hy), (cx - hr * 0.9, hy - 7), (cx - 3, hy - hr - 1), (cx + hr * 0.5, hy - hr + 1),
                           (cx + hr * 0.95, hy - 5), (cx + hr * 0.5, hy - hr * 0.55), (cx, hy - hr * 0.7),
                           (cx - hr * 0.55, hy - hr * 0.5)])
    else:
        L.poly(osc, [(cx - hr * 0.5, hy - hr + 1), (cx + hr * 0.5, hy - hr + 1), (cx, hy - hr - 2)])
    for ex_ in (-4, 4):
        L.elipse((26, 12, 14), cx + ex_ - 3.4, hy - 1, 7, 5.5)    # cuencas
        L.circ(p["ojos"], cx + ex_, hy + 1.2, 1.7)
        L.circ((255, 255, 240), cx + ex_ - 0.6, hy + 0.6, 0.6)
        L.linea(osc, (cx + ex_ * 1.6, hy + 1), (cx + ex_ * 2.2, hy + 6), 0.9)   # venas
    L.linea(osc, (cx, hy + 2), (cx - 1, hy + 6), 1)               # nariz
    L.elipse((24, 4, 6), cx - 4.6, hy + 6, 9.2, 5.4)              # boca abierta
    for tx in (-3, -1, 1, 3):
        L.rect((236, 230, 206), cx + tx - 0.6, hy + 6, 1.4, 2)
    L.poly(SANGRE, [(cx - 3, hy + 10), (cx + 3, hy + 10), (cx + 4, hy + 19), (cx, hy + 22), (cx - 4, hy + 16)])
    L.linea(SANGRE2, (cx + 3, hy - 5), (cx + 6, hy + 4), 1.1)     # herida en la cara


def crear_zombi(tipo, estado, frame=0):
    p = PERFIL_ZOMBI[tipo]
    L = Lienzo(128, 128, 0, 3)
    if estado == "muerto":
        _zombi_muerto(L, p)
    else:
        _zombi_vivo(L, p, frame)
    s = L.listo()
    if estado == "herido":
        s.fill((110, 110, 110, 0), special_flags=pygame.BLEND_RGB_ADD)
    return s


SPRITES_ENEMIGO = {}
for _t in PERFIL_ZOMBI:
    SPRITES_ENEMIGO[_t] = {"a": crear_zombi(_t, "normal", 0), "b": crear_zombi(_t, "normal", 1),
                           "muerto": crear_zombi(_t, "muerto")}
    for _f, _n in ((0, "a"), (1, "b")):
        SPRITES_ENEMIGO[_t]["herido_" + _n] = crear_zombi(_t, "herido", _f)


# ---------------------------------------------------------------------------
# 6.2  OBJETOS DE MISIÓN (baterías, documentos, generador, antena, tarjeta, extracción)
# ---------------------------------------------------------------------------
def _obj_bateria(L, f):
    if f:
        L.circ((120, 255, 150, 70), 64, 84, 40)
    L.elipse((0, 0, 0, 90), 30, 112, 68, 12)
    L.rect((190, 190, 200), 58, 38, 12, 14, 2)                       # polo
    L.rect((34, 38, 46), 42, 50, 44, 66, 7)                          # cuerpo
    L.rect((196, 168, 36) if not f else (230, 200, 60), 46, 58, 36, 52, 4)   # etiqueta
    L.poly((30, 30, 36), [(66, 62), (53, 86), (62, 86), (58, 106), (76, 80), (66, 80)])
    L.rect((120, 120, 132), 42, 50, 44, 5, 2)


def _obj_documento(L, f):
    L.elipse((0, 0, 0, 90), 26, 112, 76, 12)
    L.rect((236, 234, 224), 40, 50, 52, 20, 2)                        # hojas asomando
    L.rect((214, 192, 126), 32, 62, 64, 52, 3)                        # carpeta
    L.rect((196, 172, 104), 34, 56, 26, 9, 2)                         # pestaña
    for k in range(3):
        L.rect((90, 76, 50), 40, 74 + k * 9, 46 - k * 8, 3)
    L.rect((190, 30, 30), 62, 92, 26, 14, 2)                          # sello rojo
    L.rect((236, 200, 200), 65, 95, 20, 8, 1)
    if f:
        for dx, dy, r in ((96, 54, 4), (30, 72, 3)):                  # destellos
            L.linea((255, 255, 255), (dx - r * 2, dy), (dx + r * 2, dy), 1.4)
            L.linea((255, 255, 255), (dx, dy - r * 2), (dx, dy + r * 2), 1.4)


def _obj_generador(L, f):
    L.elipse((0, 0, 0, 90), 16, 112, 96, 12)
    L.rect((40, 40, 46), 22, 100, 10, 14, 2)                          # patas
    L.rect((40, 40, 46), 96, 100, 10, 14, 2)
    L.rect((176, 128, 36), 22, 64, 84, 40, 5)                         # chasis
    L.rect((130, 92, 24), 22, 94, 84, 10, 3)
    L.rect((166, 38, 32), 30, 44, 44, 24, 9)                          # depósito
    L.rect((220, 90, 70), 36, 48, 8, 14, 3)
    L.rect((70, 70, 78), 86, 40, 9, 26, 2)                            # escape
    L.rect((24, 24, 28), 74, 72, 26, 20, 3)                           # panel
    for i, c in enumerate(((60, 255, 90), (255, 190, 40), (255, 60, 50))):
        activo = (i == 0) if not f else (i == 1)
        L.circ(c if activo else _oscuro(c, 150), 80 + i * 8, 82, 2.6)
    L.linea((50, 50, 56), (22, 70), (22, 100), 2)                     # tubo del bastidor
    L.linea((50, 50, 56), (106, 70), (106, 100), 2)


def _obj_antena(L, f):
    L.elipse((0, 0, 0, 90), 30, 114, 68, 10)
    L.rect((90, 94, 106), 44, 96, 40, 22, 3)                          # caseta
    L.rect((36, 40, 52), 50, 102, 28, 10, 2)
    L.linea((196, 198, 206), (64, 96), (64, 20), 3)                   # mástil
    for y, w in ((38, 18), (56, 24), (74, 30)):
        L.linea((170, 172, 182), (64 - w, y + 10), (64, y), 2)
        L.linea((170, 172, 182), (64 + w, y + 10), (64, y), 2)
    L.elipse((150, 152, 164), 38, 26, 52, 18)                         # plato
    L.elipse((100, 102, 114), 44, 30, 40, 11)
    if f:
        L.circ((255, 60, 50, 80), 64, 14, 12)
    L.circ((255, 70, 56) if f else (110, 20, 18), 64, 14, 4)


def _obj_llave(L, f):
    dy = -4 if f else 0
    L.elipse((0, 0, 0, 90), 34, 112, 60, 10)
    L.rect((70, 74, 86), 48, 92, 32, 22, 3)                           # pedestal
    L.rect((100, 104, 120), 48, 92, 32, 5, 2)
    if f:
        L.circ((90, 190, 255, 60), 64, 70 + dy, 34)
    L.poly((40, 110, 200), [(38, 56 + dy), (90, 50 + dy), (92, 80 + dy), (40, 86 + dy)])      # tarjeta
    L.poly((18, 18, 24), [(39, 62 + dy), (90, 56 + dy), (90, 62 + dy), (39, 68 + dy)])        # banda
    L.rect((226, 190, 70), 46, 72 + dy, 14, 11, 2)                                            # chip
    L.rect((230, 235, 245), 68, 70 + dy, 16, 12, 2)                                           # foto


def _obj_extraccion(L, f):
    d = 8 if f else 0
    L.poly((80, 255, 160, 46), [(30, 108), (98, 108), (84, 4), (44, 4)])                       # haz de luz
    L.poly((80, 255, 160, 36), [(44, 108), (84, 108), (76, 4), (52, 4)])
    L.elipse((60, 255, 140, 235), 8, 96, 112, 28)                                              # anillo en el suelo
    L.elipse((10, 60, 40, 240), 16, 100, 96, 20)
    for k in range(3):                                                                         # flechas que suben
        y = 92 - k * 26 - d
        L.linea((210, 255, 226), (50, y), (64, y - 14), 3)
        L.linea((210, 255, 226), (78, y), (64, y - 14), 3)


_OBJ_DIBUJO = {"bateria": _obj_bateria, "documento": _obj_documento, "generador": _obj_generador,
               "antena": _obj_antena, "llave": _obj_llave, "extraccion": _obj_extraccion}


def _crear_obj(nombre, f):
    L = Lienzo(128, 128, 0, 2)
    _OBJ_DIBUJO[nombre](L, f)
    return L.listo()


SPR_OBJ = {n: [_crear_obj(n, 0), _crear_obj(n, 1)] for n in _OBJ_DIBUJO}


# ===========================================================================
# 7. ENTIDADES
# ===========================================================================
CAMARA = {"zoom": 1.0}              # aumento actual de la cámara (lo usan el render y los disparos)


class Item:
    def __init__(self, x, y, tipo):
        self.x, self.y, self.tipo = x, y, tipo


TIPOS_ENEMIGO = {
    "zombi": {"vida": 1.0, "vel": 2.7, "vel_nivel": 0.04, "vel_max": 3.5, "escala": 0.85, "dano": 6,
              "recompensa": 1, "ataque": 0.9},
    "corredor": {"vida": 0.6, "vel": 4.3, "vel_nivel": 0.05, "vel_max": 5.1, "escala": 0.80, "dano": 5,
                 "recompensa": 2, "ataque": 0.7},
    "tanque": {"vida": 2.6, "vel": 1.9, "vel_nivel": 0.03, "vel_max": 2.6, "escala": 1.10, "dano": 11,
               "recompensa": 3, "ataque": 1.1},
}


class Enemigo:
    def __init__(self, x, y, tipo, nivel):
        t = TIPOS_ENEMIGO[tipo]
        self.x, self.y, self.tipo = x, y, tipo
        base = 50 * (1 + 0.3 * (nivel - 1))             # +30% de vida por nivel
        self.vida = base * t["vida"]
        self.vida_max = self.vida
        self.velocidad = min(t["vel_max"], t["vel"] + t["vel_nivel"] * nivel)
        self.escala = t["escala"]
        self.dano_min = max(1, int(t["dano"] * (1 + 0.08 * (nivel - 1))))
        self.recompensa = t["recompensa"]
        self.intervalo = t["ataque"]
        self.vivo = True
        self.alerta = False
        self.t_ataque = 0.0
        self.t_herido = 0.0
        self.anim = random.uniform(0, 4)

    def actualizar(self, dt, jug, juego):
        if not self.vivo:
            return
        self.t_herido = max(0.0, self.t_herido - dt)
        self.t_ataque = max(0.0, self.t_ataque - dt)
        dx, dy = jug.x - self.x, jug.y - self.y
        d = math.hypot(dx, dy)
        vis = d < 16 and hay_linea_vision(self.x, self.y, jug.x, jug.y)
        if not self.alerta and d < 11 and vis:
            self.alerta = True
        if not self.alerta:
            return
        if d > 0.9:
            if vis:
                tx, ty = jug.x, jug.y
            else:
                tx, ty = juego.siguiente_celda(self, jug)
            vx, vy = tx - self.x, ty - self.y
            n = math.hypot(vx, vy) or 1.0
            ox, oy = self.x, self.y
            mover_con_colision(self, vx / n * self.velocidad * dt, vy / n * self.velocidad * dt, 0.3)
            if abs(self.x - ox) + abs(self.y - oy) > 1e-4:
                self.anim += dt * (3.0 + self.velocidad * 1.1)    # camina más rápido = pasos más rápidos
        elif self.t_ataque <= 0 and vis:
            self.t_ataque = self.intervalo
            jug.recibir_dano(random.randint(self.dano_min, self.dano_min + 6))

    def sprite(self):
        if not self.vivo:
            return SPRITES_ENEMIGO[self.tipo]["muerto"]
        f = "a" if int(self.anim) % 2 == 0 else "b"
        return SPRITES_ENEMIGO[self.tipo][("herido_" if self.t_herido > 0 else "") + f]


class Jugador:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.angulo = 0.0
        self.pitch = 0.0
        self.vida = 100
        self.energia = 100.0
        self.agotado = False
        self.armas = list(DATOS["armas"])
        self.arma = DATOS["equipada"] if DATOS["equipada"] in self.armas else "pistola"
        self.municion = {a: municion_maxima(a) for a in self.armas}
        self.stats = stats_arma(self.arma)
        self.apuntando = 0.0
        self.zoom = 1.0
        self.bob = 0.0
        self.retroceso = 0.0
        self.t_disparo = 0.0
        self.flash = 0.0
        self.dano_flash = 0.0
        self.marca = 0.0
        self.marca_cabeza = False

    def recibir_dano(self, cantidad):
        self.vida = max(0, self.vida - cantidad)
        self.dano_flash = 0.35
        reproducir(SND_DANO)

    def cambiar_arma(self, id_arma):
        if id_arma in self.armas and id_arma != self.arma:
            self.arma = id_arma
            self.stats = stats_arma(id_arma)
            self.t_disparo = 0.25
            self.apuntando = 0.0

    def ciclar_arma(self, sentido):
        i = self.armas.index(self.arma)
        self.cambiar_arma(self.armas[(i - sentido) % len(self.armas)])

    def actualizar(self, dt, teclas, rel_x, rel_y, ads):
        objetivo = 1.0 if ads else 0.0
        self.apuntando += (objetivo - self.apuntando) * min(1.0, 12 * dt)
        if abs(objetivo - self.apuntando) < 0.01:
            self.apuntando = objetivo
        self.zoom = 1.0 + (self.stats["zoom"] - 1.0) * self.apuntando
        CAMARA["zoom"] = self.zoom
        sens = 1.0 / (self.zoom ** 0.9)                      # con zoom el mouse se vuelve más fino

        self.angulo += rel_x * 0.0025 * sens
        self.pitch -= rel_y * 0.7 * sens
        if teclas[pygame.K_LEFT]:
            self.angulo -= 2.2 * dt * sens
        if teclas[pygame.K_RIGHT]:
            self.angulo += 2.2 * dt * sens
        if teclas[pygame.K_q]:
            self.pitch += 200 * dt
        if teclas[pygame.K_e]:
            self.pitch -= 200 * dt
        if teclas[pygame.K_c]:
            self.pitch *= max(0.0, 1 - 8 * dt)
        self.pitch = max(-PITCH_MAX, min(PITCH_MAX, self.pitch))

        c, s = math.cos(self.angulo), math.sin(self.angulo)
        mx = my = 0.0
        if teclas[pygame.K_w] or teclas[pygame.K_UP]:
            mx += c
            my += s
        if teclas[pygame.K_s] or teclas[pygame.K_DOWN]:
            mx -= c
            my -= s
        if teclas[pygame.K_d]:
            mx -= s
            my += c
        if teclas[pygame.K_a]:
            mx += s
            my -= c
        if MOVIL:                                            # joystick virtual (analógico)
            tx, ty = TOQUE.vector_movimiento(c, s)
            mx += tx
            my += ty

        norma = math.hypot(mx, my)
        corriendo = False
        if norma > 0:
            quiere_correr = teclas[pygame.K_LSHIFT] or teclas[pygame.K_RSHIFT]
            corriendo = bool(quiere_correr) and not self.agotado and self.apuntando < 0.3
            vel = 3.2 * self.stats["vel"] * (1 - 0.4 * self.apuntando) * (1.75 if corriendo else 1.0) * min(1.0, norma)
            mover_con_colision(self, mx / norma * vel * dt, my / norma * vel * dt, 0.25)
            self.bob += dt * (13 if corriendo else 9)
        if corriendo:
            self.energia = max(0.0, self.energia - 28 * dt)
            if self.energia <= 0:
                self.agotado = True
        else:
            self.energia = min(100.0, self.energia + 16 * dt)
            if self.agotado and self.energia >= 25:
                self.agotado = False

        self.t_disparo = max(0.0, self.t_disparo - dt)
        self.retroceso = max(0.0, self.retroceso - dt * 6)
        self.flash = max(0.0, self.flash - dt)
        self.dano_flash = max(0.0, self.dano_flash - dt)
        self.marca = max(0.0, self.marca - dt)


class Juego:
    def __init__(self, nivel):
        self.nivel = nivel
        datos = cargar_nivel(nivel)
        CAMARA["zoom"] = 1.0
        self.jugador = Jugador(*datos["inicio"])
        self.enemigos = [Enemigo(x, y, t, nivel) for x, y, t in datos["enemigos"]]
        self.items = [Item(x, y, t) for x, y, t in datos["items"]]
        self.misiones = [dict(m) for m in datos["misiones"]]
        self.celdas_libres = datos["libres"]
        self.muertes = 0
        self.estado = "jugando"                 # jugando / muerto / victoria
        self.monedas_nivel = 0
        self.bonus = 0
        self.efectos = []
        self.mensaje, self.t_mensaje = "", 0.0
        self.t_headshot = 0.0
        self.t_sonido_impacto = 0.0
        self.campo, self.celda_campo = None, None
        self.cache = {}                         # mapas pre-dibujados (minimapa / mapa ampliado)
        self.reloj = 0.0
        self.pista = ""
        self.progreso = 0.0
        self.objetos = []
        self.paso = 0
        self.iniciar_paso(0)
        self.avisar("MISIÓN: " + self.texto_mision(self.misiones[0]))

    # ---- utilidades --------------------------------------------------------
    def avisar(self, txt):
        self.mensaje, self.t_mensaje = txt, 3.0

    def dar_monedas(self, n):
        DATOS["monedas"] += n
        self.monedas_nivel += n

    def vivos(self):
        return sum(1 for e in self.enemigos if e.vivo)

    def alertar_cerca(self, x, y, radio):
        for e in self.enemigos:
            if e.vivo and math.hypot(e.x - x, e.y - y) < radio:
                e.alerta = True

    def siguiente_celda(self, e, jug):
        cx, cy = int(e.x), int(e.y)
        if self.campo is None or not (0 <= cx < COLS and 0 <= cy < FILAS) or self.campo[cy][cx] >= 9999:
            return jug.x, jug.y
        mejor = (self.campo[cy][cx], cx, cy)
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if 0 <= nx < COLS and 0 <= ny < FILAS and self.campo[ny][nx] < mejor[0]:
                mejor = (self.campo[ny][nx], nx, ny)
        return mejor[1] + 0.5, mejor[2] + 0.5

    def generar_refuerzos(self, n, alertados):
        jug = self.jugador
        cand = [c for c in self.celdas_libres if 10 < math.hypot(c[0] + 0.5 - jug.x, c[1] + 0.5 - jug.y) < 28]
        if not cand:
            cand = [c for c in self.celdas_libres if math.hypot(c[0] + 0.5 - jug.x, c[1] + 0.5 - jug.y) > 6]
        if not cand:
            return
        pesos = [70, 0 if self.nivel < 2 else 30, 0 if self.nivel < 3 else 12]
        for _ in range(n):
            cx, cy = random.choice(cand)
            tipo = random.choices(["zombi", "corredor", "tanque"], weights=pesos)[0]
            e = Enemigo(cx + 0.5, cy + 0.5, tipo, self.nivel)
            e.alerta = alertados
            self.enemigos.append(e)

    # ---- misiones ----------------------------------------------------------
    def texto_mision(self, m):
        t = m["tipo"]
        if t == "matar":
            return f"Elimina {m['n']} infectados"
        if t == "recoger":
            return f"Recupera {m['n']} {m['nombre']}"
        if t == "activar":
            return f"Activa {m['nombre']} (mantén {'ACTIVAR' if MOVIL else 'F'})"
        if t == "llave":
            return f"Consigue {m['nombre']}"
        return "Llega a la zona de extracción"

    def progreso_mision(self, m):
        if m["tipo"] in ("matar", "recoger"):
            return f"{m['cont']}/{m['n']}"
        return ""

    def iniciar_paso(self, i):
        self.paso = i
        m = self.misiones[i]
        m["cont"] = 0
        self.progreso = 0.0
        self.objetos = []
        t = m["tipo"]
        if t == "matar":
            falta = m["n"] + 3 - self.vivos()
            if falta > 0:
                self.generar_refuerzos(falta, False)
        elif t == "recoger":
            self.objetos = [{"x": x, "y": y, "sprite": m["sprite"]} for x, y in m["pos"]]
        else:
            self.objetos = [{"x": m["pos"][0], "y": m["pos"][1], "sprite": m["sprite"]}]

    def completar_paso(self, extra=""):
        premio = 40 + 12 * self.nivel
        self.dar_monedas(premio)
        reproducir(SND_COMPRA)
        if self.paso + 1 >= len(self.misiones):
            self.objetos = []
            self.estado = "victoria"
            self.bonus = 150 + 40 * self.nivel
            self.dar_monedas(self.bonus)
            DATOS["nivel_max"] = max(DATOS["nivel_max"], self.nivel + 1)
            guardar_datos()
            return
        self.iniciar_paso(self.paso + 1)
        self.avisar(f"¡Misión cumplida! +{premio}   ▶ " + self.texto_mision(self.misiones[self.paso]) + extra)

    def objetivo_pos(self):
        """Posición de lo que hay que buscar ahora (para la flecha del HUD)."""
        jug = self.jugador
        if self.objetos:
            o = min(self.objetos, key=lambda o: math.hypot(o["x"] - jug.x, o["y"] - jug.y))
            return o["x"], o["y"]
        vivos = [e for e in self.enemigos if e.vivo]
        if vivos:
            e = min(vivos, key=lambda e: math.hypot(e.x - jug.x, e.y - jug.y))
            return e.x, e.y
        return None

    def actualizar_mision(self, dt, teclas):
        jug = self.jugador
        m = self.misiones[self.paso]
        t = m["tipo"]
        self.pista = ""
        if t == "recoger":
            for o in list(self.objetos):
                if math.hypot(o["x"] - jug.x, o["y"] - jug.y) < 0.8:
                    self.objetos.remove(o)
                    m["cont"] += 1
                    reproducir(SND_ITEM)
                    if m["cont"] >= m["n"]:
                        self.completar_paso()
                        return
                    self.avisar(f"{m['cont']}/{m['n']} {m['nombre']} recuperados")
        elif t == "llave":
            o = self.objetos[0]
            if math.hypot(o["x"] - jug.x, o["y"] - jug.y) < 0.8:
                reproducir(SND_ITEM)
                self.completar_paso()
        elif t == "activar":
            o = self.objetos[0]
            cerca = math.hypot(o["x"] - jug.x, o["y"] - jug.y) < 1.5
            if cerca and teclas[pygame.K_f]:
                self.progreso += dt / m["tiempo"]
                if self.progreso >= 1.0:
                    self.alertar_cerca(o["x"], o["y"], 24)
                    self.generar_refuerzos(3 + self.nivel // 2, True)
                    reproducir(SND_EXPLOSION, 0.5)
                    self.completar_paso("   ¡El ruido atrajo a una horda!")
                    return
            else:
                self.progreso = max(0.0, self.progreso - dt * 0.8)
                if cerca:
                    self.pista = "Mantén F para activar"
        elif t == "extraer":
            o = self.objetos[0]
            if math.hypot(o["x"] - jug.x, o["y"] - jug.y) < 1.5:
                self.completar_paso()

    # ---- combate -----------------------------------------------------------
    def aplicar_dano(self, e, dano, cabeza):
        e.vida -= dano
        e.alerta = True
        e.t_herido = 0.15
        jug = self.jugador
        jug.marca, jug.marca_cabeza = 0.18, cabeza
        if cabeza:
            self.t_headshot = 0.9
        if e.vida <= 0 and e.vivo:
            e.vivo = False
            self.muertes += 1
            premio = (12 + 3 * self.nivel) * e.recompensa + (15 if cabeza else 0)
            self.dar_monedas(premio)
            reproducir(SND_MUERTE)
            m = self.misiones[self.paso]
            if m["tipo"] == "matar" and self.estado == "jugando":
                m["cont"] += 1
                if m["cont"] >= m["n"]:
                    self.completar_paso()
        elif self.t_sonido_impacto <= 0:
            self.t_sonido_impacto = 0.05
            reproducir(SND_IMPACTO, 0.6)

    def trazar(self, ah, dv):
        """Un disparo: devuelve (enemigo, 'cabeza'|'cuerpo') o (None, None).
        ah = desvío horizontal (radianes), dv = desvío vertical (píxeles de pantalla)."""
        jug = self.jugador
        zoom = CAMARA["zoom"]
        ang = jug.angulo + ah
        c, s = math.cos(ang), math.sin(ang)
        mp = distancia_pared(jug.x, jug.y, c, s)
        mejor, mejor_zona = None, None
        for e in self.enemigos:
            if not e.vivo:
                continue
            rx, ry = e.x - jug.x, e.y - jug.y
            prof = rx * c + ry * s
            if prof <= 0.1 or prof >= mp:
                continue
            lat = abs(-rx * s + ry * c)
            k = e.escala
            if lat > 0.26 * k:
                continue
            tam = ALTO / prof * zoom
            size = tam * k
            f = 1 + (dv - jug.pitch - tam / 2) / size     # 0 = cabeza arriba, 1 = pies
            if f < 0 or f > 0.97:
                continue
            if f < 0.30 and lat < 0.13 * k:
                zona = "cabeza"
            elif f >= 0.24:
                zona = "cuerpo"
            else:
                continue
            mejor, mejor_zona, mp = e, zona, prof
        return mejor, mejor_zona

    def disparar(self):
        jug = self.jugador
        if jug.t_disparo > 0:
            return
        arma = ARMA_POR_ID[jug.arma]
        st = jug.stats
        if jug.municion[jug.arma] <= 0:
            jug.t_disparo = 0.3
            reproducir(SND_VACIO)
            self.avisar("¡Sin munición! (1-6 cambia de arma)")
            return
        jug.municion[jug.arma] -= 1
        jug.t_disparo = st["cadencia"]
        jug.retroceso = st["retroceso"]
        jug.flash = arma["flash"] * (0.5 if st["silencio"] else 1.0)
        reproducir(SONIDOS_ARMA[jug.arma], 0.3 if st["silencio"] else 0.8)
        if not st["silencio"]:
            self.alertar_cerca(jug.x, jug.y, 10)

        if "explosivo" in arma:
            self.disparar_cohete(arma, st)
            return
        ap = jug.apuntando
        disp = st["dispersion"] * (1 - 0.5 * ap) + st["hip"] * (1 - ap)
        zoom = CAMARA["zoom"]
        for _ in range(arma["perdigones"]):
            ah = random.uniform(-disp, disp) if disp else 0.0
            dv = random.uniform(-1, 1) * disp * ALTO * 0.9 * zoom if disp else 0.0
            e, zona = self.trazar(ah, dv)
            if e is not None:
                cabeza = zona == "cabeza"
                self.aplicar_dano(e, st["dano"] * (st["cabeza"] if cabeza else 1.0), cabeza)

    def disparar_cohete(self, arma, st):
        jug = self.jugador
        c, s = math.cos(jug.angulo), math.sin(jug.angulo)
        impacto = min(distancia_pared(jug.x, jug.y, c, s), MAX_PROF)
        for e in self.enemigos:
            if e.vivo:
                rx, ry = e.x - jug.x, e.y - jug.y
                prof = rx * c + ry * s
                if 0.1 < prof < impacto and abs(-rx * s + ry * c) < 0.4 * e.escala:
                    impacto = prof
        impacto = max(0.4, impacto - 0.3)
        px, py = jug.x + c * impacto, jug.y + s * impacto
        radio = arma["explosivo"]
        for e in list(self.enemigos):
            if e.vivo:
                d = math.hypot(e.x - px, e.y - py)
                if d < radio:
                    self.aplicar_dano(e, st["dano"] * (1 - 0.65 * d / radio), False)
        if math.hypot(jug.x - px, jug.y - py) < 1.6:
            jug.recibir_dano(20)
        self.efectos.append({"x": px, "y": py, "t": 0.0})
        reproducir(SND_EXPLOSION)

    # ---- actualización -----------------------------------------------------
    def actualizar_efectos(self, dt):
        self.reloj += dt
        self.t_mensaje = max(0.0, self.t_mensaje - dt)
        self.t_headshot = max(0.0, self.t_headshot - dt)
        self.t_sonido_impacto = max(0.0, self.t_sonido_impacto - dt)
        for ef in self.efectos:
            ef["t"] += dt
        self.efectos = [ef for ef in self.efectos if ef["t"] < 0.45]
        self.jugador.dano_flash = max(0.0, self.jugador.dano_flash - dt)

    def separar_enemigos(self):
        """Evita que los infectados se amontonen todos en el mismo punto."""
        act = [e for e in self.enemigos if e.vivo and e.alerta]
        for i in range(len(act)):
            a = act[i]
            for j in range(i + 1, len(act)):
                b = act[j]
                dx, dy = b.x - a.x, b.y - a.y
                if abs(dx) > 0.5 or abs(dy) > 0.5:
                    continue
                d = math.hypot(dx, dy) or 0.01
                if d < 0.5:
                    push = (0.5 - d) * 0.5
                    mover_con_colision(a, -dx / d * push, -dy / d * push, 0.3)
                    mover_con_colision(b, dx / d * push, dy / d * push, 0.3)

    def actualizar(self, dt, teclas, rel_x, rel_y, disparando, ads):
        self.actualizar_efectos(dt)
        if self.estado != "jugando":
            return
        jug = self.jugador
        jug.actualizar(dt, teclas, rel_x, rel_y, ads)
        if disparando:
            self.disparar()

        celda = (int(jug.x), int(jug.y))
        if celda != self.celda_campo:
            self.celda_campo = celda
            self.campo = calcular_campo(*celda)
        for e in self.enemigos:
            e.actualizar(dt, jug, self)
        self.separar_enemigos()

        for it in list(self.items):
            if math.hypot(it.x - jug.x, it.y - jug.y) < 0.6:
                if it.tipo == "municion":
                    for a in jug.armas:
                        tope = municion_maxima(a) * 3
                        extra = int(ARMA_POR_ID[a]["recogida"] * stats_arma(a)["muni"])
                        jug.municion[a] = min(tope, jug.municion[a] + extra)
                    self.avisar("¡Munición recogida!")
                elif jug.vida < 100:
                    jug.vida = min(100, jug.vida + 30)
                    self.avisar("+30 vida")
                else:
                    continue
                reproducir(SND_ITEM)
                self.items.remove(it)

        self.actualizar_mision(dt, teclas)
        if self.estado == "jugando" and jug.vida <= 0:
            self.estado = "muerto"
            guardar_datos()


# ===========================================================================
# 8. RENDER 3D
# ===========================================================================
def dibujar_paredes(jug, zbuf):
    pitch = int(jug.pitch)
    hz = ALTO // 2 + pitch
    zoom = CAMARA["zoom"]
    pantalla.blit(FONDO, (0, pitch - PITCH_MAX))
    dx, dy = math.cos(jug.angulo), math.sin(jug.angulo)
    plano = math.tan(FOV / 2) / zoom                    # con zoom se ve un trozo más estrecho del mundo
    plx, ply = -dy * plano, dx * plano

    # --- todo lo que no cambia por rayo se prepara una sola vez (menos trabajo de Python por columna) ---
    px, py = jug.x, jug.y
    mx0, my0 = int(px), int(py)
    n_rayos, esc = NUM_RAYOS, ESCALA
    paso_cam = 2.0 / n_rayos
    dist_max = float(GRAF["dist"])                      # distancia de dibujo: más allá no se calcula nada
    fade_ini = dist_max * 0.70
    fade_k = 8.0 / (dist_max * 0.30)
    k_osc = 2.0 * OSCURIDAD / GRAF["brillo"]
    suave = GRAF["suave"] and SUAVE_OK[0]
    variar = GRAF["var"]
    mip_min = TEX_N.index(GRAF["tex"])
    mapa = MAPA
    blit = pantalla.blit
    escalar, suavizar = pygame.transform.scale, pygame.transform.smoothscale
    cache_get = PAREDES.cache.get
    floor = math.floor
    alto = ALTO

    for i in range(n_rayos):
        cam = (i + 0.5) * paso_cam - 1.0
        rdx, rdy = dx + plx * cam, dy + ply * cam
        mx, my = mx0, my0
        ddx = abs(1 / rdx) if rdx else 1e30
        ddy = abs(1 / rdy) if rdy else 1e30
        if rdx < 0:
            stx, sdx = -1, (px - mx) * ddx
        else:
            stx, sdx = 1, (mx + 1 - px) * ddx
        if rdy < 0:
            sty, sdy = -1, (py - my) * ddy
        else:
            sty, sdy = 1, (my + 1 - py) * ddy

        lado = 0
        golpe = True
        while True:
            if sdx < sdy:
                if sdx > dist_max:
                    golpe = False
                    break
                sdx += ddx
                mx += stx
                lado = 0
            else:
                if sdy > dist_max:
                    golpe = False
                    break
                sdy += ddy
                my += sty
                lado = 1
            if mapa[my][mx] > 0:
                break
        if not golpe:
            zbuf[i] = 1e9
            continue

        perp = (sdx - ddx) if lado == 0 else (sdy - ddy)
        if perp < 0.05:
            perp = 0.05
        zbuf[i] = perp

        wx = (py + perp * rdy) if lado == 0 else (px + perp * rdx)
        wx -= floor(wx)
        h = int(alto / perp * zoom)
        if h < 1:
            h = 1
        # mipmap: a distancia se usa una versión reducida de la textura (sin parpadeo ni "arena")
        mip = 0 if h >= 115 else 1 if h >= 58 else 2 if h >= 29 else 3
        if mip < mip_min:
            mip = mip_min
        n = TEX_N[mip]
        tx = int(wx * n)
        if (lado == 0 and rdx > 0) or (lado == 1 and rdy < 0):
            tx = n - 1 - tx

        kf = int(perp * k_osc) + (3 if lado else 0)     # 30 niveles de sombra: sin bandas visibles
        if perp > fade_ini:
            kf += int((perp - fade_ini) * fade_k)       # al final del alcance la pared se funde con la niebla
        if kf > 29:
            kf = 29
        tipo = mapa[my][mx]
        var = (((mx * 31 + my * 17) ^ (mx * my)) & 1) if variar else 0
        clave = (((tipo * 2 + var) * 4 + mip) << 5) + kf
        tex = cache_get(clave)
        if tex is None:
            tex = PAREDES.crear(tipo, var, mip, kf, clave)

        top = hz - h // 2
        bot = top + h
        if top >= 0 and bot <= alto:
            src = tex.subsurface((tx, 0, 1, n))
            alto_dest = h
            v0, v1 = 0, n
            y0 = top
        else:
            y0, y1 = max(0, top), min(alto, bot)
            if y1 <= y0:
                continue
            v0 = min(n - 1, int((y0 - top) * n / h))
            v1 = max(v0 + 1, min(n, int((y1 - top) * n / h)))
            src = tex.subsurface((tx, v0, 1, v1 - v0))
            alto_dest = y1 - y0
        if suave and v1 - v0 >= 2 and alto_dest > (v1 - v0) * 3 // 2:
            try:                                        # filtro suave solo cuando la pared se ve "ampliada"
                col = suavizar(src, (esc, alto_dest))
            except (ValueError, pygame.error):
                SUAVE_OK[0] = False
                suave = False
                col = escalar(src, (esc, alto_dest))
        else:
            col = escalar(src, (esc, alto_dest))
        blit(col, (i * esc, y0))


_CACHE_SPR = {}


def _sprite_escalado(img, size, v, suave):
    """Sprite ya escalado y oscurecido, guardado en caché (los objetos quietos no se recalculan)."""
    k = (id(img), size, v, suave)
    r = _CACHE_SPR.get(k)
    if r is None:
        if len(_CACHE_SPR) > 320:
            _CACHE_SPR.clear()
        if suave:
            try:
                e = pygame.transform.smoothscale(img, (size, size))
            except (ValueError, pygame.error):
                e = pygame.transform.scale(img, (size, size))
        else:
            e = pygame.transform.scale(img, (size, size))
        e.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
        r = (e, img)                                     # se guarda img para que su id no se reutilice
        _CACHE_SPR[k] = r
    return r[0]


def dibujar_sprites(jug, lista, zbuf):
    zoom = CAMARA["zoom"]
    dx, dy = math.cos(jug.angulo), math.sin(jug.angulo)
    plano = math.tan(FOV / 2) / zoom
    plx, ply = -dy * plano, dx * plano
    inv = 1.0 / (plx * dy - dx * ply)
    hz = ALTO // 2 + int(jug.pitch)
    esc, n_rayos = ESCALA, NUM_RAYOS
    dist_max = float(GRAF["dist"])
    fade_ini = dist_max * 0.70
    osc = OSCURIDAD / GRAF["brillo"]
    suave = GRAF["suave"] and SUAVE_OK[0]
    blit = pantalla.blit

    visibles = []
    for x, y, img, k, barra in lista:
        rx, ry = x - jug.x, y - jug.y
        tx = inv * (dy * rx - dx * ry)
        ty = inv * (-ply * rx + plx * ry)
        if 0.15 < ty < dist_max:
            visibles.append((ty, tx, img, k, barra))
    visibles.sort(key=lambda v: v[0], reverse=True)

    for ty, tx, img, k, barra in visibles:
        tam = int(ALTO / ty * zoom)
        size = int(tam * k)
        if size < 2 or size > 1800:
            continue
        size -= size % (4 if size > 48 else 2)           # tamaños redondeados: se reutilizan en la caché
        if size < 2:
            continue
        top = hz + tam // 2 - size
        if top >= ALTO or top + size <= 0:
            continue
        sx = int(ANCHO / 2 * (1 + tx / ty))
        izq = sx - size // 2
        r0 = max(0, -(-izq // esc))
        r1 = min(n_rayos - 1, (izq + size - esc) // esc)
        if r0 > r1:
            continue
        v = max(0.2, 1 - ty * 0.075 * osc)
        if ty > fade_ini:
            v *= (dist_max - ty) / (dist_max - fade_ini)
        v = min(255, (int(255 * v) + 4) // 8 * 8)
        if v < 8:
            continue
        e = _sprite_escalado(img, size, v, suave)
        r = r0
        while r <= r1:                                   # un solo blit por cada tramo visible (no uno por columna)
            if zbuf[r] > ty:
                ini = r
                r += 1
                while r <= r1 and zbuf[r] > ty:
                    r += 1
                x0 = ini * esc
                blit(e, (x0, top), (x0 - izq, 0, (r - ini) * esc, size))
            else:
                r += 1
        if barra is not None and zbuf[max(0, min(n_rayos - 1, sx // esc))] > ty:
            bw = max(12, size // 2)
            pygame.draw.rect(pantalla, (40, 0, 0), (sx - bw // 2, top - 8, bw, 5))
            pygame.draw.rect(pantalla, (220, 30, 30), (sx - bw // 2, top - 8, int(bw * barra), 5))


def lista_sprites(juego):
    lista = []
    for e in juego.enemigos:
        barra = max(0.0, e.vida / e.vida_max) if (e.vivo and e.vida < e.vida_max) else None
        lista.append((e.x, e.y, e.sprite(), e.escala, barra))
    for it in juego.items:
        lista.append((it.x, it.y, SPR_MUNICION if it.tipo == "municion" else SPR_BOTIQUIN, 1.0, None))
    tam_obj = {"extraccion": 1.4, "generador": 1.0, "antena": 1.15}
    for ob in juego.objetos:
        img = SPR_OBJ[ob["sprite"]][int(juego.reloj * 2.5) % 2]
        lista.append((ob["x"], ob["y"], img, tam_obj.get(ob["sprite"], 0.9), None))
    for ef in juego.efectos:
        idx = min(3, int(ef["t"] / 0.45 * 4))
        lista.append((ef["x"], ef["y"], SPR_EXPLOSION[idx], 1.7, None))
    return lista


# ---------------------------------------------------------------------------
# 8.1  MIRAS ÓPTICAS AL APUNTAR (botón derecho del mouse)
# ---------------------------------------------------------------------------
NOMBRE_CORTO_MIRA = {"mira_hierro": "HIERRO", "mira_punto": "PUNTO ROJO", "mira_holo2": "HOLO x2",
                     "mira_holo3": "HOLO x3", "mira_holo4": "HOLO x4", "mira_tele": "TELESCÓPICA x3.5"}
_VENTANAS_MIRA = {"mira_punto": (K(250), K(190), K(22)), "mira_holo2": (K(340), K(250), K(26)),
                  "mira_holo3": (K(300), K(224), K(26)), "mira_holo4": (K(264), K(200), K(26))}
_CACHE_OVERLAY = {}


def _overlay_hierro():
    s = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
    cx, cy = ANCHO // 2, ALTO // 2
    for i in range(14):                                          # viñeta oscura en los bordes
        pygame.draw.rect(s, (0, 0, 0, 12 + i * 8), (i * 16, i * 12, ANCHO - i * 32, ALTO - i * 24), 16)
    n = (10, 10, 12, 255)
    pygame.draw.rect(s, n, (cx - K(46), cy + K(28), K(30), K(90)))          # alza trasera (muesca en U)
    pygame.draw.rect(s, n, (cx + K(16), cy + K(28), K(30), K(90)))
    pygame.draw.rect(s, n, (cx - K(46), cy + K(100), K(92), K(40)))
    pygame.draw.rect(s, n, (cx - K(3), cy - K(40), K(6), K(62)))            # punta de la mira delantera
    pygame.draw.polygon(s, n, [(cx - K(9), cy + K(22)), (cx + K(9), cy + K(22)),
                               (cx + K(3), cy - K(4)), (cx - K(3), cy - K(4))])
    return s


def _overlay_ventana(clave):
    an, al, radio = _VENTANAS_MIRA[clave]
    s = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
    s.fill((0, 0, 0, 236))
    r = pygame.Rect(0, 0, an, al)
    r.center = (ANCHO // 2, ALTO // 2)
    g = K(26)
    pygame.draw.rect(s, (60, 68, 82, 255), r.inflate(g, g), border_radius=radio + K(10))   # carcasa
    pygame.draw.rect(s, (30, 34, 42, 255), r.inflate(g, g), 3, border_radius=radio + K(10))
    pygame.draw.rect(s, (0, 0, 0, 0), r, border_radius=radio)                              # cristal
    pygame.draw.rect(s, (120, 135, 160, 255), r.inflate(4, 4), 3, border_radius=radio + 2)
    for k in (-1, 1):                                                                      # tornillos
        pygame.draw.circle(s, (30, 34, 42, 255), (r.centerx + k * (an // 2 + 2), r.top - K(5)), K(4))
        pygame.draw.circle(s, (130, 140, 160, 255), (r.centerx + k * (an // 2 + 2), r.top - K(5)), K(2))
    pygame.draw.polygon(s, (255, 255, 255, 16), [(r.left + K(10), r.top + K(6)), (r.left + K(90), r.top + K(6)),
                                                 (r.left + K(30), r.bottom - K(6)), (r.left + K(10), r.bottom - K(6))])
    pygame.draw.polygon(s, (120, 200, 255, 14), [(r.right - K(70), r.top + K(6)), (r.right - K(10), r.top + K(6)),
                                                 (r.right - K(10), r.bottom - K(6)), (r.right - K(120), r.bottom - K(6))])
    return s


def _overlay_telescopica():
    s = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
    cx, cy, rad = ANCHO // 2, ALTO // 2, K(236)
    a1, a2 = K(46), K(6)
    s.fill((0, 0, 0, 255))
    pygame.draw.circle(s, (0, 0, 0, 0), (cx, cy), rad)
    pygame.draw.circle(s, (46, 50, 58, 255), (cx, cy), rad + K(8), K(10))
    for (a, b) in (((cx - rad, cy), (cx - a1, cy)), ((cx + a1, cy), (cx + rad, cy)),
                   ((cx, cy - rad), (cx, cy - a1)), ((cx, cy + a1), (cx, cy + rad))):
        pygame.draw.line(s, (0, 0, 0, 255), a, b, 4)                                       # filar grueso
    for (a, b) in (((cx - a1, cy), (cx - a2, cy)), ((cx + a2, cy), (cx + a1, cy)),
                   ((cx, cy - a1), (cx, cy - a2)), ((cx, cy + a2), (cx, cy + a1))):
        pygame.draw.line(s, (0, 0, 0, 255), a, b, 1)                                       # filar fino
    for k in range(1, 6):                                                                  # puntos de medición
        for sg in (-1, 1):
            pygame.draw.circle(s, (0, 0, 0, 255), (cx + sg * (a2 + k * K(7)), cy), 1)
            pygame.draw.circle(s, (0, 0, 0, 255), (cx, cy + sg * (a2 + k * K(7))), 1)
    pygame.draw.circle(s, (255, 255, 255, 18), (cx - K(90), cy - K(100)), K(70))
    return s


def overlay_mira(tipo):
    if tipo not in _CACHE_OVERLAY:
        if tipo == "mira_hierro":
            _CACHE_OVERLAY[tipo] = _overlay_hierro()
        elif tipo == "mira_tele":
            _CACHE_OVERLAY[tipo] = _overlay_telescopica()
        else:
            _CACHE_OVERLAY[tipo] = _overlay_ventana(tipo)
    return _CACHE_OVERLAY[tipo]


def dibujar_reticula(tipo, color):
    """Retícula holográfica: cada aumento (x2, x3, x4) tiene su propio diseño."""
    cx, cy = ANCHO // 2, ALTO // 2
    dim = tuple(c // 3 for c in color)
    if tipo == "mira_punto":
        pygame.draw.circle(pantalla, dim, (cx, cy), K(5), 3)
        pygame.draw.circle(pantalla, color, (cx, cy), K(3))
    elif tipo == "mira_holo2":                                   # anillo + punto + marcas
        pygame.draw.circle(pantalla, dim, (cx, cy), K(40), 5)
        pygame.draw.circle(pantalla, color, (cx, cy), K(40), 2)
        for k in range(4):
            a = k * math.pi / 2
            pygame.draw.line(pantalla, color, (cx + math.cos(a) * K(40), cy + math.sin(a) * K(40)),
                             (cx + math.cos(a) * K(50), cy + math.sin(a) * K(50)), 2)
        pygame.draw.circle(pantalla, color, (cx, cy), 2)
    elif tipo == "mira_holo3":                                   # chevrón + línea de alcance
        v = [(cx - K(20), cy + K(20)), (cx, cy - K(2)), (cx + K(20), cy + K(20))]
        pygame.draw.lines(pantalla, dim, False, v, 5)
        pygame.draw.lines(pantalla, color, False, v, 2)
        pygame.draw.line(pantalla, color, (cx - K(52), cy), (cx - K(18), cy), 2)
        pygame.draw.line(pantalla, color, (cx + K(18), cy), (cx + K(52), cy), 2)
        pygame.draw.circle(pantalla, color, (cx, cy), 2)
    elif tipo == "mira_holo4":                                   # cruz de precisión con marcas de caída
        for a, b in (((cx - K(90), cy), (cx - K(12), cy)), ((cx + K(12), cy), (cx + K(90), cy)),
                     ((cx, cy - K(80)), (cx, cy - K(12))), ((cx, cy + K(12)), (cx, cy + K(20)))):
            pygame.draw.line(pantalla, dim, a, b, 4)
            pygame.draw.line(pantalla, color, a, b, 1)
        pygame.draw.circle(pantalla, color, (cx, cy), K(6), 1)
        pygame.draw.circle(pantalla, color, (cx, cy), 1)
        for k, w in enumerate((18, 14, 10)):
            y = cy + K(32) + k * K(22)
            pygame.draw.line(pantalla, color, (cx - K(w), y), (cx + K(w), y), 2)
    if tipo in _VENTANAS_MIRA and tipo != "mira_punto":
        an, al, _ = _VENTANAS_MIRA[tipo]
        texto("x" + tipo[-1], FUENTE_M, (150, 170, 200), (cx + an // 2 - K(26), cy - al // 2 + K(22)), centro=True)


def dibujar_ads(jug):
    """Devuelve True si la mira óptica tapa el arma (apuntando del todo)."""
    ap = jug.apuntando
    if ap < 0.55:
        return False
    tipo = jug.stats["mira"]
    ov = overlay_mira(tipo)
    a = int(255 * min(1.0, (ap - 0.55) / 0.35))
    ov.set_alpha(a)
    pantalla.blit(ov, (0, 0))
    if a > 180:
        color = COLORES_MIRA[DATOS["mira_color"] % len(COLORES_MIRA)]
        if tipo == "mira_tele":
            pygame.draw.circle(pantalla, color, (ANCHO // 2, ALTO // 2), 2)
        elif tipo != "mira_hierro":
            dibujar_reticula(tipo, color)
        if jug.flash > 0:
            f = pygame.transform.smoothscale(FLASH, (K(110), K(110)))
            pantalla.blit(f, f.get_rect(center=(ANCHO // 2, ALTO // 2 + K(20))))
    return ap > 0.95


_ESC_FP = {}


def _arma_escalada(id_arma):
    """Arma en primera persona escalada a la resolución (con caché)."""
    img, off = sprite_fp(id_arma)
    clave = id(img)
    if clave not in _ESC_FP:
        if len(_ESC_FP) > 64:
            _ESC_FP.clear()
        grande = pygame.transform.smoothscale(img, (max(1, K(img.get_width())), max(1, K(img.get_height()))))
        _ESC_FP[clave] = (img, grande, (off[0] * UI, off[1] * UI))        # se guarda `img` para que su id no se reutilice
    return _ESC_FP[clave][1], _ESC_FP[clave][2]


def dibujar_arma(jug):
    img, off = _arma_escalada(jug.arma)
    ap = jug.apuntando
    w, h = img.get_width(), img.get_height()
    centro_x = ANCHO // 2 + int(0.72 * ANCHO / 2)                 # el arma va a la derecha de la pantalla
    bx = centro_x - w / 2 + math.sin(jug.bob) * K(10) * (1 - ap) + jug.retroceso * K(16)
    by = ALTO - h + K(60) + abs(math.cos(jug.bob)) * K(8) * (1 - ap) + jug.retroceso * K(22) + ap * K(330)
    mx = bx + w / 2 + off[0]
    my = by + h / 2 + off[1]
    if jug.stats["laser"] and ap < 0.5:                          # haz del láser hasta el centro de la pantalla
        fuerte = jug.stats["laser"] > 1
        pygame.draw.line(pantalla, (210, 40, 36) if fuerte else (150, 28, 26), (mx, my), (ANCHO // 2, ALTO // 2), 1)
        pygame.draw.circle(pantalla, (120, 14, 14), (ANCHO // 2, ALTO // 2), 7 if fuerte else 5)
        pygame.draw.circle(pantalla, (255, 70, 60), (ANCHO // 2, ALTO // 2), 3 if fuerte else 2)
    if jug.flash > 0 and ap < 0.5:
        k = 0.5 if jug.stats["silencio"] else 0.9
        f = pygame.transform.smoothscale(FLASH, (K(200 * k), K(200 * k)))
        pantalla.blit(f, f.get_rect(center=(int(mx), int(my))))
    pantalla.blit(img, (bx, by))


# ---------------------------------------------------------------------------
# 8.2  MINIMAPA Y MAPA AMPLIADO (con globo terráqueo)
# ---------------------------------------------------------------------------
def crear_base_mapa(celda, piso, pared):
    s = pygame.Surface((COLS * celda, FILAS * celda), pygame.SRCALPHA)
    s.fill(pared)
    for y in range(FILAS):
        fila, x = MAPA[y], 0
        while x < COLS:
            if fila[x] == 0:
                x0 = x
                while x < COLS and fila[x] == 0:
                    x += 1
                pygame.draw.rect(s, piso, (x0 * celda, y * celda, (x - x0) * celda, celda))
            else:
                x += 1
    return s


def _marcas_mapa(juego, destino, celda, ox, oy, t):
    """Dibuja enemigos, objetivos y jugador sobre un mapa ya pintado."""
    for e in juego.enemigos:
        if e.vivo:
            pygame.draw.circle(destino, (255, 60, 60), (int(ox + e.x * celda), int(oy + e.y * celda)), max(2, celda // 2))
    pulso = 1.0 + 0.4 * math.sin(t * 6)
    for ob in juego.objetos:
        col = (80, 255, 140) if ob["sprite"] == "extraccion" else (90, 210, 255)
        px, py = int(ox + ob["x"] * celda), int(oy + ob["y"] * celda)
        r = max(3, int(celda * 0.9 * pulso))
        pygame.draw.polygon(destino, col, [(px, py - r), (px + r, py), (px, py + r), (px - r, py)])
        pygame.draw.polygon(destino, (255, 255, 255), [(px, py - r), (px + r, py), (px, py + r), (px - r, py)], 1)
    for mx, my in getattr(juego, "marcas_tac", ()):                 # puntos marcados por el jugador
        px, py = int(ox + mx * celda), int(oy + my * celda)
        r = max(3, min(10, int(celda * 0.8)))
        pygame.draw.polygon(destino, (255, 150, 30), [(px, py), (px - r, py - 2 * r), (px + r, py - 2 * r)])
        pygame.draw.circle(destino, (255, 150, 30), (px, py - 2 * r), r)
        pygame.draw.circle(destino, (255, 255, 255), (px, py - 2 * r), r, 1)
    jug = juego.jugador
    px, py = int(ox + jug.x * celda), int(oy + jug.y * celda)
    pygame.draw.circle(destino, (255, 230, 60), (px, py), max(2, celda // 2 + 1))
    pygame.draw.line(destino, (255, 230, 60), (px, py),
                     (px + math.cos(jug.angulo) * celda * 2.2, py + math.sin(jug.angulo) * celda * 2.2), 2)


def dibujar_minimapa(juego):
    celda = max(2, min(5, K(190) // max(COLS, FILAS)))
    if "mini" not in juego.cache:
        juego.cache["mini"] = (crear_base_mapa(celda, (20, 36, 52, 150), (150, 150, 165, 200)), celda)
    base, celda = juego.cache["mini"]
    pantalla.blit(base, (K(12), K(12)))
    pygame.draw.rect(pantalla, (90, 160, 210), (K(12) - 3, K(12) - 3, base.get_width() + 6, base.get_height() + 6), 2, border_radius=6)
    _marcas_mapa(juego, pantalla, celda, K(12), K(12), juego.reloj)


UBICACIONES = [("Londres", 51.5, -0.1), ("Tokio", 35.7, 139.7), ("Nueva York", 40.7, -74.0),
               ("El Cairo", 30.0, 31.2), ("Sídney", -33.9, 151.2), ("Moscú", 55.8, 37.6),
               ("Ciudad de México", 19.4, -99.1), ("Río de Janeiro", -22.9, -43.2),
               ("Ciudad del Cabo", -33.9, 18.4), ("Bombay", 19.1, 72.9), ("Pekín", 39.9, 116.4),
               ("Los Ángeles", 34.1, -118.2), ("Buenos Aires", -34.6, -58.4), ("Nairobi", -1.3, 36.8),
               ("París", 48.9, 2.3), ("Estambul", 41.0, 29.0), ("Anchorage", 61.2, -149.9),
               ("Reikiavik", 64.1, -21.9), ("Lima", -12.0, -77.0), ("Singapur", 1.35, 103.8)]

# Contornos aproximados de los continentes (longitud, latitud), dibujados a mano.
_TIERRA = [
    [(-168, 65.5), (-163, 69), (-156, 71.3), (-141, 69.7), (-128, 70), (-115, 68.5), (-108, 68), (-97, 68),
     (-90, 69), (-82, 68), (-86, 64), (-93, 60), (-94, 57), (-88, 56), (-82, 52), (-79, 55), (-78, 60),
     (-72, 62), (-65, 60), (-62, 56), (-56, 52), (-60, 47), (-66, 45), (-70, 43), (-74, 40), (-76, 35),
     (-81, 31), (-80, 26), (-83, 29), (-85, 30), (-90, 29), (-94, 29), (-97, 26), (-97, 22), (-95, 18.5),
     (-91, 19), (-90, 21), (-87, 21), (-88, 16), (-84, 15.5), (-83, 10), (-79.5, 9), (-77.5, 8), (-80, 7),
     (-84, 9), (-86, 12), (-92, 14.5), (-96, 16), (-105, 20), (-106, 23.5), (-109, 26), (-112, 29),
     (-114.5, 31.5), (-117, 32.5), (-120, 34.5), (-122, 37), (-124, 40), (-124, 46), (-123, 48.5),
     (-128, 51), (-133, 56), (-140, 59.5), (-148, 60.5), (-153, 58.5), (-158, 57), (-163, 55),
     (-158, 58.5), (-162, 60), (-166, 62), (-165, 64)],                                   # Norteamérica
    [(-77.5, 8), (-72, 12), (-62, 10.5), (-52, 5), (-50, 0), (-44, -2), (-35, -5), (-35, -9), (-39, -15),
     (-41, -22), (-48, -26), (-53, -33), (-58, -35), (-57, -38), (-62, -39), (-65, -41), (-66, -47),
     (-69, -51), (-68, -54), (-72, -54), (-74, -50), (-73, -40), (-71.5, -30), (-70, -18), (-76, -14),
     (-81, -6), (-80, -2), (-78.5, 2)],                                                   # Sudamérica
    [(-17, 21), (-13, 28), (-6, 35.5), (10, 37), (11, 33), (20, 32), (32, 31.5), (34, 28), (37, 22),
     (39, 16), (43, 12), (51, 12), (51, 10), (46, 3), (40, -3), (39, -8), (40, -15), (35, -20), (35, -25),
     (32, -29), (27, -34), (20, -35), (18, -32), (15, -26), (12, -17), (14, -10), (12, -5), (9, -1),
     (9, 4), (5, 6), (-2, 5), (-8, 4.5), (-13, 8), (-17, 13)],                            # África
    [(-9, 37), (-9, 43), (-2, 43.5), (-1.5, 46), (-4.5, 48.2), (-1.5, 49.5), (2, 51), (5, 53), (8, 54),
     (8.5, 57), (10.5, 57.7), (10, 55), (11, 54), (14, 54), (19, 54.5), (21, 55.5), (21, 57), (24, 57),
     (24.5, 59), (29, 59.8), (30, 60.2), (24, 60), (22, 60), (21.5, 61.5), (21.5, 63), (25, 65),
     (25.5, 65.5), (22, 65), (21, 63.5), (18, 62), (17.5, 60.5), (18.5, 59.5), (16.5, 57), (16, 56),
     (14, 55.5), (12.5, 56), (11.5, 58), (10.5, 59.5), (8, 58), (5, 59), (5, 62), (10, 64.5), (14, 67),
     (19, 70), (25, 71), (31, 70), (33, 69.3), (41, 67), (37, 64.5), (40, 65), (44, 66.5), (54, 68.5),
     (60, 69), (68, 69), (70, 73), (80, 73), (87, 75), (100, 77), (105, 77.5), (113, 74), (125, 73),
     (140, 72.5), (150, 71), (160, 70), (170, 70), (180, 68.5), (180, 65), (178, 64), (170, 60),
     (163, 60), (163, 56), (156, 51), (156, 57), (160, 61), (155, 59), (143, 59), (137, 54), (141, 52),
     (140, 48), (135, 43), (130, 42.5), (129, 40), (127.5, 39), (129, 35.5), (126.5, 34.5), (126, 37.5),
     (125, 40), (122, 40.5), (118, 39), (121, 37), (122, 31), (120.5, 26), (116, 22.5), (110, 21),
     (108, 21.5), (106, 19), (109, 15), (109, 12), (106, 9), (105, 8.5), (103, 10.5), (100, 13), (100, 9),
     (103, 5), (104, 1.5), (101, 3), (98, 8), (98, 12), (94, 16), (94, 19), (91, 22.5), (88, 22),
     (86, 20), (80, 15), (80, 10), (77, 8), (73, 17), (72, 21), (68, 23.5), (66, 25), (61, 25),
     (57, 25.5), (56.5, 27), (54, 26.5), (50.5, 28.5), (48.5, 30), (48, 29), (50, 26), (51.5, 24.5),
     (55, 25), (56.5, 24), (59, 22.5), (57, 19), (52, 16), (45, 13), (43, 13), (39, 21), (35, 28),
     (34.5, 29.5), (34.5, 31), (35.5, 34), (36, 36.5), (30, 36.5), (27, 37), (26, 40.8), (22.5, 40.5),
     (23.5, 38), (22, 36.5), (20, 39.5), (19.5, 41.5), (16, 43.5), (13.5, 45.5), (12.5, 44), (16, 41.5),
     (18.5, 40), (16.5, 38.5), (15.7, 38), (12, 41.5), (10, 43.5), (8, 44), (3.5, 43.3), (3, 42),
     (0, 40), (-1, 37.5), (-5, 36)],                                                       # Eurasia
    [(-73, 78), (-60, 82), (-30, 83.5), (-20, 80), (-20, 72), (-30, 68), (-40, 65), (-44, 60), (-50, 63),
     (-53, 68), (-58, 75)],                                                               # Groenlandia
    [(-80, 73.5), (-70, 71), (-62, 67), (-68, 63), (-78, 65), (-82, 69)],                 # Baffin
    [(-118, 72), (-102, 73), (-100, 69), (-115, 69)],
    [(-90, 80), (-62, 82), (-75, 77), (-88, 77)],
    [(-85, 22), (-80, 23), (-74, 20), (-78, 20)],                                         # Cuba
    [(-74, 19.5), (-69, 19.5), (-68.5, 18.3), (-74, 18)],
    [(-24, 64), (-14, 64), (-15, 66), (-22, 66.5)],                                       # Islandia
    [(-5, 50), (1, 51), (2, 53), (-2, 56), (-2, 58.5), (-5, 58.5), (-6, 56), (-3, 54.5), (-5, 52)],
    [(-10, 52), (-6, 52), (-6, 55), (-9, 54.5)],
    [(130.5, 31), (132, 34), (136, 34), (140, 35), (142, 40), (141.5, 45), (140, 42), (138, 38), (132, 35.5)],
    [(44, -25), (47, -25), (50, -15), (49, -12), (44, -17)],                              # Madagascar
    [(95, 5.5), (98, 4), (104, -2), (106, -6), (101, -3), (97, 1)],                       # Sumatra
    [(109, 2), (114, 5), (119, 5), (117, 0), (116, -4), (110, -3)],                       # Borneo
    [(105, -6.5), (114, -7), (114, -8.5), (106, -7.5)],                                   # Java
    [(131, -1), (141, -2.5), (148, -6), (150, -10), (142, -9), (138, -8), (132, -4)],     # Nueva Guinea
    [(120, 18), (122, 18), (125, 10), (126, 7), (122, 7), (120, 14)],                     # Filipinas
    [(114, -22), (114, -26), (115, -34), (119, -35), (124, -33.5), (131, -31.5), (135, -34), (138, -35),
     (140, -38), (146, -39), (150, -37), (153, -31), (153, -25), (149, -20), (146, -19), (145, -15),
     (143, -11), (141, -17), (136, -12), (131, -12), (127, -14), (122, -17)],             # Australia
    [(173, -35), (178, -37.5), (175, -41.5), (172, -40)],
    [(172, -41), (174, -41.5), (171, -45), (167, -46), (168, -44)],
    [(-180, -90), (-180, -71), (-150, -76), (-120, -74), (-100, -73), (-75, -73), (-70, -68), (-62, -64.5),
     (-58, -63.5), (-62, -71), (-60, -75), (-45, -78), (-30, -74), (-10, -71), (0, -70), (20, -70),
     (50, -67), (70, -68), (90, -66), (110, -66), (135, -66), (150, -69), (170, -71), (180, -71),
     (180, -90)],                                                                         # Antártida
    [(144.7, -40.7), (148.3, -40.9), (148.3, -42.5), (147, -43.5), (145.3, -42.8)],       # Tasmania
    [(79.8, 9.5), (81.8, 7.5), (81.2, 6.2), (80, 6), (79.8, 7.8)],                        # Sri Lanka
    [(120.1, 23), (121.5, 25.2), (122, 24.5), (120.9, 22)],                               # Taiwán
    [(108.7, 19.2), (110.5, 20.1), (111, 19.6), (109.5, 18.2)],                           # Hainán
    [(12.4, 38), (15.6, 38.3), (15.1, 36.7), (12.6, 37.6)],                               # Sicilia
    [(8.2, 41), (9.6, 41), (9.6, 39.2), (8.5, 39)],                                       # Cerdeña
    [(32.3, 35), (34.6, 35.7), (33.9, 34.7), (32.5, 34.7)],                               # Chipre
    [(-59.2, 47.6), (-56, 51.5), (-52.8, 47.5), (-53.5, 46.6), (-57.5, 47.5)],            # Terranova
    [(11, 79), (17, 80.3), (25, 80), (27, 79), (20, 77), (15, 77)],                       # Svalbard
    [(52, 71), (55, 73.5), (60, 76.5), (68, 77), (63, 75), (57, 72), (55, 70.8)],         # Nueva Zembla
    [(142, 46), (143.5, 49), (143, 54), (142.5, 54.3), (141.7, 51), (142, 47)],           # Sajalín
    [(-78.3, 18.4), (-76.3, 18.2), (-76.8, 17.8), (-77.8, 18)],                           # Jamaica
    [(-67.2, 18.5), (-65.7, 18.4), (-65.8, 18), (-67.2, 18)],                             # Puerto Rico
    [(119.5, 0), (121, 1), (125, 1.5), (123, -1), (122, -4), (123, -5.5), (120.5, -5.5), (119.5, -3)],  # Célebes
    [(164, -20.2), (166.8, -22), (166, -22.4), (164.2, -20.8)],                           # Nueva Caledonia
    [(-156, 20), (-155.2, 19.8), (-154.8, 19.4), (-155.7, 18.9)],                         # Hawái
    [(-128.3, 50.7), (-125, 50.2), (-123.5, 48.4), (-124.8, 48.4)],                       # isla de Vancouver
]
_MARES = [
    [(28, 41.5), (28, 44), (30, 46), (33, 46), (35, 45), (38, 44.5), (41.5, 42), (41, 41), (36, 41.5),
     (32, 41.7), (29, 41.2)],                                                             # Mar Negro
    [(47, 44.5), (49, 46.5), (53, 45.5), (53.5, 42), (54, 40), (54, 37), (51, 36.7), (49, 38),
     (49, 40.5), (47.5, 42)],                                                             # Mar Caspio
    [(-92.1, 46.8), (-89.5, 48.0), (-86.5, 48.8), (-84.7, 47.0), (-85.0, 46.7), (-87.5, 46.5), (-90.5, 46.6)],  # Superior
    [(-87.8, 42.3), (-87.0, 41.6), (-86.3, 42.0), (-86.5, 44.0), (-85.5, 45.2), (-85.0, 45.8), (-86.8, 45.8),
     (-87.8, 44.5)],                                                                      # Míchigan
    [(-84.8, 45.8), (-83.5, 46.2), (-81.5, 46.0), (-80.2, 44.8), (-81.7, 43.5), (-82.5, 43.9), (-83.8, 44.0),
     (-83.3, 45.3)],                                                                      # Hurón
    [(-83.4, 41.7), (-81.5, 41.5), (-79.0, 42.8), (-80.0, 42.8), (-82.5, 42.0)],          # Erie
    [(-79.8, 43.3), (-77.5, 43.3), (-76.2, 43.6), (-76.5, 44.1), (-78.5, 43.9)],          # Ontario
    [(31.7, -0.5), (33.5, 0.2), (34.5, -1), (33.2, -2.8), (32, -2.5)],                    # lago Victoria
    [(103.8, 51.5), (106.5, 53), (109.8, 55.8), (109.3, 53), (106, 51.6)],                # lago Baikal
]
_MASCARA = {}


def _mascara_tierra(MW=1080, MH=540):
    """Rasteriza los contornos en una cuadrícula (1 = tierra, 0 = agua)."""
    if "m" in _MASCARA:
        return _MASCARA["m"]
    mask = [bytearray(MW) for _ in range(MH)]
    for lista, valor in ((_TIERRA, 1), (_MARES, 0)):
        for pts in lista:
            P = [((lon + 180) * MW / 360.0, (90 - lat) * MH / 180.0) for lon, lat in pts]
            n = len(P)
            ymin = max(0, int(min(p[1] for p in P)))
            ymax = min(MH - 1, int(max(p[1] for p in P)))
            for j in range(ymin, ymax + 1):
                yc = j + 0.5
                xs = []
                for i in range(n):
                    x0, y0 = P[i]
                    x1, y1 = P[(i + 1) % n]
                    if (y0 <= yc < y1) or (y1 <= yc < y0):
                        xs.append(x0 + (yc - y0) * (x1 - x0) / (y1 - y0))
                xs.sort()
                fila = mask[j]
                for k in range(0, len(xs) - 1, 2):
                    a, b = max(0, int(math.ceil(xs[k] - 0.5))), min(MW - 1, int(math.floor(xs[k + 1] - 0.5)))
                    if b >= a:
                        fila[a:b + 1] = bytes([valor]) * (b - a + 1)
    _MASCARA["m"] = mask
    return mask


# ---------------------------------------------------------------------------
# Modelo terrestre 2026: sol real (día / noche), luces de ciudades y globo interactivo
# ---------------------------------------------------------------------------
CIUDADES_LUCES = UBICACIONES + [
    ("Bogotá", 4.7, -74.1), ("Barranquilla", 11.0, -74.8), ("Santiago", -33.4, -70.7),
    ("Caracas", 10.5, -66.9), ("La Habana", 23.1, -82.4), ("Toronto", 43.7, -79.4),
    ("Chicago", 41.9, -87.6), ("Dallas", 32.8, -96.8), ("Miami", 25.8, -80.2),
    ("Vancouver", 49.3, -123.1), ("Montreal", 45.5, -73.6), ("Panamá", 9.0, -79.5),
    ("Quito", -0.2, -78.5), ("São Paulo", -23.5, -46.6), ("Honolulu", 21.3, -157.9),
    ("Madrid", 40.4, -3.7), ("Roma", 41.9, 12.5), ("Berlín", 52.5, 13.4),
    ("Estocolmo", 59.3, 18.1), ("Kiev", 50.5, 30.5), ("Casablanca", 33.6, -7.6),
    ("Lagos", 6.5, 3.4), ("Kinsasa", -4.3, 15.3), ("Johannesburgo", -26.2, 28.0),
    ("Adís Abeba", 9.0, 38.7), ("Teherán", 35.7, 51.4), ("Riad", 24.7, 46.7),
    ("Dubái", 25.2, 55.3), ("Karachi", 24.9, 67.0), ("Delhi", 28.6, 77.2),
    ("Daca", 23.8, 90.4), ("Novosibirsk", 55.0, 82.9), ("Bangkok", 13.8, 100.5),
    ("Yakarta", -6.2, 106.8), ("Manila", 14.6, 121.0), ("Hong Kong", 22.3, 114.2),
    ("Shanghái", 31.2, 121.5), ("Seúl", 37.6, 127.0), ("Perth", -32.0, 115.9),
    ("Auckland", -36.8, 174.8)]
MESES_ES = ("ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC")
GLOBO_ZOOMS = (1.0, 1.5, 2.0)             # aumentos del planeta
PLANO_ZOOMS = (1, 2, 3)                   # aumentos del plano táctico
PLANO_CELDA_MAX = 28                      # tope de píxeles por celda (cuida la memoria en el móvil)
MAX_MARCAS_GLOBO = 24
MAX_MARCAS_PLANO = 16
_GLOBOS = {}                              # planetas ya calculados (nitidez completa)
_HALOS = {}


def _proyectar(lat, lon, lat0, lon0):
    """(lat, lon) en grados -> (x, y, z) sobre la esfera unidad vista desde (lat0, lon0). z > 0 = cara visible."""
    la, la0 = math.radians(lat), math.radians(lat0)
    dl = math.radians(lon - lon0)
    cl = math.cos(la)
    return (cl * math.sin(dl),
            math.cos(la0) * math.sin(la) - math.sin(la0) * cl * math.cos(dl),
            math.sin(la0) * math.sin(la) + math.cos(la0) * cl * math.cos(dl))


def _desproyectar(xn, yn, lat0, lon0):
    """Operación inversa: punto (xn, yn) del disco (-1..1) -> (lat, lon) en grados, o None si cae fuera."""
    r2 = xn * xn + yn * yn
    if r2 >= 1.0:
        return None
    cz = math.sqrt(1.0 - r2)
    la0 = math.radians(lat0)
    lat = math.asin(max(-1.0, min(1.0, cz * math.sin(la0) + yn * math.cos(la0))))
    lon = lon0 + math.degrees(math.atan2(xn, math.cos(la0) * cz - yn * math.sin(la0)))
    return math.degrees(lat), ((lon + 180.0) % 360.0) - 180.0


def _dist_km(la1, lo1, la2, lo2):
    p1, p2 = math.radians(la1), math.radians(la2)
    h = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2)
    return 12742.0 * math.asin(min(1.0, math.sqrt(h)))


def ciudad_cercana(lat, lon, max_km=1500):
    mejor = None
    for n, la, lo in CIUDADES_LUCES:
        d = _dist_km(lat, lon, la, lo)
        if mejor is None or d < mejor[1]:
            mejor = (n, d)
    return mejor if mejor and mejor[1] <= max_km else None


def posicion_sol(ahora=None):
    """Punto subsolar (lat, lon) en grados para la fecha y hora UTC dadas (por defecto, ahora mismo)."""
    ahora = ahora or datetime.datetime.now(datetime.timezone.utc)
    n = ahora.timetuple().tm_yday
    h = ahora.hour + ahora.minute / 60.0 + ahora.second / 3600.0
    decl = -23.44 * math.cos(math.radians(360.0 / 365.0 * (n + 10)))
    b = math.radians(360.0 / 364.0 * (n - 81))
    ecuacion = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)       # minutos
    lon = -15.0 * (h - 12.0 + ecuacion / 60.0)
    return decl, ((lon + 180.0) % 360.0) - 180.0


def _dia(d):
    """0 = noche, 1 = día (con crepúsculo suave) a partir del coseno del ángulo con el sol."""
    t = (d + 0.10) / 0.35
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return t * t * (3.0 - 2.0 * t)


def _generar_globo(lat0, lon0, R, sol):
    """Calcula el planeta fila a fila (generador) para repartir el trabajo entre fotogramas.
    Al terminar devuelve la superficie de la esfera (2R x 2R, con alfa)."""
    masc = _mascara_tierra()
    MH, MW = len(masc), len(masc[0])
    la0, lo0 = math.radians(lat0), math.radians(lon0)
    sin0, cos0 = math.sin(la0), math.cos(la0)
    sx, sy, sz = _proyectar(sol[0], sol[1], lat0, lon0)
    D = 2 * R
    buf = bytearray(D * D * 4)
    pi = math.pi
    inv = 1.0 / R
    for py in range(D):
        yn = (R - py - 0.5) * inv
        for px in range(D):
            xn = (px + 0.5 - R) * inv
            r2 = xn * xn + yn * yn
            if r2 >= 1.0:
                continue
            cz = math.sqrt(1.0 - r2)
            lat = math.asin(max(-1.0, min(1.0, cz * sin0 + yn * cos0)))
            lon = lo0 + math.atan2(xn, cos0 * cz - yn * sin0)
            mx = int((lon + pi) / (2 * pi) * MW) % MW
            my = min(MH - 1, max(0, int((pi / 2 - lat) / pi * MH)))
            latd = math.degrees(lat)
            alat = abs(latd)
            d = xn * sx + yn * sy + cz * sz                      # coseno del ángulo con el sol
            t = (d + 0.10) * 2.857142857
            t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
            t = t * t * (3.0 - 2.0 * t)                          # 0 = noche, 1 = día
            lam = d if d > 0.0 else 0.0
            if masc[my][mx]:
                if alat > 68:
                    r, g, b = 232, 238, 244
                else:
                    seco = max(0.0, 1.0 - abs(alat - 26) / 13.0)
                    trop = max(0.0, 1.0 - alat / 14.0)
                    r = 54 + 116 * seco - 22 * trop
                    g = 112 + 34 * seco - 14 * trop
                    b = 52 + 36 * seco - 10 * trop
                    ruido = ((mx * 73 + my * 151) % 17) / 17.0 - 0.5
                    r, g, b = r + 22 * ruido, g + 22 * ruido, b + 14 * ruido
            else:
                brillo = 90 * lam ** 24 * t                      # reflejo del sol en el océano
                r, g, b = 14 + 14 * cz + brillo, 50 + 46 * cz + brillo, 110 + 58 * cz + brillo
            nube = (math.sin(lon * 6.0 + 1.3) * math.sin(lat * 9.0 + lon * 2.0)
                    + math.sin(lat * 14.0 + 0.7) * math.sin(lon * 11.0))
            if nube > 0.9:
                k = min(0.6, (nube - 0.9) * 0.6)
                r, g, b = r + (240 - r) * k, g + (244 - g) * k, b + (250 - b) * k
            lond = math.degrees(lon)
            if abs(((latd + 15) % 30) - 15) < 0.55 or abs(((lond + 15) % 30) - 15) < 0.55 / max(0.25, math.cos(lat)):
                r, g, b = r + (255 - r) * 0.13, g + (255 - g) * 0.13, b + (255 - b) * 0.13
            luz = 0.14 + 0.60 * t + 0.40 * lam
            borde = (1.0 - cz) ** 3
            atm = 0.30 + 0.70 * t                                # la atmósfera brilla menos de noche
            tw = 4.0 * t * (1.0 - t)                             # franja naranja del atardecer
            r = r * luz + 70 * borde * atm + 26 * tw
            g = g * luz + 140 * borde * atm + 8 * tw
            b = b * luz + 230 * borde * atm
            a = 255 if r2 < 0.975 else int(255 * (1.0 - r2) / 0.025)
            o = (py * D + px) * 4
            buf[o] = int(min(255, max(0, r)))
            buf[o + 1] = int(min(255, max(0, g)))
            buf[o + 2] = int(min(255, max(0, b)))
            buf[o + 3] = a
        yield
    esfera = pygame.image.frombuffer(bytes(buf), (D, D), "RGBA").copy()
    rad = max(1, R // 80)
    for _n, lat, lon in CIUDADES_LUCES:                          # luces de las ciudades en el lado nocturno
        x, y, z = _proyectar(lat, lon, lat0, lon0)
        if z < 0.06:
            continue
        noche = 1.0 - _dia(x * sx + y * sy + z * sz)
        if noche < 0.45:                                         # de día no se ven
            continue
        noche = (noche - 0.45) / 0.55
        c = (int(R + x * R), int(R - y * R))
        pygame.draw.circle(esfera, (int(120 * noche), int(80 * noche), int(30 * noche), 255), c, rad * 2)
        pygame.draw.circle(esfera, (int(255 * noche), int(214 * noche), int(130 * noche), 255), c, rad)
    return esfera


def _correr(gen, ms=None):
    """Avanza un generador durante 'ms' milisegundos (o hasta el final). Devuelve (terminó, resultado)."""
    fin = None if ms is None else pygame.time.get_ticks() + ms
    while True:
        try:
            next(gen)
        except StopIteration as e:
            return True, e.value
        if fin is not None and pygame.time.get_ticks() >= fin:
            return False, None


def _halo(R):
    if R not in _HALOS:
        M = 36
        res = pygame.Surface((2 * (R + M), 2 * (R + M)), pygame.SRCALPHA)
        for k in range(M, 0, -3):                                # halo de la atmósfera
            pygame.draw.circle(res, (80, 150, 255, int(70 * (1 - k / M) ** 2) + 4), (R + M, R + M), R + k)
        _HALOS[R] = (res, M)
    return _HALOS[R]


def _arco(va, vb, n=24):
    """Puntos del arco de círculo máximo entre dos vectores unitarios (la ruta más corta sobre el planeta)."""
    dot = max(-1.0, min(1.0, va[0] * vb[0] + va[1] * vb[1] + va[2] * vb[2]))
    om = math.acos(dot)
    if om < 1e-4:
        return [va]
    s = math.sin(om)
    out = []
    for k in range(n + 1):
        f = k / n
        a, b = math.sin((1 - f) * om) / s, math.sin(f * om) / s
        out.append((a * va[0] + b * vb[0], a * va[1] + b * vb[1], a * va[2] + b * vb[2]))
    return out


def _fondo_espacio():
    if "e" not in _MASCARA:
        rng = random.Random(77)
        s = pygame.Surface((ANCHO, ALTO))
        for y in range(ALTO):
            pygame.draw.line(s, (int(3 + 6 * y / ALTO), int(4 + 5 * y / ALTO), int(14 + 12 * y / ALTO)), (0, y), (ANCHO, y))
        for _ in range(int(220 * ANCHO * ALTO / 480000)):
            c = rng.randint(90, 255)
            pygame.draw.circle(s, (c, c, min(255, c + 20)), (rng.randint(0, ANCHO), rng.randint(0, ALTO)),
                               1 if rng.random() < 0.85 else 2)
        _MASCARA["e"] = s.convert()
    return _MASCARA["e"]


def _coord_texto(lat, lon):
    return f"{abs(lat):.1f}°{'N' if lat >= 0 else 'S'}  {abs(lon):.1f}°{'E' if lon >= 0 else 'O'}"


ACENTO = (80, 220, 255)
COLOR_MARCA = (255, 150, 40)


def _vidrio(rect, alpha=200, radio=14, borde=(90, 150, 200)):
    """Panel translúcido de bordes redondeados (estilo 'vidrio')."""
    s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(s, (8, 16, 30, alpha), s.get_rect(), border_radius=radio)
    pygame.draw.rect(s, (borde[0], borde[1], borde[2], 140), s.get_rect(), 2, border_radius=radio)
    pygame.draw.line(s, (255, 255, 255, 40), (radio, 3), (rect.width - radio, 3), 1)
    pantalla.blit(s, rect.topleft)


def _pin(destino, x, y, r, col, num=None):
    """Chincheta con sombra: la punta queda exactamente en (x, y)."""
    pygame.draw.ellipse(destino, (0, 0, 0), (x - r, y - max(2, r // 3), 2 * r, max(3, 2 * r // 3)))
    pygame.draw.polygon(destino, col, [(x, y), (x - r, y - 2 * r), (x + r, y - 2 * r)])
    pygame.draw.circle(destino, col, (x, y - 2 * r), r)
    pygame.draw.circle(destino, (255, 255, 255), (x, y - 2 * r), r, 2)
    if num is not None:
        texto(str(num), FUENTE_XS, (40, 20, 0), (x, y - 2 * r), centro=True)


class MapaInteractivo:
    """Mapa ampliado interactivo.
    PLANETA: arrastra para girarlo, rueda / botones +/- para acercar, clic o toque para marcar un punto
             (otro clic encima lo quita). Las marcas se guardan en la partida.
    PLANO TÁCTICO: arrastra para moverte por el mapa, rueda / botones para acercar, clic para marcar un punto
             en una zona libre (otro clic encima lo quita). Las marcas se ven también en el minimapa."""

    def __init__(self):
        self.juego = None
        self.ultimo = -10000
        self.arrastre = None
        self.cursor = None
        self.aviso = ("", 0)

    # ------------------------------------------------------------------ estado
    def preparar(self, juego):
        ahora = pygame.time.get_ticks()
        if self.juego is not juego or ahora - self.ultimo > 1500:     # el mapa se acaba de abrir
            self.abrir(juego)
        self.ultimo = ahora

    def abrir(self, juego):
        self.juego = juego
        _, lat, lon = UBICACIONES[(juego.nivel - 1) % len(UBICACIONES)]
        self.sede = (lat, lon)
        self.lat0, self.lon0 = lat, lon
        self.gz = 0                                   # nivel de zoom del planeta
        self.pz = 0                                   # nivel de zoom del plano
        self.pan = [0.0, 0.0]
        self.sol_real = True
        self.ahora = datetime.datetime.now(datetime.timezone.utc)
        self.sol = posicion_sol(self.ahora)
        self.arrastre = None
        self.cursor = None
        self.tarea = None
        self.tarea_clave = None
        self.preview = None
        self.vuelo = None
        self.aviso = ("Toca el planeta o el plano para marcar puntos" if MOVIL else
                      "Arrastra para girar · clic para marcar puntos · rueda = zoom",
                      pygame.time.get_ticks() + 5000)
        if not hasattr(juego, "marcas_tac"):
            juego.marcas_tac = []

    def _avisar(self, txt):
        self.aviso = (txt, pygame.time.get_ticks() + 2200)

    def marcas_plano(self):
        return self.juego.marcas_tac

    # ------------------------------------------------------------------ geometría
    def layout(self):
        R, m = K(125), 36
        gcx, gcy = K(30) + R + m // 2 + K(20), K(70) + R + m // 2
        rg = pygame.Rect(gcx - R - m, gcy - R - m, 2 * (R + m), 2 * (R + m))
        px, py = rg.right + K(10), K(54)
        return {"R": R, "m": m, "gcx": gcx, "gcy": gcy, "rg": rg,
                "plano": pygame.Rect(px, py, ANCHO - px - K(24), ALTO - py - K(24))}

    def botones(self, L):
        rg, pl = L["rg"], L["plano"]
        bs, g = K(28), K(6)
        b = {"cerrar": pygame.Rect(ANCHO - K(24) - K(104), K(10), K(104), K(30))}
        x = rg.right - bs - K(4)
        for i, n in enumerate(("g_mas", "g_menos", "g_centro", "g_deshacer")):
            b[n] = pygame.Rect(x, rg.top + K(24) + i * (bs + g), bs, bs)
        b["g_limpiar"] = pygame.Rect(rg.left + K(4), rg.top + K(24), K(92), bs)
        b["g_sol"] = pygame.Rect(rg.left + K(4), rg.top + K(24) + bs + g, K(92), bs)
        x = pl.right - K(8) - K(92)
        b["p_limpiar"] = pygame.Rect(x, pl.top + K(6), K(92), bs)
        for n in ("p_deshacer", "p_centro", "p_menos", "p_mas"):
            x -= bs + g
            b[n] = pygame.Rect(x, pl.top + K(6), bs, bs)
        return b

    def _centrado(self, L, pz):
        pl = L["plano"]
        area = pygame.Rect(pl.left + 4, pl.top + K(34), pl.width - 8, pl.height - K(34) - K(48))
        cb = max(2, min(12, (pl.width - K(20)) // max(COLS, FILAS), (pl.height - K(80)) // max(COLS, FILAS)))
        celda = min(PLANO_CELDA_MAX, cb * PLANO_ZOOMS[pz]) if pz else cb
        ox0 = area.left + (area.width - COLS * celda) // 2
        oy0 = area.top + max(0, (area.height - FILAS * celda) // 2)
        return area, celda, ox0, oy0, cb

    def geom_plano(self, L):
        """(zona visible, píxeles por celda, origen x, origen y, celda base) del plano con zoom y desplazamiento."""
        area, celda, ox0, oy0, cb = self._centrado(L, self.pz)
        ox, oy = ox0 + self.pan[0], oy0 + self.pan[1]
        bw, bh = COLS * celda, FILAS * celda
        ox = min(area.left, max(area.right - bw, ox)) if bw > area.width else ox0
        oy = min(area.top, max(area.bottom - bh, oy)) if bh > area.height else oy0
        self.pan = [ox - ox0, oy - oy0]
        return area, celda, ox, oy, cb

    def radio_globo(self, L):
        return int(L["R"] * GLOBO_ZOOMS[self.gz])

    def pos_globo(self, lat, lon, L):
        """Posición en pantalla (x, y) de una coordenada, o None si está en la cara oculta del planeta."""
        x, y, z = _proyectar(lat, lon, self.lat0, self.lon0)
        if z <= 0.03:
            return None
        Re = self.radio_globo(L)
        return L["gcx"] + x * Re, L["gcy"] - y * Re

    def _sol_efectivo(self):
        if self.sol_real:
            return self.sol
        return (max(-85.0, min(85.0, self.lat0 + 25.0)), self.lon0 - 35.0)     # luz fija desde arriba-izquierda

    # ------------------------------------------------------------------ eventos
    def evento(self, ev, juego):
        """Procesa un evento mientras el mapa está abierto. Devuelve False si no es para el mapa,
        True si lo consumió y 'cerrar' si se pidió cerrar el mapa."""
        if self.juego is not juego:
            return False
        t = ev.type
        if t == pygame.KEYDOWN:
            k = ev.key
            pos = pygame.mouse.get_pos()
            if k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self._zoom(1, pos)
            elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self._zoom(-1, pos)
            elif k == pygame.K_c:
                self._accion("p_centro" if self.layout()["plano"].collidepoint(pos) else "g_centro")
            elif k == pygame.K_z:
                self._accion("p_deshacer" if self.layout()["plano"].collidepoint(pos) else "g_deshacer")
            elif k in (pygame.K_DELETE, pygame.K_BACKSPACE):
                self._accion("p_limpiar" if self.layout()["plano"].collidepoint(pos) else "g_limpiar")
            else:
                return False
            return True
        if t == pygame.MOUSEWHEEL:
            self._zoom(ev.y, pygame.mouse.get_pos())
            return True
        dedo = hasattr(pygame, "FINGERDOWN") and t in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP)
        if not (dedo or t in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION)):
            return False
        if MOVIL:
            r = TOQUE.convertir(ev)                         # toque o ratón -> (tipo, dedo, x, y)
            if r is None:
                return True
            tipo, fid, x, y = r
        else:
            if dedo:
                return True
            fid = -1
            if t == pygame.MOUSEBUTTONDOWN:
                if ev.button == 3:                          # clic derecho: quitar la marca que haya debajo
                    self._quitar_en(ev.pos[0], ev.pos[1])
                    return True
                if ev.button != 1:
                    return True
                tipo = "down"
            elif t == pygame.MOUSEBUTTONUP:
                if ev.button != 1:
                    return True
                tipo = "up"
            else:
                if not ev.buttons[0]:
                    self.cursor = ev.pos
                    return True
                tipo = "move"
            x, y = ev.pos
        return self._puntero(tipo, fid, x, y)

    def _puntero(self, tipo, fid, x, y):
        L = self.layout()
        self.cursor = (x, y)
        if tipo == "down":
            if self.arrastre is not None:
                return True
            for nombre, r in self.botones(L).items():
                if r.collidepoint(x, y):
                    return self._accion(nombre)
            if L["rg"].collidepoint(x, y):
                zona = "globo"
            elif L["plano"].collidepoint(x, y):
                zona = "plano"
            else:
                return True
            self.arrastre = {"zona": zona, "fid": fid, "x0": x, "y0": y, "x": x, "y": y, "mov": False}
            return True
        a = self.arrastre
        if a is None or a["fid"] != fid:
            return True
        if tipo == "move":
            if not a["mov"] and math.hypot(x - a["x0"], y - a["y0"]) > K(7):
                a["mov"] = True
            if a["mov"]:
                if a["zona"] == "globo":
                    self.vuelo = None
                    self._girar(x - a["x"], y - a["y"], L)
                else:
                    self.pan[0] += x - a["x"]
                    self.pan[1] += y - a["y"]
            a["x"], a["y"] = x, y
            return True
        self.arrastre = None                                 # soltar
        if not a["mov"]:
            if a["zona"] == "globo":
                self._clic_globo(x, y, L)
            else:
                self._clic_plano(x, y, L)
        return True

    def _accion(self, nombre):
        L = self.layout()
        if nombre == "cerrar":
            return "cerrar"
        if nombre == "g_mas":
            self._zoom_globo(1)
        elif nombre == "g_menos":
            self._zoom_globo(-1)
        elif nombre == "g_centro":
            self.vuelo = self.sede
            self._avisar("Volando a tu ubicación")
        elif nombre == "g_deshacer":
            if DATOS["marcas_globo"]:
                DATOS["marcas_globo"].pop()
                guardar_datos()
                self._avisar("Última marca quitada")
        elif nombre == "p_deshacer":
            if self.marcas_plano():
                self.marcas_plano().pop()
                self._avisar("Última marca quitada")
        elif nombre == "g_sol":
            self.sol_real = not self.sol_real
            self._avisar("Sol real de la fecha y hora actuales" if self.sol_real else "Luz fija: se ve mejor el mapa")
        elif nombre == "g_limpiar":
            if DATOS["marcas_globo"]:
                DATOS["marcas_globo"].clear()
                guardar_datos()
                self._avisar("Marcas del planeta borradas")
        elif nombre == "p_mas":
            self._zoom_plano(1, None, L)
        elif nombre == "p_menos":
            self._zoom_plano(-1, None, L)
        elif nombre == "p_centro":
            area, celda, ox0, oy0, _cb = self._centrado(L, self.pz)
            j = self.juego.jugador
            self.pan = [area.centerx - j.x * celda - ox0, area.centery - j.y * celda - oy0]
        elif nombre == "p_limpiar":
            if self.marcas_plano():
                self.marcas_plano().clear()
                self._avisar("Marcas del plano borradas")
        return True

    def _zoom(self, delta, pos):
        L = self.layout()
        if pos is not None and L["plano"].collidepoint(pos):
            self._zoom_plano(delta, pos, L)
        else:
            self._zoom_globo(delta)

    def _zoom_globo(self, delta):
        self.gz = max(0, min(len(GLOBO_ZOOMS) - 1, self.gz + (1 if delta > 0 else -1)))

    def _zoom_plano(self, delta, foco, L):
        area, celda, ox, oy, cb = self.geom_plano(L)
        nz = max(0, min(len(PLANO_ZOOMS) - 1, self.pz + (1 if delta > 0 else -1)))
        if nz == self.pz:
            return
        fx, fy = foco if foco else area.center
        gx, gy = (fx - ox) / celda, (fy - oy) / celda           # la celda que está bajo el foco debe quedarse ahí
        self.pz = nz
        _a, nc, ox0, oy0, _b = self._centrado(L, nz)
        self.pan = [fx - gx * nc - ox0, fy - gy * nc - oy0]

    def _girar(self, dx, dy, L):
        k = math.degrees(1.0 / self.radio_globo(L))               # grados por píxel
        self.lon0 = ((self.lon0 - dx * k / max(0.25, math.cos(math.radians(self.lat0))) + 180.0) % 360.0) - 180.0
        self.lat0 = max(-85.0, min(85.0, self.lat0 + dy * k))

    # ------------------------------------------------------------------ marcas
    def _marca_globo_en(self, x, y, L):
        for i, m in enumerate(DATOS["marcas_globo"]):
            p = self.pos_globo(m["lat"], m["lon"], L)
            if p and math.hypot(p[0] - x, p[1] - y) <= K(13):
                return i
        return None

    def _marca_plano_en(self, x, y, L):
        area, celda, ox, oy, _cb = self.geom_plano(L)
        if not area.collidepoint(x, y):
            return None
        gx, gy = (x - ox) / celda, (y - oy) / celda
        rad = max(0.9, K(13) / celda)
        for i, (mx, my) in enumerate(self.marcas_plano()):
            if math.hypot(mx - gx, my - gy) <= rad:
                return i
        return None

    def _quitar_en(self, x, y):
        L = self.layout()
        i = self._marca_globo_en(x, y, L) if L["rg"].collidepoint(x, y) else None
        if i is not None:
            DATOS["marcas_globo"].pop(i)
            guardar_datos()
            self._avisar("Marca quitada")
            return
        j = self._marca_plano_en(x, y, L)
        if j is not None:
            self.marcas_plano().pop(j)
            self._avisar("Marca quitada")

    def _clic_globo(self, x, y, L):
        marcas = DATOS["marcas_globo"]
        i = self._marca_globo_en(x, y, L)
        if i is not None:
            marcas.pop(i)
            guardar_datos()
            self._avisar("Marca quitada")
            return
        Re = self.radio_globo(L)
        ll = _desproyectar((x - L["gcx"]) / Re, (L["gcy"] - y) / Re, self.lat0, self.lon0)
        if ll is None:
            return
        if len(marcas) >= MAX_MARCAS_GLOBO:
            self._avisar(f"Máximo {MAX_MARCAS_GLOBO} marcas en el planeta")
            return
        marcas.append({"lat": round(ll[0], 2), "lon": round(ll[1], 2)})
        guardar_datos()
        c = ciudad_cercana(*ll)
        self._avisar(f"Punto {len(marcas)}: {_coord_texto(*ll)}" + (f" · cerca de {c[0]}" if c else ""))

    def _clic_plano(self, x, y, L):
        area, celda, ox, oy, _cb = self.geom_plano(L)
        if not area.collidepoint(x, y):
            return
        marcas = self.marcas_plano()
        i = self._marca_plano_en(x, y, L)
        if i is not None:
            marcas.pop(i)
            self._avisar("Marca quitada")
            return
        gx, gy = (x - ox) / celda, (y - oy) / celda
        if not (0 <= gx < COLS and 0 <= gy < FILAS):
            return
        if MAPA[int(gy)][int(gx)] != 0:
            self._avisar("Solo puedes marcar zonas libres")
            return
        if len(marcas) >= MAX_MARCAS_PLANO:
            self._avisar(f"Máximo {MAX_MARCAS_PLANO} marcas en el plano")
            return
        marcas.append((gx, gy))
        self._avisar(f"Punto {len(marcas)} marcado")

    # ------------------------------------------------------------------ dibujo
    def _esfera(self, Re):
        """Planeta con nitidez completa si ya está calculado; si no, una vista previa rápida mientras se calcula."""
        sol = self._sol_efectivo()
        clave = (round(self.lat0, 1), round(self.lon0, 1), Re, round(sol[0]), round(sol[1]))
        if clave in _GLOBOS:
            return _GLOBOS[clave]
        if self.tarea_clave != clave:                            # vista nueva: vista previa + cálculo en segundo plano
            self.tarea_clave = clave
            self.tarea = _generar_globo(self.lat0, self.lon0, Re, sol)
            _, chico = _correr(_generar_globo(self.lat0, self.lon0, max(24, min(64, Re // 4)), sol))
            self.preview = pygame.transform.smoothscale(chico, (2 * Re, 2 * Re))
        moviendo = self.arrastre is not None and self.arrastre["mov"] and self.arrastre["zona"] == "globo"
        if not moviendo:
            fin, esf = _correr(self.tarea, 9)                    # unos 9 ms por fotograma
            if fin:
                self.tarea_clave = None                          # tarea terminada (si se descarta de la caché, se recalcula)
                _GLOBOS[clave] = esf
                while len(_GLOBOS) > 8:
                    _GLOBOS.pop(next(iter(_GLOBOS)))
                return esf
        return self.preview

    def _animar(self):
        """Vuelo suave de la cámara del planeta hacia un destino (botón ◎)."""
        if self.vuelo is None:
            return
        la, lo = self.vuelo
        dlo = ((lo - self.lon0 + 180.0) % 360.0) - 180.0
        dla = la - self.lat0
        if abs(dlo) < 0.05 and abs(dla) < 0.05:
            self.lat0, self.lon0, self.vuelo = la, lo, None
            return
        self.lat0 += dla * 0.18
        self.lon0 = ((self.lon0 + dlo * 0.18 + 180.0) % 360.0) - 180.0

    def _dibujar_marcas_globo(self, L, t):
        marcas = DATOS["marcas_globo"]
        Re = self.radio_globo(L)
        gcx, gcy = L["gcx"], L["gcy"]
        vec = [_proyectar(m["lat"], m["lon"], self.lat0, self.lon0) for m in marcas]
        for i in range(1, len(vec)):                              # ruta entre marcas (arco de círculo máximo)
            prev = None
            for v in _arco(vec[i - 1], vec[i]):
                p = (gcx + v[0] * Re, gcy - v[1] * Re) if v[2] > 0.03 else None
                if p and prev:
                    pygame.draw.line(pantalla, (0, 0, 0), (prev[0] + 1, prev[1] + 1), (p[0] + 1, p[1] + 1), 3)
                    pygame.draw.line(pantalla, COLOR_MARCA, prev, p, 2)
                prev = p
        lista = CIUDADES_LUCES if self.gz >= 2 else (UBICACIONES if self.gz == 1 else ())
        for n, la, lo in lista:                                   # nombres de ciudades al acercar
            x, y, z = _proyectar(la, lo, self.lat0, self.lon0)
            if z > 0.3:
                p = (int(gcx + x * Re), int(gcy - y * Re))
                pygame.draw.circle(pantalla, (235, 235, 245), p, 2)
                texto(n, FUENTE_XS, (190, 205, 230), (p[0] + K(5), p[1] - K(7)))
        sede = _proyectar(self.sede[0], self.sede[1], self.lat0, self.lon0)
        if sede[2] > 0.03:                                        # tu ubicación (pulso)
            p = (int(gcx + sede[0] * Re), int(gcy - sede[1] * Re))
            pulso = (t * 0.9) % 1.0
            pygame.draw.circle(pantalla, (255, 80, 60), p, int(K(6) + K(30) * pulso), 2)
            pygame.draw.circle(pantalla, (255, 80, 60), p, K(5))
            pygame.draw.circle(pantalla, (255, 255, 255), p, K(5), 1)
        for i, v in enumerate(vec):
            if v[2] > 0.03:
                _pin(pantalla, int(gcx + v[0] * Re), int(gcy - v[1] * Re), K(7), COLOR_MARCA, i + 1)
        c = self.cursor                                           # punto fantasma bajo el cursor
        moviendo = self.arrastre is not None and self.arrastre["mov"]
        if c and not moviendo and L["rg"].collidepoint(c) and \
                _desproyectar((c[0] - gcx) / Re, (gcy - c[1]) / Re, self.lat0, self.lon0):
            hay = self._marca_globo_en(c[0], c[1], L) is not None
            col = (255, 90, 80) if hay else ACENTO
            pygame.draw.circle(pantalla, col, c, K(9), 2)
            pygame.draw.line(pantalla, col, (c[0] - K(14), c[1]), (c[0] - K(5), c[1]), 2)
            pygame.draw.line(pantalla, col, (c[0] + K(5), c[1]), (c[0] + K(14), c[1]), 2)

    def _texto_info_globo(self, L):
        Re = self.radio_globo(L)
        c = self.cursor
        if c and L["rg"].collidepoint(c):
            ll = _desproyectar((c[0] - L["gcx"]) / Re, (L["gcy"] - c[1]) / Re, self.lat0, self.lon0)
            if ll:
                s = _coord_texto(*ll)
                ciudad = ciudad_cercana(*ll)
                return s + (f" · cerca de {ciudad[0]}" if ciudad else "")
        marcas = DATOS["marcas_globo"]
        if marcas:
            km = sum(_dist_km(marcas[i - 1]["lat"], marcas[i - 1]["lon"], marcas[i]["lat"], marcas[i]["lon"])
                     for i in range(1, len(marcas)))
            s = f"{len(marcas)} marca{'s' if len(marcas) != 1 else ''}"
            return s + (f" · ruta {km:,.0f} km".replace(",", ".") if len(marcas) > 1 else "")
        return "Toca el planeta para marcar un punto" if MOVIL else "Arrastra para girar · clic para marcar"

    def _dibujar_botones(self, L, mouse):
        etiquetas = {"cerrar": "CERRAR", "g_limpiar": "LIMPIAR", "p_limpiar": "LIMPIAR",
                     "g_sol": "SOL REAL" if self.sol_real else "LUZ FIJA"}
        ayudas = {"cerrar": "Volver al juego (M)", "g_mas": "Acercar (+)", "g_menos": "Alejar (−)",
                  "g_centro": "Ir a tu ubicación (C)", "g_deshacer": "Quitar la última marca (Z)",
                  "g_limpiar": "Borrar todas las marcas (Supr)", "g_sol": "Sol real de ahora / luz fija",
                  "p_mas": "Acercar (+)", "p_menos": "Alejar (−)", "p_centro": "Centrar en ti (C)",
                  "p_deshacer": "Quitar la última marca (Z)", "p_limpiar": "Borrar todas las marcas (Supr)"}
        tip = None
        for nombre, r in self.botones(L).items():
            hover = r.collidepoint(mouse)
            activo = nombre == "g_sol" and self.sol_real
            rad = r.height // 2
            fondo = (30, 74, 112) if hover else ((20, 46, 70) if activo else (12, 24, 42))
            borde = (255, 120, 90) if (hover and nombre == "cerrar") else (ACENTO if (hover or activo) else (70, 120, 165))
            pygame.draw.rect(pantalla, fondo, r, border_radius=rad)
            pygame.draw.rect(pantalla, borde, r, 2, border_radius=rad)
            cx, cy = r.center
            h, col = max(4, r.height // 4), (235, 240, 250)
            if nombre.endswith("_mas"):
                pygame.draw.line(pantalla, col, (cx - h, cy), (cx + h, cy), 2)
                pygame.draw.line(pantalla, col, (cx, cy - h), (cx, cy + h), 2)
            elif nombre.endswith("_menos"):
                pygame.draw.line(pantalla, col, (cx - h, cy), (cx + h, cy), 2)
            elif nombre.endswith("_centro"):
                pygame.draw.circle(pantalla, col, (cx, cy), h, 2)
                pygame.draw.circle(pantalla, col, (cx, cy), max(1, h // 3))
            elif nombre.endswith("_deshacer"):
                pygame.draw.arc(pantalla, col, (cx - h, cy - h, 2 * h, 2 * h), 0.3, 3.4, 2)
                pygame.draw.polygon(pantalla, col, [(cx - h - 3, cy - 1), (cx - h + 4, cy - 1), (cx - h, cy + 5)])
            else:
                if nombre == "cerrar":
                    pygame.draw.line(pantalla, col, (r.left + K(14), cy - h // 2), (r.left + K(14) + h, cy + h // 2), 2)
                    pygame.draw.line(pantalla, col, (r.left + K(14), cy + h // 2), (r.left + K(14) + h, cy - h // 2), 2)
                    texto(etiquetas[nombre], FUENTE_XS, col, (cx + K(8), cy), centro=True)
                else:
                    texto(etiquetas[nombre], FUENTE_XS, col, (cx, cy), centro=True)
            if hover:
                tip = (r, ayudas.get(nombre, ""))
        if tip and tip[1]:                                        # ayuda emergente
            r, msg = tip
            s = FUENTE_XS.render(msg, True, (240, 245, 255))
            tr = s.get_rect(center=(min(max(r.centerx, K(80)), ANCHO - K(80)), r.bottom + K(16)))
            fondo = tr.inflate(K(16), K(8))
            pygame.draw.rect(pantalla, (8, 14, 26), fondo, border_radius=8)
            pygame.draw.rect(pantalla, ACENTO, fondo, 1, border_radius=8)
            pantalla.blit(s, tr)

    def dibujar(self, juego):
        L = self.layout()
        t = juego.reloj
        mouse = pygame.mouse.get_pos()
        self._animar()
        pantalla.blit(_fondo_espacio(), (0, 0))
        nombre, lat, lon = UBICACIONES[(juego.nivel - 1) % len(UBICACIONES)]
        texto("MAPA", FUENTE_BOTON, (235, 240, 250), (K(24), K(12)))
        x_niv = K(24) + FUENTE_BOTON.size("MAPA")[0] + K(14)
        etq_niv = f"NIVEL {juego.nivel}"
        w1 = FUENTE_P.size(etq_niv)[0] + K(20)
        chip = pygame.Rect(x_niv, K(12), w1, K(28))
        pygame.draw.rect(pantalla, (70, 18, 22), chip, border_radius=K(14))
        pygame.draw.rect(pantalla, (255, 110, 90), chip, 2, border_radius=K(14))
        texto(etq_niv, FUENTE_P, (255, 190, 170), chip.center, centro=True)
        d = self.ahora
        etq_fecha = f"{d.day:02d} {MESES_ES[d.month - 1]} {d.year} · {d.hour:02d}:{d.minute:02d} UTC"
        chip2 = pygame.Rect(chip.right + K(10), K(12), FUENTE_XS.size(etq_fecha)[0] + K(24), K(28))
        pygame.draw.rect(pantalla, (12, 30, 52), chip2, border_radius=K(14))
        pygame.draw.rect(pantalla, (70, 120, 165), chip2, 2, border_radius=K(14))
        texto(etq_fecha, FUENTE_XS, (170, 205, 240), chip2.center, centro=True)

        # ---- planeta Tierra (columna izquierda)
        R, gcx, gcy, rg = L["R"], L["gcx"], L["gcy"], L["rg"]
        Re = self.radio_globo(L)
        esfera = self._esfera(Re)
        halo, hm = _halo(Re)
        pantalla.set_clip(rg)
        pantalla.blit(halo, (gcx - Re - hm, gcy - Re - hm))
        pantalla.blit(esfera, (gcx - Re, gcy - Re))
        self._dibujar_marcas_globo(L, t)
        pantalla.set_clip(None)
        info = self._texto_info_globo(L)
        ir = pygame.Rect(0, 0, FUENTE_XS.size(info)[0] + K(22), K(24))
        ir.center = (rg.centerx, rg.top + K(12))
        pygame.draw.rect(pantalla, (8, 16, 30), ir, border_radius=K(12))
        pygame.draw.rect(pantalla, (70, 120, 165), ir, 1, border_radius=K(12))
        texto(info, FUENTE_XS, (210, 228, 250), ir.center, centro=True)
        texto(nombre.upper(), FUENTE_M, (255, 230, 200), (gcx, gcy + R + K(22)), centro=True)
        texto(_coord_texto(lat, lon), FUENTE_XS, (160, 190, 230), (gcx, gcy + R + K(44)), centro=True)

        # ---- lista de misiones bajo el planeta (panel de vidrio)
        y0 = gcy + R + K(70)
        x0 = K(28)
        _vidrio(pygame.Rect(K(14), y0 - K(8), rg.right - K(18), K(40) + len(juego.misiones) * K(22)), 170, 12)
        texto("MISIONES", FUENTE_P, (235, 215, 200), (x0, y0))
        for i, mi in enumerate(juego.misiones):
            y = y0 + K(24) + i * K(22)
            hecho, actual = i < juego.paso, i == juego.paso
            col = (110, 200, 120) if hecho else ((255, 230, 120) if actual else (150, 150, 160))
            _marca_mision(x0, y + K(8), hecho, actual)
            txt = juego.texto_mision(mi) + (f"  {juego.progreso_mision(mi)}" if actual and juego.progreso_mision(mi) else "")
            texto(txt, FUENTE_XS, col, (x0 + K(20), y))

        # ---- plano táctico (panel de vidrio)
        pl = L["plano"]
        px, py, pw, ph = pl.x, pl.y, pl.width, pl.height
        _vidrio(pl, 215, 14)
        texto("PLANO TÁCTICO", FUENTE_P, (150, 200, 235), (px + K(16), py + K(14)))
        area, celda, ox, oy, _cb = self.geom_plano(L)
        if ("grande", celda) not in juego.cache:
            juego.cache[("grande", celda)] = crear_base_mapa(celda, (20, 38, 62, 255), (58, 78, 110, 255))
        pantalla.set_clip(area)
        pantalla.blit(juego.cache[("grande", celda)], (ox, oy))
        _marcas_mapa(juego, pantalla, celda, ox, oy, t)
        for i, (mx, my) in enumerate(self.marcas_plano()):
            r = max(3, min(10, int(celda * 0.8)))
            texto(str(i + 1), FUENTE_XS, (255, 225, 170), (int(ox + mx * celda) + r + K(2), int(oy + my * celda) - 3 * r - K(8)))
        c = self.cursor                                           # casilla resaltada bajo el cursor
        if c and area.collidepoint(c) and not (self.arrastre and self.arrastre["mov"]):
            gx, gy = (c[0] - ox) / celda, (c[1] - oy) / celda
            if 0 <= gx < COLS and 0 <= gy < FILAS:
                libre = MAPA[int(gy)][int(gx)] == 0
                hay = self._marca_plano_en(c[0], c[1], L) is not None
                col = (255, 90, 80) if (hay or not libre) else (90, 255, 160)
                pygame.draw.rect(pantalla, col, (ox + int(gx) * celda, oy + int(gy) * celda, celda, celda), 2)
        pantalla.set_clip(None)
        ly = py + ph - K(24)                                         # leyenda
        pygame.draw.circle(pantalla, (255, 230, 60), (px + K(24), ly), 5)
        texto("Tú", FUENTE_XS, (220, 220, 220), (px + K(36), ly - K(8)))
        pygame.draw.circle(pantalla, (255, 60, 60), (px + K(90), ly), 4)
        texto("Infectados", FUENTE_XS, (220, 220, 220), (px + K(100), ly - K(8)))
        ox2 = px + K(215)
        pygame.draw.polygon(pantalla, (90, 210, 255), [(ox2, ly - 5), (ox2 + 5, ly), (ox2, ly + 5), (ox2 - 5, ly)])
        texto("Objetivo", FUENTE_XS, (220, 220, 220), (ox2 + 12, ly - K(8)))
        ox3 = px + K(305)
        pygame.draw.circle(pantalla, COLOR_MARCA, (ox3, ly - 2), 5)
        texto(f"Marcas {len(self.marcas_plano())}/{MAX_MARCAS_PLANO}", FUENTE_XS, (220, 220, 220), (ox3 + 10, ly - K(8)))
        ayuda = "Arrastra: mover · Toca: marcar / quitar" if MOVIL else \
            "Arrastra: mover · Clic: marcar / quitar · Rueda: zoom · Z: deshacer · M: volver"
        texto(ayuda, FUENTE_XS, (150, 160, 180), (pl.centerx, area.bottom + K(11)), centro=True)

        self._dibujar_botones(L, mouse)
        txt, hasta = self.aviso
        if txt and pygame.time.get_ticks() < hasta:
            s = FUENTE_P.render(txt, True, (255, 240, 215))
            r = s.get_rect(center=(pl.centerx, area.bottom - K(16)))
            fondo = r.inflate(K(26), K(12))
            pygame.draw.rect(pantalla, (36, 14, 10), fondo, border_radius=K(14))
            pygame.draw.rect(pantalla, COLOR_MARCA, fondo, 2, border_radius=K(14))
            pantalla.blit(s, r)


MAPA_UI = MapaInteractivo()


def dibujar_mapa_ampliado(juego):
    """Mapa a pantalla completa e interactivo: planeta Tierra (sol real 2026) + plano táctico del nivel."""
    MAPA_UI.preparar(juego)
    MAPA_UI.dibujar(juego)


def dibujar_marcas_hud(juego):
    """Puntos marcados por el jugador, visibles en la vista 3D con su distancia (como los waypoints de un juego moderno)."""
    marcas = getattr(juego, "marcas_tac", None)
    if not marcas:
        return
    jug = juego.jugador
    mitad = FOV / 2
    for i, (mx, my) in enumerate(marcas):
        dx, dy = mx - jug.x, my - jug.y
        dist = math.hypot(dx, dy)
        if dist < 0.8:
            continue
        ang = (math.atan2(dy, dx) - jug.angulo + math.pi) % (2 * math.pi) - math.pi
        y = int(ALTO * 0.28)
        if abs(ang) < mitad:
            x = int(ANCHO / 2 + math.tan(ang) / math.tan(mitad) * ANCHO / 2)
            _pin(pantalla, x, y, K(8), COLOR_MARCA, i + 1)
            texto(f"{dist:.0f} m", FUENTE_XS, (255, 235, 200), (x, y + K(14)), centro=True)
        else:                                                    # fuera de la vista: flecha en el borde
            lado = 1 if ang > 0 else -1
            x = ANCHO - K(22) if lado > 0 else K(22)
            pygame.draw.polygon(pantalla, COLOR_MARCA, [(x + lado * K(10), y), (x - lado * K(6), y - K(9)), (x - lado * K(6), y + K(9))])
            texto(f"{i + 1} · {dist:.0f} m", FUENTE_XS, (255, 235, 200), (x - lado * K(34), y), centro=True)


def alternar_marca_aqui(juego):
    """Tecla P: deja un punto donde estás (o quita el que tengas al lado)."""
    if not hasattr(juego, "marcas_tac"):
        juego.marcas_tac = []
    jug = juego.jugador
    for i, (mx, my) in enumerate(juego.marcas_tac):
        if math.hypot(mx - jug.x, my - jug.y) < 1.5:
            juego.marcas_tac.pop(i)
            return
    if len(juego.marcas_tac) < MAX_MARCAS_PLANO:
        juego.marcas_tac.append((jug.x, jug.y))


# ---------------------------------------------------------------------------
# 8.3  HUD
# ---------------------------------------------------------------------------
def _marca_mision(x, y, hecho, actual):
    if hecho:
        pygame.draw.lines(pantalla, (110, 220, 130), False, [(x - 5, y), (x - 1, y + 4), (x + 6, y - 5)], 2)
    elif actual:
        pygame.draw.polygon(pantalla, (255, 220, 90), [(x - 4, y - 5), (x + 5, y), (x - 4, y + 5)])
    else:
        pygame.draw.circle(pantalla, (120, 120, 130), (x, y), 4, 1)


def dibujar_panel_misiones(juego):
    n = len(juego.misiones)
    lineas = []
    for i, m in enumerate(juego.misiones):
        txt = juego.texto_mision(m)
        if i == juego.paso and juego.progreso_mision(m):
            txt += "  " + juego.progreso_mision(m)
        lineas.append(txt)
    w = max(K(282), max(FUENTE_XS.size(t)[0] for t in lineas) + K(48))
    x0, y0 = ANCHO - w - K(10), K(10)
    panel = pygame.Surface((w, K(30) + n * K(21)), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 140))
    pantalla.blit(panel, (x0, y0))
    texto("MISIONES", FUENTE_P, (235, 215, 200), (x0 + K(10), y0 + K(6)))
    for i, m in enumerate(juego.misiones):
        y = y0 + K(30) + i * K(21)
        hecho, actual = i < juego.paso, i == juego.paso
        col = (110, 200, 120) if hecho else ((255, 255, 255) if actual else (140, 140, 150))
        _marca_mision(x0 + K(16), y + K(8), hecho, actual)
        txt = juego.texto_mision(m)
        if actual and juego.progreso_mision(m):
            txt += "  " + juego.progreso_mision(m)
        texto(txt, FUENTE_XS, col, (x0 + K(32), y))


def dibujar_flecha_objetivo(juego):
    pos = juego.objetivo_pos()
    if pos is None:
        return
    jug = juego.jugador
    ang = math.atan2(pos[1] - jug.y, pos[0] - jug.x) - jug.angulo
    d = math.hypot(pos[0] - jug.x, pos[1] - jug.y)
    cx, cy = ANCHO // 2, K(70)
    u = (math.sin(ang), -math.cos(ang))                         # "adelante" = arriba en pantalla
    v = (math.cos(ang), math.sin(ang))
    tip = (cx + u[0] * K(17), cy + u[1] * K(17))
    b1 = (cx - u[0] * K(9) + v[0] * K(10), cy - u[1] * K(9) + v[1] * K(10))
    b2 = (cx - u[0] * K(9) - v[0] * K(10), cy - u[1] * K(9) - v[1] * K(10))
    pygame.draw.polygon(pantalla, (255, 210, 60), [tip, b1, b2])
    pygame.draw.polygon(pantalla, (40, 30, 0), [tip, b1, b2], 2)
    texto(f"{int(d)} m", FUENTE_XS, (255, 235, 170), (cx, cy + K(26)), centro=True)


def dibujar_hud(juego):
    jug = juego.jugador
    arma = ARMA_POR_ID[jug.arma]
    hb = K(56)                                                   # alto de la barra inferior
    barra = pygame.Surface((ANCHO, hb), pygame.SRCALPHA)
    barra.fill((0, 0, 0, 160))
    pantalla.blit(barra, (0, ALTO - hb))
    ya, yb, yg = ALTO - K(50), ALTO - K(31), ALTO - K(23)        # fila de etiquetas, fila de valores, barritas

    color_vida = (60, 220, 80) if jug.vida > 40 else (240, 60, 50)
    xv, xe = K(20), K(20) + K(130)
    texto(f"VIDA {jug.vida}", FUENTE_P, color_vida, (xv, ya))
    pygame.draw.rect(pantalla, (60, 60, 60), (xv, yg, K(110), K(9)))
    pygame.draw.rect(pantalla, color_vida, (xv, yg, int(K(110) * jug.vida / 100), K(9)))
    col_en = (110, 190, 255) if not jug.agotado else (200, 90, 90)
    texto("ENERGÍA", FUENTE_P, col_en, (xe, ya))
    pygame.draw.rect(pantalla, (60, 60, 60), (xe, yg, K(100), K(9)))
    pygame.draw.rect(pantalla, (80, 170, 255) if not jug.agotado else (200, 90, 90),
                     (xe, yg, int(K(100) * jug.energia / 100), K(9)))
    xa = int(ANCHO * 0.27)
    texto(f"{arma['nombre']}  ·  {NOMBRE_CORTO_MIRA[jug.stats['mira']]}", FUENTE_XS, (255, 255, 255), (xa, ya + K(2)))
    texto(f"MUNICIÓN {jug.municion[jug.arma]}", FUENTE_M, (255, 210, 60), (xa, yb))
    xn = int(ANCHO * 0.57)
    texto(f"NIVEL {juego.nivel}", FUENTE_P, (255, 120, 100), (xn, ya))
    texto(f"INFECTADOS {juego.vivos()}", FUENTE_M, (255, 255, 255), (xn, yb))
    xm = int(ANCHO * 0.80)
    texto(f"+{juego.monedas_nivel}", FUENTE_P, (200, 200, 120), (xm, ya))
    texto(f"MONEDAS {DATOS['monedas']}", FUENTE_M, (255, 210, 60), (xm, yb))

    cx, cy = ANCHO // 2, ALTO // 2
    if jug.apuntando < 0.5:
        color_mira = COLORES_MIRA[DATOS["mira_color"] % len(COLORES_MIRA)]
        dibujar_mira(cx, cy, DATOS["mira_estilo"], color_mira)
    if jug.marca > 0:
        col = (255, 40, 40) if jug.marca_cabeza else (255, 255, 255)
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            pygame.draw.line(pantalla, col, (cx + dx * K(12), cy + dy * K(12)), (cx + dx * K(20), cy + dy * K(20)), 2)
    if juego.t_headshot > 0:
        texto("¡HEADSHOT!", FUENTE_M, (255, 50, 40), (ANCHO // 2, ALTO // 2 - K(60)), centro=True)

    if juego.progreso > 0:                                       # barra de activación (mantén F)
        bw = K(120)
        pygame.draw.rect(pantalla, (20, 20, 20), (cx - bw // 2 - 2, cy + K(60), bw + 4, K(14)))
        pygame.draw.rect(pantalla, (255, 170, 40), (cx - bw // 2, cy + K(62), int(bw * min(1.0, juego.progreso)), K(10)))
        texto("ACTIVANDO...", FUENTE_XS, (255, 230, 170), (cx, cy + K(90)), centro=True)
    elif juego.pista:
        texto(juego.pista, FUENTE_P, (255, 230, 170), (cx, cy + K(70)), centro=True)

    if juego.t_mensaje > 0:
        texto(juego.mensaje, FUENTE_P, (255, 255, 255), (ANCHO // 2, ALTO - hb - K(22)), centro=True)
    dibujar_panel_misiones(juego)
    dibujar_flecha_objetivo(juego)
    if jug.dano_flash > 0:
        rojo = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        rojo.fill((220, 0, 0, int(130 * jug.dano_flash / 0.35)))
        pantalla.blit(rojo, (0, 0))


# ===========================================================================
# 9. INTERFAZ DE TERROR (fondo, botones, efectos)
# ===========================================================================
def _rama(s, x, y, ang, largo, grosor, prof, rng):
    if prof == 0 or largo < 4:
        return
    x2, y2 = x + math.cos(ang) * largo, y + math.sin(ang) * largo
    pygame.draw.line(s, (4, 2, 6), (x, y), (x2, y2), max(1, grosor))
    for da in (-0.5, 0.45):
        _rama(s, x2, y2, ang + da + rng.uniform(-0.2, 0.2), largo * rng.uniform(0.68, 0.8), grosor - 1, prof - 1, rng)


def crear_fondo_menu():
    """Cementerio embrujado. Las posiciones se reparten según el tamaño real de la pantalla."""
    rng = random.Random(6)
    fx = lambda v: int(v * ANCHO / 800)          # posición horizontal del diseño original
    fy = lambda v: int(v * ALTO / 600)           # posición vertical del diseño original
    s = pygame.Surface((ANCHO, ALTO))
    for y in range(ALTO):
        t = y / ALTO
        pygame.draw.line(s, (int(6 + 30 * t * t), int(2 + 5 * t), int(10 + 8 * t)), (0, y), (ANCHO, y))
    for _ in range(int(60 * ANCHO / 800)):                     # estrellas apagadas
        pygame.draw.circle(s, (90, 85, 100), (rng.randint(0, ANCHO), rng.randint(0, fy(260))), 1)
    lx_, ly_ = fx(590), fy(130)                                  # luna
    halo = pygame.Surface((K(320), K(320)), pygame.SRCALPHA)
    for r, a in ((160, 14), (120, 22), (85, 40)):
        pygame.draw.circle(halo, (200, 190, 170, a), (K(160), K(160)), K(r))
    s.blit(halo, (lx_ - K(160), ly_ - K(160)))
    pygame.draw.circle(s, (215, 205, 185), (lx_, ly_), K(46))
    pygame.draw.circle(s, (180, 170, 150), (lx_ - K(15), ly_ - K(12)), K(9))
    pygame.draw.circle(s, (185, 175, 155), (lx_ + K(14), ly_ + K(10)), K(6))
    colinas = [(0, 430), (120, 385), (260, 420), (420, 372), (560, 415), (700, 380), (800, 410)]
    pygame.draw.polygon(s, (10, 4, 12), [(fx(x), fy(y)) for x, y in colinas] + [(ANCHO, ALTO), (0, ALTO)])
    hx, hy = fx(60), fy(330)                                     # casa embrujada
    pygame.draw.rect(s, (8, 3, 10), (hx, hy, K(120), K(100)))
    pygame.draw.polygon(s, (8, 3, 10), [(hx - K(10), hy + K(2)), (hx + K(60), hy - K(60)), (hx + K(130), hy + K(2))])
    pygame.draw.rect(s, (8, 3, 10), (hx + K(90), hy - K(45), K(16), K(40)))
    pygame.draw.rect(s, (170, 120, 30), (hx + K(28), hy + K(30), K(18), K(26)))
    pygame.draw.rect(s, (110, 75, 20), (hx + K(70), hy + K(30), K(18), K(26)))
    for bx in (250, 690, 745):
        _rama(s, fx(bx), fy(440), -math.pi / 2, rng.randint(K(55), K(80)), 6, 7, rng)
    for lx in range(fx(230), ANCHO - K(20), K(62)):             # lápidas
        ly = fy(470) + rng.randint(0, K(25))
        pygame.draw.rect(s, (12, 6, 14), (lx, ly, K(20), K(30)), border_top_left_radius=K(10), border_top_right_radius=K(10))
        pygame.draw.line(s, (30, 20, 34), (lx + K(10), ly + K(6)), (lx + K(10), ly + K(16)), 2)
        pygame.draw.line(s, (30, 20, 34), (lx + K(6), ly + K(10)), (lx + K(14), ly + K(10)), 2)
    return s.convert()


def crear_vineta():
    s = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
    pasos = 70
    for i in range(pasos):
        a = int(230 * (1 - i / pasos) ** 2)
        pygame.draw.rect(s, (0, 0, 0, a), (i * 4, i * 3, ANCHO - i * 8, ALTO - i * 6), 4)
    return s.convert_alpha()


def crear_niebla(w, h):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(22):
        ox, oy = i * w // 48, i * h // 48
        pygame.draw.ellipse(s, (150, 150, 168, int(3 + i * 1.5)), (ox, oy, w - 2 * ox, h - 2 * oy))
    return s


FONDO_MENU = crear_fondo_menu()
VINETA = crear_vineta()
NIEBLAS = [crear_niebla(int(ANCHO * 0.65), K(170)), crear_niebla(int(ANCHO * 0.52), K(140)),
           crear_niebla(int(ANCHO * 0.75), K(190))]
_rng_d = random.Random(12)
GOTEOS = [(_rng_d.randint(10, ANCHO - 10), _rng_d.uniform(0.02, 0.06), _rng_d.uniform(0, 3000),
           _rng_d.randint(K(40), K(180))) for _ in range(int(16 * ANCHO / 800))]
OJOS = [(int(ANCHO * 110 / 800), K(400), 0.0), (int(ANCHO * 690 / 800), K(330), 2.1),
        (int(ANCHO * 400 / 800), K(455), 4.0), (int(ANCHO * 745 / 800), K(505), 5.5),
        (int(ANCHO * 300 / 800), K(430), 1.2), (int(ANCHO * 580 / 800), K(480), 3.3)]


class AmbienteTerror:
    """Animaciones del fondo de terror: niebla, sangre, ojos, relámpagos, parpadeo."""

    def __init__(self):
        self.t = 0.0
        self.rayo = 0.0
        self.prox_rayo = random.uniform(4, 9)
        self.parpadeo = 0.0

    def actualizar(self, dt):
        self.t += dt
        self.rayo = max(0.0, self.rayo - dt * 1.6)
        self.parpadeo = max(0.0, self.parpadeo - dt)
        if self.t > self.prox_rayo:
            self.prox_rayo = self.t + random.uniform(7, 15)
            self.rayo = 1.0
            reproducir(SND_TRUENO, 0.7)
        if random.random() < 0.02:
            self.parpadeo = 0.10

    def dibujar_fondo(self, oscurecer=0):
        pantalla.blit(FONDO_MENU, (0, 0))
        ms = self.t * 1000
        for x, y, fase in OJOS:
            if math.sin(ms / 1100 + fase) > -0.55:
                glow = pygame.Surface((60, 30), pygame.SRCALPHA)
                pygame.draw.ellipse(glow, (255, 0, 0, 40), glow.get_rect())
                pantalla.blit(glow, (x - 30, y - 15))
                for ox in (-9, 9):
                    pygame.draw.circle(pantalla, (255, 30, 20), (x + ox, y), 3)
        for i, n in enumerate(NIEBLAS):
            w = n.get_width()
            px = (self.t * (14 + 9 * i) * UI + i * K(300)) % (ANCHO + w) - w
            pantalla.blit(n, (px, K(300) + i * K(70) + math.sin(self.t * 0.4 + i) * K(12)))
        for gx, vel, fase, largo in GOTEOS:
            l = min(largo, int((ms * vel + fase) % (largo * 1.6)))
            pygame.draw.line(pantalla, (120, 0, 0), (gx, 0), (gx, l), 3)
            pygame.draw.circle(pantalla, (150, 0, 0), (gx, l), 4)
        if oscurecer:
            velo = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
            velo.fill((0, 0, 0, oscurecer))
            pantalla.blit(velo, (0, 0))

    def dibujar_capas_finales(self):
        pantalla.blit(VINETA, (0, 0))
        if self.rayo > 0:
            luz = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
            luz.fill((220, 225, 255, int(90 * self.rayo)))
            pantalla.blit(luz, (0, 0))

    def titulo(self, txt, y=95, fuente=None):
        fuente = fuente or FUENTE_TITULO
        color = (70, 0, 0) if self.parpadeo > 0 else (205, 12, 12)
        sombra = fuente.render(txt, True, (40, 0, 0))
        render = fuente.render(txt, True, color)
        r = render.get_rect(center=(ANCHO // 2, y))
        pantalla.blit(sombra, sombra.get_rect(center=(ANCHO // 2 + 4, y + 4)))
        pantalla.blit(render, r)
        ms = self.t * 1000
        for i in range(10):                                      # gotas bajo el título
            gx = r.left + 25 + i * (r.width - 50) // 9
            largo = 8 + int((math.sin(ms / 600 + i * 1.7) + 1) * 14) + (i * 7) % 12
            pygame.draw.line(pantalla, (150, 0, 0), (gx, r.bottom - 8), (gx, r.bottom + largo), 3)
            pygame.draw.circle(pantalla, (170, 0, 0), (gx, r.bottom + largo), 4)


def boton_terror(txt, x, y, w, h, mouse, activo=True, seleccionado=False):
    r = pygame.Rect(x, y, w, h)
    hover = bool(activo and r.collidepoint(mouse))
    if not activo:
        fondo, borde, col = (18, 12, 14), (70, 50, 50), (110, 95, 95)
    elif hover:
        fondo, borde, col = (62, 4, 6), (255, 40, 30), (255, 235, 225)
        glow = pygame.Surface((w + 30, h + 30), pygame.SRCALPHA)
        pygame.draw.rect(glow, (255, 20, 10, 60), glow.get_rect(), border_radius=16)
        pantalla.blit(glow, (x - 15, y - 15))
    else:
        fondo, borde, col = (22, 4, 6), (130, 12, 12), (215, 195, 185)
    if seleccionado:
        borde = (255, 210, 40)
    pygame.draw.rect(pantalla, fondo, r, border_radius=8)
    pygame.draw.rect(pantalla, borde, r, width=3, border_radius=8)
    off = (random.randint(-1, 1), random.randint(-1, 1)) if hover else (0, 0)
    texto(txt, FUENTE_BOTON, col, (x + w // 2 + off[0], y + h // 2 + off[1]), centro=True)
    return r, hover


def dibujar_candado(x, y):
    pygame.draw.rect(pantalla, (150, 150, 160), (x - K(7), y - 1, K(14), K(11)), border_radius=2)
    pygame.draw.arc(pantalla, (150, 150, 160), (x - K(5), y - K(11), K(10), K(14)), 0, math.pi, 2)


def eventos_basicos():
    """Devuelve (clics, teclas_pulsadas) y cierra si se pide."""
    clics, teclas = [], []
    ciclo_android()
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            salir()
        elif ev.type == pygame.KEYDOWN:
            teclas.append(pygame.K_ESCAPE if ev.key == TECLA_ATRAS else ev.key)
        elif MOVIL:
            clic = TOQUE.evento(ev)
            if clic:
                clics.append(clic)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            clics.append(ev.pos)
    return clics, teclas


# ===========================================================================
# 10. PANTALLAS: MENÚ, NIVELES, TIENDA, PERSONALIZAR
# ===========================================================================
def pantalla_menu():
    amb = AmbienteTerror()
    while True:
        dt = min(0.05, reloj.tick(FPS_LIMITE) / 1000.0)
        amb.actualizar(dt)
        mouse = pygame.mouse.get_pos()

        amb.dibujar_fondo()
        amb.titulo("ABISMO DE SANGRE", Y(95))
        texto("No mires atrás. Ellos ya te vieron.", FUENTE_P, (150, 120, 120), (ANCHO // 2, Y(175)), centro=True)

        opciones = [("JUGAR", "jugar"), ("ARMERÍA", "tienda"), ("ACCESORIOS", "accesorios"),
                    ("PERSONALIZAR", "personalizar"), ("AJUSTES", "ajustes"), ("SALIR", "salir")]
        if MOVIL:
            opciones.insert(len(opciones) - 2, ("CONTROLES", "controles"))
        paso, alto_b = (46, 40) if MOVIL else (58, 48)
        botones = []
        for i, (txt, clave) in enumerate(opciones):
            r, _ = boton_terror(txt, ANCHO // 2 - K(150), Y(215 + i * paso), K(300), K(alto_b), mouse)
            botones.append((r, clave))
        texto(f"MONEDAS: {DATOS['monedas']}", FUENTE_M, (255, 210, 60), (ANCHO - K(150), K(26)), centro=True)
        amb.dibujar_capas_finales()

        clics, teclas = eventos_basicos()
        if pygame.K_ESCAPE in teclas:
            return "salir"
        for c in clics:
            for r, clave in botones:
                if r.collidepoint(c):
                    reproducir(SND_CLIC)
                    return clave
        pygame.display.flip()


# ---------------------------------------------------------------------------
# AJUSTES GRÁFICOS: pantalla con vista previa en vivo
# ---------------------------------------------------------------------------
def _crear_mapa_demo():
    W, H = 20, 9
    g = [[0] * W for _ in range(H)]
    for x in range(W):
        g[0][x], g[H - 1][x] = 1, 2
    for y in range(H):
        g[y][0], g[y][W - 1] = 4, 3
    for x in (6, 10, 14):
        g[2][x], g[6][x] = 2, 1
    g[4][16] = 4
    return g


DEMO_MAPA = _crear_mapa_demo()


class _JugDemo:
    x = y = angulo = pitch = 0.0


def _escena_demo(t):
    """Pasillo de prueba con los 4 tipos de pared: se ve cómo quedan los ajustes sin entrar a jugar."""
    global OSCURIDAD
    guardado = [fila[:] for fila in MAPA]
    osc, zoom = OSCURIDAD, CAMARA["zoom"]
    j = _JugDemo()
    j.x, j.y = 3.0 + 4.5 * (0.5 + 0.5 * math.sin(t * 0.35)), 4.5
    j.angulo, j.pitch = 0.55 * math.sin(t * 0.5), 0
    MAPA[:] = DEMO_MAPA
    OSCURIDAD, CAMARA["zoom"] = 1.1, 1.0
    try:
        dibujar_paredes(j, _ZBUF_DEMO)
    finally:
        MAPA[:] = guardado
        OSCURIDAD, CAMARA["zoom"] = osc, zoom


_ZBUF_DEMO = [0.0] * (ANCHO + 1)
_LISTAS_GRAF = {"col": COLUMNAS_OPC, "dist": DIST_OPC, "tex": TEXCAL_OPC, "brillo": BRILLO_OPC, "fps": FPS_OPC}


def pantalla_graficos(fondo=None):
    """Panel de ajustes gráficos. `fondo` dibuja la escena real (desde la pausa); si es None se usa un pasillo
    de prueba. Los cambios se aplican al instante y se guardan solos."""
    fijar_columnas(GRAF["col"])
    t = 0.0
    px, pw, rh, gap = K(14), K(400), K(34), K(4)
    y0 = K(40)
    panel = pygame.Rect(px - K(8), K(6), pw + K(16), ALTO - K(12))
    velo = pygame.Surface(panel.size, pygame.SRCALPHA)
    velo.fill((0, 0, 0, 205))
    fila = lambda i: y0 + i * (rh + gap)
    while True:
        dt = min(0.05, reloj.tick(FPS_LIMITE) / 1000.0)
        t += dt
        mouse = pygame.mouse.get_pos()
        if fondo is not None:
            fondo()
        else:
            _escena_demo(t)
        pantalla.blit(velo, panel.topleft)
        pygame.draw.rect(pantalla, (130, 12, 12), panel, width=2, border_radius=6)
        actual = nombre_preset()
        texto(f"GRÁFICOS · {actual}", FUENTE_P, (235, 215, 200), (panel.centerx, K(24)), centro=True)
        acciones = []

        wp = (pw - 3 * K(4)) // 4                                   # perfiles
        for i, nombre in enumerate(ORDEN_PRESETS):
            r = pygame.Rect(px + i * (wp + K(4)), fila(0), wp, rh)
            _boton_panel(nombre, r, mouse, True, FUENTE_XS)
            if actual == nombre:
                pygame.draw.rect(pantalla, (255, 210, 60), r, width=3, border_radius=6)
            acciones.append((r, ("preset", nombre)))

        def paso(i, etiqueta, valor, clave):
            rm = pygame.Rect(px, fila(i), K(44), rh)
            rp = pygame.Rect(px + pw - K(44), fila(i), K(44), rh)
            _boton_panel("-", rm, mouse, True, FUENTE_M)
            _boton_panel("+", rp, mouse, True, FUENTE_M)
            texto(f"{etiqueta}: {valor}", FUENTE_XS, (235, 215, 200), (px + pw // 2, fila(i) + rh // 2), centro=True)
            acciones.append((rm, (clave, -1)))
            acciones.append((rp, (clave, 1)))

        def pareja(i, a, b):
            ancho = (pw - K(6)) // 2
            for j, (txt, clave) in enumerate((a, b)):
                r = pygame.Rect(px + j * (ancho + K(6)), fila(i), ancho, rh)
                on = GRAF[clave]
                _boton_panel(f"{txt}: {'SÍ' if on else 'NO'}", r, mouse, True, FUENTE_XS)
                if on:
                    pygame.draw.rect(pantalla, (80, 200, 100), r, width=2, border_radius=6)
                acciones.append((r, (clave, 0)))

        paso(1, "DETALLE PAREDES", f"{NOMBRES_COLUMNAS[GRAF['col']]} ({GRAF['col']}px)", "col")
        paso(2, "DISTANCIA", f"{GRAF['dist']}", "dist")
        paso(3, "TEXTURAS", f"{GRAF['tex']}px", "tex")
        paso(4, "BRILLO", f"{int(GRAF['brillo'] * 100)}%", "brillo")
        paso(5, "LÍMITE FPS", f"{GRAF['fps']}", "fps")
        pareja(6, ("FILTRO SUAVE", "suave"), ("NIEBLA", "niebla"))
        pareja(7, ("VARIAR PAREDES", "var"), ("VIÑETA", "vineta"))
        pareja(8, ("AUTO-AJUSTE", "adapt"), ("VER FPS", "ver_fps"))
        ancho = (pw - K(6)) // 2
        r = pygame.Rect(px, fila(9), ancho, rh)
        _boton_panel("RESTABLECER", r, mouse, True, FUENTE_XS)
        acciones.append((r, ("reset", 0)))
        r = pygame.Rect(px + ancho + K(6), fila(9), ancho, rh)
        _boton_panel("GUARDAR Y VOLVER", r, mouse, True, FUENTE_XS)
        acciones.append((r, ("salir", 0)))
        dibujar_fps()

        clics, teclas = eventos_basicos()
        if pygame.K_ESCAPE in teclas:
            aplicar_graficos()
            guardar_datos()
            return
        for c in clics:
            for rect, (clave, val) in acciones:
                if not rect.collidepoint(c):
                    continue
                reproducir(SND_CLIC)
                if clave == "preset":
                    GRAF.update(PRESETS_GRAF[val])
                elif clave in _LISTAS_GRAF:
                    lista = _LISTAS_GRAF[clave]
                    i = max(0, min(len(lista) - 1, lista.index(GRAF[clave]) + val))
                    GRAF[clave] = lista[i]
                elif clave == "reset":
                    GRAF.update(PRESETS_GRAF[PRESET_DEFECTO])
                    GRAF["brillo"], GRAF["ver_fps"] = 1.0, False
                elif clave == "salir":
                    aplicar_graficos()
                    guardar_datos()
                    return
                else:
                    GRAF[clave] = not GRAF[clave]
                aplicar_graficos()
                break
        pygame.display.flip()


ZONAS_NIVELES = [
    {"nombre": "ZONA 1 · CEMENTERIO", "y": K(165), "color": (200, 190, 170)},
    {"nombre": "ZONA 2 · CATACUMBAS", "y": K(280), "color": (190, 120, 60)},
    {"nombre": "ZONA 3 · INFIERNO", "y": K(395), "color": (230, 50, 30)},
    {"nombre": "ZONA 4 · ABISMO", "y": K(505), "color": (170, 60, 200)},
]


def obtener_puntos_mapa():
    puntos = []
    columnas = [int(ANCHO * f) for f in (0.17, 0.335, 0.5, 0.665, 0.83)]       # repartidas por todo el ancho
    for i in range(20):
        fila, col = i // 5, i % 5
        if fila % 2 == 1:
            col = 4 - col
        puntos.append((columnas[col], ZONAS_NIVELES[fila]["y"]))
    return puntos


def _catmull_rom(puntos, segmentos=14):
    ext = [puntos[0]] + list(puntos) + [puntos[-1]]
    curva = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for paso in range(segmentos):
            t = paso / segmentos
            t2, t3 = t * t, t * t * t
            x = 0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            curva.append((x, y))
    curva.append(puntos[-1])
    return curva


def info_nivel(n):
    return total_enemigos(n), int(30 * (n - 1))


def pantalla_niveles():
    """Devuelve el número de nivel elegido o None si se vuelve al menú."""
    amb = AmbienteTerror()
    puntos = obtener_puntos_mapa()
    curva = _catmull_rom(puntos)
    while True:
        dt = min(0.05, reloj.tick(FPS_LIMITE) / 1000.0)
        amb.actualizar(dt)
        mouse = pygame.mouse.get_pos()
        maximo = DATOS["nivel_max"]

        amb.dibujar_fondo(oscurecer=110)
        for z in ZONAS_NIVELES:
            texto(z["nombre"], FUENTE_P, z["color"], (K(24), z["y"] - K(50)))
            pygame.draw.line(pantalla, tuple(int(c * 0.3) for c in z["color"]),
                             (0, z["y"] - K(55)), (ANCHO, z["y"] - K(55)), 2)
        pygame.draw.lines(pantalla, (12, 0, 0), False, curva, K(16))
        pygame.draw.lines(pantalla, (105, 8, 8), False, curva, K(8))
        amb.titulo("ELIGE TU PESADILLA", Y(42), FUENTE_BOTON)

        pulso = 0.5 + 0.5 * math.sin(amb.t * 4)
        hover_nivel = None
        nodos = []
        for i, (x, y) in enumerate(puntos):
            n = i + 1
            libre = n <= maximo
            actual = n == maximo
            hover = libre and math.hypot(mouse[0] - x, mouse[1] - y) < K(24)
            if actual:
                rg = int(K(30) + K(6) * pulso)
                glow = pygame.Surface((rg * 2, rg * 2), pygame.SRCALPHA)
                pygame.draw.circle(glow, (255, 30, 20, 90), (rg, rg), rg)
                pantalla.blit(glow, (x - rg, y - rg))
            pygame.draw.circle(pantalla, (0, 0, 0), (x, y), K(26))
            if not libre:
                col = (38, 36, 42)
            elif hover:
                col = (255, 70, 40)
            elif actual:
                col = (200, 20, 20)
            else:
                col = (110, 28, 28)
            pygame.draw.circle(pantalla, col, (x, y), K(22))
            pygame.draw.circle(pantalla, (200, 190, 170) if libre else (70, 70, 78), (x, y), K(22), 2)
            if libre:
                texto(str(n), FUENTE_M, (240, 230, 215), (x, y + 1), centro=True)
            else:
                dibujar_candado(x, y)
            if hover:
                hover_nivel = n
            nodos.append((x, y, n, libre))

        if hover_nivel:
            mons, vida = info_nivel(hover_nivel)
            texto(f"NIVEL {hover_nivel}:  {mons} infectados  ·  vida +{vida}%",
                  FUENTE_M, (235, 200, 190), (ANCHO // 2, ALTO - K(30)), centro=True)
        else:
            texto("Cada nivel: mapa más grande, más infectados y más oscuridad", FUENTE_P, (150, 120, 120),
                  (ANCHO // 2, ALTO - K(30)), centro=True)
        r_volver, _ = boton_terror("VOLVER", K(20), K(20), K(120), K(40), mouse)
        amb.dibujar_capas_finales()

        clics, teclas = eventos_basicos()
        if pygame.K_ESCAPE in teclas:
            return None
        for c in clics:
            if r_volver.collidepoint(c):
                reproducir(SND_CLIC)
                return None
            for x, y, n, libre in nodos:
                if libre and math.hypot(c[0] - x, c[1] - y) < K(24):
                    reproducir(SND_CLIC)
                    return n
        pygame.display.flip()


def pantalla_tienda():
    amb = AmbienteTerror()
    mensaje, t_msg, col_msg = "", 0.0, (255, 255, 255)
    previas = {a["id"]: pygame.transform.smoothscale(obtener_sprite_arma(a["id"], DATOS["skin"]), (K(110), K(110)))
               for a in ARMAS}
    while True:
        dt = min(0.05, reloj.tick(FPS_LIMITE) / 1000.0)
        amb.actualizar(dt)
        t_msg = max(0.0, t_msg - dt)
        mouse = pygame.mouse.get_pos()

        amb.dibujar_fondo(oscurecer=140)
        amb.titulo("ARMERÍA", Y(38), FUENTE_BOTON)
        texto(f"MONEDAS: {DATOS['monedas']}", FUENTE_M, (255, 210, 60), (ANCHO // 2, Y(78)), centro=True)

        botones = []
        for i, a in enumerate(ARMAS):
            cx, cy = X(10) + (i % 3) * K(265), Y(100) + (i // 3) * K(215)
            tarjeta = pygame.Rect(cx, cy, K(255), K(200))
            pygame.draw.rect(pantalla, (16, 4, 8), tarjeta, border_radius=10)
            pygame.draw.rect(pantalla, (110, 12, 12), tarjeta, 2, border_radius=10)
            texto(a["nombre"], FUENTE_P, (235, 215, 200), (cx + K(127), cy + K(16)), centro=True)
            pantalla.blit(previas[a["id"]], (cx + K(8), cy + K(30)))
            dano_txt = f"{a['dano']} x{a['perdigones']}" if a["perdigones"] > 1 else str(a["dano"])
            if "explosivo" in a:
                dano_txt += " (área)"
            for k, linea in enumerate((f"Daño: {dano_txt}",
                                       f"Disparos/s: {1 / a['cadencia']:.1f}",
                                       f"Munición: {a['municion']}",
                                       f"Cabeza: x{a.get('mult_cabeza', MULT_CABEZA)}")):
                texto(linea, FUENTE_XS, (200, 190, 180), (cx + K(124), cy + K(40) + k * K(20)))
            poseida = a["id"] in DATOS["armas"]
            equipada = DATOS["equipada"] == a["id"]
            if equipada:
                txt, activo = "EQUIPADA", False
            elif poseida:
                txt, activo = "EQUIPAR", True
            else:
                txt, activo = f"COMPRAR ${a['precio']}", DATOS["monedas"] >= a["precio"]
            r, _ = boton_terror(txt, cx + K(18), cy + K(148), K(219), K(38), mouse, activo, seleccionado=equipada)
            botones.append((r, a, poseida, activo))

        if t_msg > 0:
            texto(mensaje, FUENTE_M, col_msg, (ANCHO // 2, Y(545)), centro=True)
        r_volver, _ = boton_terror("VOLVER", ANCHO // 2 - K(90), Y(555), K(180), K(38), mouse)
        amb.dibujar_capas_finales()

        clics, teclas = eventos_basicos()
        if pygame.K_ESCAPE in teclas:
            guardar_datos()
            return
        for c in clics:
            if r_volver.collidepoint(c):
                reproducir(SND_CLIC)
                guardar_datos()
                return
            for r, a, poseida, activo in botones:
                if not r.collidepoint(c):
                    continue
                if DATOS["equipada"] == a["id"]:
                    continue
                if poseida:
                    DATOS["equipada"] = a["id"]
                    mensaje, col_msg, t_msg = f"{a['nombre']} equipada", (120, 255, 140), 1.6
                    reproducir(SND_CLIC)
                elif activo:
                    DATOS["monedas"] -= a["precio"]
                    DATOS["armas"].append(a["id"])
                    DATOS["equipada"] = a["id"]
                    mensaje, col_msg, t_msg = f"¡{a['nombre']} comprada!", (120, 255, 140), 1.6
                    reproducir(SND_COMPRA)
                else:
                    mensaje, col_msg, t_msg = "Monedas insuficientes", (255, 80, 70), 1.6
                    reproducir(SND_VACIO)
                guardar_datos()
        pygame.display.flip()


def pantalla_personalizar():
    amb = AmbienteTerror()
    mensaje, t_msg, col_msg = "", 0.0, (255, 255, 255)
    while True:
        dt = min(0.05, reloj.tick(FPS_LIMITE) / 1000.0)
        amb.actualizar(dt)
        t_msg = max(0.0, t_msg - dt)
        mouse = pygame.mouse.get_pos()

        amb.dibujar_fondo(oscurecer=140)
        amb.titulo("PERSONALIZAR", Y(38), FUENTE_BOTON)
        texto(f"MONEDAS: {DATOS['monedas']}", FUENTE_M, (255, 210, 60), (ANCHO // 2, Y(78)), centro=True)

        # --- color del arma
        texto("COLOR DEL ARMA", FUENTE_P, (235, 215, 200), (X(215), Y(112)), centro=True)
        swatches = []
        for i, (nombre, color, precio) in enumerate(SKINS_ARMA):
            sx, sy = X(40) + (i % 4) * K(100), Y(135) + (i // 4) * K(105)
            r = pygame.Rect(sx, sy, K(80), K(60))
            tiene = i in DATOS["skins"]
            pygame.draw.rect(pantalla, (0, 0, 0), r.inflate(K(8), K(8)), border_radius=8)
            pygame.draw.rect(pantalla, color if tiene else tuple(c // 3 for c in color), r, border_radius=6)
            borde = (255, 210, 40) if DATOS["skin"] == i else ((200, 30, 30) if r.collidepoint(mouse) else (90, 90, 100))
            pygame.draw.rect(pantalla, borde, r, 3, border_radius=6)
            texto(nombre, FUENTE_XS, (220, 210, 200), (sx + K(40), sy + K(72)), centro=True)
            if not tiene:
                texto(f"${precio}", FUENTE_P, (255, 255, 255), (sx + K(40), sy + K(30)), centro=True)
            swatches.append((r, i, tiene, precio))

        # --- mira
        texto("MIRA · ESTILO", FUENTE_P, (235, 215, 200), (X(600), Y(112)), centro=True)
        estilos = []
        for i, nombre in enumerate(ESTILOS_MIRA):
            r = pygame.Rect(X(440) + i * K(90), Y(130), K(76), K(76))
            pygame.draw.rect(pantalla, (14, 6, 10), r, border_radius=8)
            borde = (255, 210, 40) if DATOS["mira_estilo"] == i else ((200, 30, 30) if r.collidepoint(mouse) else (90, 90, 100))
            pygame.draw.rect(pantalla, borde, r, 3, border_radius=8)
            dibujar_mira(r.centerx, r.centery, i, COLORES_MIRA[DATOS["mira_color"]])
            texto(nombre, FUENTE_XS, (220, 210, 200), (r.centerx, r.bottom + K(12)), centro=True)
            estilos.append((r, i))
        texto("MIRA · COLOR", FUENTE_P, (235, 215, 200), (X(600), Y(255)), centro=True)
        colores = []
        for i, col in enumerate(COLORES_MIRA):
            r = pygame.Rect(X(445) + i * K(58), Y(275), K(46), K(46))
            pygame.draw.rect(pantalla, col, r, border_radius=6)
            borde = (255, 210, 40) if DATOS["mira_color"] == i else ((200, 30, 30) if r.collidepoint(mouse) else (60, 60, 70))
            pygame.draw.rect(pantalla, borde, r, 3, border_radius=6)
            colores.append((r, i))

        # --- vista previa
        prev = pygame.transform.smoothscale(obtener_sprite_arma(DATOS["equipada"], DATOS["skin"]), (K(190), K(190)))
        marco = pygame.Rect(X(40), Y(350), K(330), K(190))
        pygame.draw.rect(pantalla, (12, 4, 8), marco, border_radius=10)
        pygame.draw.rect(pantalla, (110, 12, 12), marco, 2, border_radius=10)
        pantalla.blit(prev, prev.get_rect(center=marco.center))
        texto(ARMA_POR_ID[DATOS["equipada"]]["nombre"], FUENTE_P, (235, 215, 200), (marco.centerx, marco.top - K(12)), centro=True)
        vista = pygame.Rect(X(440), Y(350), K(320), K(190))
        pygame.draw.rect(pantalla, (20, 8, 12), vista, border_radius=10)
        pygame.draw.rect(pantalla, (110, 12, 12), vista, 2, border_radius=10)
        dibujar_mira(vista.centerx, vista.centery, DATOS["mira_estilo"], COLORES_MIRA[DATOS["mira_color"]])
        texto("Vista previa de la mira", FUENTE_XS, (170, 150, 150), (vista.centerx, vista.bottom - K(14)), centro=True)

        if t_msg > 0:
            texto(mensaje, FUENTE_M, col_msg, (ANCHO // 2, Y(515)), centro=True)
        r_volver, _ = boton_terror("VOLVER", ANCHO // 2 - K(90), Y(555), K(180), K(38), mouse)
        amb.dibujar_capas_finales()

        clics, teclas = eventos_basicos()
        if pygame.K_ESCAPE in teclas:
            guardar_datos()
            return
        for c in clics:
            if r_volver.collidepoint(c):
                reproducir(SND_CLIC)
                guardar_datos()
                return
            for r, i, tiene, precio in swatches:
                if r.collidepoint(c):
                    if tiene:
                        DATOS["skin"] = i
                        mensaje, col_msg, t_msg = f"Color «{SKINS_ARMA[i][0]}» equipado", (120, 255, 140), 1.5
                        reproducir(SND_CLIC)
                    elif DATOS["monedas"] >= precio:
                        DATOS["monedas"] -= precio
                        DATOS["skins"].append(i)
                        DATOS["skin"] = i
                        mensaje, col_msg, t_msg = "¡Color comprado!", (120, 255, 140), 1.5
                        reproducir(SND_COMPRA)
                    else:
                        mensaje, col_msg, t_msg = "Monedas insuficientes", (255, 80, 70), 1.5
                        reproducir(SND_VACIO)
                    guardar_datos()
            for r, i in estilos:
                if r.collidepoint(c):
                    DATOS["mira_estilo"] = i
                    reproducir(SND_CLIC)
                    guardar_datos()
            for r, i in colores:
                if r.collidepoint(c):
                    DATOS["mira_color"] = i
                    reproducir(SND_CLIC)
                    guardar_datos()
        pygame.display.flip()


NOMBRES_CORTOS_ARMA = {"pistola": "PISTOLA", "escopeta": "ESCOPETA", "rifle": "RIFLE", "sniper": "SNIPER",
                       "minigun": "MINIGUN", "cohetes": "COHETES"}


def _boton_acc(rect, nombre, sub, equipado, activo, mouse):
    """Botón pequeño de accesorio. sub = texto de precio / estado."""
    hover = activo and rect.collidepoint(mouse)
    fondo = (62, 4, 6) if hover else ((22, 4, 6) if activo else (16, 12, 14))
    borde = (255, 210, 40) if equipado else ((255, 40, 30) if hover else ((130, 12, 12) if activo else (70, 50, 50)))
    pygame.draw.rect(pantalla, fondo, rect, border_radius=7)
    pygame.draw.rect(pantalla, borde, rect, 3 if equipado else 2, border_radius=7)
    col = (235, 220, 210) if activo else (120, 105, 105)
    fuente = FUENTE_P if FUENTE_P.size(nombre)[0] <= rect.width - 8 else FUENTE_XS
    texto(nombre, fuente, col, (rect.centerx, rect.centery - K(9)), centro=True)
    texto(sub, FUENTE_XS, (255, 210, 60) if (activo and not equipado and sub.startswith("$")) else (170, 160, 150),
          (rect.centerx, rect.centery + K(12)), centro=True)


def pantalla_accesorios():
    amb = AmbienteTerror()
    mensaje, t_msg, col_msg = "", 0.0, (255, 255, 255)
    sel = DATOS["equipada"] if DATOS["equipada"] in ARMA_POR_ID else "pistola"
    cache_prev = {}
    # ---- medidas de la pantalla (todo calculado a partir de ANCHO y ALTO)
    margen = max(K(30), int(ANCHO * 0.04))
    tab_w, tab_h, tab_p = K(170), K(42), K(50)
    top = K(112)
    prev_x = margen + tab_w + K(30)
    prev_s = K(220)
    der_x = prev_x + prev_s + K(30)
    der_w = ANCHO - margen - der_x
    gap = K(10)
    bw3 = (der_w - 2 * gap) // 3                                 # ancho de un botón en filas de 3
    bh = K(48)
    while True:
        dt = min(0.05, reloj.tick(FPS_LIMITE) / 1000.0)
        amb.actualizar(dt)
        t_msg = max(0.0, t_msg - dt)
        mouse = pygame.mouse.get_pos()
        cfg = config_arma(sel)

        amb.dibujar_fondo(oscurecer=150)
        amb.titulo("ACCESORIOS", Y(38), FUENTE_BOTON)
        texto(f"MONEDAS: {DATOS['monedas']}", FUENTE_M, (255, 210, 60), (ANCHO // 2, Y(78)), centro=True)

        acciones = []                                            # (rect, categoría, valor, acc_id, activo)

        # ---- pestañas de armas
        for i, a in enumerate(ARMAS):
            r, _ = boton_terror(NOMBRES_CORTOS_ARMA[a["id"]], margen, top + i * tab_p, tab_w, tab_h, mouse,
                                activo=a["id"] in DATOS["armas"], seleccionado=sel == a["id"])
            acciones.append((r, "arma", a["id"], None, a["id"] in DATOS["armas"]))

        # ---- vista previa y estadísticas
        marco = pygame.Rect(prev_x, top, prev_s, prev_s)
        pygame.draw.rect(pantalla, (12, 4, 8), marco, border_radius=10)
        pygame.draw.rect(pantalla, (110, 12, 12), marco, 2, border_radius=10)
        clave_prev = (sel, DATOS["skin"], cfg["mira"], cfg["laser"], cfg["silencio"], cfg["cargador"])
        if clave_prev not in cache_prev:
            img, _ = sprite_fp(sel)
            lado = prev_s - K(20)
            k = min(lado / img.get_width(), lado / img.get_height())
            cache_prev[clave_prev] = pygame.transform.smoothscale(
                img, (max(1, int(img.get_width() * k)), max(1, int(img.get_height() * k))))
        prev = cache_prev[clave_prev]
        pantalla.blit(prev, prev.get_rect(center=marco.center))
        st = stats_arma(sel)
        texto(ARMA_POR_ID[sel]["nombre"], FUENTE_P, (235, 215, 200), (marco.centerx, marco.top - K(14)), centro=True)
        for k, linea in enumerate((f"Aumento al apuntar: x{st['zoom']:g}",
                                   f"Daño: {st['dano']:.0f}   Cabeza x{st['cabeza']:g}",
                                   f"Munición máx.: {municion_maxima(sel)}",
                                   f"Movilidad: {int(st['vel'] * 100)}%",
                                   "Silenciada: sí" if st["silencio"] else "Silenciada: no")):
            texto(linea, FUENTE_XS, (200, 190, 180), (prev_x, marco.bottom + K(14) + k * K(22)))

        # ---- miras (3 columnas x 2 filas)
        y = top - K(4)
        texto("MIRA  (botón derecho para apuntar)", FUENTE_P, (235, 215, 200), (der_x, y))
        y += K(26)
        for i, clave in enumerate(ORDEN_MIRAS):
            r = pygame.Rect(der_x + (i % 3) * (bw3 + gap), y + (i // 3) * (bh + gap), bw3, bh)
            tiene = acc_disponible(sel, clave)
            equipado = cfg["mira"] == clave
            if equipado:
                sub = "EQUIPADA"
            elif tiene:
                sub = f"x{MIRAS[clave]['zoom']:g} · equipar"
            else:
                sub = f"${PRECIOS_ACC[clave]}"
            _boton_acc(r, MIRAS[clave]["nombre"], sub, equipado, True, mouse)
            acciones.append((r, "mira", clave, clave, True))
        y += 2 * (bh + gap) + K(10)

        # ---- láser
        texto("LÁSER  (menos dispersión sin apuntar)", FUENTE_P, (235, 215, 200), (der_x, y))
        y += K(26)
        for i, (nom, acc) in enumerate((("Ninguno", None), ("Láser rojo", "laser_1"), ("Láser potente", "laser_2"))):
            r = pygame.Rect(der_x + i * (bw3 + gap), y, bw3, bh)
            tiene = acc is None or acc in DATOS["acc_poseidos"]
            equipado = cfg["laser"] == i
            sub = "EQUIPADO" if equipado else ("equipar" if tiene else f"${PRECIOS_ACC[acc]}")
            _boton_acc(r, nom, sub, equipado, True, mouse)
            acciones.append((r, "laser", i, acc, True))
        y += bh + K(18)

        # ---- silenciador
        texto("SILENCIADOR  (no alerta a los infectados)", FUENTE_P, (235, 215, 200), (der_x, y))
        y += K(26)
        r = pygame.Rect(der_x, y, 2 * bw3 + gap, bh)
        permitido = sel not in SIN_SILENCIADOR
        tiene = "silenciador" in DATOS["acc_poseidos"]
        equipado = bool(cfg["silencio"]) and permitido
        if not permitido:
            sub = "No compatible"
        elif equipado:
            sub = "EQUIPADO · clic para quitar"
        else:
            sub = "equipar (−12% daño)" if tiene else f"${PRECIOS_ACC['silenciador']}"
        _boton_acc(r, "Silenciador", sub, equipado, permitido, mouse)
        acciones.append((r, "silencio", 0 if equipado else 1, "silenciador", permitido))
        y += bh + K(18)

        # ---- cargador
        texto("CARGADOR  (más munición máxima y por recogida)", FUENTE_P, (235, 215, 200), (der_x, y))
        y += K(26)
        for i, (nom, acc) in enumerate((("Normal", None), ("Extendido +50%", "cargador_1"),
                                        ("Doble +100%", "cargador_2"))):
            r = pygame.Rect(der_x + i * (bw3 + gap), y, bw3, bh)
            tiene = acc is None or acc in DATOS["acc_poseidos"]
            equipado = cfg["cargador"] == i
            sub = "EQUIPADO" if equipado else ("equipar" if tiene else f"${PRECIOS_ACC[acc]}")
            _boton_acc(r, nom, sub, equipado, True, mouse)
            acciones.append((r, "cargador", i, acc, True))
        y += bh

        if t_msg > 0:
            texto(mensaje, FUENTE_M, col_msg, (ANCHO // 2, ALTO - K(100)), centro=True)
        r_volver, _ = boton_terror("VOLVER", margen, ALTO - K(62), K(170), K(40), mouse)
        amb.dibujar_capas_finales()

        clics, teclas = eventos_basicos()
        if pygame.K_ESCAPE in teclas:
            guardar_datos()
            return
        for c in clics:
            if r_volver.collidepoint(c):
                reproducir(SND_CLIC)
                guardar_datos()
                return
            for r, cat, valor, acc, activo in acciones:
                if not activo or not r.collidepoint(c):
                    continue
                if cat == "arma":
                    sel = valor
                    reproducir(SND_CLIC)
                    continue
                if acc is None or acc_disponible(sel, acc):
                    poner_config(sel, cat, valor)
                    mensaje, col_msg, t_msg = "Accesorio equipado" if valor else "Accesorio quitado", (120, 255, 140), 1.4
                    reproducir(SND_CLIC)
                elif DATOS["monedas"] >= PRECIOS_ACC[acc]:
                    DATOS["monedas"] -= PRECIOS_ACC[acc]
                    DATOS["acc_poseidos"].append(acc)
                    poner_config(sel, cat, valor)
                    mensaje, col_msg, t_msg = "¡Accesorio comprado y equipado!", (120, 255, 140), 1.6
                    reproducir(SND_COMPRA)
                else:
                    mensaje, col_msg, t_msg = "Monedas insuficientes", (255, 80, 70), 1.5
                    reproducir(SND_VACIO)
                guardar_datos()
        pygame.display.flip()


# ===========================================================================
# 11. CONTROLES TÁCTILES (móvil)
# ===========================================================================
# acción: (etiqueta, se mantiene pulsada)
ACCIONES = {
    "disparar": ("FUEGO", True),
    "apuntar": ("MIRA", True),
    "correr": ("CORRER", True),
    "activar": ("ACTIVAR", True),
    "centrar": ("CENTRO", True),
    "arma_sig": ("ARMA +", False),
    "arma_ant": ("ARMA -", False),
    "mapa": ("MAPA", False),
    "minimapa": ("RADAR", False),
    "pausa": ("PAUSA", False),
}
ORDEN_ACCIONES = list(ACCIONES)
# (acción, x, y, radio): x e y son fracciones del ancho/alto; el radio es fracción del alto
BOTONES_DEFECTO = [
    ("disparar", 0.90, 0.66, 0.14),
    ("apuntar", 0.78, 0.82, 0.09),
    ("activar", 0.775, 0.57, 0.08),
    ("correr", 0.27, 0.82, 0.09),
    ("arma_ant", 0.835, 0.38, 0.065),
    ("arma_sig", 0.92, 0.38, 0.065),
    ("mapa", 0.07, 0.30, 0.06),
    ("minimapa", 0.07, 0.17, 0.06),
    ("pausa", 0.04, 0.06, 0.055),
    ("centrar", 0.27, 0.62, 0.06),
]
JOY_DEFECTO = {"x": 0.13, "y": 0.68, "r": 0.20, "vis": True}
AJUSTES_DEFECTO = {"opac": 0.6, "sens": 1.0, "inv_y": False, "joy_flotante": False}


class ControlesTactiles:
    """Joystick + botones en pantalla con multitoque. La disposición se guarda en DATOS['controles']."""

    def __init__(self):
        self.reiniciar_config()
        self.dedos = {}
        self.activos = set()          # índices de botones "mantenidos" que están pulsados
        self.cola = []                # acciones de un solo toque pendientes
        self.rel = [0.0, 0.0]         # giro de cámara acumulado
        self.joy_id = None
        self.joy_vec = (0.0, 0.0)
        self.joy_centro = None
        self.joy_knob = None
        self.t_dedo = -10000
        self._cache = {}
        self._fuentes = {}

    # ----------------------------------------------------------- configuración
    def reiniciar_config(self):
        self.botones = [{"accion": a, "x": x, "y": y, "r": r, "vis": True} for a, x, y, r in BOTONES_DEFECTO]
        self.joy = dict(JOY_DEFECTO)
        self.aj = dict(AJUSTES_DEFECTO)
        self._cache = {}

    def cargar(self):
        cfg = DATOS.get("controles")
        if not isinstance(cfg, dict) or not cfg:
            return
        try:
            for b, g in zip(self.botones, cfg.get("botones", [])):
                if g.get("accion") in ACCIONES:
                    b["accion"] = g["accion"]
                for k in ("x", "y", "r"):
                    if isinstance(g.get(k), (int, float)):
                        b[k] = float(g[k])
                b["vis"] = bool(g.get("vis", True))
            g = cfg.get("joy", {})
            for k in ("x", "y", "r"):
                if isinstance(g.get(k), (int, float)):
                    self.joy[k] = float(g[k])
            self.joy["vis"] = bool(g.get("vis", True))
            g = cfg.get("aj", {})
            for k in ("opac", "sens"):
                if isinstance(g.get(k), (int, float)):
                    self.aj[k] = float(g[k])
            self.aj["inv_y"] = bool(g.get("inv_y", False))
            self.aj["joy_flotante"] = bool(g.get("joy_flotante", False))
        except (AttributeError, TypeError, ValueError):
            self.reiniciar_config()
        self.limitar()

    def limitar(self):
        for o in self.botones + [self.joy]:
            o["x"] = max(0.03, min(0.97, o["x"]))
            o["y"] = max(0.04, min(0.96, o["y"]))
            o["r"] = max(0.04, min(0.30, o["r"]))
        self.aj["opac"] = max(0.15, min(1.0, self.aj["opac"]))
        self.aj["sens"] = max(0.3, min(3.0, self.aj["sens"]))
        self._cache = {}

    def guardar(self):
        self.limitar()
        DATOS["controles"] = {"botones": self.botones, "joy": self.joy, "aj": self.aj}
        guardar_datos()

    # ----------------------------------------------------------- entrada
    def reiniciar(self):
        self.dedos.clear()
        self.activos.clear()
        self.cola.clear()
        self.rel = [0.0, 0.0]
        self.joy_id = None
        self.joy_vec = (0.0, 0.0)
        self.joy_centro = None
        self.joy_knob = None

    def convertir(self, ev):
        """Evento de pygame -> (tipo, id_dedo, x, y) con tipo 'down' / 'move' / 'up', o None."""
        t = ev.type
        if hasattr(pygame, "FINGERDOWN") and t in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
            self.t_dedo = pygame.time.get_ticks()
            tipo = "down" if t == pygame.FINGERDOWN else "move" if t == pygame.FINGERMOTION else "up"
            return tipo, ev.finger_id, ev.x * ANCHO, ev.y * ALTO
        if t in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            if getattr(ev, "touch", False) or pygame.time.get_ticks() - self.t_dedo < 400:
                return None                       # ratón emulado por el toque: ya lo tenemos como dedo
            if t == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                return "down", -1, ev.pos[0], ev.pos[1]
            if t == pygame.MOUSEBUTTONUP and ev.button == 1:
                return "up", -1, ev.pos[0], ev.pos[1]
            if t == pygame.MOUSEMOTION and ev.buttons[0]:
                return "move", -1, ev.pos[0], ev.pos[1]
        return None

    def evento(self, ev):
        """Procesa un evento. Devuelve (x, y) si fue un toque nuevo (sirve como 'clic' en los menús)."""
        r = self.convertir(ev)
        if r is None:
            return None
        tipo, fid, x, y = r
        if tipo == "down":
            self._bajar(fid, x, y)
            return int(x), int(y)
        if tipo == "move":
            self._mover(fid, x, y)
        else:
            self._soltar(fid)
        return None

    def _bajar(self, fid, x, y):
        if fid in self.dedos:
            self._soltar(fid)
        for i in range(len(self.botones) - 1, -1, -1):
            b = self.botones[i]
            if b["vis"] and math.hypot(x - b["x"] * ANCHO, y - b["y"] * ALTO) <= b["r"] * ALTO * 1.15:
                self.dedos[fid] = {"rol": "btn", "idx": i, "x": x, "y": y}
                if ACCIONES[b["accion"]][1]:
                    self.activos.add(i)
                else:
                    self.cola.append(b["accion"])
                return
        j = self.joy
        if j["vis"] and self.joy_id is None:
            fijo = (j["x"] * ANCHO, j["y"] * ALTO)
            if self.aj["joy_flotante"]:
                usar = x < ANCHO * 0.42
                centro = (x, y)
            else:
                usar = math.hypot(x - fijo[0], y - fijo[1]) <= j["r"] * ALTO * 1.4
                centro = fijo
            if usar:
                self.joy_id = fid
                self.joy_centro = centro
                self.dedos[fid] = {"rol": "joy", "x": x, "y": y}
                self._mover_joy(x, y)
                return
        self.dedos[fid] = {"rol": "mirar", "x": x, "y": y}

    def _mover(self, fid, x, y):
        d = self.dedos.get(fid)
        if d is None:
            return
        dx, dy = x - d["x"], y - d["y"]
        d["x"], d["y"] = x, y
        if d["rol"] == "joy":
            self._mover_joy(x, y)
        elif d["rol"] == "mirar" or self.botones[d["idx"]]["accion"] == "disparar":
            k = self.aj["sens"]
            self.rel[0] += dx / ANCHO * 1366 * k
            self.rel[1] += dy * k * (-1 if self.aj["inv_y"] else 1)

    def _soltar(self, fid):
        d = self.dedos.pop(fid, None)
        if d is None:
            return
        if d["rol"] == "joy":
            self.joy_id = None
            self.joy_vec = (0.0, 0.0)
            self.joy_centro = None
            self.joy_knob = None
        elif d["rol"] == "btn":
            if not any(o["rol"] == "btn" and o["idx"] == d["idx"] for o in self.dedos.values()):
                self.activos.discard(d["idx"])

    def _mover_joy(self, x, y):
        cx, cy = self.joy_centro
        R = self.joy["r"] * ALTO
        dx, dy = (x - cx) / R, (y - cy) / R
        m = math.hypot(dx, dy)
        if m > 1:
            dx, dy, m = dx / m, dy / m, 1.0
        zona = 0.12                                    # zona muerta
        if m < zona:
            self.joy_vec = (0.0, 0.0)
        else:
            e = (m - zona) / (1 - zona) / m
            self.joy_vec = (dx * e, dy * e)
        self.joy_knob = (cx + dx * R, cy + dy * R)

    # ----------------------------------------------------------- lectura desde el juego
    def tomar_rel(self):
        r = (self.rel[0], self.rel[1])
        self.rel = [0.0, 0.0]
        return r

    def tomar_acciones(self):
        a, self.cola = self.cola, []
        return a

    def mantenido(self, accion):
        return any(self.botones[i]["accion"] == accion for i in self.activos)

    def vector_movimiento(self, c, s):
        vx, vy = self.joy_vec
        if vx == 0.0 and vy == 0.0:
            return 0.0, 0.0
        f, sr = -vy, vx                                # arriba = avanzar, derecha = lado derecho
        return c * f - s * sr, s * f + c * sr

    def teclas(self, reales):
        extra = set()
        if self.mantenido("correr"):
            extra.add(pygame.K_LSHIFT)
        if self.mantenido("activar"):
            extra.add(pygame.K_f)
        if self.mantenido("centrar"):
            extra.add(pygame.K_c)
        return _TeclasMixtas(reales, extra)

    def buscar(self, x, y):
        """Editor: índice de botón, 'joy' o None bajo el punto (incluye los ocultos)."""
        for i in range(len(self.botones) - 1, -1, -1):
            b = self.botones[i]
            if math.hypot(x - b["x"] * ANCHO, y - b["y"] * ALTO) <= b["r"] * ALTO:
                return i
        j = self.joy
        if math.hypot(x - j["x"] * ANCHO, y - j["y"] * ALTO) <= j["r"] * ALTO:
            return "joy"
        return None

    # ----------------------------------------------------------- dibujo
    def _fuente(self, tam):
        if tam not in self._fuentes:
            self._fuentes[tam] = pygame.font.Font(None, tam)
        return self._fuentes[tam]

    def _sup_boton(self, rad, etiqueta, estado):
        clave = ("b", rad, etiqueta, estado, round(self.aj["opac"], 2))
        s = self._cache.get(clave)
        if s is None:
            op = self.aj["opac"]
            if estado == 2:                                  # oculto (solo se ve en el editor)
                fondo, borde, col_t = (30, 30, 30, 70), (130, 130, 130, 140), (150, 150, 150)
            elif estado == 1:                                # pulsado
                fondo, borde, col_t = (190, 25, 20, int(255 * min(1, op + 0.25))), (255, 120, 100, 255), (255, 255, 255)
            else:
                fondo, borde, col_t = (8, 8, 10, int(255 * op * 0.6)), (200, 40, 35, int(255 * min(1, op + 0.3))), (240, 225, 215)
            s = pygame.Surface((rad * 2 + 4, rad * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, fondo, (rad + 2, rad + 2), rad)
            pygame.draw.circle(s, borde, (rad + 2, rad + 2), rad, max(2, rad // 12))
            tam = max(12, int(rad * 0.62))
            while tam > 10:
                t = self._fuente(tam).render(etiqueta, True, col_t)
                if t.get_width() <= rad * 1.7:
                    break
                tam -= 2
            s.blit(t, t.get_rect(center=(rad + 2, rad + 2)))
            self._cache[clave] = s
        return s

    def _sup_joy(self, R, oculto):
        clave = ("j", R, oculto, round(self.aj["opac"], 2))
        s = self._cache.get(clave)
        if s is None:
            op = self.aj["opac"] * (0.4 if oculto else 1.0)
            s = pygame.Surface((R * 2 + 4, R * 2 + 4), pygame.SRCALPHA)
            c = (R + 2, R + 2)
            pygame.draw.circle(s, (8, 8, 10, int(255 * op * 0.45)), c, R)
            pygame.draw.circle(s, (200, 40, 35, int(255 * min(1, op + 0.25))), c, R, max(2, R // 18))
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                pygame.draw.circle(s, (230, 215, 205, int(255 * op)), (c[0] + dx * int(R * 0.78), c[1] + dy * int(R * 0.78)),
                                   max(2, R // 14))
            self._cache[clave] = s
        return s

    def dibujar(self, editor=False, sel=None):
        op = self.aj["opac"]
        j = self.joy
        if j["vis"] or editor:
            R = max(8, int(j["r"] * ALTO))
            cx, cy = self.joy_centro if self.joy_centro else (j["x"] * ANCHO, j["y"] * ALTO)
            base = self._sup_joy(R, not j["vis"])
            pantalla.blit(base, base.get_rect(center=(int(cx), int(cy))))
            kx, ky = self.joy_knob if self.joy_knob else (cx, cy)
            kr = max(6, int(R * 0.42))
            ks = self._sup_boton(kr, "", 1 if self.joy_id is not None else (2 if not j["vis"] else 0))
            pantalla.blit(ks, ks.get_rect(center=(int(kx), int(ky))))
            if editor and sel == "joy":
                pygame.draw.circle(pantalla, (255, 210, 40), (int(cx), int(cy)), R + 4, 3)
        for i, b in enumerate(self.botones):
            if not b["vis"] and not editor:
                continue
            rad = max(8, int(b["r"] * ALTO))
            estado = 2 if not b["vis"] else 1 if i in self.activos else 0
            sup = self._sup_boton(rad, ACCIONES[b["accion"]][0], estado)
            cx, cy = int(b["x"] * ANCHO), int(b["y"] * ALTO)
            pantalla.blit(sup, sup.get_rect(center=(cx, cy)))
            if editor and sel == i:
                pygame.draw.circle(pantalla, (255, 210, 40), (cx, cy), rad + 4, 3)


class _TeclasMixtas:
    """Combina las teclas reales con las virtuales de los botones táctiles."""

    def __init__(self, reales, extra):
        self.reales, self.extra = reales, extra

    def __getitem__(self, k):
        return k in self.extra or bool(self.reales[k])


TOQUE = ControlesTactiles()


def _boton_panel(txt, r, mouse, activo=True, fuente=None):
    hover = activo and r.collidepoint(mouse)
    fondo = (62, 4, 6) if hover else (22, 4, 6) if activo else (18, 12, 14)
    borde = (255, 40, 30) if hover else (130, 12, 12) if activo else (70, 50, 50)
    col = (255, 235, 225) if activo else (110, 95, 95)
    pygame.draw.rect(pantalla, fondo, r, border_radius=6)
    pygame.draw.rect(pantalla, borde, r, width=2, border_radius=6)
    texto(txt, fuente or FUENTE_P, col, r.center, centro=True)


def pantalla_controles():
    """Editor de controles táctiles: arrastra para mover, y usa el panel para ajustar el control elegido."""
    amb = AmbienteTerror()
    sel = 0
    arrastre = None                      # (id_dedo, desplazamiento_x, desplazamiento_y)
    TOQUE.reiniciar()
    while True:
        dt = min(0.05, reloj.tick(FPS_LIMITE) / 1000.0)
        amb.actualizar(dt)
        mouse = pygame.mouse.get_pos()
        amb.dibujar_fondo()
        amb.dibujar_capas_finales()

        pw, rh, gap = K(300), K(34), K(5)
        px, y0 = ANCHO // 2 - pw // 2, K(34)
        panel = pygame.Rect(px - K(8), y0 - K(28), pw + K(16), 9 * (rh + gap) + K(34))
        fondo = pygame.Surface(panel.size, pygame.SRCALPHA)
        fondo.fill((0, 0, 0, 190))
        pantalla.blit(fondo, panel.topleft)
        pygame.draw.rect(pantalla, (130, 12, 12), panel, width=2, border_radius=6)
        texto("CONTROLES TÁCTILES", FUENTE_P, (235, 215, 200), (ANCHO // 2, y0 - K(14)), centro=True)

        obj = TOQUE.joy if sel == "joy" else TOQUE.botones[sel]
        fila = lambda i: y0 + i * (rh + gap)
        ancho_m = (pw - K(6)) // 2
        acciones = []

        def ajuste(i, etiqueta, valor, clave, activo=True):
            rm = pygame.Rect(px, fila(i), K(44), rh)
            rp = pygame.Rect(px + pw - K(44), fila(i), K(44), rh)
            _boton_panel("<" if clave == "acc" else "-", rm, mouse, activo, FUENTE_M)
            _boton_panel(">" if clave == "acc" else "+", rp, mouse, activo, FUENTE_M)
            texto(f"{etiqueta}: {valor}", FUENTE_XS, (235, 215, 200) if activo else (110, 95, 95),
                  (ANCHO // 2, fila(i) + rh // 2), centro=True)
            if activo:
                acciones.append((rm, (clave, -1)))
                acciones.append((rp, (clave, 1)))

        nombre = "JOYSTICK" if sel == "joy" else ACCIONES[obj["accion"]][0]
        texto(f"Elegido: {nombre}", FUENTE_P, (255, 210, 60), (ANCHO // 2, fila(0) + rh // 2), centro=True)
        ajuste(1, "TAMAÑO", f"{int(obj['r'] * 100)}", "tam")
        ajuste(2, "ACCIÓN", "—" if sel == "joy" else ACCIONES[obj["accion"]][0], "acc", sel != "joy")
        r = pygame.Rect(px, fila(3), pw, rh)
        _boton_panel("OCULTAR" if obj["vis"] else "MOSTRAR", r, mouse)
        acciones.append((r, ("vis", 0)))
        ajuste(4, "OPACIDAD", f"{int(TOQUE.aj['opac'] * 100)}%", "opac")
        ajuste(5, "SENSIBILIDAD", f"{TOQUE.aj['sens']:.1f}", "sens")
        r = pygame.Rect(px, fila(6), ancho_m, rh)
        _boton_panel("Y INVERTIDO" if TOQUE.aj["inv_y"] else "Y NORMAL", r, mouse, True, FUENTE_XS)
        acciones.append((r, ("inv", 0)))
        r = pygame.Rect(px + ancho_m + K(6), fila(6), ancho_m, rh)
        _boton_panel("JOY FLOTANTE" if TOQUE.aj["joy_flotante"] else "JOY FIJO", r, mouse, True, FUENTE_XS)
        acciones.append((r, ("flot", 0)))
        r = pygame.Rect(px, fila(7), ancho_m, rh)
        _boton_panel("RESTABLECER", r, mouse, True, FUENTE_XS)
        acciones.append((r, ("reset", 0)))
        r = pygame.Rect(px + ancho_m + K(6), fila(7), ancho_m, rh)
        _boton_panel("GUARDAR Y SALIR", r, mouse, True, FUENTE_XS)
        acciones.append((r, ("salir", 0)))
        texto("Arrastra un control para moverlo · tócalo para elegirlo", FUENTE_XS, (170, 150, 150),
              (ANCHO // 2, fila(8) + rh // 2 + K(4)), centro=True)

        TOQUE.dibujar(editor=True, sel=sel)

        clics = []
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                TOQUE.guardar()
                salir()
            elif ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, TECLA_ATRAS):
                    TOQUE.guardar()
                    return
                continue
            t = TOQUE.convertir(ev)
            if t is None:
                continue
            tipo, fid, x, y = t
            if tipo == "down":
                if panel.collidepoint(x, y):
                    clics.append((x, y))
                    continue
                hit = TOQUE.buscar(x, y)
                if hit is not None:
                    sel = hit
                    o = TOQUE.joy if hit == "joy" else TOQUE.botones[hit]
                    arrastre = (fid, o["x"] * ANCHO - x, o["y"] * ALTO - y)
            elif tipo == "move" and arrastre and arrastre[0] == fid:
                o = TOQUE.joy if sel == "joy" else TOQUE.botones[sel]
                o["x"] = max(0.03, min(0.97, (x + arrastre[1]) / ANCHO))
                o["y"] = max(0.04, min(0.96, (y + arrastre[2]) / ALTO))
            elif tipo == "up" and arrastre and arrastre[0] == fid:
                arrastre = None

        for c in clics:
            for rect, (clave, d) in acciones:
                if not rect.collidepoint(c):
                    continue
                reproducir(SND_CLIC)
                if clave == "tam":
                    obj["r"] += 0.01 * d
                elif clave == "acc":
                    i = ORDEN_ACCIONES.index(obj["accion"])
                    obj["accion"] = ORDEN_ACCIONES[(i + d) % len(ORDEN_ACCIONES)]
                elif clave == "vis":
                    obj["vis"] = not obj["vis"]
                elif clave == "opac":
                    TOQUE.aj["opac"] += 0.1 * d
                elif clave == "sens":
                    TOQUE.aj["sens"] += 0.1 * d
                elif clave == "inv":
                    TOQUE.aj["inv_y"] = not TOQUE.aj["inv_y"]
                elif clave == "flot":
                    TOQUE.aj["joy_flotante"] = not TOQUE.aj["joy_flotante"]
                elif clave == "reset":
                    TOQUE.reiniciar_config()
                    sel = 0
                elif clave == "salir":
                    TOQUE.guardar()
                    return
                TOQUE.limitar()
        pygame.display.flip()


# ===========================================================================
# 12. PARTIDA
# ===========================================================================
TECLAS_ARMAS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6]


def jugar_nivel(nivel):
    """Juega un nivel. Devuelve 'siguiente', 'reintentar' o 'menu'."""
    juego = Juego(nivel)
    TOQUE.reiniciar()
    zbuf = [0.0] * (ANCHO + 1)
    minimapa, pausa, agarrado, mapa_grande = True, False, None, False
    congelado = None                     # imagen fija de la partida mientras está en pausa (ahorra batería)
    amb = AmbienteTerror()
    ambiente_juego()
    ADAPT.reiniciar()

    def escena():
        dibujar_paredes(juego.jugador, zbuf)
        dibujar_sprites(juego.jugador, lista_sprites(juego), zbuf)
        dibujar_arma(juego.jugador)
        dibujar_ads(juego.jugador)
        if GRAF["vineta"]:
            pantalla.blit(VINETA, (0, 0))
        dibujar_hud(juego)
        dibujar_marcas_hud(juego)
        if minimapa:
            dibujar_minimapa(juego)

    try:
        while True:
            ciclo_android()
            dt = min(0.05, reloj.tick(FPS_LIMITE) / 1000.0)
            if pausa or juego.estado != "jugando":
                amb.actualizar(dt)
            else:
                ADAPT.actualizar(dt, reloj.get_fps())
            clics = []
            for ev in pygame.event.get():
                if mapa_grande and not pausa:                  # el mapa ampliado es interactivo
                    r_mapa = MAPA_UI.evento(ev, juego)
                    if r_mapa:
                        if r_mapa == "cerrar":
                            mapa_grande = False
                            if MOVIL:
                                TOQUE.reiniciar()
                        continue
                if ev.type == pygame.QUIT:
                    salir()
                elif ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_ESCAPE, TECLA_ATRAS):
                        if mapa_grande:
                            mapa_grande = False
                        elif juego.estado == "jugando":
                            pausa = not pausa
                    elif ev.key == pygame.K_m and juego.estado == "jugando" and not pausa:
                        mapa_grande = not mapa_grande
                    elif ev.key == pygame.K_TAB:
                        minimapa = not minimapa
                    elif ev.key == pygame.K_p and juego.estado == "jugando" and not pausa and not mapa_grande:
                        alternar_marca_aqui(juego)
                    elif ev.key in TECLAS_ARMAS and juego.estado == "jugando" and not pausa and not mapa_grande:
                        juego.jugador.cambiar_arma(ARMAS[TECLAS_ARMAS.index(ev.key)]["id"])
                elif ev.type == pygame.MOUSEWHEEL and juego.estado == "jugando" and not pausa and not mapa_grande:
                    juego.jugador.ciclar_arma(ev.y)
                elif MOVIL:
                    clic = TOQUE.evento(ev)
                    if clic:
                        clics.append(clic)
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    clics.append(ev.pos)

            if MOVIL:                                     # botones de un solo toque
                for acc in TOQUE.tomar_acciones():
                    activo = juego.estado == "jugando"
                    if acc == "pausa":
                        if mapa_grande:
                            mapa_grande = False
                        elif activo:
                            pausa = not pausa
                    elif acc == "mapa" and activo and not pausa:
                        mapa_grande = not mapa_grande
                    elif acc == "minimapa":
                        minimapa = not minimapa
                    elif acc in ("arma_sig", "arma_ant") and activo and not pausa and not mapa_grande:
                        juego.jugador.ciclar_arma(-1 if acc == "arma_sig" else 1)

            jugando = juego.estado == "jugando" and not pausa and not mapa_grande
            if not MOVIL and jugando != agarrado:                       # captura / libera el mouse
                pygame.mouse.set_visible(not jugando)
                pygame.event.set_grab(jugando)
                pygame.mouse.get_rel()
                agarrado = jugando

            teclas = pygame.key.get_pressed()
            if MOVIL:
                rx, ry = TOQUE.tomar_rel()
                teclas = TOQUE.teclas(teclas)
            if jugando:
                if MOVIL:
                    botones = (TOQUE.mantenido("disparar"), False, TOQUE.mantenido("apuntar"))
                else:
                    rx, ry = pygame.mouse.get_rel()
                    botones = pygame.mouse.get_pressed()
                rx, ry = max(-120, min(120, rx)), max(-120, min(120, ry))
                disparando = botones[0] or teclas[pygame.K_SPACE]
                juego.actualizar(dt, teclas, rx, ry, disparando, botones[2])   # botón derecho = apuntar
            else:
                juego.actualizar_efectos(dt)
                if juego.estado != "jugando":             # al terminar el nivel se baja el arma
                    jg = juego.jugador
                    jg.apuntando = max(0.0, jg.apuntando - 4 * dt)
                    jg.zoom = 1.0 + (jg.stats["zoom"] - 1.0) * jg.apuntando
                    CAMARA["zoom"] = jg.zoom

            if mapa_grande:
                dibujar_mapa_ampliado(juego)
            elif pausa and congelado is not None:
                pantalla.blit(congelado, (0, 0))
            else:
                escena()
                if pausa:
                    congelado = pantalla.copy()
            if not pausa:
                congelado = None
            if GRAF["ver_fps"]:
                dibujar_fps()

            if MOVIL and juego.estado == "jugando" and not pausa and not mapa_grande:
                TOQUE.dibujar()

            mouse = pygame.mouse.get_pos()
            if pausa:
                velo = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
                velo.fill((0, 0, 0, 170))
                pantalla.blit(velo, (0, 0))
                amb.titulo("PAUSA", Y(150), FUENTE_TITULO)
                items = [("REANUDAR", "reanudar"), ("AJUSTES", "ajustes")]
                if MOVIL:
                    items.append(("CONTROLES", "controles"))
                items.append(("ABANDONAR NIVEL", "salir"))
                rects = [(boton_terror(txt, ANCHO // 2 - K(150), Y(255 + i * 62), K(300), K(50), mouse)[0], clave)
                         for i, (txt, clave) in enumerate(items)]
                for c in clics:
                    elegido = next((clave for r, clave in rects if r.collidepoint(c)), None)
                    if elegido is None:
                        continue
                    reproducir(SND_CLIC)
                    if elegido == "reanudar":
                        pausa = False
                    elif elegido == "ajustes":
                        pantalla_graficos(escena)
                        TOQUE.reiniciar()
                        ADAPT.reiniciar()
                        congelado = None
                    elif elegido == "controles":
                        pantalla_controles()
                        TOQUE.reiniciar()
                    else:
                        guardar_datos()
                        return "menu"
                    break
            elif juego.estado in ("muerto", "victoria"):
                velo = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
                velo.fill((80, 0, 0, 175) if juego.estado == "muerto" else (0, 30, 8, 175))
                pantalla.blit(velo, (0, 0))
                if juego.estado == "muerto":
                    amb.titulo("HAS MUERTO", Y(120), FUENTE_TITULO)
                    texto(f"Infectados abatidos: {juego.muertes}   ·   Monedas ganadas: {juego.monedas_nivel}",
                          FUENTE_M, (235, 215, 200), (ANCHO // 2, Y(200)), centro=True)
                    txt_principal, resultado = "REINTENTAR", "reintentar"
                else:
                    texto("NIVEL SUPERADO", FUENTE_G, (120, 255, 140), (ANCHO // 2, Y(120)), centro=True)
                    texto(f"Monedas ganadas: {juego.monedas_nivel}  (bonus +{juego.bonus})",
                          FUENTE_M, (255, 210, 60), (ANCHO // 2, Y(200)), centro=True)
                    txt_principal, resultado = "SIGUIENTE NIVEL", "siguiente"
                r1, _ = boton_terror(txt_principal, ANCHO // 2 - K(160), Y(250), K(320), K(52), mouse)
                r2, _ = boton_terror("ARMERÍA", ANCHO // 2 - K(160), Y(320), K(320), K(52), mouse)
                r3, _ = boton_terror("MENÚ PRINCIPAL", ANCHO // 2 - K(160), Y(390), K(320), K(52), mouse)
                texto(f"Monedas: {DATOS['monedas']}", FUENTE_M, (255, 210, 60), (ANCHO // 2, Y(470)), centro=True)
                for c in clics:
                    if r1.collidepoint(c):
                        reproducir(SND_CLIC)
                        return resultado
                    if r2.collidepoint(c):
                        pantalla_tienda()
                        agarrado = None
                        break
                    if r3.collidepoint(c):
                        return "menu"
            pygame.display.flip()
    finally:
        pygame.mouse.set_visible(True)
        pygame.event.set_grab(False)


# ===========================================================================
# 13. PROGRAMA PRINCIPAL
# ===========================================================================
def main():
    cargar_datos()
    cargar_graficos()
    TOQUE.cargar()
    iniciar_musica()
    try:
        while True:
            ambiente_menu()
            opcion = pantalla_menu()
            if opcion == "jugar":
                nivel = pantalla_niveles()
                while nivel is not None:
                    resultado = jugar_nivel(nivel)
                    if resultado == "siguiente":
                        nivel += 1
                    elif resultado != "reintentar":
                        break
            elif opcion == "tienda":
                pantalla_tienda()
            elif opcion == "accesorios":
                pantalla_accesorios()
            elif opcion == "personalizar":
                pantalla_personalizar()
            elif opcion == "controles":
                pantalla_controles()
            elif opcion == "ajustes":
                pantalla_graficos()
            else:
                break
    finally:
        guardar_datos()
        pygame.quit()


if __name__ == "__main__":
    main()
