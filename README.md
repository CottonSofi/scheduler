# Alerter

Aplicacion de escritorio (Tkinter + Selenium) para monitorear disponibilidad de citas y lanzar alertas.

## Guia de instalacion

### Requisitos

- Python 3.10+
- Google Chrome instalado
- Dependencias Python del archivo `requirements.txt`

### Instalacion recomendada

Desde la raiz del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Arranque en Windows

Si usas Inicio con Windows, el programa crea un acceso oculto con `pythonw.exe` cuando esta disponible.
Eso evita la ventana de consola que suele aparecer con `python.exe`.

## Ejecucion

```powershell
python alerter.py
```

Si en otro equipo aparece un error de dependencia faltante, instala primero la misma lista dentro de la `.venv` activa:

```powershell
python -m pip install -r requirements.txt
```

## Notas de uso

- cookies de sesion en `cookies/`
- cache y configuracion runtime en `datos_temporales/`
- HTML de debug/export (`pagina_citas_sura.html`, `resultado_citas_*.html`)

## Archivos locales no versionados

Estos archivos no deberian versionarse porque cambian segun la sesion y el equipo.
