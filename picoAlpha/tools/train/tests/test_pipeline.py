import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from common import connect,schema,quant_params

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/'test.pb'
    def run_script(self,name,*args):
        return subprocess.run([sys.executable,str(BASE/name),*map(str,args)],capture_output=True,text=True,check=True)
    def test_create_and_schema(self):
        self.run_script('create.py','--out',self.db)
        with connect(self.db) as db:
            self.assertEqual(db.execute('select count(*) from games').fetchone()[0],0)
            self.assertEqual(db.execute('select count(*) from positions').fetchone()[0],0)
    def test_sampler_complete_and_teacher_persistence(self):
        with connect(self.db) as db:
            schema(db)
            for idx in range(3):
                id=db.execute('insert into games(source_file,source_ordinal,headers_json,result,start_fen) values(?,?,?,?,?)',
                    (f'a{idx}.pgn',1,'{}','1-0','start')).lastrowid
                for ply in range(1,4):db.execute('insert into positions(game_id,ply,fen,played_uci,teacher_uci,teacher_value) values(?,?,?,?,?,?)',
                    (id,ply,'fen','e2e4','d2d4',0.5))
            db.commit()
        dst=Path(self.temp.name)/'sample.pb'
        self.run_script('sampler.py','--in',self.db,'--out',dst,'--sample','100','--seed','2')
        with connect(dst) as db:
            self.assertEqual(db.execute('select count(*) from games').fetchone()[0],3)
            self.assertEqual(db.execute('select count(*) from positions').fetchone()[0],9)
            self.assertEqual(db.execute('select count(*) from positions where teacher_uci="d2d4"').fetchone()[0],9)
        self.run_script('sampler.py','--in',self.db,'--out',dst,'--sample','0')
        with connect(dst) as db:self.assertEqual(db.execute('select count(*) from games').fetchone()[0],0)
    def test_model_shapes_and_export(self):
        try: import torch
        except ImportError:self.skipTest('torch unavailable')
        from model import build_model
        net=build_model();self.assertEqual(sum(p.numel() for p in net.parameters()),quant_params())
        indices=torch.tensor([0,12,768,779,11,770],dtype=torch.long)
        offsets=torch.tensor([0,4],dtype=torch.long)
        frm,to,v=net(indices,offsets)
        self.assertEqual(tuple(frm.shape),(2,64));self.assertEqual(tuple(to.shape),(2,64));self.assertEqual(tuple(v.shape),(2,))
        ck=Path(self.temp.name)/'best.pt'
        torch.save({'state_dict':net.state_dict(),'config':{'features':780,'hidden':16}},ck)
        out=Path(self.temp.name)/'weights.hpp'
        out_int8=Path(self.temp.name)/'weights_int8.pt'
        self.run_script('export.py','--in',ck,'--out',out,'--int8',out_int8)
        t=out.read_text();self.assertIn('W_INPUT[12480]',t);self.assertIn('W_VALUE[16]',t)
        quant=torch.load(out_int8,weights_only=True)
        self.assertEqual(quant['format'],'picoalpha-nnue-int8-v1')
        self.assertEqual(quant['weights']['W_INPUT'].dtype,torch.int8)

if __name__=='__main__': unittest.main()
