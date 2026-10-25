#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* test_boost_audit_coverage.py
#* Ejecuta pruebas de regresion para test boost audit coverage
#* v0.6.153
#=================================================================================================================*
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from sargon_nnue.boost_audit_coverage import analyze

def test_coverage(tmp_path):
    p = tmp_path / 'a_engine.jsonl'
    p.write_text(json.dumps({'event':'boost_search_metrics','schema':2,'boost_mask':1,
          'turbo_mask':2, 'counters':{'1:history_updates':3},
          'turbo_counters':{'2:emitted_events':2}})+'\n', encoding='utf-8')
    rows=analyze(str(tmp_path),str(tmp_path/'coverage.csv'))
    assert next(r for r in rows if r['kind']=='boost' and r['index']==1)['status']=='observed'
    assert next(r for r in rows if r['kind']=='turbo' and r['index']==2)['status']=='observed'
    assert next(r for r in rows if r['kind']=='boost' and r['index']==2)['status']=='disabled'
