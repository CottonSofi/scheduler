import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import threading
import time
import os
import sys
import json
import re
import traceback
import webbrowser
import queue
import random
import tempfile
import subprocess
import ctypes
from datetime import datetime

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import Select
    from selenium.common.exceptions import UnexpectedAlertPresentException, NoAlertPresentException, TimeoutException
    HAS_SELENIUM = True
except ImportError:
    webdriver = None
    Options = None
    By = None
    WebDriverWait = None
    EC = None
    Select = None
    UnexpectedAlertPresentException = None
    NoAlertPresentException = Exception
    TimeoutException = Exception
    HAS_SELENIUM = False

# ==========================================
# VALIDACIÓN DE ENTRADA
# ==========================================
def validate_date_format(date_str):
    """Valida y retorna True si el formato es correcto de fecha."""
    if not date_str or not date_str.strip(): 
        return True
    for fmt in ("%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            datetime.strptime(date_str.strip(), fmt)
            return True
        except ValueError:
            pass
    return False

def validate_time_format(time_str):
    """Valida y retorna True si el formato es correcto de hora."""
    if not time_str or not time_str.strip(): 
        return True
    try:
        datetime.strptime(time_str.strip(), "%H:%M")
        return True
    except ValueError:
        return False

def parse_date(date_str):
    """Parsea una fecha en múltiples formatos."""
    if not date_str: 
        return None
    for fmt in ("%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%d", "%d-%m-%Y"):
        try: 
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError: 
            pass
    return None

def parse_time(time_str):
    """Parsea una hora en formato HH:MM."""
    if not time_str: 
        return None
    try: 
        return datetime.strptime(time_str.strip(), "%H:%M").time()
    except ValueError: 
        return None

def date_to_ordinal(d):
    if not d:
        return None
    try:
        return d.toordinal()
    except Exception:
        return None

def time_to_minutes(t):
    if not t:
        return None
    return (t.hour * 60) + t.minute

def extract_first_time_from_text(text):
    s = str(text or "")
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", s)
    if not m:
        return None
    try:
        hour = int(m.group(1))
        minute = int(m.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M").time()
    except Exception:
        pass
    return None

def extract_first_date_time_from_text(text):
    """Extrae fecha/hora desde textos mixtos de SURA (con ruido adicional)."""
    s = str(text or "")
    d = parse_date(s) or extract_first_date_from_text(s)
    t = parse_time(s) or extract_first_time_from_text(s)
    return d, t

def extract_first_date_from_text(text):
    s = str(text or "")
    patterns = [
        r"\b\d{2}/\d{2}/\d{4}\b",
        r"\b\d{4}/\d{2}/\d{2}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{2}-\d{2}-\d{4}\b",
    ]
    for p in patterns:
        m = re.search(p, s)
        if not m:
            continue
        d = parse_date(m.group(0))
        if d:
            return d
    return None

def normalize_text(text):
    return re.sub(r"\s+", " ", str(text or "").strip().lower())

def detect_windows_monitors_fallback():
    monitors = []
    try:
        if os.name == "nt":
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32

            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            class MONITORINFOEXW(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong),
                    ("rcMonitor", RECT),
                    ("rcWork", RECT),
                    ("dwFlags", ctypes.c_ulong),
                    ("szDevice", ctypes.c_wchar * 32),
                ]

            MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(RECT), ctypes.c_long)

            def _enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
                info = MONITORINFOEXW()
                info.cbSize = ctypes.sizeof(MONITORINFOEXW)
                if user32.GetMonitorInfoW(hMonitor, ctypes.byref(info)):
                    rect = info.rcMonitor
                    monitors.append(
                        {
                            "device": str(info.szDevice or ""),
                            "left": int(rect.left),
                            "top": int(rect.top),
                            "width": int(rect.right - rect.left),
                            "height": int(rect.bottom - rect.top),
                            "primary": bool(info.dwFlags & 1),
                        }
                    )
                return 1

            user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(_enum_proc), 0)
    except Exception:
        monitors = []

    if not monitors:
        try:
            root = tk._default_root
            width = int(root.winfo_screenwidth()) if root else 1920
            height = int(root.winfo_screenheight()) if root else 1080
        except Exception:
            width, height = 1920, 1080
        monitors = [
            {
                "device": "default",
                "left": 0,
                "top": 0,
                "width": width,
                "height": height,
                "primary": True,
            }
        ]

    monitors.sort(key=lambda item: (not bool(item.get("primary", False)), int(item.get("left", 0)), int(item.get("top", 0))))
    for idx, item in enumerate(monitors, start=1):
        item["id"] = idx
        item["label"] = f"Monitor {idx} ({int(item.get('width', 0))}x{int(item.get('height', 0))} @ {int(item.get('left', 0))},{int(item.get('top', 0))})"
    return monitors

# ==========================================
# SISTEMA DE ARCHIVOS Y JSON
# ==========================================
def play_alert_sound():
    if HAS_WINSOUND:
        sound_file = "alerta.wav"
        if os.path.exists(sound_file): 
            winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else: 
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
    else: 
        print("\a") 

def get_default_cookies_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    paths = [
        os.path.join(base_dir, "agendaweb.suramericana.com_cookies.txt"),
        os.path.join(base_dir, "cookies", "agendaweb.suramericana.com_cookies.txt"),
        os.path.join(os.getcwd(), "agendaweb.suramericana.com_cookies.txt")
    ]
    for p in paths:
        if os.path.exists(p): 
            return p
    return "" 

def resolve_portable_cookie_path(raw_path):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    clean = str(raw_path or "").strip()
    if not clean:
        return ""

    if not os.path.isabs(clean):
        return os.path.abspath(os.path.join(base_dir, clean))

    if os.path.isfile(clean):
        return os.path.abspath(clean)

    normalized = clean.replace("\\", "/")
    lowered = normalized.lower()
    mappings = [
        ("/message/alerter/", base_dir),
        ("/message/", os.path.dirname(base_dir)),
        ("/alerter/", base_dir),
    ]
    for marker, target_root in mappings:
        idx = lowered.find(marker)
        if idx == -1:
            continue
        suffix = normalized[idx + len(marker):].strip("/")
        if not suffix:
            return os.path.abspath(target_root)
        return os.path.abspath(os.path.join(target_root, *suffix.split("/")))

    return os.path.abspath(clean)

def load_cookies(driver, filepath):
    if not filepath or not os.path.exists(filepath): 
        return False
    with open(filepath, "r", encoding="utf-8") as file:
        for line in file:
            if line.startswith("#") or not line.strip(): 
                continue
            parts = line.strip().split("\t")
            if len(parts) >= 7:
                cookie = {"domain": parts[0], "path": parts[2], "secure": parts[3].lower() == "true", "name": parts[5], "value": parts[6]}
                try: 
                    driver.add_cookie(cookie)
                except Exception: 
                    pass
    return True

_DATA_DIR_CACHE = None

def _is_writable_directory(path):
    try:
        os.makedirs(path, exist_ok=True)
        test_path = os.path.join(path, "._write_test.tmp")
        with open(test_path, "w", encoding="utf-8") as tmp:
            tmp.write("ok")
        os.remove(test_path)
        return True
    except Exception:
        return False

def get_data_dir(force_refresh=False):
    """Resuelve una carpeta de datos escribible y estable para los JSON locales."""
    global _DATA_DIR_CACHE

    if _DATA_DIR_CACHE and (not force_refresh):
        return _DATA_DIR_CACHE

    base_dir = os.path.dirname(os.path.abspath(__file__))
    appdata_dir = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "SuraGestorCitas", "datos_temporales")
    candidates = [
        appdata_dir,
        os.path.join(base_dir, "datos_temporales"),
        os.path.join(os.getcwd(), "datos_temporales"),
        os.path.join(tempfile.gettempdir(), "sura_alerter_datos"),
    ]

    for path in candidates:
        if _is_writable_directory(path):
            _DATA_DIR_CACHE = path
            return path

    _DATA_DIR_CACHE = tempfile.gettempdir()
    return _DATA_DIR_CACHE

def get_data_file_path(name):
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(name or "data"))
    return os.path.join(get_data_dir(), f"{safe_name}.json")

def save_json(name, data):
    path = get_data_file_path(name)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        # Fuerza refresco de carpeta si hubo bloqueo temporal y reintenta una vez.
        try:
            safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(name or "data"))
            path = os.path.join(get_data_dir(force_refresh=True), f"{safe_name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as ex:
            print(f"[WARN] No se pudo guardar '{name}': {ex}")
            return False

def load_json(name):
    path = get_data_file_path(name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception: 
        return []

def load_config():
    path = get_data_file_path("config")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception: 
        return {}

def set_startup(enable):
    startup_dir = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
    os.makedirs(startup_dir, exist_ok=True)
    vbs_path = os.path.join(startup_dir, "SuraGestorCitas.vbs")
    bat_path = os.path.join(startup_dir, "SuraGestorCitas.bat")
    pythonw_exe = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "pythonw.exe")
    if not os.path.isfile(pythonw_exe):
        pythonw_exe = sys.executable
    if enable:
        try:
            script_path = os.path.abspath(__file__)
            if os.path.exists(bat_path):
                os.remove(bat_path)
            with open(vbs_path, "w", encoding="utf-8") as f:
                f.write(
                    'Set shell = CreateObject("WScript.Shell")\n'
                    'Set fso = CreateObject("Scripting.FileSystemObject")\n'
                    f'If fso.FileExists("{pythonw_exe}") And fso.FileExists("{script_path}") Then shell.Run Chr(34) & "{pythonw_exe}" & Chr(34) & " " & Chr(34) & "{script_path}" & Chr(34), 0, False\n'
                )
        except Exception: 
            pass
    else:
        if os.path.exists(vbs_path):
            try:
                os.remove(vbs_path)
            except: 
                pass
        if os.path.exists(bat_path):
            try: 
                os.remove(bat_path)
            except: 
                pass

# ==========================================
# UTILIDADES Y NAVEGACIÓN SEGURA
# ==========================================
def limpiar_popups(driver, update_callback=None):
    closed_any = False
    for _ in range(3):
        try:
            alert = driver.switch_to.alert
            texto = alert.text
            alert.accept()
            closed_any = True
            if update_callback:
                update_callback(f"  [+] Alerta nativa cerrada: '{texto[:25]}...'")
            time.sleep(1)
        except NoAlertPresentException:
            break

    try:
        closed_count = driver.execute_script(
            """
            let closed = 0;

            // Cierre dirigido para modales conocidos.
            try {
              if (typeof $ !== 'undefined' && typeof $('#userData').modal === 'function') {
                $('#userData').modal('hide');
                closed += 1;
              }
              if (typeof $ !== 'undefined' && typeof $('#information').modal === 'function') {
                $('#information').modal('hide');
                closed += 1;
              }
            } catch (e) {}

            // Cierre genérico por botones típicos de modal.
            const selectors = [
              '.modal.show button.close', '.modal.show [data-dismiss="modal"]',
              '.modal.in button.close', '.modal.in [data-dismiss="modal"]',
              '[role="dialog"] button.close', '[role="dialog"] [aria-label="Close"]',
              '.swal2-container .swal2-confirm', '.swal2-container .swal2-close',
              '.ui-dialog .ui-dialog-titlebar-close'
            ];
            for (const sel of selectors) {
              document.querySelectorAll(sel).forEach((btn) => {
                try {
                  btn.click();
                  closed += 1;
                } catch (e) {}
              });
            }

            // Forzar desbloqueo visual si quedó backdrop pegado.
            document.querySelectorAll('.modal-backdrop, .swal2-container').forEach((el) => {
              try {
                el.remove();
                closed += 1;
              } catch (e) {}
            });
            if (document.body) {
              document.body.classList.remove('modal-open');
              document.body.style.removeProperty('overflow');
              document.body.style.removeProperty('padding-right');
            }

            return closed;
            """
        )
        if closed_count:
            closed_any = True
            if update_callback:
                update_callback(f"  [+] Popups/overlays cerrados: {closed_count}")
    except Exception:
        pass

    return closed_any

def ir_a_perfil_con_clic(driver, update_callback, fast_mode=False):
    if fast_mode:
        update_callback("↪ Cambio rápido a 'Consulta, pago y cancelación'...")
    else:
        update_callback("Haciendo clic en menú 'Consulta, pago y cancelación'...")
    try:
        wait_s = 2.5 if fast_mode else 5
        enlace = WebDriverWait(driver, wait_s).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cancelaci') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'consulta')]")))
        enlace.click()
    except Exception:
        try: 
            driver.execute_script("if(typeof doTraerPaginaCancelacionCitas === 'function') doTraerPaginaCancelacionCitas();")
        except: 
            pass
    time.sleep(1.2 if fast_mode else 4)
    limpiar_popups(driver, update_callback)

def ir_a_asignacion_con_clic(driver, update_callback, fast_mode=False):
    if fast_mode:
        update_callback("↩ Regresando rápido a 'Asignación de Citas'...")
    else:
        update_callback("Haciendo clic en menú 'Asignación de Citas'...")
    try:
        wait_s = 2.5 if fast_mode else 5
        enlace = WebDriverWait(driver, wait_s).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'asignaci')]")))
        enlace.click()
    except Exception:
        try: 
            driver.execute_script("if(typeof doTraerPaginaParametrosAsignacionCitas === 'function') doTraerPaginaParametrosAsignacionCitas();")
        except: 
            pass
    time.sleep(1.5 if fast_mode else 4)
    limpiar_popups(driver, update_callback)

