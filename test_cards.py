import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from approved_week import Client, main, prepare, publish

ROOT = Path(__file__).resolve().parent

# A temporary subprocess implements the existing framectl contract. No SSH,
# gateway, credentials, source assets, or real frame are used.
FAKE = r'''
import json,sys
from pathlib import Path
p=Path(sys.argv[1]); state=json.loads(p.read_text()); args=sys.argv[2:]
state['calls'].append(args)
if args == ['json','-']:
    payload=json.load(sys.stdin); ident=payload['card']['id']
    state['writes']+=1
    if state.get('fail_write') == state['writes']:
        p.write_text(json.dumps(state)); print(json.dumps({'error':'fake failure'}),file=sys.stderr); sys.exit(1)
    state['deck'][ident]=payload
    state['revision']+=1
    response={'ok':True,'card_id':'wrong' if state.get('bad_id') else ident,'revision':state['revision']}
elif args[0] == 'remove':
    ident=args[1]
    if ident == state.get('fail_remove'):
        p.write_text(json.dumps(state)); print(json.dumps({'error':'fake failure'}),file=sys.stderr); sys.exit(1)
    if ident not in state['deck']:
        p.write_text(json.dumps(state)); print(json.dumps({'error':'Card not found'}),file=sys.stderr); sys.exit(1)
    del state['deck'][ident]; state['revision']+=1
    response={'ok':True,'revision':state['revision']}
else:
    state['polls']+=1
    response={'last_poll':state['polls'] if not state.get('stale_poll') else 0,
              'revision':state['revision'],'recently_connected':True}
p.write_text(json.dumps(state)); print(json.dumps(response))
'''


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.photo = self.root/'photo.png'
        Image.new('RGB', (80, 120), 'orange').save(self.photo)

    def test_collage_contains_whole_portraits_and_exif_orientation(self):
        from render_cards import collage

        left = self.root/'left.jpg'
        # Orientation 6 turns this landscape image into a complete portrait.
        image = Image.new('RGB', (120, 80), 'red')
        exif = Image.Exif(); exif[274] = 6
        image.save(left, exif=exif)
        right = self.root/'right.png'
        image = Image.new('RGB', (80, 120), 'blue')
        # Distinct top/bottom edges must survive contain (no crop).
        for y, color in ((0, 'white'), (119, 'lime')):
            for x in range(80):
                image.putpixel((x, y), Image.new('RGB', (1, 1), color).getpixel((0, 0)))
        image.save(right)
        result = collage(left, right)
        self.assertEqual(result.size, (1280, 800))
        self.assertEqual(result.getpixel((30, 400)), (22, 27, 25))
        self.assertGreater(result.getpixel((326, 20))[0], 240)
        self.assertEqual(result.getpixel((954, 400)), (0, 0, 255))
        self.assertEqual(result.getpixel((954, 16)), (255, 255, 255))
        self.assertEqual(result.getpixel((954, 783)), (0, 255, 0))

    def test_recipe_layout_and_literal_text(self):
        from render_cards import recipe

        data = {'title': 'Test <meal> & rice', 'ingredients': ['Rice', 'Water'],
                'steps': ['Add rice & water.', 'Cook until tender.'], 'note': 'Serve warm.'}
        result = recipe(data, self.photo)
        self.assertEqual(result.size, (1280, 800))
        self.assertEqual(result.getpixel((200, 400)), (255, 165, 0))
        self.assertTrue(all(abs(a-b) <= 1 for a, b in
                            zip(result.getpixel((450, 400)), (22, 27, 25))))
        # Text creates non-background pixels in the right column.
        self.assertGreater(len(set(result.crop((466, 24, 1256, 774)).getdata())), 2)

    def test_overflow_and_missing_steps_fail(self):
        from render_cards import recipe

        with self.assertRaisesRegex(ValueError, 'overflow'):
            recipe({'title': 'Test', 'ingredients': 'ingredient '*2000,
                    'steps': ['Cook.']}, self.photo)
        with self.assertRaisesRegex(ValueError, 'steps'):
            recipe({'title': 'Test', 'ingredients': 'Rice', 'steps': []}, self.photo)

    def test_cli_paths_json_and_blank_title_manifest(self):
        data = self.root/'recipe.json'
        data.write_text(json.dumps({'title': 'Test', 'ingredients': 'Rice', 'steps': ['Cook.'],
                                    'photo': 'photo.png'}))
        out = self.root/'card with spaces.png'
        manifest = self.root/'manifest.json'
        result = subprocess.run([sys.executable, '-B', str(ROOT/'render_cards.py'), 'recipe',
                                 str(data), '--output', str(out), '--manifest', str(manifest),
                                 '--week', '2026-10-19'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        card = json.loads(manifest.read_text())['cards'][0]
        self.assertEqual(card['title'], '')
        self.assertIs(card['focus'], False)
        with Image.open(out) as image:
            self.assertEqual(image.size, (1280, 800))
        result = subprocess.run([sys.executable, '-B', str(ROOT/'render_cards.py'), 'collage',
                                 str(self.photo), str(self.photo), '--output', str(out)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class PublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = self.root/'rendered.png'
        Image.new('RGB', (1280, 800), 'green').save(self.image)
        self.manifest = self.root/'manifest.json'
        self.manifest.write_text(json.dumps({'week': '2026-10-19', 'cards': [
            {'id': ident, 'path': 'rendered.png', 'title': '', 'focus': False}
            for ident in ('dinner-week', 'recipe-mon')]}))
        self.approval = {'approved': True, 'accepted_by': 'Ian', 'week': '2026-10-19',
                         'sha256': prepare(self.manifest)[1],
                         'source_message': 'Synthetic test conversation, message 2: Ian accepts the test menu.'}
        self.ledger = self.root/'ledger.json'
        self.fake = self.root/'fake client.py'
        self.fake.write_text(FAKE)
        self.state = self.root/'fake state.json'
        self.state.write_text(json.dumps({'calls': [], 'writes': 0, 'polls': 0, 'revision': 0,
                                         'deck': {ident: 'original' for ident in
                                                  ('clock', 'photo', 'photo-pair', 'other',
                                                   'sample-recipe-1', 'sample-recipe-2',
                                                   'sample-recipe-3', 'recipe-sun')}}))
        self.client = Client([sys.executable, '-B', str(self.fake), str(self.state)])

    def state_update(self, **kwargs):
        state = json.loads(self.state.read_text()); state.update(kwargs)
        self.state.write_text(json.dumps(state))

    def run_publish(self, **kwargs):
        return publish(self.manifest, self.ledger, self.approval, client=self.client,
                       poll_timeout=.2, poll_interval=.001, **kwargs)

    def test_default_dry_run_even_with_approval_has_no_calls_or_ledger(self):
        result = self.run_publish()
        self.assertEqual(result['status'], 'dry-run')
        self.assertEqual(json.loads(self.state.read_text())['calls'], [])
        self.assertFalse(self.ledger.exists())
        self.assertEqual(publish(self.manifest, self.ledger)['status'], 'dry-run')

    def test_cli_dry_run_does_not_use_ssh(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT/'approved_week.py'),
                                 str(self.manifest), '--ledger', str(self.ledger)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'dry-run')
        self.assertFalse(self.ledger.exists())

    def test_approval_required_and_mismatch(self):
        with self.assertRaisesRegex(ValueError, 'explicit approval'):
            publish(self.manifest, self.ledger, apply=True, client=self.client)
        for key, value in (('approved', False), ('accepted_by', 'someone'),
                           ('week', '2026-10-26'), ('sha256', '0'*64)):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'mismatch'):
                publish(self.manifest, self.ledger, dict(self.approval, **{key: value}),
                        apply=True, client=self.client)
        self.assertEqual(json.loads(self.state.read_text())['calls'], [])

    def test_source_message_required_before_any_calls_or_ledger_changes(self):
        missing = dict(self.approval, session_id='synthetic-test-session')
        del missing['source_message']
        invalid = [missing] + [dict(self.approval, source_message=value)
                               for value in (None, '', ' \t\n', 123, False, [], {})]
        for approval in invalid:
            for apply in (False, True):
                with self.subTest(approval=approval, apply=apply), self.assertRaisesRegex(ValueError, 'source_message'):
                    publish(self.manifest, self.ledger, approval, apply=apply, client=self.client)
        self.assertEqual(json.loads(self.state.read_text())['calls'], [])
        self.assertFalse(self.ledger.exists())

    def test_source_message_accepts_optional_session_metadata(self):
        for metadata in ({}, {'session_id': 'synthetic-test-session'}):
            with self.subTest(metadata=metadata):
                approval = dict(self.approval, **metadata)
                result = publish(self.manifest, self.ledger, approval, client=self.client)
                self.assertTrue(result['approval_matches'])
        self.assertEqual(json.loads(self.state.read_text())['calls'], [])
        self.assertFalse(self.ledger.exists())

    def test_manifest_and_image_changes_invalidate_acceptance(self):
        self.manifest.write_text(self.manifest.read_text()+'\n')
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            self.run_publish(apply=True)
        self.approval['sha256'] = prepare(self.manifest)[1]
        Image.new('RGB', (1280, 800), 'red').save(self.image)
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            self.run_publish(apply=True)
        self.assertEqual(json.loads(self.state.read_text())['calls'], [])

    def test_publication_preserves_photos_clock_and_untracked_cards(self):
        self.ledger.write_text(json.dumps({'version': 1, 'managed_ids': ['recipe-sun'],
                                           'legacy_removed': False}))
        result = self.run_publish(apply=True)
        self.assertTrue(result['poll_verified'])
        self.assertFalse(result['rendering_verified'])
        state = json.loads(self.state.read_text())
        for ident in ('clock', 'photo', 'photo-pair', 'other'):
            self.assertEqual(state['deck'][ident], 'original')
        self.assertNotIn('recipe-sun', state['deck'])
        for ident in ('sample-recipe-1', 'sample-recipe-2', 'sample-recipe-3'):
            self.assertNotIn(ident, state['deck'])
        self.assertEqual(state['calls'][:2], [['json', '-'], ['json', '-']])
        for ident in ('recipe-mon', 'dinner-week'):
            self.assertIs(state['deck'][ident]['focus'], False)
            self.assertEqual(state['deck'][ident]['card']['title'], '')
        ledger = json.loads(self.ledger.read_text())
        self.assertEqual(ledger['managed_ids'], ['dinner-week', 'recipe-mon'])
        self.assertEqual(self.ledger.stat().st_mode & 0o777, 0o600)
        with self.assertRaisesRegex(ValueError, 'already published'):
            self.run_publish(apply=True)

    def test_untracked_recipe_is_preserved_and_absent_legacy_is_ok(self):
        state = json.loads(self.state.read_text())
        del state['deck']['sample-recipe-1']
        self.state_update(deck=state['deck'])
        self.run_publish(apply=True)
        self.assertIn('recipe-sun', json.loads(self.state.read_text())['deck'])

    def test_invalid_last_image_prevents_any_client_calls(self):
        data = json.loads(self.manifest.read_text())
        data['cards'][-1]['path'] = 'missing.png'
        self.manifest.write_text(json.dumps(data))
        with self.assertRaises(FileNotFoundError):
            self.run_publish(apply=True)
        self.assertEqual(json.loads(self.state.read_text())['calls'], [])

    def test_unmanaged_ledger_cannot_remove_photo(self):
        self.ledger.write_text(json.dumps({'version': 1, 'managed_ids': ['photo'],
                                           'legacy_removed': True}))
        with self.assertRaisesRegex(ValueError, 'unmanaged'):
            self.run_publish(apply=True)
        self.assertEqual(json.loads(self.state.read_text())['calls'], [])

    def test_partial_write_stops_and_records_completed_writes(self):
        self.state_update(fail_write=2)
        with self.assertRaisesRegex(RuntimeError, 'Partial publication'):
            self.run_publish(apply=True)
        ledger = json.loads(self.ledger.read_text())
        self.assertEqual(ledger['attempt']['completed_writes'], ['dinner-week'])
        self.assertEqual(ledger['attempt']['operation'], {'write': 'recipe-mon'})
        self.assertEqual(ledger['attempt']['status'], 'partial')
        state = json.loads(self.state.read_text())
        self.assertEqual(state['calls'], [['json', '-'], ['json', '-']])
        self.assertIn('sample-recipe-1', state['deck'])
        with self.assertRaisesRegex(ValueError, 'manual reconciliation'):
            self.run_publish(apply=True)
        self.assertEqual(json.loads(self.state.read_text())['calls'], state['calls'])

    def test_bad_returned_id_records_uncertain_operation_and_stops(self):
        self.state_update(bad_id=True)
        with self.assertRaisesRegex(RuntimeError, 'card ID'):
            self.run_publish(apply=True)
        attempt = json.loads(self.ledger.read_text())['attempt']
        self.assertEqual(attempt['completed_writes'], [])
        self.assertEqual(attempt['operation'], {'write': 'dinner-week'})
        self.assertEqual(len(json.loads(self.state.read_text())['calls']), 1)

    def test_cleanup_failure_preserves_completed_write_record(self):
        self.state_update(fail_remove='sample-recipe-2')
        with self.assertRaisesRegex(RuntimeError, 'Partial publication'):
            self.run_publish(apply=True)
        ledger = json.loads(self.ledger.read_text())
        self.assertFalse(ledger['legacy_removed'])
        self.assertEqual(ledger['attempt']['completed_writes'], ['dinner-week', 'recipe-mon'])
        self.assertEqual(ledger['attempt']['completed_removes'], ['sample-recipe-1'])
        self.assertEqual(ledger['attempt']['operation'], {'remove': 'sample-recipe-2'})

    def test_next_week_overwrites_stable_ids_and_cleans_only_previous_managed(self):
        data = json.loads(self.manifest.read_text())
        data['cards'].append(dict(data['cards'][-1], id='recipe-tue'))
        self.manifest.write_text(json.dumps(data))
        self.approval['sha256'] = prepare(self.manifest)[1]
        self.run_publish(apply=True)
        before = len(json.loads(self.state.read_text())['calls'])
        data['week'] = '2026-10-26'
        data['cards'].pop()
        self.manifest.write_text(json.dumps(data))
        self.approval.update(week=data['week'], sha256=prepare(self.manifest)[1])
        self.run_publish(apply=True)
        state = json.loads(self.state.read_text())
        self.assertNotIn('recipe-tue', state['deck'])
        self.assertIn('recipe-sun', state['deck'])
        later = state['calls'][before:]
        self.assertEqual(later[:3], [['json', '-'], ['json', '-'], ['remove', 'recipe-tue']])
        self.assertEqual([a for a in later if a[0] == 'remove'], [['remove', 'recipe-tue']])

    def test_invalid_card_constraints_fail_without_writes(self):
        original = json.loads(self.manifest.read_text())
        for key, value in (('id', 'photo'), ('focus', True), ('title', 'Visible title')):
            data = json.loads(json.dumps(original)); data['cards'][-1][key] = value
            self.manifest.write_text(json.dumps(data))
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.run_publish(apply=True)
        self.assertEqual(json.loads(self.state.read_text())['calls'], [])

    def test_stale_poll_reports_accepted_without_rendering_claim(self):
        self.state_update(stale_poll=True)
        result = self.run_publish(apply=True)
        self.assertEqual(result['status'], 'published')
        self.assertFalse(result['poll_verified'])
        self.assertFalse(result['rendering_verified'])
        self.assertEqual(json.loads(self.ledger.read_text())['attempt']['status'], 'complete')


class PublishCliTest(unittest.TestCase):
    def test_ssh_argv_with_optional_identity_without_reads_or_live_calls(self):
        identity = '/caller/private/key with spaces'
        for options, host, identity_args in (
                ([], 'shell-e@ian-mini-m6.local', []),
                (['--identity-file', identity], 'shell-e@ian-mini-m6.local', ['-i', identity]),
                (['--identity-file', identity, '--host', 'shell-e@other.local'],
                 'shell-e@other.local', ['-i', identity])):
            with self.subTest(options=options), \
                    patch.object(sys, 'argv', ['approved_week.py', '/caller/week.json',
                                              '--ledger', '/caller/ledger.json'] + options), \
                    patch('approved_week.publish', return_value={'status': 'dry-run'}) as mock_publish, \
                    patch('approved_week.subprocess.run') as mock_run, \
                    patch.object(Path, 'read_bytes', side_effect=AssertionError('Unexpected file read')), \
                    patch.object(Path, 'read_text', side_effect=AssertionError('Unexpected file read')), \
                    patch('builtins.print'):
                main()
                mock_publish.assert_called_once()
                client = mock_publish.call_args.args[4]
                self.assertEqual(client.argv, ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10']
                                 + identity_args + [host, '/usr/bin/python3', '-B',
                                                    '/Users/Shared/HermesFrameClient/framectl.py'])
                mock_run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
