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
#* test_brainmaker_level_v06149.py
#* Ejecuta pruebas de regresion para test brainmaker level v06149
#* v0.6.153
#=================================================================================================================*
import contextlib, io, json, tempfile, unittest
from pathlib import Path
from sargon_nnue.sargon_brainmaker import level_report

class UnknownBrainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.brain = root / "brains.json"
        self.rally = root / "rally.json"
        self.brain.write_text(json.dumps({"brains":{"a":{"rating_elo":1000},"b":{"rating_elo":1000}}}), encoding="utf-8")
        self.rows = [{"match":1,"game":1,"white":"a","black":"b","result":"1-0"}]
    def tearDown(self):
        self.tmp.cleanup()
    def run_report(self, save=True):
        self.rally.write_text(json.dumps({"tournaments":{"t":{"ranking":{"resultados":self.rows}}}}), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = level_report(self.brain,self.rally,32,save)
        return result,output.getvalue()
    def test_unknown_is_excluded_from_both_ratings(self):
        self.rows.extend([
          {"match":2,"game":1,"white":"a","black":"missing","result":"0-1"},
          {"match":3,"game":1,"white":"missing","black":"b","result":"1-0"}])
        result,log = self.run_report()
        self.assertEqual(result,0)
        profiles=json.loads(self.brain.read_text())["brains"]
        self.assertEqual(profiles["a"]["rating_elo"],1016)
        self.assertEqual(profiles["b"]["rating_elo"],984)
        self.assertNotIn("missing",profiles)
        self.assertIn("no registrados excluidos=2",log)
    def test_only_unknown_match_does_not_write(self):
        self.rows=[{"match":8,"game":1,"white":"a","black":"missing","result":"1-0"}]
        previous=self.brain.read_bytes()
        with self.assertRaisesRegex(ValueError,"entre brainid registrados"):
            self.run_report()
        self.assertEqual(previous,self.brain.read_bytes())
    def test_missing_rating_remains_400(self):
        brains=json.loads(self.brain.read_text())
        del brains["brains"]["b"]["rating_elo"]
        self.brain.write_text(json.dumps(brains))
        self.run_report()
        new=json.loads(self.brain.read_text())["brains"]
        self.assertEqual(new["b"]["rating_elo"],399.02)