def wait_for_results_table(driver, timeout=2.2):
    """Espera corta para que aparezcan filas de resultados sin bloquear demasiado el ciclo."""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "table.control_citas tbody tr")) > 0
        )
    except TimeoutException:
        pass

def consultar_disponibilidad_con_preferencia_fecha(driver, update_callback=None, fecha_preferida="", usar_preferencia=False):
    """Resuelve el flujo de consulta cuando SURA muestra modal de fecha deseada."""
    fecha_iso = ""
    if usar_preferencia and str(fecha_preferida or "").strip():
        parsed = parse_date(str(fecha_preferida).strip())
        if parsed:
            fecha_iso = parsed.strftime("%Y-%m-%d")
        elif update_callback:
            update_callback(f"⚠️ Fecha preferida SURA inválida: {fecha_preferida}")

    try:
        driver.execute_script("if(typeof consultarDisponibilidadCitas === 'function') consultarDisponibilidadCitas();")
    except Exception:
        return False

    modal_visible = False
    try:
        WebDriverWait(driver, 2.0).until(
            lambda d: d.execute_script(
                """
                const m = document.querySelector('#disponible');
                if (!m) return false;
                const cls = (m.className || '').toLowerCase();
                const st = (m.style && m.style.display) ? m.style.display.toLowerCase() : '';
                return cls.includes('show') || st === 'block';
                """
            )
        )
        modal_visible = True
    except Exception:
        modal_visible = False

    if modal_visible and fecha_iso:
        try:
            set_ok = bool(driver.execute_script(
                """
                const input = document.querySelector('#recipient-date') || document.querySelector('input[type="date"]');
                if (!input) return false;
                input.value = arguments[0];
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
                """,
                fecha_iso,
            ))
            if set_ok and update_callback:
                update_callback(f"📅 Fecha preferida SURA aplicada: {fecha_iso}")
        except Exception:
            pass

    try:
        clicked = bool(driver.execute_script(
            """
            const btn = document.querySelector('#disponible button[onclick*="consultarDisponibilidadCitasResolucion"]')
              || document.querySelector('button[onclick*="consultarDisponibilidadCitasResolucion"]');
            if (btn) {
              btn.click();
              return true;
            }
            if (typeof consultarDisponibilidadCitasResolucion === 'function') {
              consultarDisponibilidadCitasResolucion();
              return true;
            }
            return false;
            """
        ))
        return clicked
    except Exception:
        try:
            driver.execute_script("if(typeof consultarDisponibilidadCitasResolucion === 'function') consultarDisponibilidadCitasResolucion();")
            return True
        except Exception:
            return False

def confirmar_accion_con_regex(driver, update_callback=None, timeout=12):
    """Intenta confirmar un modal buscando primero botones tipo 'sí' y luego 'aceptar'."""
    patrones = [
        re.compile(r"\bs[ií]\b", re.IGNORECASE),
        re.compile(r"\bacept(ar|o)?\b", re.IGNORECASE),
    ]
    selectores = ["button", "a", "input[type='button']", "input[type='submit']", "[role='button']"]

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            for selector in selectores:
                for elem in driver.find_elements(By.CSS_SELECTOR, selector):
                    try:
                        if not elem.is_displayed() or not elem.is_enabled():
                            continue
                    except Exception:
                        continue

                    textos = [
                        (elem.text or "").strip(),
                        (elem.get_attribute("value") or "").strip(),
                        (elem.get_attribute("aria-label") or "").strip(),
                    ]
                    for patron in patrones:
                        for texto in textos:
                            if texto and patron.search(texto):
                                try:
                                    elem.click()
                                except Exception:
                                    driver.execute_script("arguments[0].click();", elem)
                                if update_callback:
                                    update_callback(f"  [+] Confirmación pulsada: '{texto}'")
                                time.sleep(1)
                                limpiar_popups(driver, update_callback)
                                return True
        except Exception:
            pass

        time.sleep(0.25)

    if update_callback:
        update_callback("  [-] No encontré confirmación 'sí/aceptar' para la acción (timeout).")
    return False

def seleccionar_cita_por_prioridad(citas, prioridad="Más temprana (tope)"):
    """Elige una cita por prioridad de hora/fecha: tope (temprana) o fondo (tardía)."""
    candidatas = [c for c in (citas or []) if isinstance(c, dict)]
    if not candidatas:
        return None

    def _key(c):
        f = parse_date(str(c.get("fecha") or ""))
        h = parse_time(str(c.get("hora") or ""))
        return (f or datetime.max.date(), h or datetime.max.time(), str(c.get("doctor") or ""))

    ordered = sorted(candidatas, key=_key)
    if "tard" in str(prioridad).lower() or "fondo" in str(prioridad).lower():
        return ordered[-1]
    return ordered[0]

def get_profile_for_reprogram_from_cache():
    """Obtiene una cita vigente desde cache para ejecutar reprogramación automática."""
    perfiles = load_json("perfil_cache") or []
    if not perfiles:
        return None

    def _key(item):
        fecha = parse_date(str(item.get("fecha") or ""))
        return (fecha or datetime.max.date(), str(item.get("doctor") or ""))

    perfiles.sort(key=_key)
    return perfiles[0]

def get_profile_current_time_from_cache():
    """Intenta obtener la hora actual de la cita vigente desde perfil_cache."""
    perfil_obj = get_profile_for_reprogram_from_cache()
    if not perfil_obj:
        return None
    return extract_first_time_from_text(perfil_obj.get("fecha"))

def get_profile_current_date_from_cache():
    """Intenta obtener la fecha actual de la cita vigente desde perfil_cache."""
    perfil_obj = get_profile_for_reprogram_from_cache()
    if not perfil_obj:
        return None
    raw = str(perfil_obj.get("fecha") or "")
    parsed = parse_date(raw)
    if parsed:
        return parsed
    return extract_first_date_from_text(raw)

def seleccionar_cita_hacia_objetivo(citas, prioridad, target_date=None, target_time=None, current_date=None, current_time=None):
    """Selecciona cita que mejore hacia día/hora objetivo sin empeorar frente a la cita actual."""
    target_date_ord = date_to_ordinal(target_date)
    target_minutes = time_to_minutes(target_time)
    if target_date_ord is None and target_minutes is None:
        return seleccionar_cita_por_prioridad(citas, prioridad)

    current_date_ord = date_to_ordinal(current_date)
    current_minutes = time_to_minutes(current_time)

    prioridad_txt = str(prioridad or "").lower()
    prefer_tardia = ("tard" in prioridad_txt or "fondo" in prioridad_txt)

    current_date_diff = None
    current_time_diff = None
    if target_date_ord is not None and current_date_ord is not None:
        current_date_diff = abs(current_date_ord - target_date_ord)
    if target_minutes is not None and current_minutes is not None:
        current_time_diff = abs(current_minutes - target_minutes)

    def lado_objetivo_score(c_minutes):
        """Score para desempate de lado del objetivo horario (más bajo = mejor)."""
        if target_minutes is None or c_minutes is None:
            return 0
        if c_minutes == target_minutes:
            return 0
        # Si se prefiere tardía, se favorece quedar por encima del objetivo.
        if prefer_tardia:
            return 0 if c_minutes > target_minutes else 1
        # Si se prefiere temprana, se favorece quedar por debajo del objetivo.
        return 0 if c_minutes < target_minutes else 1

    def lado_objetivo_dia_score(c_date_ord):
        """Score para desempate de lado del objetivo de fecha (más bajo = mejor)."""
        if target_date_ord is None or c_date_ord is None:
            return 0
        if c_date_ord == target_date_ord:
            return 0
        # Si se prefiere tardía, se favorece quedar después del día objetivo.
        if prefer_tardia:
            return 0 if c_date_ord > target_date_ord else 1
        # Si se prefiere temprana, se favorece quedar antes del día objetivo.
        return 0 if c_date_ord < target_date_ord else 1

    candidatas = []
    for c in (citas or []):
        if not isinstance(c, dict):
            continue

        fecha_obj = parse_date(str(c.get("fecha") or ""))
        d_ord = date_to_ordinal(fecha_obj)
        h = parse_time(str(c.get("hora") or ""))
        m = time_to_minutes(h)

        if target_date_ord is not None and d_ord is None:
            continue
        if target_minutes is not None and m is None:
            continue

        date_diff = abs(d_ord - target_date_ord) if (target_date_ord is not None and d_ord is not None) else 0
        time_diff = abs(m - target_minutes) if (target_minutes is not None and m is not None) else 0

        # No permitir citas que empeoren frente a la cita actual respecto al objetivo.
        if current_date_diff is not None and date_diff > current_date_diff:
            continue
        if current_time_diff is not None and time_diff > current_time_diff:
            continue

        # Si la cercanía es igual a la actual, solo permitir cambio cuando mejora el lado
        # del objetivo según preferencia (temprana/tardía).
        if current_time_diff is not None and time_diff == current_time_diff and current_minutes is not None:
            if lado_objetivo_score(m) > lado_objetivo_score(current_minutes):
                continue

        candidatas.append((date_diff, time_diff, lado_objetivo_dia_score(d_ord), lado_objetivo_score(m), d_ord or 0, m or 0, c))

    if not candidatas:
        return None

    if "tard" in prioridad_txt or "fondo" in prioridad_txt:
        candidatas.sort(key=lambda x: (x[0], x[1], x[2], x[3], -x[4], -x[5]))
    else:
        candidatas.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4], x[5]))
    return candidatas[0][6]

def cita_dentro_de_filtros(cita, d_start=None, d_end=None, t_start=None, t_end=None):
    """Verifica nuevamente que una cita esté dentro de los filtros activos."""
    if not isinstance(cita, dict):
        return False

    fecha_raw = str(cita.get("fecha") or "")
    hora_raw = str(cita.get("hora") or "")

    fecha_cita, hora_extraida_en_fecha = extract_first_date_time_from_text(fecha_raw)
    hora_cita = parse_time(hora_raw) or extract_first_time_from_text(hora_raw) or hora_extraida_en_fecha

    if d_start and (not fecha_cita or fecha_cita < d_start):
        return False
    if d_end and (not fecha_cita or fecha_cita > d_end):
        return False
    if t_start and (not hora_cita or hora_cita < t_start):
        return False
    if t_end and (not hora_cita or hora_cita > t_end):
        return False
    return True

# ==========================================
# MOTORES DE EXTRACCIÓN Y ACCIÓN (SELENIUM)
# ==========================================
def extraer_perfil_silencioso(driver, update_callback=None, gui_callback=None):
    try:
        driver.execute_script("if(typeof dolistarCitasXInternet === 'function') dolistarCitasXInternet();")
        time.sleep(4) 
        filas = driver.find_elements(By.CSS_SELECTOR, "table.control_citas tbody tr")
        perfil_data = []
        if filas and len(filas) > 0:
            for idx, fila in enumerate(filas):
                celdas = fila.find_elements(By.TAG_NAME, "td")
                if len(celdas) >= 4:
                    js_canc, js_repr = "", ""
                    for elem in fila.find_elements(By.CSS_SELECTOR, "button, a"):
                        texto, accion = elem.text.lower(), elem.get_attribute("onclick") or elem.get_attribute("href") or ""
                        if "cancel" in texto or "cancel" in accion.lower(): 
                            js_canc = accion
                        elif "repro" in texto or "repro" in accion.lower(): 
                            js_repr = accion

                    perfil_data.append({
                        "id_perfil": idx, "fecha": celdas[0].text.strip(),
                        "servicio": celdas[2].text.strip(), "doctor": celdas[3].text.strip(),
                        "js_cancelar": js_canc, "js_reprogramar": js_repr
                    })
            save_json("perfil_cache", perfil_data)
            if gui_callback: 
                gui_callback("update_profile_table", perfil_data)
            if update_callback: 
                update_callback(f"✅ Perfil extraído exitosamente: {len(perfil_data)} citas vigentes.")
        else:
            save_json("perfil_cache", [])
            if gui_callback:
                gui_callback("update_profile_table", [])
            if update_callback: 
                update_callback("⚠️ Tu perfil está validado pero no tienes citas vigentes.")
    except Exception as e:
        if update_callback: 
            update_callback(f"⚠️ Error leyendo tabla de perfil: {e}")

def cita_aparece_en_perfil(cita_objetivo, perfil_data):
    """Valida si la cita objetivo quedó reflejada en el perfil extraído."""
    if not cita_objetivo or not perfil_data:
        return False

    fecha_obj = normalize_text(cita_objetivo.get("fecha"))
    doctor_obj = normalize_text(cita_objetivo.get("doctor"))
    doctor_tokens = [t for t in re.split(r"\W+", doctor_obj) if len(t) >= 4]

    for item in perfil_data:
        fecha_perfil = normalize_text(item.get("fecha"))
        doctor_perfil = normalize_text(item.get("doctor"))

        fecha_ok = (fecha_obj and fecha_obj in fecha_perfil) or (fecha_perfil and fecha_perfil in fecha_obj)
        if not fecha_ok:
            continue

        if doctor_obj and doctor_obj in doctor_perfil:
            return True

        if doctor_tokens and any(tok in doctor_perfil for tok in doctor_tokens):
            return True

    return False

