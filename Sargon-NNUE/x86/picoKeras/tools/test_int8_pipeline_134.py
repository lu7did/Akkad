import ast
from pathlib import Path
p=Path(__file__).with_name('int8_pipeline.py')
s=p.read_text(encoding='utf8')
ast.parse(s)
assert "choices=['direct', 'clone']" in s
assert "if a.source == 'clone':" in s
assert 'original = keras.models.load_model' in s
assert "report['tensorflow_version']" in s
print('PASS: sintaxis y rutas direct/clone presentes (no prueba conversión TensorFlow)')
