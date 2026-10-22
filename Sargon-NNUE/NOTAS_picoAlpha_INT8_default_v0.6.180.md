# Notas del parche v0.6.180

- `picoAlpha.exe` queda establecido como ejecutable INT8 por defecto.
- El ejecutable FP32 de referencia pasa a llamarse `picoAlpha32.exe`.
- `build_windows.ps1` elimina binarios legados `picoAlphaFP32.exe` y `picoAlphaInt8.exe` para evitar ambiguedades.
- No hay cambios funcionales en el motor ni en el adaptador UCI.
