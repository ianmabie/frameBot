#!/usr/bin/env python3
"""Prevalidate a rendered cookbook bundle, upload assets, then replace its index.

No deck operations, weekly approvals, source-photo downloads, or credential copies.
"""
import base64
import json
from pathlib import Path
from cookbook import manifest, validate_png, asset_path, THUMB_SIZE, DETAIL_SIZE


def prepare(path):
    path = Path(path)
    value = json.loads(path.read_text())
    clean = manifest(value)
    assets = {}
    for recipe in clean['recipes']:
        for key, size in [('thumbnail_path', THUMB_SIZE), ('detail_path', DETAIL_SIZE)]:
            remote = recipe[key]
            local = path.parent / 'assets' / remote.split('/')[-1]
            # Read only bundle-local assets, never source URLs or absolute paths.
            if not local.resolve().is_relative_to(path.parent.resolve()):
                raise ValueError('Asset escapes bundle directory')
            body = local.read_bytes()
            validate_png(body, size)
            if asset_path(body) != remote:
                raise ValueError('Asset hash mismatch: ' + local.name)
            assets[remote] = local
    return value, clean['revision'], assets


def publish(path, request, apply=False):
    value, revision, assets = prepare(path)  # No HTTP calls before complete validation.
    if not apply:
        return {'status': 'dry-run', 'revision': revision, 'recipes': len(value['recipes']), 'assets': len(assets)}
    for remote, local in assets.items():
        body = local.read_bytes()
        # Detect concurrent bundle edits before sending this asset.
        validate_png(body)
        if asset_path(body) != remote:
            raise ValueError('Bundle changed during upload')
        result = request('/cookbook/assets', {'image': 'data:image/png;base64,' + base64.b64encode(body).decode()})
        if result.get('asset_path') != remote or result.get('ok') is not True:
            raise ValueError('Gateway returned unexpected asset path')
    result = request('/cookbook/import', value)
    if result.get('revision') != revision or result.get('ok') is not True:
        raise ValueError('Gateway returned unexpected cookbook revision; inspect /cookbook before retrying')
    return dict(result, status='published', rendering_verified=False)
