"""Cookbook schema and bounded PNG assets. Independent of the weekly card deck.

Standard library only: the owner-installed gateway needs no rendering packages.
"""
import hashlib
import json
import re
import struct
import zlib
from pathlib import PurePosixPath
from urllib.parse import urlsplit

MAX_RECIPES = 50
MAX_ASSET = 1536 * 1024
THUMB_SIZE = (384, 200)
DETAIL_SIZE = (1280, 800)
ASSET_RE = r'/cookbook/assets/[a-f0-9]{64}\.png'
FIELDS = {'id', 'title', 'category', 'minutes', 'servings', 'ingredients', 'steps',
          'note', 'photo', 'photo_credit', 'photo_source_url', 'photo_representative',
          'source_urls', 'original_or_adapted'}


def text(value, key, limit, empty=False):
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
        raise ValueError('Invalid ' + key)
    if any(ord(c) < 32 and c not in '\n\t' for c in value):
        raise ValueError('Invalid control character in ' + key)
    return value


def url(value, key):
    text(value, key, 1000)
    p = urlsplit(value)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('Invalid ' + key)
    return value  # Attribution only. Never fetched by the gateway or Android app.


def validate_recipes(entries, rendered=False, exact_count=None):
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_RECIPES:
        raise ValueError('Cookbook requires 1..50 recipes')
    if exact_count is not None and len(entries) != exact_count:
        raise ValueError('Catalog requires exactly ' + str(exact_count) + ' recipes')
    result, ids = [], set()
    for entry in entries:
        required = FIELDS | ({'thumbnail_path', 'detail_path'} if rendered else set())
        if not isinstance(entry, dict) or set(entry) != required:
            raise ValueError('Recipe fields must match cookbook schema')
        r = dict(entry)
        ident = r['id']
        if not isinstance(ident, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', ident) or ident in ids:
            raise ValueError('Invalid or duplicate recipe id')
        ids.add(ident)
        for key, limit, empty in [('title', 90, False), ('category', 32, False),
                                  ('note', 300, True), ('photo_credit', 180, False),
                                  ('original_or_adapted', 300, False)]:
            text(r[key], key, limit, empty)
        if type(r['minutes']) is not int or not 10 <= r['minutes'] <= 35:
            raise ValueError('minutes must be an estimated integer from 10 to 35')
        if type(r['servings']) is not int or r['servings'] != 3:
            raise ValueError('servings must be 3')
        for key, minimum, maximum, limit in [('ingredients', 1, 18, 180), ('steps', 3, 5, 500)]:
            if not isinstance(r[key], list) or not minimum <= len(r[key]) <= maximum:
                raise ValueError('Invalid ' + key + ' count')
            for value in r[key]:
                text(value, key, limit)
        for value in r['ingredients']:
            if not re.search(r'[0-9¼½¾⅓⅔⅛⅜⅝⅞]', value):
                raise ValueError('Each ingredient must include a quantity: ' + value)
        text(r['photo'], 'photo', 240)
        path = PurePosixPath(r['photo'])
        if path.is_absolute() or len(path.parts) < 2 or path.parts[0] != 'photos' or '..' in path.parts or '\\' in r['photo']:
            raise ValueError('photo must be a relative path under photos/')
        if r['photo_representative'] is not True:
            raise ValueError('photo_representative must be true')
        url(r['photo_source_url'], 'photo_source_url')
        if not isinstance(r['source_urls'], list) or not 1 <= len(r['source_urls']) <= 10:
            raise ValueError('Invalid source_urls')
        for value in r['source_urls']:
            url(value, 'source_urls')
        if rendered:
            for key in ('thumbnail_path', 'detail_path'):
                if not isinstance(r[key], str) or not re.fullmatch(ASSET_RE, r[key]):
                    raise ValueError('Invalid ' + key)
        result.append(r)
    return result


def manifest(value):
    if not isinstance(value, dict) or set(value) != {'version', 'recipes'} or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Expected cookbook manifest {version:1, recipes:[...]}')
    clean = {'version': 1, 'recipes': validate_recipes(value['recipes'], rendered=True)}
    encoded = json.dumps(clean, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    if len(encoded) > 512 * 1024:
        raise ValueError('Cookbook index exceeds 512 KiB')
    return dict(clean, revision=hashlib.sha256(encoded).hexdigest())


def empty_index():
    return {'version': 1, 'revision': 'empty', 'recipes': []}


def validate_png(data, expected=None):
    """Validate fixed RGB/RGBA noninterlaced PNG structure, CRC and scanlines.

    A narrow renderer format avoids decoder bombs on the Android 6 device.
    """
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_ASSET or not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Cookbook asset must be a PNG up to 1.5 MiB')
    offset, size, channels, compressed, ended = 8, None, None, bytearray(), False
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError('Truncated PNG')
        length, kind = struct.unpack('>I4s', data[offset:offset+8])
        end = offset + length + 12
        if end > len(data):
            raise ValueError('Truncated PNG chunk')
        chunk = data[offset+8:end-4]
        if zlib.crc32(kind + chunk) & 0xffffffff != struct.unpack('>I', data[end-4:end])[0]:
            raise ValueError('Invalid PNG CRC')
        if size is None and kind != b'IHDR':
            raise ValueError('PNG requires IHDR first')
        if kind == b'IHDR':
            if size is not None or length != 13:
                raise ValueError('Invalid PNG header')
            w, h, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', chunk)
            size = (w, h)
            if size not in (THUMB_SIZE, DETAIL_SIZE) or (expected and size != expected):
                raise ValueError('Wrong cookbook PNG dimensions')
            if depth != 8 or color not in (2, 6) or compression or filtering or interlace:
                raise ValueError('Use 8-bit RGB/RGBA noninterlaced PNG')
            channels = 3 if color == 2 else 4
        elif kind == b'IDAT':
            compressed.extend(chunk)
        elif kind == b'IEND':
            if length or end != len(data):
                raise ValueError('Invalid PNG ending')
            ended = True
        elif kind[:1].isupper():
            raise ValueError('Unsupported critical PNG chunk')
        offset = end
    if not ended or not compressed:
        raise ValueError('Incomplete PNG')
    stride = size[0] * channels + 1
    limit = stride * size[1]
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(bytes(compressed), limit + 1)
        if len(raw) != limit or not decoder.eof or decoder.unused_data or any(raw[i] > 4 for i in range(0, len(raw), stride)):
            raise ValueError('Invalid PNG scanlines')
    except zlib.error as e:
        raise ValueError('Invalid PNG compression') from e
    return size


def asset_path(data):
    return '/cookbook/assets/' + hashlib.sha256(data).hexdigest() + '.png'