def ejecutar_agendamiento(driver, cita_data, update_callback):
    update_callback("Ejecutando Agendamiento Automático...")
    ir_a_asignacion_con_clic(driver, update_callback)
    
    try:
        driver.execute_script("consultarDisponibilidadCitas();")
        time.sleep(2)
        driver.execute_script("consultarDisponibilidadCitasResolucion();")
        time.sleep(4)
    except: 
        pass
    
    try:
        select_element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "listaDisponibilidad")))
        select = Select(select_element)
        encontrado = False
        for idx, option in enumerate(select.options):
            if cita_data['doctor'] in option.text and cita_data['fecha'] in option.text:
                select.select_by_index(idx)
                encontrado = True
                break
        
        if encontrado:
            try: 
                driver.execute_script("if(typeof consultarCitasDisponibles === 'function') consultarCitasDisponibles();")
            except: 
                pass
            time.sleep(4)
            
            for fila in driver.find_elements(By.CSS_SELECTOR, "table.control_citas tbody tr"):
                celdas = fila.find_elements(By.TAG_NAME, "td")
                if len(celdas) >= 3 and cita_data['hora'] in celdas[0].text:
                    btn = fila.find_elements(By.XPATH, ".//button[contains(@onclick, 'seleccionarCita')]")
                    if btn: 
                        driver.execute_script(btn[0].get_attribute("onclick").replace("javascript:", ""))
                        update_callback("✅ Cita seleccionada en la web! Revisa Chrome para finalizar.")
                        return {"ok": True, "reason": "selected"}
                    enlace = fila.find_elements(By.XPATH, ".//a[contains(@href, 'seleccionarCita')]")
                    if enlace:
                        driver.execute_script(enlace[0].get_attribute("href").replace("javascript:", ""))
                        update_callback("✅ Cita seleccionada en la web! Revisa Chrome para finalizar.")
                        return {"ok": True, "reason": "selected"}
        update_callback("❌ La cita requerida ya no está disponible o el menú cambió.")
        return {"ok": False, "reason": "not_available"}
    except Exception as e:
        update_callback(f"❌ Error durante agendamiento: {str(e)}")
        return {"ok": False, "reason": "error"}

def intentar_agendamiento_con_reintentos(driver, cita_data, update_callback, max_attempts=2):
    """Reintenta agendar si falla por tiempo/transición antes de reportar error final."""
    ultimo = {"ok": False, "reason": "unknown"}
    for intento in range(1, max_attempts + 1):
        if intento > 1:
            update_callback(f"🔁 Reintentando agendamiento ({intento}/{max_attempts})...")
            try:
                ir_a_asignacion_con_clic(driver, update_callback, fast_mode=True)
            except Exception:
                pass
            time.sleep(1)

        ultimo = ejecutar_agendamiento(driver, cita_data, update_callback)
        if ultimo.get("ok"):
            return ultimo
    return ultimo

def verificar_agendamiento_en_perfil(driver, cita_data, update_callback, gui_callback=None, checks=2):
    """Confirma en consulta/perfil si la cita realmente quedó agendada."""
    for i in range(checks):
        try:
            ir_a_perfil_con_clic(driver, update_callback, fast_mode=True)
            extraer_perfil_silencioso(driver, update_callback, gui_callback)
            perfil_actual = load_json("perfil_cache") or []
            if cita_aparece_en_perfil(cita_data, perfil_actual):
                return True
        except Exception:
            pass
        time.sleep(1.5)
    return False

def detect_backend_outage_error(driver):
    """Detecta errores de backend SURA (WebLogic/Oracle) visibles en la página."""
    try:
        page_text = str(driver.page_source or "").lower()
    except Exception:
        return False

    patrones = [
        "alerta: ocurrio un error inesperado",
        "alerta: ocurrió un error inesperado",
        "weblogic.common.resourceexception",
        "resourceexception: could not create pool connection",
        "resourcepool.resourcedisabledexception",
        "pool agendawebcoreds is suspended",
        "could not create pool connection for datasource 'agendawebcoreds'",
        "ora-28000",
        "the account is locked",
        "agew-0599999",
    ]
    return any(p in page_text for p in patrones)

