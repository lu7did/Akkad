# Hive v0.2.12
Base: v0.2.10 (v0.2.11 was not authorized for application).
Root candidate MultiPV summaries are diagnostic stderr lines (ℹ️), visible only at verbose=2, never sent to the external UCI client. The final consolidated info and bestmove remain unchanged at all levels. Worker parsing, selection and scheduling are unchanged. No YAML replacement.
Regression: simulated search through Session._search at all three verbosity levels, verifying two wire messages and diagnostic visibility. python-chess absent; stub used only for import, no board operations exercised. Live engine testing pending.
