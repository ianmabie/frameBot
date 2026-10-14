"""Synthetic cookbook checks. Handler harness executes real API paths without sockets."""
import base64
import copy
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from unittest.mock import Mock

from cookbook import manifest, validate_recipes, validate_png, asset_path, MAX_ASSET
from cookbook_import import prepare, publish
from gateway import Store, make_handler

ROOT = Path(__file__).resolve().parent


def synthetic_recipe(n=0):
    return {'id': 'bowl-' + str(n), 'title': 'Bean and vegetable bowl ' + str(n),
            'category': 'Beans' if n % 2 else 'Vegetables', 'minutes': 20, 'servings': 3,
            'ingredients': ['2 cups cooked beans', '2 cups cooked brown rice',
                            '3 cups chopped broccoli', '1 tbsp olive oil', '1/4 tsp salt'],
            'steps': ['Heat oil in a skillet over medium heat.',
                      'Add broccoli and 1/4 cup water. Cover and cook 5 minutes.',
                      'Stir in beans, rice and salt. Heat 5 minutes and divide among 3 bowls.'],
            'note': 'Estimated time uses cooked rice and beans.', 'photo': 'photos/bowl.png',
            'photo_credit': 'Synthetic test image', 'photo_source_url': 'https://example.org/photo',
            'photo_representative': True, 'source_urls': ['https://example.org/recipe'],
            'original_or_adapted': 'Original synthetic recipe for testing'}


def png(w, h):
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + bytes([60, 90, 50]) * w) * h)) + chunk(b'IEND', b''))


class CookbookTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        (self.root/'config.json').write_text(json.dumps({'read_token': 'read', 'push_token': 'push'}))
        self.store = Store(self.root)
        self.thumb, self.detail = png(384, 200), png(1280, 800)
        self.value = {'version': 1, 'recipes': [dict(synthetic_recipe(i),
                      thumbnail_path=asset_path(self.thumb), detail_path=asset_path(self.detail)) for i in range(50)]}

    def tearDown(self): self.temp.cleanup()

    def request(self, path, payload=None, token='push', address='127.0.0.1', method=None):
        Handler = make_handler(self.store)
        h = Handler.__new__(Handler)
        h.path = path; h.client_address = (address, 12345)
        body = json.dumps(payload).encode() if payload is not None else b''
        h.headers = {'Authorization': 'Bearer ' + token, 'Content-Length': str(len(body))}
        h.rfile = io.BytesIO(body); h.wfile = io.BytesIO(); h.connection = Mock()
        result = {}
        def answer(status, data): result.update(status=status, data=data)
        h.answer = answer; h.send_response = lambda status: result.update(status=status)
        h.send_header = Mock(); h.end_headers = Mock()
        (h.do_POST if (method or ('GET' if payload is None else 'POST')) == 'POST' else h.do_GET)()
        if 'data' not in result: result['data'] = h.wfile.getvalue()
        return result

    def upload(self):
        for body in (self.thumb, self.detail):
            result = self.request('/cookbook/assets', {'image': 'data:image/png;base64,' + base64.b64encode(body).decode()})
            self.assertEqual(result['status'], 200)

    def bundle(self):
        bundle = self.root/'bundle'; (bundle/'assets').mkdir(parents=True)
        for body in (self.thumb, self.detail): (bundle/'assets'/asset_path(body).split('/')[-1]).write_bytes(body)
        path = bundle/'manifest.json'; path.write_text(json.dumps(self.value)); return path

    def test_50_independent_of_full_deck_persistence_and_stable_revision(self):
        for i in range(18): self.store.push({'id': 'deck-' + str(i), 'title': 'Untouched'})
        before = copy.deepcopy(self.store.state); disk = self.store.path.read_bytes()
        self.upload()
        result = self.request('/cookbook/import', self.value)
        self.assertEqual(result['status'], 200); self.assertEqual(result['data']['recipes'], 50)
        revision = result['data']['revision']
        again = copy.deepcopy(self.value)
        again['recipes'][0] = dict(reversed(list(again['recipes'][0].items())))
        self.assertEqual(self.request('/cookbook/import', again)['data']['revision'], revision)
        self.assertEqual(Store(self.root).cookbook, self.store.cookbook)
        self.assertEqual(self.store.state, before); self.assertEqual(self.store.path.read_bytes(), disk)
        with self.assertRaisesRegex(ValueError, 'Maximum 20'): self.store.push({'id': 'deck-21'})
        self.assertEqual(self.request('/cookbook', token='read')['data']['revision'], revision)
        self.assertEqual(self.request(asset_path(self.detail), token='read')['data'], self.detail)
        self.assertEqual(self.store.cookbook_path.stat().st_mode & 0o777, 0o600)

    def test_auth_guards_and_admitted_lan_only(self):
        for token in ('', 'push', 'delete-only'):
            self.assertEqual(self.request('/cookbook', token=token)['status'], 401)
            self.assertEqual(self.request(asset_path(self.detail), token=token)['status'], 401)
        for path, payload in [('/cookbook/import', self.value), ('/cookbook/assets', {'image': 'bad'})]:
            self.assertEqual(self.request(path, payload, token='read')['status'], 401)
            self.assertEqual(self.request(path, payload, token='delete-only')['status'], 401)
            self.assertEqual(self.request(path, payload, address='192.168.1.42')['status'], 403)
        self.store.config.update(public_push=True, public_push_networks=['192.168.1.0/24'])
        payload = {'image': 'data:image/png;base64,' + base64.b64encode(self.thumb).decode()}
        self.assertEqual(self.request('/cookbook/assets', payload, token='', address='192.168.1.42')['status'], 200)
        self.assertEqual(self.request('/cookbook/assets', payload, token='', address='8.8.8.8')['status'], 403)
        self.assertEqual(self.request('/cookbook', token='', address='192.168.1.42')['status'], 401)

    def test_all_malformed_manifests_leave_index_and_deck_unchanged(self):
        self.upload(); self.store.import_cookbook(self.value)
        before = self.store.cookbook_path.read_bytes(); deck = copy.deepcopy(self.store.state)
        mutations = [('id', '../bad'), ('minutes', True), ('minutes', 36), ('servings', 4),
                     ('ingredients', ['beans']), ('steps', ['one']), ('photo', '../secret'),
                     ('photo_representative', False), ('photo_source_url', 'file:///private'),
                     ('thumbnail_path', asset_path(self.detail)), ('detail_path', '/media/' + '0'*64 + '.png'),
                     ('detail_path', '/cookbook/assets/' + '0'*64 + '.png')]
        for key, val in mutations:
            value = copy.deepcopy(self.value); value['recipes'][-1][key] = val
            with self.subTest(key=key, val=val):
                self.assertEqual(self.request('/cookbook/import', value)['status'], 400)
                self.assertEqual(self.store.cookbook_path.read_bytes(), before)
                self.assertEqual(self.store.state, deck)
        for value in ({'version': 1, 'recipes': []}, dict(self.value, revision='forged'),
                      {'version': 1, 'recipes': self.value['recipes'] + [self.value['recipes'][0]]}):
            self.assertEqual(self.request('/cookbook/import', value)['status'], 400)
            self.assertEqual(self.store.cookbook_path.read_bytes(), before)

    def test_failed_atomic_replace_does_not_change_memory_or_disk(self):
        from unittest.mock import patch
        self.upload(); self.store.import_cookbook(self.value)
        before = copy.deepcopy(self.store.cookbook); disk = self.store.cookbook_path.read_bytes()
        value = copy.deepcopy(self.value); value['recipes'][0]['note'] = 'Changed note'
        with patch('gateway.os.replace', side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError): self.store.import_cookbook(value)
        self.assertEqual(self.store.cookbook, before); self.assertEqual(self.store.cookbook_path.read_bytes(), disk)

    def test_png_bounds_corruption_and_upload_without_index_mutation(self):
        original = copy.deepcopy(self.store.cookbook)
        for bad in (self.thumb[:-5], b'not png', png(385, 200), self.thumb + b'trailer', b'x'*(MAX_ASSET+1)):
            with self.assertRaises(ValueError): validate_png(bad)
        corrupted = bytearray(self.thumb); corrupted[50] ^= 1
        with self.assertRaises(ValueError): validate_png(bytes(corrupted))
        self.assertEqual(self.request('/cookbook/assets', {'image': 'data:image/png;base64,bad!'})['status'], 400)
        self.assertEqual(self.store.cookbook, original); self.assertFalse(self.store.cookbook_path.exists())

    def test_corrupt_uploaded_asset_is_repaired_before_import(self):
        self.upload()
        path = self.store.cookbook_media / asset_path(self.detail).split('/')[-1]
        path.write_bytes(b'corrupt cache')
        with self.assertRaises(ValueError): self.store.import_cookbook(self.value)
        self.assertFalse(self.store.cookbook_path.exists())
        self.upload()
        self.assertEqual(self.store.import_cookbook(self.value)['recipes'], 50)

    def test_failed_client_upload_keeps_previous_offline_index(self):
        self.upload(); self.store.import_cookbook(self.value)
        before = self.store.cookbook_path.read_bytes()
        value = copy.deepcopy(self.value); value['recipes'][0]['note'] = 'New revision'
        path = self.bundle(); path.write_text(json.dumps(value)); calls = []
        def interrupted(endpoint, payload):
            calls.append(endpoint)
            if len(calls) == 2: raise OSError('Synthetic network loss')
            return self.request(endpoint, payload)['data']
        with self.assertRaises(OSError): publish(path, interrupted, apply=True)
        self.assertNotIn('/cookbook/import', calls)
        self.assertEqual(self.store.cookbook_path.read_bytes(), before)

    def test_import_client_prevalidation_dryrun_and_real_api_paths(self):
        path = self.bundle(); calls = []
        def client(endpoint, payload):
            calls.append(endpoint)
            result = self.request(endpoint, payload)
            self.assertEqual(result['status'], 200)
            return result['data']
        dry = publish(path, client); self.assertEqual(dry['recipes'], 50); self.assertEqual(calls, [])
        result = publish(path, client, apply=True)
        self.assertEqual(result['revision'], manifest(self.value)['revision'])
        self.assertEqual(calls, ['/cookbook/assets', '/cookbook/assets', '/cookbook/import'])
        self.assertEqual(self.store.state['revision'], 0)
        (path.parent/'assets'/asset_path(self.detail).split('/')[-1]).unlink(); calls.clear()
        with self.assertRaises(FileNotFoundError): publish(path, client, apply=True)
        self.assertEqual(calls, [])

    def test_cli_dryrun_needs_no_server_or_token(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT/'framectl.py'), '--url',
                                 'http://127.0.0.1:1', 'cookbook-import', str(self.bundle())], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'dry-run')

    def test_exact_catalog_contract(self):
        entries = [synthetic_recipe(i) for i in range(50)]
        self.assertEqual(len(validate_recipes(entries, exact_count=50)), 50)
        with self.assertRaises(ValueError): validate_recipes(entries[:-1], exact_count=50)
        entries[-1]['id'] = entries[0]['id']
        with self.assertRaises(ValueError): validate_recipes(entries)