def check_appointments(cookie_path, headless, single_run, show_popup_ui, date_start, date_end, time_start, time_end, interval, use_sound, alert_block, stop_event, update_callback, gui_callback, action_queue, get_filters_callback=None):
    driver = None
    try:
        def resolve_interval_value(base_interval, dynamic_filters=None):
            """Resuelve intervalo fijo o aleatorio en rango, siempre >= 15s."""
            filters = dynamic_filters if isinstance(dynamic_filters, dict) else {}

            def _to_int(value, fallback=None):
                try:
                    return int(str(value).strip())
                except Exception:
                    return fallback

            base = _to_int(filters.get("interval"), _to_int(base_interval, 60))
            min_v = _to_int(filters.get("interval_min"), base)
            max_v = _to_int(filters.get("interval_max"), min_v)

            if min_v is None:
                min_v = 60
            if max_v is None:
                max_v = min_v

            min_v = max(15, min_v)
            max_v = max(15, max_v)
            if max_v < min_v:
                max_v = min_v

            use_random = bool(filters.get("interval_random", False))
            if use_random:
                return random.randint(min_v, max_v)
            return min_v

        base_domain_url = "https://agendaweb.suramericana.com"
        cita_url = "https://agendaweb.suramericana.com/agenda/internet/internet-asignarCita.do#no-back-button"

        if not HAS_SELENIUM:
            update_callback("ERROR CRÍTICO: Selenium no está instalado.")
            return

        update_callback(f"Iniciando Chrome (Oculto: {headless})...")
        chrome_options = Options()
        if headless: 
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
            
        driver = webdriver.Chrome(options=chrome_options)
        
        update_callback("Cargando sesión...")
        driver.get(base_domain_url)
        time.sleep(3)
        if not load_cookies(driver, cookie_path):
            update_callback(f"⚠️ Ruta de cookies inválida o no encontrada.")
            driver.quit()
            return

        driver.get("https://agendaweb.suramericana.com/agenda/internet/internet-menu.do")
        time.sleep(3)
        limpiar_popups(driver, update_callback)

        update_callback("Ingresando a Asignación de Citas...")
        driver.get(cita_url)
        time.sleep(4)
        limpiar_popups(driver, update_callback)

        count = 0
        fallos_consecutivos = 0 
        last_seen_citas = set() 
        is_baseline_scan = True 
        stop_after_auto_action = False
        backend_outage_streak = 0
        backend_outage_popup_shown = False

        last_filters_signature = None

        def handle_backend_outage_if_needed():
            nonlocal backend_outage_streak, backend_outage_popup_shown

            if not detect_backend_outage_error(driver):
                if backend_outage_streak > 0:
                    update_callback("✅ Conexión con SURA restablecida. Continuando monitoreo normal.")
                    if gui_callback:
                        gui_callback("show_info_popup", "SURA volvió a responder correctamente. El monitoreo continúa.")
                backend_outage_streak = 0
                backend_outage_popup_shown = False
                return False

            backend_outage_streak += 1
            wait_seconds = min(300, 60 + (backend_outage_streak - 1) * 60)
            update_callback(
                "⚠️ SURA reporta falla temporal de backend (WebLogic/Oracle). "
                f"Reintento automático en {wait_seconds}s (intento {backend_outage_streak})."
            )
            if gui_callback and (not backend_outage_popup_shown):
                backend_outage_popup_shown = True
                gui_callback(
                    "show_warning_popup",
                    "SURA devolvió un error interno del servidor (no es tu configuración/cookies).\n\n"
                    "El bot esperará y reintentará automáticamente."
                )

            while wait_seconds > 0 and (not stop_event.is_set()):
                time.sleep(1)
                wait_seconds -= 1

            try:
                # Método de recuperación habitual: forzar retorno a Asignación sin disparar consulta vacía.
                ir_a_perfil_con_clic(driver, update_callback, fast_mode=True)
                ir_a_asignacion_con_clic(driver, update_callback, fast_mode=True)
                driver.get(cita_url)
                time.sleep(2)
                limpiar_popups(driver, update_callback)
            except Exception:
                pass
            return True

        while not stop_event.is_set():

            if handle_backend_outage_if_needed():
                continue
            
            # --- DETECCIÓN DE CADUCIDAD POR URL ---
            current_url = driver.current_url.lower()
            if "login" in current_url or "ingreso" in current_url or len(driver.find_elements(By.NAME, "j_username")) > 0:
                update_callback("❌ ¡ALERTA! SURA HA CERRADO TU SESIÓN O TE BLOQUEÓ.")
                if alert_block and gui_callback: 
                    gui_callback("show_error_popup", "Tu sesión ha expirado o SURA te ha bloqueado el acceso temporalmente.\n\nSaca unas nuevas cookies desde Chrome, guárdalas en tu archivo .txt y vuelve a iniciar el Bucle.")
                stop_event.set()
                break

            # PROCESAR COLA DE ACCIONES PENDIENTES
            if not action_queue.empty():
                task = action_queue.get()
                update_callback(f"⚙️ Pausando radar para ejecutar acción: {task['type']}")
                try:
                    if task['type'] == 'sync_profile':
                        ir_a_perfil_con_clic(driver, update_callback)
                        extraer_perfil_silencioso(driver, update_callback, gui_callback)
                        ir_a_asignacion_con_clic(driver, update_callback)
                        
                    elif task['type'] == 'agendar':
                        ag_result = intentar_agendamiento_con_reintentos(driver, task['data'], update_callback, max_attempts=2)
                        agendo = bool(ag_result.get("ok"))
                        confirmado_en_perfil = False
                        if gui_callback:
                            if agendo:
                                confirmado_en_perfil = verificar_agendamiento_en_perfil(driver, task['data'], update_callback, gui_callback, checks=2)
                                if confirmado_en_perfil:
                                    gui_callback("show_info_popup", "Cita agendada exitosamente (confirmada en Consulta).")
                                else:
                                    gui_callback("show_warning_popup", "Se hizo click para agendar, pero aún no aparece confirmada en Consulta.")
                            else:
                                if ag_result.get("reason") == "not_available":
                                    gui_callback("show_warning_popup", "No se agendó: la cita dejó de estar disponible.")
                                else:
                                    gui_callback("show_warning_popup", "No se agendó la cita. Revisa el navegador o vuelve a intentarlo.")
                        time.sleep(3) 
                        try:
                            ir_a_asignacion_con_clic(driver, update_callback, fast_mode=True)
                        except Exception:
                            pass

                        # Si veníamos en auto-programar + continuar, migrar a auto-reprogramar tras primer agendamiento confirmado.
                        auto_meta = task.get('auto_meta') if isinstance(task, dict) else {}
                        if confirmado_en_perfil and isinstance(auto_meta, dict):
                            came_from_programar = bool(auto_meta.get("from_auto_programar", False))
                            continue_mode = bool(auto_meta.get("continue_mode", False))
                            already_reprogram = bool(auto_meta.get("from_auto_reprogram", False))
                            if came_from_programar and continue_mode and (not already_reprogram):
                                update_callback("🔁 Auto-modo: cambiando de Programar a Reprogramar para seguir buscando horario mejor.")
                                if gui_callback:
                                    gui_callback("switch_to_auto_reprogram", None)

                        if stop_after_auto_action:
                            update_callback("🛑 Motor detenido tras completar acción automática (configuración post-acción).")
                            if gui_callback:
                                gui_callback("clear_auto_modes", None)
                            stop_event.set()

                    elif task['type'] in ['cancelar', 'reprogramar']:
                        ir_a_perfil_con_clic(driver, update_callback)
                        js = task['data'].get('js_cancelar') if task['type'] == 'cancelar' else task['data'].get('js_reprogramar')
                        driver.execute_script(js.replace("javascript:", ""))
                        confirmado = confirmar_accion_con_regex(driver, update_callback)
                        if confirmado:
                            update_callback(f"✅ Acción de {task['type']} confirmada y enviada exitosamente.")
                            time.sleep(3)
                            ir_a_perfil_con_clic(driver, update_callback)
                            extraer_perfil_silencioso(driver, update_callback, gui_callback)
                            perfil_actual = load_json("perfil_cache") or []
                            if task['type'] == 'cancelar':
                                if not perfil_actual:
                                    if gui_callback:
                                        gui_callback("show_info_popup", "Cita cancelada exitosamente.")
                                else:
                                    if gui_callback:
                                        gui_callback("show_warning_popup", "Se confirmó la cancelación, pero el perfil aún muestra citas vigentes.")
                            elif task['type'] == 'reprogramar':
                                if gui_callback:
                                    gui_callback("show_info_popup", "Reprogramación enviada correctamente.")
                        else:
                            update_callback(f"⚠️ Acción de {task['type']} lanzada, pero sin confirmar clic en 'sí/aceptar'.")
                            if gui_callback:
                                gui_callback("show_warning_popup", f"No se pudo confirmar la acción de {task['type']}. No se completó el cambio.")
                        time.sleep(3)
                        ir_a_asignacion_con_clic(driver, update_callback)
                except Exception as e:
                    update_callback(f"❌ Error ejecutando acción: {e}")
                
                continue 

            # FLUJO NORMAL DE ESCANEO
            update_callback(f"\n--- [Ciclo {count+1}] Revisando disponibilidad ---")
            
            # 🔄 PROTOCOLO DE RECARGA (Tu petición principal)
            if count > 0:
                update_callback("🔄 Recargando sesión por menú (sin F5): Consulta/Cancelación -> Asignación...")
                try:
                    ir_a_perfil_con_clic(driver, update_callback, fast_mode=True)
                    extraer_perfil_silencioso(driver, update_callback, gui_callback)
                    ir_a_asignacion_con_clic(driver, update_callback, fast_mode=True)
                    wait_for_results_table(driver, timeout=1.2)
                except Exception as e:
                    update_callback(f"⚠️ Falló recarga por menú, uso fallback F5: {e}")
                    try:
                        driver.refresh()
                        time.sleep(2)
                        extraer_perfil_silencioso(driver, update_callback, gui_callback)
                    except Exception as e2:
                        update_callback(f"⚠️ También falló fallback F5: {e2}")

            # Segunda barrera: si aparece el error justo antes de consultar disponibilidad,
            # lo manejamos aquí mismo sin lanzar consultas sobre una vista rota.
            if handle_backend_outage_if_needed():
                continue

            citas_encontradas = []
            current_seen_citas = set()
            active_interval = resolve_interval_value(interval)
            tiempo_espera_actual = active_interval
            scan_successful = False
            scan_started_at = time.time()
            opciones_totales = 0
            opciones_analizadas = 0
            pre_dynamic_filters = {}
            pre_sura_pref_enabled = False
            pre_sura_pref_date = ""

            if callable(get_filters_callback):
                try:
                    pre_dynamic_filters = get_filters_callback() or {}
                except Exception:
                    pre_dynamic_filters = {}

            if isinstance(pre_dynamic_filters, dict):
                pre_sura_pref_enabled = bool(pre_dynamic_filters.get("sura_pref_enabled", False))
                pre_sura_pref_date = (pre_dynamic_filters.get("sura_pref_date") or "").strip()

            limpiar_popups(driver, update_callback)

            try:
                btn_previa = driver.find_elements(By.XPATH, "//button[contains(@onclick, 'consultarDisponibilidadCitas()')]")
                if btn_previa:
                    consultar_disponibilidad_con_preferencia_fecha(
                        driver,
                        update_callback,
                        fecha_preferida=pre_sura_pref_date,
                        usar_preferencia=pre_sura_pref_enabled,
                    )
                    wait_for_results_table(driver, timeout=2.0)
            except Exception: 
                pass

            limpiar_popups(driver, update_callback)

            try:
                select_element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "listaDisponibilidad")))
                select = Select(select_element)
                total_opciones = len(select.options)
                opciones_totales = max(0, total_opciones - 1)

                if total_opciones <= 1: 
                    raise ValueError("Menú vacío.")
                fallos_consecutivos = 0 
                max_opciones = total_opciones
                
                active_date_start = date_start
                active_date_end = date_end
                active_time_start = time_start
                active_time_end = time_end
                dynamic_filters = {}

                if callable(get_filters_callback):
                    try:
                        dynamic_filters = get_filters_callback() or {}
                        active_date_start = (dynamic_filters.get("date_start") or "").strip()
                        active_date_end = (dynamic_filters.get("date_end") or "").strip()
                        active_time_start = (dynamic_filters.get("time_start") or "").strip()
                        active_time_end = (dynamic_filters.get("time_end") or "").strip()
                    except Exception:
                        pass

                active_interval = resolve_interval_value(interval, dynamic_filters)

                auto_programar = bool(dynamic_filters.get("auto_programar", dynamic_filters.get("auto_schedule", False))) if isinstance(dynamic_filters, dict) else False
                auto_reprogram = bool(dynamic_filters.get("auto_reprogram", False)) if isinstance(dynamic_filters, dict) else False
                auto_priority = (dynamic_filters.get("auto_priority") or "Más temprana (tope)") if isinstance(dynamic_filters, dict) else "Más temprana (tope)"
                auto_post_action = (dynamic_filters.get("auto_post_action") or "Detener tras ejecutar") if isinstance(dynamic_filters, dict) else "Detener tras ejecutar"
                auto_target_date_raw = (dynamic_filters.get("auto_target_date") or "").strip() if isinstance(dynamic_filters, dict) else ""
                auto_target_date = parse_date(auto_target_date_raw) if auto_target_date_raw else None
                auto_target_time_raw = (dynamic_filters.get("auto_target_time") or "").strip() if isinstance(dynamic_filters, dict) else ""
                auto_target_time = parse_time(auto_target_time_raw) if auto_target_time_raw else None
                sura_pref_enabled = bool(dynamic_filters.get("sura_pref_enabled", False)) if isinstance(dynamic_filters, dict) else False
                sura_pref_date_raw = (dynamic_filters.get("sura_pref_date") or "").strip() if isinstance(dynamic_filters, dict) else ""

                d_start = parse_date(active_date_start) if active_date_start else None
                d_end = parse_date(active_date_end) if active_date_end else None
                t_start = parse_time(active_time_start) if active_time_start else None
                t_end = parse_time(active_time_end) if active_time_end else None

                filters_signature = (
                    active_date_start,
                    active_date_end,
                    active_time_start,
                    active_time_end,
                    auto_post_action,
                    auto_target_date_raw,
                    auto_target_time_raw,
                    sura_pref_enabled,
                    sura_pref_date_raw,
                )
                if filters_signature != last_filters_signature:
                    filtro_log = "📋 Filtros activos: "
                    if d_start or d_end:
                        filtro_log += f"Fechas {d_start or 'desde siempre'} → {d_end or 'hasta siempre'} | "
                    if t_start or t_end:
                        filtro_log += f"Horas {t_start or 'desde 00:00'} → {t_end or 'hasta 23:59'}"
                    else:
                        if not (d_start or d_end):
                            filtro_log += "Sin filtros (buscando todas las citas)"
                    if auto_target_date:
                        filtro_log += f" | Día objetivo {auto_target_date.isoformat()}"
                    if auto_target_time:
                        filtro_log += f" | Objetivo {auto_target_time.strftime('%H:%M')}"
                    if sura_pref_enabled:
                        filtro_log += " | Preferencia consulta SURA activa"
                        if sura_pref_date_raw:
                            filtro_log += f" ({sura_pref_date_raw})"
                    update_callback(filtro_log)
                    last_filters_signature = filters_signature

                per_option_wait = 1.2

                for idx in range(1, max_opciones):
                    try:
                        select_element = driver.find_element(By.NAME, "listaDisponibilidad")
                        select = Select(select_element)
                        if idx >= len(select.options):
                            continue
                        option = select.options[idx]
                        
                        doc_parts = option.text.split(" - ")
                        doctor_name = doc_parts[0].strip() if len(doc_parts) > 0 else "Médico"
                        fecha_disp = doc_parts[1].strip() if len(doc_parts) > 1 else ""

                        if fecha_disp:
                            sura_date = parse_date(fecha_disp) or extract_first_date_from_text(fecha_disp)
                            if sura_date:
                                if d_start and sura_date < d_start: 
                                    continue
                                if d_end and sura_date > d_end: 
                                    continue

                        opciones_analizadas += 1
                        if opciones_analizadas == 1 or opciones_analizadas % 4 == 0:
                            update_callback(f"🔎 Evaluando: {doctor_name[:15]}... ({fecha_disp})")
                        select.select_by_index(idx)
                        
                        try: 
                            driver.execute_script("if(typeof consultarCitasDisponibles === 'function') consultarCitasDisponibles();")
                        except: 
                            pass
                        wait_for_results_table(driver, timeout=per_option_wait)
                        limpiar_popups(driver, update_callback) 
                        
                        for row_idx, fila in enumerate(driver.find_elements(By.CSS_SELECTOR, "table.control_citas tbody tr")):
                            celdas = fila.find_elements(By.TAG_NAME, "td")
                            if len(celdas) >= 3:
                                hora = celdas[0].text.strip()
                                lugar = celdas[1].text.strip()
                                
                                if "Horas (" in hora: 
                                    continue
                                hora_obj = parse_time(hora)
                                if hora_obj:
                                    if t_start and hora_obj < t_start: 
                                        continue
                                    if t_end and hora_obj > t_end: 
                                        continue
                                
                                js_action = ""
                                try:
                                    btn = fila.find_elements(By.XPATH, ".//button[contains(@onclick, 'seleccionarCita')]")
                                    if btn: 
                                        js_action = btn[0].get_attribute("onclick")
                                    else:
                                        enlace = fila.find_elements(By.XPATH, ".//a[contains(@href, 'seleccionarCita')]")
                                        if enlace: 
                                            js_action = enlace[0].get_attribute("href")
                                except Exception: 
                                    pass
                                
                                if hora and lugar:
                                    citas_encontradas.append({
                                        'id_internal': f"{idx}_{row_idx}", 'fecha': fecha_disp, 'hora': hora,
                                        'doctor': doctor_name, 'lugar': lugar, 'js_action': js_action
                                    })
                    except Exception: 
                        continue

                scan_successful = True 

                save_json("citas_cache", citas_encontradas)
                if gui_callback: 
                    gui_callback("update_table", citas_encontradas)

                scan_duration = time.time() - scan_started_at
                update_callback(
                    f"⏱️ Escaneo completado en {scan_duration:.1f}s | Opciones analizadas: {opciones_analizadas}/{opciones_totales} | Citas filtradas: {len(citas_encontradas)}"
                )

                if is_baseline_scan:
                    for c in citas_encontradas:
                        last_seen_citas.add(f"{c['fecha']}_{c['hora']}_{c['doctor']}")
                    update_callback(f"Memoria Base Establecida: {len(citas_encontradas)} citas iniciales.")
                    is_baseline_scan = False
                    
                    action_queue.put({'type': 'sync_profile'})
                else:
                    nuevas_citas = []
                    for c in citas_encontradas:
                        c_id = f"{c['fecha']}_{c['hora']}_{c['doctor']}"
                        current_seen_citas.add(c_id)
                        if c_id not in last_seen_citas: 
                            nuevas_citas.append(c)

                    if nuevas_citas:
                        update_callback(f"¡ALERTA! Se agregaron {len(nuevas_citas)} CITAS NUEVAS.")
                        if use_sound: 
                            play_alert_sound()

                        if auto_programar or auto_reprogram:
                            perfil_fecha_actual = get_profile_current_date_from_cache()
                            perfil_hora_actual = get_profile_current_time_from_cache()
                            cita_objetivo = seleccionar_cita_hacia_objetivo(
                                nuevas_citas,
                                auto_priority,
                                target_date=auto_target_date,
                                target_time=auto_target_time,
                                current_date=perfil_fecha_actual,
                                current_time=perfil_hora_actual,
                            )
                            if not cita_objetivo and not auto_target_date and not auto_target_time:
                                cita_objetivo = seleccionar_cita_por_prioridad(nuevas_citas, auto_priority)

                            if cita_objetivo and (not cita_dentro_de_filtros(cita_objetivo, d_start, d_end, t_start, t_end)):
                                update_callback("⚠️ Se descartó cita candidata por quedar fuera de filtros tras validación final.")
                                cita_objetivo = None

                            if cita_objetivo:
                                if auto_reprogram:
                                    perfil_objetivo = get_profile_for_reprogram_from_cache()
                                    if perfil_objetivo:
                                        action_queue.put({'type': 'reprogramar', 'data': perfil_objetivo})
                                        update_callback("🤖 Reprogramar automáticamente: reprogramación encolada.")
                                    else:
                                        update_callback("⚠️ Reprogramar automáticamente activo, pero no encontré cita vigente en perfil_cache.")

                                auto_meta = {
                                    "from_auto_programar": bool(auto_programar),
                                    "from_auto_reprogram": bool(auto_reprogram),
                                    "continue_mode": ("detener" not in str(auto_post_action).lower()),
                                }
                                action_queue.put({'type': 'agendar', 'data': cita_objetivo, 'auto_meta': auto_meta})
                                update_callback(
                                    f"🤖 {'Reprogramar' if auto_reprogram else 'Programar'} automáticamente ({auto_priority}): encolada {cita_objetivo.get('fecha', '')} {cita_objetivo.get('hora', '')} - {cita_objetivo.get('doctor', '')}"
                                )

                                if not auto_target_date and not auto_target_time:
                                    update_callback("🛑 Sin día/hora objetivo: se detendrá tras ejecutar esta automatización.")
                                    stop_after_auto_action = True
                                elif "detener" in str(auto_post_action).lower():
                                    update_callback("🛑 Opción post-acción en 'Detener': se detendrá tras esta automatización.")
                                    stop_after_auto_action = True
                            else:
                                if auto_target_date or auto_target_time:
                                    objetivo_dia = auto_target_date.isoformat() if auto_target_date else "cualquier día"
                                    objetivo_hora = auto_target_time.strftime('%H:%M') if auto_target_time else "cualquier hora"
                                    update_callback(f"ℹ️ No hay citas nuevas que mejoren hacia objetivo {objetivo_dia} {objetivo_hora}.")

                        if show_popup_ui and gui_callback: 
                            gui_callback("show_popup", nuevas_citas)
                    elif citas_encontradas:
                        update_callback(f"No hay citas nuevas. Se mantienen {len(citas_encontradas)} espacios.")
                    else:
                        update_callback("Ninguna cita pasó tus filtros en este ciclo.")

                    last_seen_citas = current_seen_citas 

            except (TimeoutException, ValueError) as ex:
                fallos_consecutivos += 1
                update_callback(f"⚠️ Regenerando sesión principal... (Fallo {fallos_consecutivos}/3)")
                
                if fallos_consecutivos >= 3:
                    update_callback("🛑 BLOQUEO DETECTADO: Imposible leer la tabla tras 3 intentos.")
                    if alert_block and gui_callback: 
                        gui_callback("show_error_popup", "El bot falló 3 veces seguidas al intentar ver los médicos.\n\nEs altamente probable que SURA te haya cerrado la sesión o la página esté caída. \n\nPor favor revisa, actualiza tus cookies y reinicia el sistema.")
                    stop_event.set()
                    break

                try:
                    limpiar_popups(driver, update_callback)
                    ir_a_perfil_con_clic(driver, update_callback)
                    ir_a_asignacion_con_clic(driver, update_callback)
                except Exception: 
                    pass
                tiempo_espera_actual = 2
                
            if single_run and scan_successful:
                update_callback("✅ Consulta Única Finalizada con Éxito.")
                break

            if not single_run:
                if scan_successful:
                    tiempo_espera_actual = active_interval
                if tiempo_espera_actual > 5: 
                    update_callback(f"Esperando {tiempo_espera_actual} segundos...")
                while tiempo_espera_actual > 0:
                    if stop_event.is_set(): 
                        break
                    time.sleep(1)
                    tiempo_espera_actual -= 1
            count += 1

        if driver: 
            driver.quit()
        if gui_callback: 
            gui_callback("set_driver", None)
        update_callback("Sistema Detenido.")
    except Exception as e:
        if update_callback: 
            update_callback(f"Error Fatal:\n{str(e)}")
        if driver: 
            driver.quit()

