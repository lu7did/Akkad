"""Regresión: v0.1.21 empaqueta la dependencia importada por genPST."""
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_sargon_core_is_present_and_exports_api():
    pst=ast.parse((ROOT/'genPST.py').read_text(encoding='utf-8'))
    module=ast.parse((ROOT/'gen_sargon_core.py').read_text(encoding='utf-8'))
    imports=[n for n in ast.walk(pst) if isinstance(n,ast.ImportFrom) and n.module=='gen_sargon_core']
    assert len(imports)==1
    names={n.name for n in imports[0].names}
    exports={n.name for n in module.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    exports|={target.id for n in module.body if isinstance(n,ast.Assign) for target in n.targets if isinstance(target,ast.Name)}
    assert names<=exports

if __name__=='__main__':
    test_sargon_core_is_present_and_exports_api()
    print('OK: genPST.py -> gen_sargon_core.py')
