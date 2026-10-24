# Ejecutar una sola vez desde cualquier directorio:
#   python apply_v0.2.52.py
# Elimina TIMEOUT_MS sin sobrescribir la configuracion local.
from pathlib import Path
import re

root = Path(__file__).resolve().parent
config = root / 'picoAlpha' / 'include' / 'config.h'
if not config.is_file():
    raise SystemExit(f'Falta {config}: extraer el ZIP sobre el directorio padre de picoAlpha')
s = config.read_text(encoding='utf-8')
if not re.search(r'\bTMAX_MS\b\s*=', s):
    raise SystemExit('Falta TMAX_MS en config.h; no se cambia nada')
pattern = r'(?m)^\s*inline\s+constexpr\s+unsigned\s+TIMEOUT_MS\s*=\s*[^;]+;[^\n]*\n'
updated, count = re.subn(pattern, '', s)
if count == 0 and re.search(r'\bTIMEOUT_MS\b', s):
    raise SystemExit('TIMEOUT_MS presente en formato inesperado; no se cambia nada')
if count > 1:
    raise SystemExit('TIMEOUT_MS aparece varias veces; no se cambia nada')
if updated != s:
    config.write_text(updated, encoding='utf-8')
    print('config.h: eliminada TIMEOUT_MS; TMAX_MS y el resto de la configuracion intactos')
else:
    print('config.h: TIMEOUT_MS ya no existe; ninguna modificacion necesaria')
