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
#* test_boost_audit_report.py
#* Synthetic, chess-independent integration test for saved audit data.
#* v0.6.153
#=================================================================================================================*
"""Synthetic, chess-independent integration test for saved audit data."""
from __future__ import annotations
import csv
import json
import tempfile
import unittest
from pathlib import Path
from sargon_nnue.boost_audit_report import report

class AuditReportTests(unittest.TestCase):
    def test_report_and_paired_positions(self):
        with tempfile.TemporaryDirectory() as base:
            root=Path(base)/'match_001';root.mkdir()
            (root/'manifest.json').write_text(json.dumps({'sides':{'a':{'depth':3,'qdepth':2,'tmax':15000,'network':'same.npz'},'b':{'depth':3,'qdepth':2,'tmax':15000,'network':'same.npz'}}}),encoding='utf-8')
            moves=[dict(event='move',game=1,ply=1,side='A',brain='smart_boost',player='sargon-plus',evaluator='npz',boost='0x80',turbo='0',fen='same-fen',uci='e2e4',response_ms=23.0),dict(event='move',game=2,ply=1,side='B',brain='smart_base',player='sargon-plus',evaluator='npz',boost='0',turbo='0',fen='same-fen',uci='e2e4',response_ms=40.0)]
            (root/'moves.jsonl').write_text('\n'.join(json.dumps(e) for e in moves),encoding='utf-8')
            for side,mask in [('a',0x80),('b',0)]:
                (root/f'{side}_engine.jsonl').write_text(json.dumps(dict(event='boost_search_metrics',root_fen='same-fen',boost_mask=mask,turbo_mask=0,nodes=400,elapsed_ms=20,counters={'8:reduced_moves':3} if mask else {})),encoding='utf-8')
            result=Path(base)/'report.csv'
            self.assertEqual(report(base,result),0)
            with result.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),2)
            with result.with_name('report_paired.csv').open(encoding='utf-8-sig',newline='') as f:paired=list(csv.DictReader(f))
            self.assertEqual(len(paired),1)
            self.assertEqual(paired[0]['same_move'],'True')
            self.assertTrue(result.with_name('report_moves.csv').exists())

if __name__=='__main__': unittest.main()
