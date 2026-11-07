"""Independent test of macOS platform resolution from brains.py."""
from pathlib import Path
import ast, json, sys
root=Path(__file__).resolve().parents[2]
source=(root/'Sargon-NNUE/src/sargon_nnue/brains.py').read_text()
module=ast.parse(source)
items=[n for n in module.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in {'PATH_KEYS','PLATFORM_VALUE_KEYS'} for t in n.targets)]
items += [n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='resolve_platform_paths']
ns={'os':type('O',(),{'name':'posix'})(), 'sys':type('S',(),{'platform':'darwin'})()}
exec(compile(ast.Module(body=items,type_ignores=[]),'brains.py','exec'),ns)
profile=json.loads((root/'Sargon-NNUE/etc/brains/brains.json').read_text())['brains']['emma']
resolved=ns['resolve_platform_paths'](profile)
assert resolved['engine-path'].endswith('/AlphaZero')
assert resolved['lc0-backend']=='eigen'
assert resolved['lc0-backend-options']==''
assert isinstance(resolved['lc0-weights'],str)
assert resolved['az-simulations']==1200
print('PASS: macOS brain platform paths and backend')
