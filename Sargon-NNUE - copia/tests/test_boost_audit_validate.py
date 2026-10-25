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
#* test_boost_audit_validate.py
#* Ejecuta pruebas de regresion para test boost audit validate
#* v0.6.153
#=================================================================================================================*
import json
import tempfile
import unittest
from pathlib import Path
from sargon_nnue.boost_audit_validate import validate

class ValidateAudit(unittest.TestCase):
    def test_complete_and_missing(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            (p/'manifest.json').write_text(json.dumps({'sides':{'a':{},'b':{}},'pairs':1}))
            fen='startfen'
            for side in 'ab':
                (p/f'{side}_engine.jsonl').write_text(json.dumps({'event':'boost_search_metrics',
                    'search_id':1,'root_fen':fen,'bestmove':'e2e4','elapsed_ms':10,
                    'nodes':20,'completed_depth':2,'counters':{},'timed_out':False})+'\n')
            records=[{'event':'move','game':1,'ply':1,'side':'A','fen':fen,'uci':'e2e4','response_ms':15},
                     {'event':'move','game':2,'ply':1,'side':'B','fen':fen,'uci':'e2e4','response_ms':15},
                     {'event':'game_end','game':1,'result':'1-0'},
                     {'event':'game_end','game':2,'result':'0-1'}]
            (p/'moves.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
            self.assertEqual(validate(p),0)
            records[0]['uci']='a2a3'
            (p/'moves.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
            self.assertEqual(validate(p),2)
if __name__=='__main__':unittest.main()
