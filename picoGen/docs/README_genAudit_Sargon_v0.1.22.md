# picoGenus MON=4 — compatibilidad Sargon III v0.1.22

**Causa:** `genAudit.py` antiguo solo aceptaba `picogenus-pst-v1` (David), mientras que `genPST.py` v0.1.21 escribe `picogenus-sargon3-pst-v2`. La versión compatible de `genAudit.py` había quedado únicamente en el parche v0.1.19.

**Corrección:** el auditor acepta el modelo `genus_pst.json` (Sargon III v2, campos `format` y `parameters`), `PST_best.json` (diccionario plano de parámetros), el checkpoint generacional Sargon III (`global_best.parameters`) y el anterior formato David v1. Valida los nombres de los parámetros y avisa cuáles faltan/sobran, sin inferir ni cambiar coeficientes.

El archivo `gen_sargon_core.py` se incluye para que la dependencia de la auditoría llegue junto a ella. Ninguno de los entrenadores, sus funciones objetivo o checkpoints se modifica. La salida de `genAudit.py` sigue teniendo el mismo formato de auditoría.

## Uso

Descomprimir este ZIP en la raíz del repositorio `akkad` preservando rutas. Si MON=3 finalizó, ejecutar únicamente desde `picoGenus/tools/train`:

```powershell
.\run_genesis.ps1 --mon 4
```

## Pruebas

Se ejecutaron cinco pruebas de compatibilidad de lectura JSON y verificación sintáctica. No se corrió una auditoría completa de 24 posiciones con `python-chess`, ausente del entorno de prueba. El archivo `PST_best.json` y `genus_pst.json` deben contener los 29 coeficientes Sargon III esperados, con `PAWN_VALUE=100`.
