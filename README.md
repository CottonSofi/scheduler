# Alerter

Aplicacion de escritorio (Tkinter + Selenium) para monitorear disponibilidad de citas y lanzar alertas.

## Requisitos

- Python 3.10+
- Google Chrome instalado

## Instalacion

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Ejecucion

```powershell
python alerter.py
```

## Archivos locales no versionados

- cookies de sesion en `cookies/`
- cache y configuracion runtime en `datos_temporales/`
- HTML de debug/export (`pagina_citas_sura.html`, `resultado_citas_*.html`)
