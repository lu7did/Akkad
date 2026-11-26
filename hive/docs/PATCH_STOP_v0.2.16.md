# STOP / recuperación — Hive 0.2.16, picoSargon X86 0.2.67
Base Hive: v0.2.15. Base picoSargon: akkad(20261124-175149).zip, CMake 0.2.65.

- El host C++ mantiene un lector UCI activo y ejecuta go en un hilo de búsqueda; stop y quit activan la señal atómica que consume Engine. Se conserva la última iteración completa; si no hay ninguna, se devuelve un movimiento legal sin inventar score UCI.
- Hive envía stop al motor pendiente, espera bestmove hasta 500 ms y sincroniza con isready/readyok hasta 500 ms. Si falla, descarta el transporte. El monitor vuelve a intentar conexiones locales UCI estáticas, igual que TCP, según retry_seconds. No se reasigna un motor reservado o ocupado.
- Hive recoge resultados disponibles hasta 1.2 s adicionales, limitado por el deadline de reloj cuando existe; si no hay evaluación al cancelar, devuelve un movimiento legal sin score inventado. Los eventos de cancelación son específicos de cada búsqueda.
- No se modifica la distribución, evaluación ni el algoritmo de búsqueda. Recompilar picoSargon X86 antes de reiniciar Hive.

Validación: compilación CMake Release en Linux con MULTICORE ON; stop y reutilización del mismo proceso real con bashful.bin; prueba aislada de Endpoint.analyze con transporte simulado; sintaxis Python. No se compiló MSVC ni se hizo prueba integral con FICS o recuperación real tras fallo de transporte. No se incluye binario ni configuración.
