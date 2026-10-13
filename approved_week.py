#!/usr/bin/env python3
"""Publish an accepted weekly image manifest through the existing SSH framectl."""
import argparse
import base64
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import time

from PIL import Image

MANAGED = {'dinner-week'} | {'recipe-'+day for day in ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')}
LEGACY = {'sample-recipe-1', 'sample-recipe-2', 'sample-recipe-3'}
SHARED_CLIENT = '/Users/Shared/HermesFrameClient/framectl.py'


class ClientError(RuntimeError):
    pass


class Client:
    def __init__(self, argv):
        self.argv = list(argv)

    def call(self, *args, payload=None):
        result = subprocess.run(self.argv + list(args),
                                input=None if payload is None else json.dumps(payload),
                                capture_output=True, text=True, timeout=30)
        try:
            response = json.loads(result.stdout if result.returncode == 0 else result.stderr)
        except ValueError:
            raise ClientError('Client failed or returned invalid JSON') from None
        if result.returncode or not isinstance(response, dict) or response.get('error'):
            # Only this exact existing gateway error is safe to treat as absent.
            if isinstance(response, dict) and response.get('error') == 'Card not found':
                raise ClientError('Card not found')
            raise ClientError('Client rejected operation')
        return response


def prepare(manifest_path):
    path = Path(manifest_path)
    raw = path.read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict):
        raise ValueError('Manifest must be an object')
    week = manifest['week']
    if not isinstance(week, str) or datetime.date.fromisoformat(week).isoformat() != week:
        raise ValueError('Week must be an ISO date')
    cards = manifest['cards']
    if not isinstance(cards, list) or not cards:
        raise ValueError('Manifest needs cards')
    digest = hashlib.sha256()
    digest.update(len(raw).to_bytes(8, 'big') + raw)
    payloads, ids = [], []
    for card in cards:
        if not isinstance(card, dict):
            raise ValueError('Manifest cards must be objects')
        ident = card['id']
        if not isinstance(ident, str) or ident not in MANAGED or ident in ids:
            raise ValueError('Only unique dinner-week / recipe-mon..sun IDs are allowed')
        if card.get('title', '') != '' or card.get('focus', False) is not False:
            raise ValueError('Weekly cards require blank titles and focus false')
        content = (path.parent / card['path']).read_bytes()
        if not 0 < len(content) <= 8*1024*1024:
            raise ValueError('Image must be at most 8 MiB')
        with Image.open(io.BytesIO(content)) as image:
            if image.size != (1280, 800) or image.format not in ('PNG', 'JPEG', 'WEBP'):
                raise ValueError('Each rendered image must be 1280x800 PNG/JPEG/WebP')
            mime = {'PNG': 'png', 'JPEG': 'jpeg', 'WEBP': 'webp'}[image.format]
            image.load()
        digest.update(len(content).to_bytes(8, 'big') + content)
        payloads.append({'card': {'id': ident, 'type': 'image', 'title': '',
                                  'image': 'data:image/'+mime+';base64,'+base64.b64encode(content).decode()},
                         'focus': False})
        ids.append(ident)
    if 'dinner-week' not in ids or len(ids) < 2:
        raise ValueError('Include dinner-week and at least one unique recipe card')
    return week, digest.hexdigest(), payloads, ids


def read_ledger(path):
    if not path.exists():
        return {'version': 1, 'managed_ids': [], 'legacy_removed': False}
    ledger = json.loads(path.read_text())
    if not isinstance(ledger, dict):
        raise ValueError('Invalid publisher ledger')
    if ledger.get('version') != 1 or not isinstance(ledger.get('managed_ids'), list):
        raise ValueError('Invalid publisher ledger')
    if any(not isinstance(ident, str) or ident not in MANAGED for ident in ledger['managed_ids']):
        raise ValueError('Ledger contains unmanaged IDs; refusing cleanup')
    if not isinstance(ledger.get('legacy_removed'), bool):
        raise ValueError('Invalid legacy ledger state')
    if not isinstance(ledger.get('attempt', {}), dict):
        raise ValueError('Invalid attempt ledger')
    return ledger


def save_ledger(path, ledger):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(ledger, indent=2)+'\n')
    temp.chmod(0o600)
    os.replace(temp, path)


