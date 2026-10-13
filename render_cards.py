#!/usr/bin/env python3
"""Render portable 1280x800 image cards; no private assets or paths are embedded."""
import argparse
import io
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

import fitz
from PIL import Image, ImageOps
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

W, H = 1280, 800
BG, INK, MUTED, ACCENT = '#161B19', '#F1F0E7', '#B8C6BC', '#BBD7B2'


def photo(path):
    with Image.open(path) as source:
        return ImageOps.exif_transpose(source).convert('RGB')


def collage(left, right):
    """EXIF-correct, contain both complete images in equal portrait slots."""
    result = Image.new('RGB', (W, H), BG)
    for x, path in ((24, left), (652, right)):
        image = ImageOps.contain(photo(path), (604, 768))
        result.paste(image, (x + (604-image.width)//2, (H-image.height)//2))
    return result


def recipe(data, photo_path):
    """Fixed readable typography. Overflow is an error, never an auto-shrink."""
    for key in ('title', 'ingredients', 'steps'):
        if not data.get(key):
            raise ValueError('Recipe requires ' + key)
    if not isinstance(data['title'], str):
        raise ValueError('Recipe title must be text')
    ingredients = data['ingredients']
    if isinstance(ingredients, list) and all(isinstance(v, str) and v for v in ingredients):
        ingredients = '; '.join(ingredients)
    if not isinstance(ingredients, str):
        raise ValueError('Ingredients must be text or a list of text')
    steps = data['steps']
    if not isinstance(steps, list) or not all(isinstance(s, str) and s for s in steps):
        raise ValueError('Steps must be a nonempty list of text')
    stream = io.BytesIO()
    c = canvas.Canvas(stream, pagesize=(W, H))
    c.setFillColor(HexColor(BG))
    c.rect(0, 0, W, H, fill=1, stroke=0)
    image = ImageOps.fit(photo(photo_path), (414, 700))
    c.drawImage(ImageReader(image), 24, 76, width=414, height=700)

    def para(value, x, top, width, size, color=INK, bold=False, floor=24):
        if not isinstance(value, str):
            raise ValueError('Recipe text fields must be strings')
        try:
            value.encode('cp1252')
        except UnicodeEncodeError:
            raise ValueError('Unsupported recipe glyph: use text supported by Helvetica/WinAnsi') from None
        style = ParagraphStyle('frame', fontName='Helvetica-Bold' if bold else 'Helvetica',
                               fontSize=size, leading=size*1.18, textColor=HexColor(color))
        p = Paragraph(escape(value).replace('\n', '<br/>'), style)
        _, height = p.wrap(width, H)
        if top-height < floor:
            raise ValueError('Recipe overflow: shorten text or split the recipe; font sizes stay fixed')
        p.drawOn(c, x, top-height)
        return top-height

    if data.get('credit'):
        para(data['credit'], 24, 57, 414, 15, MUTED)
    x, width, y = 466, 790, 774
    if data.get('eyebrow'):
        y = para(data['eyebrow'], x, y, width, 17, ACCENT)-12
    y = para(data['title'], x, y, width, 37, bold=True)-10
    if data.get('meta'):
        y = para(data['meta'], x, y, width, 21, MUTED)-18
    y = para('INGREDIENTS', x, y, width, 20, ACCENT, True)-8
    y = para(ingredients, x, y, width, 25)-18
    y = para('METHOD', x, y, width, 20, ACCENT, True)-8
    for number, step in enumerate(steps, 1):
        y = para(f'{number}. {step}', x, y, width, 25)-12
    if data.get('note'):
        para(data['note'], x, y, width, 21, MUTED)
    c.showPage()
    c.save()
    with fitz.open(stream=stream.getvalue(), filetype='pdf') as doc:
        for block in doc[0].get_text('dict')['blocks']:
            for line in block.get('lines', []):
                for span in line['spans']:
                    a, b, d, e = span['bbox']
                    if not (0 <= a <= d <= W and 0 <= b <= e <= H):
                        raise ValueError('Recipe overflow: text extends outside the card')
        pix = doc[0].get_pixmap(alpha=False)
        return Image.frombytes('RGB', (pix.width, pix.height), pix.samples)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    pair = sub.add_parser('collage')
    pair.add_argument('left', type=Path)
    pair.add_argument('right', type=Path)
    r = sub.add_parser('recipe')
    r.add_argument('json', type=Path, help='Recipe JSON; photo path is relative to this file')
    r.add_argument('--photo', type=Path, help='Override JSON photo with caller path')
    for parser in (pair, r):
        parser.add_argument('--output', required=True, type=Path)
        parser.add_argument('--manifest', type=Path, help='Optional one-card manifest')
        parser.add_argument('--week', help='Week-start ISO date for a weekly manifest')
        parser.add_argument('--id', default='photo-pair' if parser is pair else 'recipe-mon')
    a = p.parse_args()
    try:
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', a.id):
            raise ValueError('Invalid card ID')
        if a.output.suffix.lower() not in ('.jpg', '.jpeg', '.png'):
            raise ValueError('Output must be JPEG or PNG')
        if a.command == 'collage':
            image = collage(a.left, a.right)
        else:
            data = json.loads(a.json.read_text())
            if not isinstance(data, dict):
                raise ValueError('Recipe JSON must be an object')
            path = a.photo or a.json.parent / data['photo']
            image = recipe(data, path)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        image.save(a.output, **({'quality': 95} if a.output.suffix.lower() != '.png' else {}))
        manifest = {'week': a.week, 'cards': [{'id': a.id, 'path': str(a.output.resolve()),
                                             'title': '', 'focus': False}]}
        if a.manifest:
            a.manifest.write_text(json.dumps(manifest, indent=2)+'\n')
        print(json.dumps(manifest))
    except (ValueError, KeyError, OSError) as error:
        p.exit(1, str(error)+'\n')


if __name__ == '__main__':
    main()
