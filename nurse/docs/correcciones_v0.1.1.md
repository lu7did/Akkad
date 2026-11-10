# Nurse v0.1.1 — correcciones incrementales

- Se incluyen `benchmark_bratko_kopec.py` y `benchmark_bk_profile.py`, omitidos por error en v0.1.0 y necesarios para importar `nurse.benchmark`.
- `nurse.uci` distingue `KeyboardInterrupt`, comunica en **stderr** «Interrupción del usuario (Ctrl+C)» y devuelve código **130**. La limpieza `finally` de `Nurse.run()` cierra el transporte.
- `nurse.listen` identifica explícitamente Ctrl+C en su mensaje de cierre, conservando el retorno **0** para apagado normal del listener.
- Se agrega prueba automatizada de importación de los módulos BK y finalización por Ctrl+C.
- **No** se modifican los motores, el algoritmo BK ni los archivos de Sargon-NNUE.

Pruebas recomendadas:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python -m nurse.benchmark --help
python -m nurse.benchmark --brain etc/brains/brains.json --ids fishy nurse_classic --positions 2 --warmup 0 --timeout 30
```

**Advertencia:** la ejecución completa de Bratko-Kopec requiere `--bratko-kopec` y puede tardar mucho por perfil.