def publish(manifest_path, ledger_path, approval=None, apply=False, client=None,
            poll_timeout=15, poll_interval=.5):
    # Snapshot and decode every image before invoking the client, including status.
    week, digest, payloads, ids = prepare(manifest_path)
    if approval is not None:
        if (not isinstance(approval, dict) or approval.get('approved') is not True or approval.get('accepted_by') != 'Ian'
                or approval.get('week') != week or approval.get('sha256') != digest):
            raise ValueError('Approval mismatch: Ian must accept this week and exact manifest/image digest')
        if not isinstance(approval.get('source_message'), str) or not approval['source_message'].strip():
            raise ValueError('Approval source_message must be a nonempty string citing the actual accepting conversation message')
    elif apply:
        raise ValueError('--apply requires an explicit approval record')
    path = Path(ledger_path)
    ledger = read_ledger(path)
    cleanup = sorted(set(ledger['managed_ids'])-set(ids))
    if not ledger['legacy_removed']:
        cleanup += sorted(LEGACY)
    plan = {'week': week, 'sha256': digest, 'writes': ids, 'removes': cleanup}
    if not apply:
        return dict(plan, status='dry-run', approval_matches=approval is not None)
    if ledger.get('attempt', {}).get('status') in ('in_progress', 'partial'):
        raise ValueError('Prior partial publication requires manual reconciliation; no automatic repeat')
    if ledger.get('sha256') == digest:
        raise ValueError('This manifest was already published; no automatic repeat')
    if client is None:
        raise ValueError('Publication requires a client')
    attempt = {'week': week, 'sha256': digest, 'status': 'in_progress',
               'completed_writes': [], 'completed_removes': [], 'operation': None}
    ledger['attempt'] = attempt
    save_ledger(path, ledger)
    last_revision = None
    try:
        for payload in payloads:
            ident = payload['card']['id']
            attempt['operation'] = {'write': ident}
            save_ledger(path, ledger)
            response = client.call('json', '-', payload=payload)
            if response.get('ok') is not True or response.get('card_id') != ident:
                raise ClientError('Returned card ID did not match; write outcome uncertain')
            if type(response.get('revision')) is not int or response['revision'] < 0:
                raise ClientError('Invalid write revision; write outcome uncertain')
            last_revision = response['revision']
            attempt['completed_writes'].append(ident)
            attempt['operation'] = None
            save_ledger(path, ledger)
        # Never remove anything until every new card was acknowledged.
        for ident in cleanup:
            attempt['operation'] = {'remove': ident}
            save_ledger(path, ledger)
            try:
                response = client.call('remove', ident)
            except ClientError as error:
                if str(error) != 'Card not found':
                    raise
            else:
                if response.get('ok') is not True or type(response.get('revision')) is not int:
                    raise ClientError('Invalid removal acknowledgement')
                last_revision = response['revision']
            attempt['completed_removes'].append(ident)
            attempt['operation'] = None
            save_ledger(path, ledger)
    except Exception as error:
        attempt['status'] = 'partial'
        attempt['error'] = str(error)
        save_ledger(path, ledger)
        raise RuntimeError('Partial publication; completed writes: '+
                           ', '.join(attempt['completed_writes'])+'; consult ledger; '+str(error)) from error
    ledger.update(managed_ids=ids, legacy_removed=True, week=week, sha256=digest)
    attempt['status'] = 'complete'
    ledger['poll_verified'] = False
    save_ledger(path, ledger)
    # Demand a later poll than the first post-publication observation. Polls are
    # delivery evidence only: the API has no rendering acknowledgement.
    deadline = time.monotonic()+poll_timeout
    try:
        baseline = client.call('status')['last_poll']
        while time.monotonic() < deadline:
            time.sleep(min(poll_interval, max(0, deadline-time.monotonic())))
            status = client.call('status')
            if (status.get('recently_connected') is True and status['last_poll'] > baseline
                    and status['revision'] >= last_revision):
                ledger['poll_verified'] = True
                break
    except (ClientError, KeyError, TypeError, subprocess.TimeoutExpired):
        pass
    save_ledger(path, ledger)
    return dict(plan, status='published', poll_verified=ledger['poll_verified'], rendering_verified=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path)
    p.add_argument('--approval', type=Path, help='Explicit acceptance record, never generated by this tool')
    p.add_argument('--ledger', type=Path, required=True, help='Private persistent ledger, outside git')
    p.add_argument('--apply', action='store_true', help='Write only with exact matching approval')
    p.add_argument('--host', default='shell-e@ian-mini-m6.local')
    p.add_argument('--identity-file', help='Caller-supplied SSH identity path, passed to ssh -i without reading it')
    p.add_argument('--poll-timeout', type=float, default=15)
    a = p.parse_args()
    try:
        if not re.fullmatch(r'shell-e@[a-zA-Z0-9][a-zA-Z0-9.-]*', a.host):
            raise ValueError('Host must be shell-e@HOST')
        if not 0 <= a.poll_timeout <= 60:
            raise ValueError('Poll timeout must be between 0 and 60 seconds')
        approval = json.loads(a.approval.read_text()) if a.approval else None
        ssh_argv = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10']
        if a.identity_file is not None:
            ssh_argv += ['-i', a.identity_file]
        client = Client(ssh_argv + [a.host, '/usr/bin/python3', '-B', SHARED_CLIENT])
        result = publish(a.manifest, a.ledger, approval, a.apply, client, a.poll_timeout)
        print(json.dumps(result, indent=2))
        if a.apply and not result['poll_verified']:
            p.exit(2, 'Publication accepted; later poll unverified. Do not repeat writes.\n')
    except (ValueError, KeyError, OSError, RuntimeError) as error:
        p.exit(1, str(error)+'\n')


if __name__ == '__main__':
    main()
