"""Fail-closed regression suite for explicit external transport selection."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from nurse.config import read_brain
from nurse.uci import Nurse


class ExternalTypeContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'brains.json'

    def read(self, config):
        self.path.write_text(json.dumps({'brains': {'picoSargon': config}}), encoding='utf8')
        return read_brain(self.path, 'picoSargon')

    def test_missing_type_fails_even_with_valid_url(self):
        for player in ('external', 'null', None):
            cfg = {'url': 'picosargon.local:6110', 'player': player}
            with self.subTest(player=player), self.assertRaisesRegex(ValueError, 'type obligatorio'):
                self.read(cfg)

    def test_explicit_external_player_variants(self):
        for player in ('external', 'null', None):
            config = {'type': 'external', 'url': 'picosargon.local:6110'}
            if player is not None:
                config['player'] = player
            with self.subTest(player=player):
                cfg = self.read(config)
                self.assertEqual(cfg['type'], 'external')
                self.assertEqual(cfg['_type'], 'external')
                self.assertEqual((cfg['ipaddress'], cfg['port']), ('picosargon.local', 6110))

    def test_external_player_must_not_select_another_motor(self):
        for value in ('AlphaZero', {'windows': 'AlphaZero.exe'}, 'uci', 'sargon.py'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'type=external admite'):
                self.read({'type': 'external', 'player': value, 'url': 'picosargon.local:6110'})

    def test_missing_endpoint_never_defaults_to_localhost(self):
        with self.assertRaisesRegex(ValueError, 'sin destino TCP'):
            self.read({'type': 'external', 'player': 'null'})

    def test_different_endpoint_is_kept_verbatim(self):
        cfg = self.read({'type':'external','player':'external','url':'picosargon.local:6110'})
        self.assertNotEqual((cfg['ipaddress'],cfg['port']), ('127.0.0.1', 6200))


if __name__ == '__main__':
    unittest.main()