# ==========================================
# INTERFAZ GRÁFICA (GUI)
# ==========================================
class AlerterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SURA - Gestor Inteligente de Citas")
        self.root.geometry("1200x900")

        self.bg_color = "#f4f7f6"
        self.accent_color = "#0056b3"
        self.danger_color = "#dc3545"
        self.warn_color = "#ffc107"
        self.text_color = "#333333"

        self.style = ttk.Style()
        if "clam" in self.style.theme_names(): 
            self.style.theme_use("clam")

        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("TLabel", background=self.bg_color, font=("Segoe UI", 10), foreground=self.text_color)
        self.style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"), foreground=self.accent_color, background=self.bg_color)
        self.style.configure("TCheckbutton", background=self.bg_color, font=("Segoe UI", 10))
        self.style.configure("TLabelframe", background=self.bg_color, font=("Segoe UI", 10, "bold"), foreground=self.accent_color)
        self.style.configure("TLabelframe.Label", background=self.bg_color, font=("Segoe UI", 11, "bold"), foreground=self.accent_color)
        
        self.style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), padding=6)
        self.style.configure("Danger.TButton", font=("Segoe UI", 10, "bold"))
        self.style.configure("Warn.TButton", font=("Segoe UI", 10, "bold"))

        self.style.configure("Treeview", font=("Segoe UI", 9), rowheight=26, borderwidth=0)
        self.style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background="#e9ecef", foreground=self.text_color)

        self.root.configure(bg=self.bg_color)
        self.stop_event = threading.Event()
        self.is_running = False
        self.action_queue = queue.Queue()
        self.filters_lock = threading.Lock()
        self.current_filters = {}
        
        self.all_citas = []
        self.citas_map = {}
        self.perfil_map = {}
        self.monitors = detect_windows_monitors_fallback()
        self.monitor_labels = [item.get("label", f"Monitor {idx}") for idx, item in enumerate(self.monitors, start=1)]

        # Variables de Config
        self.cookie_var = tk.StringVar(value=get_default_cookies_path())
        self.date_start_var = tk.StringVar()
        self.date_end_var = tk.StringVar()
        self.time_start_var = tk.StringVar()
        self.time_end_var = tk.StringVar()
        self.interval_random_var = tk.BooleanVar(value=False)
        self.interval_min_var = tk.StringVar(value="60")
        self.interval_max_var = tk.StringVar(value="90")
        self.monitor_var = tk.StringVar(value=self.monitor_labels[0] if self.monitor_labels else "Monitor 1")
        self.headless_var = tk.BooleanVar(value=False)
        self.sound_var = tk.BooleanVar(value=True)
        self.popup_var = tk.BooleanVar(value=True)
        self.alert_block_var = tk.BooleanVar(value=True) 
        self.autosave_var = tk.BooleanVar(value=False)
        self.startup_var = tk.BooleanVar(value=False)
        self.auto_monitor_var = tk.BooleanVar(value=False)
        self.auto_programar_var = tk.BooleanVar(value=False)
        self.auto_reprogram_var = tk.BooleanVar(value=False)
        self.auto_priority_var = tk.StringVar(value="Más temprana (tope)")
        self.auto_post_action_var = tk.StringVar(value="Detener tras ejecutar")
        self.auto_target_date_var = tk.StringVar(value="")
        self.auto_target_time_var = tk.StringVar(value="")
        self.sura_pref_enabled_var = tk.BooleanVar(value=False)
        self.sura_pref_date_var = tk.StringVar(value="")
        self._auto_mode_lock = False
        self._priority_hint_shown = False

        self._build_gui()
        self._load_config_and_cache()
        self._setup_auto_save_triggers()
        self._maybe_autostart_monitoring()

    def set_current_filters(self, d_start, d_end, t_start, t_end):
        with self.filters_lock:
            self.current_filters = {
                'date_start': (d_start or '').strip(),
                'date_end': (d_end or '').strip(),
                'time_start': (t_start or '').strip(),
                'time_end': (t_end or '').strip()
            }

    def get_current_filters(self):
        with self.filters_lock:
            data = dict(self.current_filters)
            interval_min, interval_max, use_random = self._get_interval_settings()
            data["interval"] = interval_min
            data["interval_min"] = interval_min
            data["interval_max"] = interval_max
            data["interval_random"] = use_random
            data["auto_programar"] = bool(self.auto_programar_var.get())
            data["auto_reprogram"] = bool(self.auto_reprogram_var.get())
            data["auto_priority"] = str(self.auto_priority_var.get() or "Más temprana (tope)")
            data["auto_post_action"] = str(self.auto_post_action_var.get() or "Detener tras ejecutar")
            data["auto_target_date"] = str(self.auto_target_date_var.get() or "").strip()
            data["auto_target_time"] = str(self.auto_target_time_var.get() or "").strip()
            data["sura_pref_enabled"] = bool(self.sura_pref_enabled_var.get())
            data["sura_pref_date"] = str(self.sura_pref_date_var.get() or "").strip()
            return data

    def _get_interval_settings(self):
        """Normaliza intervalo de escaneo para modo fijo o rango."""
        def _to_int(value):
            try:
                return int(str(value).strip())
            except Exception:
                return None

        min_v = _to_int(self.interval_min_var.get())
        max_v = _to_int(self.interval_max_var.get())

        if min_v is None:
            min_v = 60
        if max_v is None:
            max_v = min_v

        min_v = max(15, min_v)
        max_v = max(15, max_v)
        if max_v < min_v:
            max_v = min_v

        use_random = bool(self.interval_random_var.get())
        return min_v, max_v, use_random

    def _get_runtime_interval(self):
        min_v, max_v, use_random = self._get_interval_settings()
        if use_random and max_v >= min_v:
            return random.randint(min_v, max_v)
        return min_v

    def _normalize_interval_inputs(self):
        min_v, max_v, _ = self._get_interval_settings()
        self.interval_min_var.set(str(min_v))
        self.interval_max_var.set(str(max_v))

    def _update_interval_controls_state(self):
        is_random = bool(self.interval_random_var.get())
        if hasattr(self, "interval_max_spin"):
            self.interval_max_spin.configure(state="normal" if is_random else "disabled")
        if hasattr(self, "interval_max_label"):
            self.interval_max_label.configure(text="Intervalo Máximo (segs):" if is_random else "Intervalo Máximo (segs, inactivo):")

    def _on_interval_mode_changed(self):
        self._update_interval_controls_state()
        self.save_config()

    def _update_sura_pref_controls_state(self):
        enabled = bool(self.sura_pref_enabled_var.get())
        if hasattr(self, "sura_pref_date_entry"):
            self.sura_pref_date_entry.configure(state="normal" if enabled else "disabled")

    def _monitor_id_by_label(self, label):
        target = normalize_text(label)
        for item in self.monitors:
            if normalize_text(item.get("label")) == target:
                return int(item.get("id", 1))
        if "izquierda" in target and self.monitors:
            return int(sorted(self.monitors, key=lambda item: (int(item.get("left", 0)), int(item.get("top", 0))))[0].get("id", 1))
        if "derecha" in target and self.monitors:
            return int(sorted(self.monitors, key=lambda item: (-int(item.get("left", 0)), int(item.get("top", 0))))[0].get("id", 1))
        return int(self.monitors[0].get("id", 1)) if self.monitors else 1

    def _monitor_by_id(self, monitor_id):
        for item in self.monitors:
            if int(item.get("id", -1)) == int(monitor_id):
                return item
        return self.monitors[0] if self.monitors else None

    def _selected_monitor(self):
        return self._monitor_by_id(self._monitor_id_by_label(self.monitor_var.get()))

    def _normalize_monitor_selection(self, config):
        monitor_id = config.get("monitor_id")
        if monitor_id is not None:
            monitor = self._monitor_by_id(monitor_id)
            if monitor:
                self.monitor_var.set(monitor.get("label", self.monitor_var.get()))
                return

        monitor_label = str(config.get("monitor", "") or "").strip()
        if monitor_label:
            monitor_id = self._monitor_id_by_label(monitor_label)
            monitor = self._monitor_by_id(monitor_id)
            if monitor:
                self.monitor_var.set(monitor.get("label", self.monitor_var.get()))

    def _monitor_combo_values(self):
        return [item.get("label", f"Monitor {idx}") for idx, item in enumerate(self.monitors, start=1)]

    def select_cookie_path(self):
        path = filedialog.askopenfilename(title="Seleccionar archivo de cookies", filetypes=[("Archivos de Texto", "*.txt"), ("Todos los archivos", "*.*")])
        if path:
            self.cookie_var.set(path)
            self.save_config()

    def _load_config_and_cache(self):
        data_dir = get_data_dir()
        self.log(f"📁 Carpeta de datos activa: {data_dir}")
        config = load_config()
        if config:
            configured_cookie = config.get("cookie_path", self.cookie_var.get())
            resolved_cookie = resolve_portable_cookie_path(configured_cookie)
            if not os.path.isfile(resolved_cookie):
                resolved_cookie = get_default_cookies_path()
            self.cookie_var.set(resolved_cookie)
            self.date_start_var.set(config.get("date_start", ""))
            self.date_end_var.set(config.get("date_end", ""))
            self.time_start_var.set(config.get("time_start", ""))
            self.time_end_var.set(config.get("time_end", ""))
            legacy_interval = config.get("interval", 60)
            self.interval_random_var.set(config.get("interval_random", False))
            self.interval_min_var.set(str(config.get("interval_min", legacy_interval)))
            self.interval_max_var.set(str(config.get("interval_max", config.get("interval_min", legacy_interval))))
            self.monitor_var.set(config.get("monitor", self.monitor_labels[0] if self.monitor_labels else "Monitor 1"))
            self.headless_var.set(config.get("headless", False))
            self.sound_var.set(config.get("sound", True))
            self.popup_var.set(config.get("popup", True))
            self.alert_block_var.set(config.get("alert_block", True))
            self.autosave_var.set(config.get("autosave", False))
            self.startup_var.set(config.get("startup", False))
            self.auto_monitor_var.set(config.get("auto_monitor", False))
            self.auto_programar_var.set(config.get("auto_programar", config.get("auto_schedule", False)))
            self.auto_reprogram_var.set(config.get("auto_reprogram", False))
            self.auto_priority_var.set(config.get("auto_priority", "Más temprana (tope)"))
            self.auto_post_action_var.set(config.get("auto_post_action", "Detener tras ejecutar"))
            self.auto_target_date_var.set(config.get("auto_target_date", ""))
            self.auto_target_time_var.set(config.get("auto_target_time", ""))
            self.sura_pref_enabled_var.set(config.get("sura_pref_enabled", False))
            self.sura_pref_date_var.set(config.get("sura_pref_date", ""))
            self._normalize_monitor_selection(config)

            try:
                set_startup(bool(self.startup_var.get()))
            except Exception:
                pass

        self._normalize_interval_inputs()
        self._update_interval_controls_state()
        self._update_sura_pref_controls_state()

        self.set_current_filters(
            self.date_start_var.get(),
            self.date_end_var.get(),
            self.time_start_var.get(),
            self.time_end_var.get()
        )

        citas = load_json("citas_cache")
        self.update_table(citas if citas else [])
        perfil = load_json("perfil_cache")
        self.update_profile(perfil if perfil else [])
        self.log("Sistema Listo. Configuraciones y datos previos cargados.")

    def save_config(self, *args):
        interval_min, interval_max, interval_random = self._get_interval_settings()
        cfg = {
            "cookie_path": self.cookie_var.get(),
            "date_start": self.date_start_var.get(), "date_end": self.date_end_var.get(),
            "time_start": self.time_start_var.get(), "time_end": self.time_end_var.get(),
            "interval": interval_min,
            "interval_min": interval_min,
            "interval_max": interval_max,
            "interval_random": interval_random,
            "monitor": self.monitor_var.get(),
            "monitor_id": self._monitor_id_by_label(self.monitor_var.get()),
            "headless": self.headless_var.get(), "sound": self.sound_var.get(),
            "popup": self.popup_var.get(), "alert_block": self.alert_block_var.get(),
            "autosave": self.autosave_var.get(), "startup": self.startup_var.get(),
            "auto_monitor": self.auto_monitor_var.get(),
            "auto_programar": self.auto_programar_var.get(),
            "auto_reprogram": self.auto_reprogram_var.get(),
            "auto_priority": self.auto_priority_var.get(),
            "auto_post_action": self.auto_post_action_var.get(),
            "auto_target_date": self.auto_target_date_var.get().strip(),
            "auto_target_time": self.auto_target_time_var.get().strip(),
            "sura_pref_enabled": self.sura_pref_enabled_var.get(),
            "sura_pref_date": self.sura_pref_date_var.get().strip(),
        }
        save_json("config", cfg)

    def on_startup_toggle(self):
        set_startup(self.startup_var.get())
        self.save_config()

    def _setup_auto_save_triggers(self):
        vars_to_trace = [self.date_start_var, self.date_end_var, self.time_start_var, self.time_end_var, self.cookie_var]
        for v in vars_to_trace: 
            v.trace_add('write', self.save_config)
        self.interval_min_var.trace_add('write', self.save_config)
        self.interval_max_var.trace_add('write', self.save_config)
        self.interval_random_var.trace_add('write', lambda *args: self._on_interval_mode_changed())
        self.monitor_var.trace_add('write', self.save_config)
        
        checkboxes = [
            self.headless_var, self.sound_var, self.popup_var, self.alert_block_var,
            self.autosave_var, self.auto_monitor_var, self.auto_programar_var, self.auto_reprogram_var
        ]
        for cb in checkboxes: 
            cb.trace_add('write', self.save_config)
        self.startup_var.trace_add('write', lambda *args: self.on_startup_toggle())
        self.auto_priority_var.trace_add('write', self.save_config)
        self.auto_post_action_var.trace_add('write', self.save_config)
        self.auto_target_date_var.trace_add('write', self.save_config)
        self.auto_target_time_var.trace_add('write', self.save_config)
        self.sura_pref_date_var.trace_add('write', self.save_config)
        self.sura_pref_enabled_var.trace_add('write', lambda *args: [self._update_sura_pref_controls_state(), self.save_config()])
        self.auto_programar_var.trace_add('write', lambda *args: self._sync_auto_mode("programar"))
        self.auto_reprogram_var.trace_add('write', lambda *args: self._sync_auto_mode("reprogramar"))

    def _sync_auto_mode(self, changed_mode):
        if self._auto_mode_lock:
            return
        try:
            self._auto_mode_lock = True
            if changed_mode == "programar" and self.auto_programar_var.get():
                self.auto_reprogram_var.set(False)
            elif changed_mode == "reprogramar" and self.auto_reprogram_var.get():
                self.auto_programar_var.set(False)
            self.save_config()
        finally:
            self._auto_mode_lock = False

    def _on_priority_mode_changed(self, event=None):
        if self.auto_priority_var.get() and not self._priority_hint_shown:
            self._priority_hint_shown = True
            messagebox.showinfo(
                "Prioridad de auto-agendamiento",
                "Recuerda ser específico con el rango de hora para mejores resultados.\n\n"
                "Este modo solo decide si tomar la más temprana (tope) o más tardía (fondo)."
            )

    def _maybe_autostart_monitoring(self):
        if self.auto_monitor_var.get() and not self.is_running:
            self.log("🤖 Auto-inicio de monitoreo activado: iniciando bucle automáticamente...")
            self.root.after(1200, lambda: self.start_monitoring(single=False))

    def _show_themed_popup(self, title, message, kind="info"):
        colors = {
            "info": {"bg": "#1f7a1f", "accent": "#e8f5e9", "button": "#ffffff", "button_fg": "#1f7a1f"},
            "warning": {"bg": "#b7791f", "accent": "#fff8e1", "button": "#ffffff", "button_fg": "#b7791f"},
            "error": {"bg": "#b91c1c", "accent": "#fee2e2", "button": "#ffffff", "button_fg": "#b91c1c"},
        }
        theme = colors.get(kind, colors["info"])

        pop = tk.Toplevel(self.root)
        pop.title(title)
        pop.configure(bg=theme["bg"])
        pop.attributes("-topmost", True)
        pop.resizable(False, False)

        width, height = 520, 250
        monitor = self._selected_monitor() or {}
        screen_w = int(monitor.get("width", self.root.winfo_screenwidth()))
        screen_h = int(monitor.get("height", self.root.winfo_screenheight()))
        monitor_left = int(monitor.get("left", 0))
        monitor_top = int(monitor.get("top", 0))
        x = monitor_left + (screen_w // 2) - (width // 2)
        y = monitor_top + (screen_h // 2) - (height // 2)
        pop.geometry(f"{width}x{height}+{x}+{y}")

        container = tk.Frame(pop, bg=theme["bg"], padx=18, pady=16)
        container.pack(fill=tk.BOTH, expand=True)

        icon_text = "✅" if kind == "info" else ("⚠️" if kind == "warning" else "⛔")
        ttk.Label(container, text=f"{icon_text} {title}", font=("Segoe UI", 18, "bold"), background=theme["bg"], foreground="white").pack(anchor=tk.W)

        body = tk.Frame(container, bg=theme["accent"], padx=14, pady=14)
        body.pack(fill=tk.BOTH, expand=True, pady=(12, 14))

        tk.Label(
            body,
            text=message,
            justify=tk.LEFT,
            wraplength=470,
            bg=theme["accent"],
            fg="#1f2937",
            font=("Segoe UI", 11),
        ).pack(anchor=tk.W, fill=tk.BOTH, expand=True)

        footer = tk.Frame(container, bg=theme["bg"])
        footer.pack(fill=tk.X)

        tk.Button(
            footer,
            text="Cerrar",
            font=("Segoe UI", 11, "bold"),
            bg=theme["button"],
            fg=theme["button_fg"],
            activebackground=theme["button"],
            command=pop.destroy,
            padx=16,
            pady=4,
        ).pack(anchor=tk.E)

        pop.bind("<Escape>", lambda _e: pop.destroy())
        pop.after(8000, pop.destroy)

    def gui_callback_handler(self, action, data):
        if action == "update_table": 
            self.root.after(0, lambda: self.update_table(data))
        elif action == "update_profile_table": 
            self.root.after(0, lambda: self.update_profile(data))
        elif action == "show_popup": 
            self.root.after(0, lambda: self.crear_popup(data))
        elif action == "show_info_popup":
            self.root.after(0, lambda: self._show_themed_popup("Éxito", data, "info"))
        elif action == "show_warning_popup":
            self.root.after(0, lambda: self._show_themed_popup("Atención", data, "warning"))
        elif action == "show_error_popup": 
            self.root.after(0, lambda: self._show_themed_popup("Error Crítico", data, "error"))
        elif action == "switch_to_auto_reprogram":
            self.root.after(0, self._switch_to_auto_reprogram_mode)
        elif action == "clear_auto_modes":
            self.root.after(0, self._clear_auto_modes)

    def _switch_to_auto_reprogram_mode(self):
        if self.auto_reprogram_var.get():
            return
        self.auto_reprogram_var.set(True)
        self.auto_programar_var.set(False)
        self.save_config()

    def _clear_auto_modes(self):
        changed = False
        if self.auto_programar_var.get():
            self.auto_programar_var.set(False)
            changed = True
        if self.auto_reprogram_var.get():
            self.auto_reprogram_var.set(False)
            changed = True
        if changed:
            self.save_config()

    def update_table(self, data_list):
        self.all_citas = data_list
        for item in self.tree.get_children(): 
            self.tree.delete(item)
        self.citas_map.clear()
        
        for i, row in enumerate(self.all_citas):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            row_id = self.tree.insert("", "end", values=(row['fecha'], row['hora'], row['doctor'], row['lugar']), tags=(tag,))
            self.citas_map[row_id] = row
            
        self.tree.tag_configure('oddrow', background="white")
        self.tree.tag_configure('evenrow', background="#f8f9fa")

    def update_profile(self, data_list):
        for item in self.tree_perfil.get_children(): 
            self.tree_perfil.delete(item)
        self.perfil_map.clear()
        for i, row in enumerate(data_list):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            row_id = self.tree_perfil.insert("", "end", values=(row['fecha'], row['servicio'], row['doctor']), tags=(tag,))
            self.perfil_map[row_id] = row
        self.tree_perfil.tag_configure('oddrow', background="white")
        self.tree_perfil.tag_configure('evenrow', background="#fff3cd") 

    def ensure_motor_running(self):
        if not self.is_running:
            messagebox.showwarning("Atención", "Para ejecutar acciones en el navegador sin bloqueos, debes iniciar el Motor (Bucle o 1 Vez) primero.")
            return False
        return True

    def exec_agendar(self, cita_directa=None):
        if not self.ensure_motor_running(): 
            return
        
        if cita_directa: 
            cita_info = cita_directa
        else:
            selected = self.tree.selection()
            if not selected: 
                return messagebox.showwarning("Atención", "Selecciona una cita en la tabla.")
            cita_info = self.citas_map.get(selected[0])

        if cita_info:
            confirm = messagebox.askyesno("Agendar", f"¿Agendar automáticamente?\n\n📅 {cita_info['fecha']}\n⏰ {cita_info['hora']}\n👨‍⚕️ {cita_info['doctor']}")
            if confirm: 
                self.action_queue.put({'type': 'agendar', 'data': cita_info})
                messagebox.showinfo("En Cola", "Se añadió el agendamiento a la cola. El bot lo procesará en breve.")

    def _get_perfil_para_reprogramar(self):
        """Selecciona una cita vigente para iniciar reprogramación automática."""
        perfiles = list(self.perfil_map.values())
        if not perfiles:
            perfiles = load_json("perfil_cache") or []
        if not perfiles:
            return None

        def _key(item):
            fecha = parse_date(str(item.get("fecha") or ""))
            return (fecha or datetime.max.date(), str(item.get("doctor") or ""))

        perfiles.sort(key=_key)
        return perfiles[0]

    def exec_reagendar(self, cita_destino):
        if not self.ensure_motor_running():
            return

        perfil_objetivo = self._get_perfil_para_reprogramar()
        if not perfil_objetivo:
            return self.exec_agendar(cita_destino)

        confirm = messagebox.askyesno(
            "Reagendar",
            "Se detectó que ya tienes cita vigente.\n\n"
            "El bot hará este orden automáticamente:\n"
            "1) Reprogramar cita vigente\n"
            "2) Agendar la nueva cita seleccionada\n\n"
            f"Nueva cita: {cita_destino.get('fecha', '')} {cita_destino.get('hora', '')} - {cita_destino.get('doctor', '')}"
        )
        if confirm:
            self.action_queue.put({'type': 'reprogramar', 'data': perfil_objetivo})
            self.action_queue.put({'type': 'agendar', 'data': cita_destino})
            messagebox.showinfo("En Cola", "Se añadió la secuencia Reprogramar -> Agendar a la cola.")

    def exec_reprogramar(self):
        if not self.ensure_motor_running(): 
            return
        selected = self.tree_perfil.selection()
        if not selected: 
            return messagebox.showwarning("Atención", "Selecciona una cita de tu Perfil.")
        info = self.perfil_map.get(selected[0])
        confirm = messagebox.askyesno("Reprogramar", f"¿Iniciar reprogramación de la cita del {info['fecha']}?")
        if confirm:
            self.action_queue.put({'type': 'reprogramar', 'data': info})
            messagebox.showinfo("En Cola", "Orden de reprogramación añadida a la cola.")

    def exec_cancelar(self):
        if not self.ensure_motor_running(): 
            return
        selected = self.tree_perfil.selection()
        if not selected: 
            return messagebox.showwarning("Atención", "Selecciona una cita de tu Perfil.")
        info = self.perfil_map.get(selected[0])
        confirm = messagebox.askyesno("Cancelar Cita", f"ALERTA: ¿Deseas CANCELAR la cita del {info['fecha']} con {info['doctor']}?")
        if confirm:
            self.action_queue.put({'type': 'cancelar', 'data': info})
            messagebox.showinfo("En Cola", "Orden de cancelación añadida a la cola.")

    def sync_profile(self):
        if not self.ensure_motor_running(): 
            return
        self.action_queue.put({'type': 'sync_profile'})
        messagebox.showinfo("En Cola", "La extracción de perfil ha sido añadida a la cola de acciones.")

    def validate_and_update_filters(self):
        """Valida todos los filtros y los actualiza."""
        d_start = self.date_start_var.get().strip()
        d_end = self.date_end_var.get().strip()
        t_start = self.time_start_var.get().strip()
        t_end = self.time_end_var.get().strip()
        target_date = self.auto_target_date_var.get().strip()
        target_time = self.auto_target_time_var.get().strip()
        
        errors = []
        
        if d_start and not validate_date_format(d_start):
            errors.append(f"❌ Fecha Desde inválida: '{d_start}'\n   Usa: DD/MM/AAAA (Ej: 15/04/2026)")
        
        if d_end and not validate_date_format(d_end):
            errors.append(f"❌ Fecha Hasta inválida: '{d_end}'\n   Usa: DD/MM/AAAA (Ej: 30/04/2026)")
        
        if t_start and not validate_time_format(t_start):
            errors.append(f"❌ Hora Desde inválida: '{t_start}'\n   Usa: HH:MM (Ej: 08:30)")
        
        if t_end and not validate_time_format(t_end):
            errors.append(f"❌ Hora Hasta inválida: '{t_end}'\n   Usa: HH:MM (Ej: 14:30)")

        if target_date and not validate_date_format(target_date):
            errors.append(f"❌ Día Objetivo inválido: '{target_date}'\n   Usa: DD/MM/AAAA (Ej: 15/04/2026)")

        if target_time and not validate_time_format(target_time):
            errors.append(f"❌ Hora Objetivo inválida: '{target_time}'\n   Usa: HH:MM (Ej: 17:00)")

        sura_pref_enabled = bool(self.sura_pref_enabled_var.get())
        sura_pref_date = self.sura_pref_date_var.get().strip()
        if sura_pref_enabled and sura_pref_date and not validate_date_format(sura_pref_date):
            errors.append(f"❌ Fecha preferida SURA inválida: '{sura_pref_date}'\n   Usa: DD/MM/AAAA (Ej: 25/04/2026)")

        if (self.auto_programar_var.get() or self.auto_reprogram_var.get()) and (not target_date) and (not target_time):
            if "continuar" in str(self.auto_post_action_var.get() or "").lower():
                errors.append("❌ Sin día/hora objetivo no se permite 'Continuar buscando'. Debe quedar en 'Detener tras ejecutar'.")
        
        # Validar coherencia de fechas
        if d_start and d_end:
            try:
                date_start_obj = parse_date(d_start)
                date_end_obj = parse_date(d_end)
                if date_start_obj and date_end_obj and date_start_obj > date_end_obj:
                    errors.append("❌ Fecha Desde no puede ser posterior a Fecha Hasta")
            except: 
                pass
        
        # Validar coherencia de horas
        if t_start and t_end:
            try:
                time_start_obj = parse_time(t_start)
                time_end_obj = parse_time(t_end)
                if time_start_obj and time_end_obj and time_start_obj > time_end_obj:
                    errors.append("❌ Hora Desde no puede ser posterior a Hora Hasta")
            except: 
                pass
        
        if errors:
            error_msg = "⚠️ ERRORES EN LOS FILTROS:\n\n" + "\n".join(errors)
            messagebox.showerror("Validación de Filtros", error_msg)
            return False
        else:
            # Almacenar filtros validados
            self.set_current_filters(d_start, d_end, t_start, t_end)
            self.save_config()
            success_msg = "✅ Filtros validados correctamente:\n\n"
            if d_start or d_end:
                success_msg += f"📅 Fechas: {d_start or 'desde siempre'} → {d_end or 'hasta siempre'}\n"
            if t_start or t_end:
                success_msg += f"⏰ Horas: {t_start or 'desde 00:00'} → {t_end or 'hasta 23:59'}"
            else:
                if not (d_start or d_end):
                    success_msg = "✅ Filtros validados.\n📍 Se buscarán todas las citas sin restricciones."
            if target_date:
                success_msg += f"\n📅 Día objetivo: {target_date}"
            if target_time:
                success_msg += f"\n🎯 Hora objetivo: {target_time}"
            if sura_pref_enabled:
                success_msg += "\n🧭 Preferencia consulta SURA: activa"
                if sura_pref_date:
                    success_msg += f" ({sura_pref_date})"
            
            self.log("✅ Filtros validados y actualizados correctamente.")
            messagebox.showinfo("Filtros Aplicados", success_msg.strip())
            
            if self.is_running:
                self.log("📍 Los filtros se aplicarán en el próximo ciclo de búsqueda.")
            return True

    def _sort_citas_for_popup(self, citas):
        def sort_key(cita):
            fecha = parse_date(str(cita.get("fecha") or ""))
            hora = parse_time(str(cita.get("hora") or ""))
            fecha_sort = fecha or datetime.max.date()
            hora_sort = hora or datetime.max.time()
            return (fecha_sort, hora_sort, str(cita.get("doctor") or ""), str(cita.get("lugar") or ""))

        ordered = list(citas or [])
        ordered.sort(key=sort_key)
        return ordered

    def crear_popup(self, cita_info):
        citas = cita_info if isinstance(cita_info, list) else [cita_info]
        citas = self._sort_citas_for_popup([c for c in citas if isinstance(c, dict)])
        if not citas:
            return

        tiene_cita_vigente = bool(self._get_perfil_para_reprogramar())

        pop = tk.Toplevel(self.root)
        pop.title("¡🚨 CITAS ENCONTRADAS 🚨!")
        w, h = 820, 620
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        
        monitor = self._selected_monitor() or {}
        screen_w = int(monitor.get("width", self.root.winfo_screenwidth()))
        screen_h = int(monitor.get("height", self.root.winfo_screenheight()))
        monitor_left = int(monitor.get("left", 0))
        monitor_top = int(monitor.get("top", 0))

        x = monitor_left + (screen_w // 2) - (w // 2)
        y = monitor_top + (screen_h // 2) - (h // 2)
        
        pop.geometry(f"{w}x{h}+{x}+{y}")
        pop.configure(bg="#28a745") 
        pop.attributes("-topmost", True)

        title_text = f"{len(citas)} cita(s) encontrada(s)"
        ttk.Label(pop, text=title_text, font=("Segoe UI", 20, "bold"), background="#28a745", foreground="white").pack(pady=(14, 6))
        ttk.Label(pop, text="Ordenadas por fecha y hora más cercanas.", font=("Segoe UI", 10), background="#28a745", foreground="white").pack(pady=(0, 10))

        outer = tk.Frame(pop, bg="#28a745")
        outer.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 12))

        canvas = tk.Canvas(outer, bg="#28a745", highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#28a745")

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def open_cita_in_browser(cita):
            url = str(cita.get("js_action") or "").strip()
            if url.startswith("javascript:"):
                url = url.replace("javascript:", "", 1)
            if url and url.startswith(("http://", "https://")):
                webbrowser.open(url)
            else:
                webbrowser.open("https://epssura.com")

        for idx, cita in enumerate(citas, start=1):
            card = tk.Frame(scroll_frame, bg="white", bd=0, highlightthickness=1, highlightbackground="#d9e2ec")
            card.pack(fill=tk.X, pady=8, padx=4)

            header = tk.Frame(card, bg="#f8fafc")
            header.pack(fill=tk.X)
            ttk.Label(header, text=f"#{idx}  {cita.get('fecha', '')}  |  {cita.get('hora', '')}", font=("Segoe UI", 13, "bold"), background="#f8fafc").pack(anchor=tk.W, padx=12, pady=(10, 2))

            body = tk.Frame(card, bg="white", padx=12, pady=10)
            body.pack(fill=tk.X)

            ttk.Label(body, text=f"👨‍⚕️ Doctor: {cita.get('doctor', '')}", font=("Segoe UI", 11), background="white").pack(anchor=tk.W)
            ttk.Label(body, text=f"🏥 Sede: {cita.get('lugar', '')}", font=("Segoe UI", 11), background="white").pack(anchor=tk.W, pady=(4, 0))

            actions = tk.Frame(body, bg="white")
            actions.pack(fill=tk.X, pady=(12, 0))

            tk.Button(
                actions,
                text="🔄 Reagendar cita" if tiene_cita_vigente else "✅ Agendar cita",
                font=("Segoe UI", 11, "bold"),
                bg="#28a745",
                fg="white",
                activebackground="#218838",
                command=lambda c=cita: [self.exec_reagendar(c), pop.destroy()] if tiene_cita_vigente else [self.exec_agendar(c), pop.destroy()],
            ).pack(side=tk.LEFT, padx=(0, 8), ipady=6, ipadx=8)

            tk.Button(
                actions,
                text="🌐 Abrir en navegador",
                font=("Segoe UI", 11, "bold"),
                bg="#0056b3",
                fg="white",
                activebackground="#004494",
                command=lambda c=cita: open_cita_in_browser(c),
            ).pack(side=tk.LEFT, ipady=6, ipadx=8)

        footer = tk.Frame(pop, bg="#28a745")
        footer.pack(fill=tk.X, pady=(0, 10))

        tk.Button(
            footer,
            text="Cerrar",
            font=("Segoe UI", 11, "bold"),
            bg="#ffffff",
            fg="#28a745",
            command=pop.destroy,
        ).pack(pady=4)

    def sort_column(self, col):
        try:
            l = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
            l.sort(reverse=False) 
            for index, (val, k) in enumerate(l): 
                self.tree.move(k, "", index)
        except: 
            pass

    def _build_gui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header_frame, text="✨ Gestor Inteligente de Citas SURA", style="Title.TLabel").pack(side=tk.LEFT)

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_monitor = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_monitor, text=" 🔍 Buscador Automático ")

        self.tab_profile = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_profile, text=" 🗓️ Mi Perfil / Citas Activas ")

        self._build_monitor_tab()
        self._build_profile_tab()

    def _build_monitor_tab(self):
        content_frame = ttk.Frame(self.tab_monitor)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # SLIDER DEL MENÚ IZQUIERDO (Canvas Scrollable)
        left_outer_frame = ttk.Frame(content_frame, width=340)
        left_outer_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_outer_frame.pack_propagate(False)

        left_scrollbar = ttk.Scrollbar(left_outer_frame, orient=tk.VERTICAL)
        left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        left_canvas = tk.Canvas(left_outer_frame, bg=self.bg_color, highlightthickness=0)
        left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        left_scrollbar.config(command=left_canvas.yview)
        left_canvas.config(yscrollcommand=left_scrollbar.set)

        left_panel = ttk.Frame(left_canvas)
        left_panel.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        )
        
        left_canvas.create_window((0, 0), window=left_panel, anchor="nw", width=320)
        
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
        left_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # CONFIGURACIÓN GENERAL
        sys_frame = ttk.LabelFrame(left_panel, text=" ⚙️ Archivos y Sistema ", padding="10")
        sys_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(sys_frame, text="Ruta de Cookies:").pack(anchor=tk.W)
        cook_frame = ttk.Frame(sys_frame)
        cook_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Entry(cook_frame, textvariable=self.cookie_var, width=15).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(cook_frame, text="...", width=3, command=self.select_cookie_path).pack(side=tk.LEFT, padx=(2,0))

        ttk.Checkbutton(sys_frame, text="Guardar Config Automático", variable=self.autosave_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(sys_frame, text="Arrancar con Windows (iniciar app)", variable=self.startup_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(sys_frame, text="Iniciar monitoreo automáticamente", variable=self.auto_monitor_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(sys_frame, text="Ocultar Chrome (Headless)", variable=self.headless_var).pack(anchor=tk.W, pady=2)

        # FILTROS
        filtros_frame = ttk.LabelFrame(left_panel, text=" 🎯 Filtros (Opcionales) ", padding="10")
        filtros_frame.pack(fill=tk.X, pady=5)

        ttk.Label(filtros_frame, text="Fecha Desde (DD/MM/AAAA):").pack(anchor=tk.W)
        ttk.Entry(filtros_frame, textvariable=self.date_start_var, width=18).pack(anchor=tk.W, pady=(0, 5))
        ttk.Label(filtros_frame, text="Fecha Hasta (DD/MM/AAAA):").pack(anchor=tk.W)
        ttk.Entry(filtros_frame, textvariable=self.date_end_var, width=18).pack(anchor=tk.W, pady=(0, 5))
        ttk.Label(filtros_frame, text="Hora Desde (HH:MM):").pack(anchor=tk.W)
        ttk.Entry(filtros_frame, textvariable=self.time_start_var, width=18).pack(anchor=tk.W, pady=(0, 5))
        ttk.Label(filtros_frame, text="Hora Hasta (HH:MM):").pack(anchor=tk.W)
        ttk.Entry(filtros_frame, textvariable=self.time_end_var, width=18).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Button(filtros_frame, text="🔍 VALIDAR Y ACTUALIZAR", command=self.validate_and_update_filters, style="Action.TButton").pack(fill=tk.X, pady=(10, 0))

        # ALERTAS Y CONTROLES
        alert_frame = ttk.LabelFrame(left_panel, text=" 🔔 Bucle y Alertas ", padding="10")
        alert_frame.pack(fill=tk.X, pady=5)

        ttk.Checkbutton(alert_frame, text="Usar intervalo variable (rango)", variable=self.interval_random_var, command=self._update_interval_controls_state).pack(anchor=tk.W, pady=(0, 4))

        ttk.Label(alert_frame, text="Intervalo Mínimo / Fijo (segs):").pack(anchor=tk.W)
        ttk.Spinbox(alert_frame, from_=15, to=3600, textvariable=self.interval_min_var, width=10).pack(anchor=tk.W, pady=(0, 5))

        self.interval_max_label = ttk.Label(alert_frame, text="Intervalo Máximo (segs):")
        self.interval_max_label.pack(anchor=tk.W)
        self.interval_max_spin = ttk.Spinbox(alert_frame, from_=15, to=3600, textvariable=self.interval_max_var, width=10)
        self.interval_max_spin.pack(anchor=tk.W, pady=(0, 5))

        ttk.Button(alert_frame, text="🔄 Aplicar nuevo intervalo", command=self.refresh_runtime_interval, style="Action.TButton").pack(fill=tk.X, pady=(2, 6))

        ttk.Label(alert_frame, text="Monitor de Pop-up:").pack(anchor=tk.W)
        self.monitor_combo = ttk.Combobox(alert_frame, textvariable=self.monitor_var, values=self._monitor_combo_values(), state="readonly", width=30)
        self.monitor_combo.pack(anchor=tk.W, pady=(0,5))
        
        ttk.Checkbutton(alert_frame, text="Sonido Alarma", variable=self.sound_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(alert_frame, text="Súper Pop-Up Verde", variable=self.popup_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(alert_frame, text="Avisar si caduca/bloquea", variable=self.alert_block_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(alert_frame, text="Programar automáticamente", variable=self.auto_programar_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(alert_frame, text="Reprogramar automáticamente", variable=self.auto_reprogram_var).pack(anchor=tk.W, pady=2)

        ttk.Label(alert_frame, text="Prioridad auto-agendar:").pack(anchor=tk.W, pady=(6, 0))
        prioridad_combo = ttk.Combobox(
            alert_frame,
            textvariable=self.auto_priority_var,
            values=["Más temprana (tope)", "Más tardía (fondo)"],
            state="readonly",
            width=24
        )
        prioridad_combo.pack(anchor=tk.W, pady=(0, 5))
        prioridad_combo.bind("<<ComboboxSelected>>", self._on_priority_mode_changed)

        ttk.Label(alert_frame, text="Después de auto-agendar/reprogramar:").pack(anchor=tk.W, pady=(6, 0))
        ttk.Combobox(
            alert_frame,
            textvariable=self.auto_post_action_var,
            values=["Detener tras ejecutar", "Continuar buscando mejor horario"],
            state="readonly",
            width=30,
        ).pack(anchor=tk.W, pady=(0, 5))

        ttk.Label(alert_frame, text="Día objetivo (DD/MM/AAAA, opcional):").pack(anchor=tk.W)
        ttk.Entry(alert_frame, textvariable=self.auto_target_date_var, width=14).pack(anchor=tk.W, pady=(0, 5))

        ttk.Label(alert_frame, text="Hora objetivo (HH:MM, opcional):").pack(anchor=tk.W)
        ttk.Entry(alert_frame, textvariable=self.auto_target_time_var, width=14).pack(anchor=tk.W, pady=(0, 5))

        ttk.Separator(alert_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)
        ttk.Checkbutton(
            alert_frame,
            text="Preferencia de consulta SURA (usar fecha deseada)",
            variable=self.sura_pref_enabled_var,
            command=self._update_sura_pref_controls_state,
        ).pack(anchor=tk.W, pady=(2, 2))
        ttk.Label(alert_frame, text="Fecha preferida SURA (DD/MM/AAAA):").pack(anchor=tk.W)
        self.sura_pref_date_entry = ttk.Entry(alert_frame, textvariable=self.sura_pref_date_var, width=14)
        self.sura_pref_date_entry.pack(anchor=tk.W, pady=(0, 5))
        self._update_sura_pref_controls_state()

        btn_frame = ttk.Frame(left_panel)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        self.btn_single = ttk.Button(btn_frame, text="👁️ CONSULTAR 1 VEZ", command=lambda: self.start_monitoring(single=True), style="Action.TButton")
        self.btn_single.pack(fill=tk.X, pady=2)
        self.btn_start = ttk.Button(btn_frame, text="▶ INICIAR BUCLE", command=lambda: self.start_monitoring(single=False), style="Action.TButton")
        self.btn_start.pack(fill=tk.X, pady=2)
        self.btn_stop = ttk.Button(btn_frame, text="⏹ DETENER", command=self.stop_monitoring, state=tk.DISABLED, style="Action.TButton")
        self.btn_stop.pack(fill=tk.X, pady=2)
        self.btn_restart = ttk.Button(btn_frame, text="♻ REINICIAR APP", command=self.restart_application, style="Warn.TButton")
        self.btn_restart.pack(fill=tk.X, pady=2)

        # PANEL DERECHO
        right_panel = ttk.Frame(content_frame)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        results_frame = ttk.LabelFrame(right_panel, text=" 📋 Citas Disponibles Encontradas ", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 5))

        tree_container = ttk.Frame(results_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        # Scrollbar vertical
        tree_scroll_v = ttk.Scrollbar(tree_container, orient=tk.VERTICAL)
        tree_scroll_v.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Scrollbar horizontal
        tree_scroll_h = ttk.Scrollbar(tree_container, orient=tk.HORIZONTAL)
        tree_scroll_h.pack(side=tk.BOTTOM, fill=tk.X)

        columns = ("Fecha", "Hora", "Especialidad/Doctor", "Lugar")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings", height=6, 
                                 yscrollcommand=tree_scroll_v.set, xscrollcommand=tree_scroll_h.set)
        tree_scroll_v.config(command=self.tree.yview)
        tree_scroll_h.config(command=self.tree.xview)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for col in columns: 
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_column(c))
        self.tree.column("Fecha", width=120, anchor=tk.CENTER)
        self.tree.column("Hora", width=100, anchor=tk.CENTER)
        self.tree.column("Especialidad/Doctor", width=280)
        self.tree.column("Lugar", width=220)

        ttk.Button(results_frame, text="✅ Agendar Cita Seleccionada", command=self.exec_agendar, style="Action.TButton").pack(side=tk.BOTTOM, pady=(10, 0), anchor=tk.E)

        log_frame = ttk.LabelFrame(right_panel, text=" 🖥️ Consola de Estado ", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=False, padx=(10, 0), pady=5, ipady=5)

        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)

        log_scroll = ttk.Scrollbar(log_container, orient=tk.VERTICAL)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(log_container, height=12, state=tk.DISABLED, bg="#1e1e1e", fg="#4CAF50", font=("Consolas", 9), relief=tk.FLAT, yscrollcommand=log_scroll.set)
        log_scroll.config(command=self.log_text.yview)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _build_profile_tab(self):
        head_frame = tk.Frame(self.tab_profile, bg=self.bg_color)
        head_frame.pack(fill=tk.X, pady=(10, 10))
        ttk.Label(head_frame, text="🗓️ Tus citas programadas vigentes en SURA:", font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        ttk.Button(head_frame, text="🔄 Sincronizar Mi Perfil Ahora", command=self.sync_profile, style="Action.TButton").pack(side=tk.RIGHT)

        perfil_frame = ttk.Frame(self.tab_profile)
        perfil_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Scrollbar vertical
        perfil_scroll_v = ttk.Scrollbar(perfil_frame, orient=tk.VERTICAL)
        perfil_scroll_v.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Scrollbar horizontal
        perfil_scroll_h = ttk.Scrollbar(perfil_frame, orient=tk.HORIZONTAL)
        perfil_scroll_h.pack(side=tk.BOTTOM, fill=tk.X)

        columns = ("Fecha de la Cita", "Servicio a Recibir", "Profesional")
        self.tree_perfil = ttk.Treeview(perfil_frame, columns=columns, show="headings", height=8, 
                                        yscrollcommand=perfil_scroll_v.set, xscrollcommand=perfil_scroll_h.set)
        perfil_scroll_v.config(command=self.tree_perfil.yview)
        perfil_scroll_h.config(command=self.tree_perfil.xview)
        self.tree_perfil.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for col in columns: 
            self.tree_perfil.heading(col, text=col)
        self.tree_perfil.column("Fecha de la Cita", width=170, anchor=tk.CENTER)
        self.tree_perfil.column("Servicio a Recibir", width=350)
        self.tree_perfil.column("Profesional", width=350)

        action_frame = ttk.Frame(self.tab_profile)
        action_frame.pack(fill=tk.X, pady=10)
        ttk.Button(action_frame, text="⚠️ Cancelar Cita", command=self.exec_cancelar, style="Danger.TButton").pack(side=tk.RIGHT, padx=5)
        ttk.Button(action_frame, text="🔄 Reprogramar Cita", command=self.exec_reprogramar, style="Warn.TButton").pack(side=tk.RIGHT, padx=5)

    def log(self, message):
        self.root.after(0, self._append_log, message)

    def _append_log(self, message):
        self.log_text.config(state=tk.NORMAL)
        current_time = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{current_time}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def start_monitoring(self, single=False):
        d_start, d_end = self.date_start_var.get().strip(), self.date_end_var.get().strip()
        t_start, t_end = self.time_start_var.get().strip(), self.time_end_var.get().strip()
        target_date = self.auto_target_date_var.get().strip()
        target_time = self.auto_target_time_var.get().strip()
        
        # Validar filtros antes de iniciar
        errors = []
        if d_start and not validate_date_format(d_start):
            errors.append(f"❌ Fecha Desde: '{d_start}'")
        if d_end and not validate_date_format(d_end):
            errors.append(f"❌ Fecha Hasta: '{d_end}'")
        if t_start and not validate_time_format(t_start):
            errors.append(f"❌ Hora Desde: '{t_start}'")
        if t_end and not validate_time_format(t_end):
            errors.append(f"❌ Hora Hasta: '{t_end}'")
        if target_date and not validate_date_format(target_date):
            errors.append(f"❌ Día Objetivo: '{target_date}'")
        if target_time and not validate_time_format(target_time):
            errors.append(f"❌ Hora Objetivo: '{target_time}'")
        if self.sura_pref_enabled_var.get() and self.sura_pref_date_var.get().strip() and (not validate_date_format(self.sura_pref_date_var.get().strip())):
            errors.append(f"❌ Fecha preferida SURA: '{self.sura_pref_date_var.get().strip()}'")

        if (self.auto_programar_var.get() or self.auto_reprogram_var.get()) and (not target_date) and (not target_time):
            if "continuar" in str(self.auto_post_action_var.get() or "").lower():
                self.auto_post_action_var.set("Detener tras ejecutar")
                self.log("ℹ️ Sin día/hora objetivo, se ajustó automáticamente a 'Detener tras ejecutar'.")
        
        if errors:
            msg = "⚠️ NO PUEDO INICIAR CON FILTROS INVÁLIDOS:\n\n"
            msg += "\n".join(errors)
            msg += "\n\nUsa el botón '🔍 VALIDAR Y ACTUALIZAR'"
            messagebox.showerror("Filtros Inválidos", msg)
            return
        
        interval = self._get_runtime_interval()

        self.btn_start.config(state=tk.DISABLED)
        self.btn_single.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.stop_event.clear()
        self.is_running = True
        self.set_current_filters(d_start, d_end, t_start, t_end)
        
        tipo = "Búsqueda Única" if single else "Bucle"
        self.log(f"🚀 Iniciando Motor ({tipo})...")
        
        filtro_desc = ""
        if d_start or d_end or t_start or t_end:
            filtro_desc = "📋 Filtros: "
            if d_start or d_end:
                filtro_desc += f"Fechas {d_start or 'cualquiera'} → {d_end or 'cualquiera'} | "
            if t_start or t_end:
                filtro_desc += f"Horas {t_start or 'cualquiera'} → {t_end or 'cualquiera'}"
            if target_date:
                filtro_desc += f" | Día objetivo {target_date}"
            if target_time:
                filtro_desc += f" | Objetivo {target_time}"
            if self.sura_pref_enabled_var.get():
                pref_date = self.sura_pref_date_var.get().strip()
                filtro_desc += " | Preferencia consulta SURA activa"
                if pref_date:
                    filtro_desc += f" ({pref_date})"
            self.log(filtro_desc)
        else:
            self.log("📋 Sin filtros activos - buscando todas las citas")

        threading.Thread(
            target=check_appointments,
            args=(self.cookie_var.get(), self.headless_var.get(), single, self.popup_var.get(), d_start, d_end, t_start, t_end, interval, self.sound_var.get(), self.alert_block_var.get(), self.stop_event, self.log, self.gui_callback_handler, self.action_queue, self.get_current_filters),
            daemon=True
        ).start()

    def stop_monitoring(self):
        self.log("🛑 Deteniendo el sistema...")
        self.stop_event.set()
        self.is_running = False
        self.btn_start.config(state=tk.NORMAL)
        self.btn_single.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)

    def refresh_runtime_interval(self):
        try:
            self._normalize_interval_inputs()
            self._update_interval_controls_state()
            min_v, max_v, random_mode = self._get_interval_settings()
            self.save_config()
            if random_mode:
                self.log(f"⏱️ Intervalo actualizado a rango {min_v}s - {max_v}s.")
            else:
                self.log(f"⏱️ Intervalo actualizado a fijo {min_v}s.")
            if self.is_running:
                self.log("📍 El nuevo intervalo se aplicará en el próximo ciclo sin detener el motor.")
            else:
                self.log("📍 Intervalo guardado para el próximo inicio del motor.")
        except Exception:
            messagebox.showerror("Intervalo inválido", "Revisa los intervalos: deben ser números enteros (mínimo 15 segundos).")

    def restart_application(self):
        confirm = messagebox.askyesno("Reiniciar aplicación", "¿Deseas reiniciar la aplicación ahora?")
        if not confirm:
            return
        try:
            self.log("♻ Reiniciando aplicación...")
            self.stop_event.set()
            self.is_running = False

            try:
                self.save_config()
            except Exception as cfg_err:
                self.log(f"⚠️ No se pudo guardar configuración antes de reiniciar: {cfg_err}")

            python_exe = sys.executable
            script_path = os.path.abspath(sys.argv[0] if sys.argv and sys.argv[0] else __file__)
            script_dir = os.path.dirname(script_path)

            # En Windows es más estable abrir un nuevo proceso y cerrar la ventana actual.
            subprocess.Popen([python_exe, script_path], cwd=script_dir)
            self.root.after(150, self.root.destroy)
        except Exception as e:
            try:
                python_exe = sys.executable
                os.execl(python_exe, python_exe, *sys.argv)
            except Exception as ex2:
                messagebox.showerror("Reiniciar aplicación", f"No se pudo reiniciar: {e}\nFallback también falló: {ex2}")

if __name__ == "__main__":
    root = tk.Tk()
    if not HAS_SELENIUM:
        root.withdraw()
        messagebox.showerror(
            "Dependencia faltante",
            "Falta instalar la dependencia 'selenium'.\n\nInstala las dependencias con:\npy -m pip install -r requirements.txt\n\nLuego vuelve a abrir la aplicación.",
        )
        root.destroy()
        raise SystemExit(1)
    app = AlerterGUI(root)
    root.mainloop()