class CookbookRenderTest(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        (self.root/'photos').mkdir(); Image.new('RGB', (600, 600), '#638b56').save(self.root/'photos/bowl.png')
        self.catalog = self.root/'catalog.json'
        self.entries = [synthetic_recipe(i) for i in range(50)]
        self.catalog.write_text(json.dumps({'recipes': self.entries}))

    def tearDown(self): self.temp.cleanup()

    def test_50_rendered_bundle_valid_and_offline_complete(self):
        from render_cards import render_cookbook
        result = render_cookbook(self.catalog, self.root/'rendered')
        value, revision, assets = prepare(result['manifest'])
        self.assertEqual(len(value['recipes']), 50); self.assertEqual(result['revision'], revision)
        self.assertGreaterEqual(len(assets), 51)
        self.assertTrue(all(path.is_file() for path in assets.values()))
        # Persist one fixture for owner visual review only when explicitly requested.
        if os.environ.get('FRAME_SYNTHETIC_PREVIEW'):
            import shutil
            shutil.copyfile(next(path for remote, path in assets.items() if remote == value['recipes'][0]['detail_path']), os.environ['FRAME_SYNTHETIC_PREVIEW'])

    def test_overflow_last_recipe_fails_no_partial_bundle(self):
        from render_cards import render_cookbook
        self.entries[-1]['steps'] = ['Very long method ' * 28] * 5
        self.catalog.write_text(json.dumps(self.entries))
        with self.assertRaisesRegex(ValueError, 'bowl-49.*overflow'):
            render_cookbook(self.catalog, self.root/'overflow')
        self.assertFalse((self.root/'overflow').exists())
        self.assertEqual(list(self.root.glob('.cookbook-*')), [])


if __name__ == '__main__': unittest.main()
