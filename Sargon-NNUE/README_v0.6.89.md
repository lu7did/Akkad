# v0.6.89 — Corrección de auditoría con TURBO desactivado

## Defecto confirmado
La v0.6.88 agregaba al hook `_after_level_complete` un evento JSONL que lee `self._boost_audit_start`. Cuando `turbo=0`, `SargonPlusPlayer.choose()` delegaba directamente en `SargonCore.choose()` sin inicializar el atributo. Una vez completado el primer nivel se producía `AttributeError`, atrapado por `UCISession`, que respondía `bestmove (none)`; MATCH registraba una partida incompleta en ply 0.

## Corrección
Con auditoría activa y `turbo=0`, crear el contexto de búsqueda antes de llamar a `super().choose()` y conservar un evento resumen `boost_search_metrics` al volver. Cuando la auditoría está desactivada, la rama original `return super().choose(board)` queda intacta. La lógica de selección, los algoritmos BOOST/TURBO y sus máscaras no se alteran.

## Instalación
Reemplazar exclusivamente `src/sargon_nnue/players/sargon_plus.py`. Mantener los demás archivos de v0.6.88 y los parches de integración previos.

## Prueba corta (desde `scripts`)

```powershell
.\sargon_match.ps1 --brain ..\data\brains\brains.json --idA blitzy --idB s0001 --pairs 1 --max-plies 4 --csv ..\data\runs\probe089.csv --boost-audit-dir ..\data\runs\probe089_audit
```

Elegir rutas nuevas para CSV y auditoría. Verificar ausencia de `bestmove (none)`, existencia de `a_engine.jsonl`, `b_engine.jsonl`, `moves.jsonl`, y eventos `boost_search_metrics` con `turbo_mask=0`.

## Validación local
AST/sintaxis y comprobación de orden de inicialización, ZIP. No hay `python-chess` en este entorno para probar una partida real. Si persistiese `bestmove (none)`, inspeccionar los logs `.a.log` y `.b.log`, porque el UCI usa ese mensaje también para cualquier otra excepción.
