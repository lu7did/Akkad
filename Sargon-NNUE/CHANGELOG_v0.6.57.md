# v0.6.57

- Repairs PowerShell 5.1 encoding/parser issue: ASCII-only source plus UTF-8 BOM.
- Uses .NET Framework-compatible Path.IsPathRooted for route handling.
- Formats floating-point arguments using invariant culture (decimal point) for Python CLI.
- Keeps training stages and algorithms unchanged.
