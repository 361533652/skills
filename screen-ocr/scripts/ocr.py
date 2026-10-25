#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ocr.py - locate text on screen via Tesseract, return click coordinates.

Why this exists: some UIs have no UI Automation tree and no DOM
(games, canvas-rendered apps, remote desktop, Java/Qt custom-drawn windows).
The only way in is pixels.

Usage:
  python ocr.py find "登录"                  search whole screen
  python ocr.py find "登录" --min-conf 70    stricter
  python ocr.py find "登录" --region 0,0,1200,800
  python ocr.py dump                         all recognised text + coords
  python ocr.py read <image>                 OCR an existing file

Coordinates printed are ABSOLUTE screen pixels when capturing the screen,
or image-relative when reading a file (use --offset for absolute).
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

TESSERACT_CANDIDATES = [
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
]


def find_tesseract():
    for p in TESSERACT_CANDIDATES:
        if os.path.isfile(p):
            return p
    from shutil import which
    w = which('tesseract')
    if w:
        return w
    sys.stderr.write('ERR: tesseract not found. install: winget install UB-Mannheim.TesseractOCR\n')
    sys.exit(1)


def grab_screen(region=None, path=None):
    """Capture screen (or region) to PNG using PIL. Returns (path, (offset_x, offset_y))."""
    if path is None:
        path = os.path.join(tempfile.gettempdir(), '_ocr_grab.png')

    from PIL import ImageGrab
    import ctypes

    if region:
        x, y, w, h = region
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
        img.save(path)
        return path, (x, y)

    # whole virtual screen
    user32 = ctypes.windll.user32
    x = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
    y = user32.GetSystemMetrics(77)
    img = ImageGrab.grab(all_screens=True)
    img.save(path)
    return path, (x, y)


def run_ocr(texe, image, lang='chi_sim+eng', psm=3):
    """Run tesseract, return word list with bboxes.

    Upscaling matters a lot: tesseract works best around 300 DPI equivalent.
    A 5120px-wide virtual-screen capture gives ~10px tall glyphs, which it
    reads as noise. Scale 2x and most Chinese UI text becomes legible.
    """
    try:
        from PIL import Image
        im = Image.open(image)
        w, h = im.size
        # Target ~2400px on the long edge: tesseract wants roughly 30px tall
        # glyphs. Small crops (a nav bar) need 4x, big captures only 2x.
        long_edge = max(w, h)
        if long_edge < 800:
            scale = 4
        elif long_edge < 1600:
            scale = 3
        elif w < 3000:
            scale = 2
        else:
            scale = 1
        if scale > 1:
            im = im.convert('L').resize((w * scale, h * scale), Image.LANCZOS)
            upscaled = os.path.join(tempfile.gettempdir(), '_ocr_up.png')
            im.save(upscaled)
            image = upscaled
    except Exception:
        scale = 1

    base = os.path.join(tempfile.gettempdir(), '_ocr_res')
    cmd = [texe, image, base, '-l', lang, '--psm', str(psm), 'tsv']
    subprocess.run(cmd, capture_output=True)
    tsv = base + '.tsv'
    if not os.path.isfile(tsv):
        return []
    rows = []
    with open(tsv, 'r', encoding='utf-8', errors='ignore') as f:
        header = f.readline()
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 12:
                continue
            try:
                conf = float(parts[10])
            except ValueError:
                continue
            text = parts[11].strip()
            if not text or conf < 0:
                continue
            rows.append({
                'x': int(parts[6]) // scale, 'y': int(parts[7]) // scale,
                'w': int(parts[8]) // scale, 'h': int(parts[9]) // scale,
                'conf': conf, 'text': text,
                'line': int(parts[4]) if parts[4].isdigit() else 0,
            })
    return rows


def group_lines(rows):
    """Merge words on the same physical line into phrases."""
    if not rows:
        return []
    rows = sorted(rows, key=lambda r: (r['y'], r['x']))
    lines, cur = [], []
    for r in rows:
        if not cur:
            cur = [r]
            continue
        prev = cur[-1]
        same = abs((r['y'] + r['h'] / 2) - (prev['y'] + prev['h'] / 2)) < max(10, prev['h'] * 0.6)
        close = (r['x'] - (prev['x'] + prev['w'])) < 30
        if same and close:
            cur.append(r)
        else:
            lines.append(cur)
            cur = [r]
    if cur:
        lines.append(cur)

    out = []
    for ln in lines:
        x0 = min(w['x'] for w in ln)
        y0 = min(w['y'] for w in ln)
        x1 = max(w['x'] + w['w'] for w in ln)
        y1 = max(w['y'] + w['h'] for w in ln)
        txt = ''.join(w['text'] for w in ln)
        conf = sum(w['conf'] for w in ln) / len(ln)
        out.append({'x': x0, 'y': y0, 'w': x1 - x0, 'h': y1 - y0,
                    'text': txt, 'conf': conf})
    return out


def norm(s):
    return re.sub(r'\s+', '', s or '').strip()


def cmd_find(texe, args):
    region = None
    if args.region:
        region = tuple(int(v) for v in args.region.split(','))

    if getattr(args, 'image', None):
        # search inside an existing image file
        img = args.image
        off = (0, 0)
        rows = run_ocr(texe, img, args.lang, args.psm)
    else:
        img, off = grab_screen(region)
        rows = run_ocr(texe, img, args.lang, args.psm)

    lines = group_lines(rows)
    target = norm(args.text)
    hits = [l for l in lines if target and target in norm(l['text'])]

    if not hits:
        # retry with a tighter crop around each line's vertical band,
        # which helps when the full-screen pass merged rows badly
        cand = [l for l in lines if l['conf'] >= args.min_conf]
        print('NOT FOUND: %s  (recognised %d lines)' % (args.text, len(lines)))
        if cand:
            print('hint: nearby text ->')
            for l in cand[:10]:
                print('   "%s"  @%d,%d conf=%.0f' % (l['text'][:50],
                      off[0] + l['x'] + l['w'] // 2,
                      off[1] + l['y'] + l['h'] // 2, l['conf']))
        sys.exit(2)

    hits.sort(key=lambda l: -l['conf'])
    best = hits[0]
    absx = off[0] + best['x'] + best['w'] // 2
    absy = off[1] + best['y'] + best['h'] // 2
    print('%d,%d  conf=%.0f  w=%d h=%d  "%s"'
          % (absx, absy, best['conf'], best['w'], best['h'], best['text']))
    if not args.quiet:
        print('  (image %s, offset %d,%d, %d candidates)'
              % (os.path.basename(img), off[0], off[1], len(hits)))


def cmd_dump(texe, args):
    region = None
    if args.region:
        region = tuple(int(v) for v in args.region.split(','))
    img, off = grab_screen(region)
    rows = run_ocr(texe, img, args.lang, args.psm)
    lines = group_lines(rows)
    lines.sort(key=lambda l: (l['y'], l['x']))
    for l in lines:
        if l['conf'] < args.min_conf:
            continue
        ax = off[0] + l['x'] + l['w'] // 2
        ay = off[1] + l['y'] + l['h'] // 2
        print('%4d,%4d  %3.0f  %s' % (ax, ay, l['conf'], l['text'][:70]))


def cmd_read(texe, args):
    # read an existing image; --region crops inside it first
    img = args.image
    offset = (0, 0)
    if args.region:
        x, y, w, h = (int(v) for v in args.region.split(','))
        try:
            from PIL import Image
            im = Image.open(img).crop((x, y, x + w, y + h))
            cropped = os.path.join(tempfile.gettempdir(), '_ocr_crop.png')
            im.save(cropped)
            img = cropped
            offset = (x, y)
        except Exception as e:
            sys.stderr.write('ERR: crop failed: %s\n' % e)
    rows = run_ocr(texe, img, args.lang, args.psm)
    lines = group_lines(rows)
    lines.sort(key=lambda l: (l['y'], l['x']))
    for l in lines:
        if l['conf'] < args.min_conf:
            continue
        print('%4d,%4d  %3.0f  %s' % (offset[0] + l['x'] + l['w'] // 2,
                                      offset[1] + l['y'] + l['h'] // 2,
                                      l['conf'], l['text'][:70]))


def main():
    ap = argparse.ArgumentParser(description='OCR based screen text finder')
    ap.add_argument('cmd', choices=['find', 'find-b64', 'dump', 'read'])
    ap.add_argument('v1', nargs='?', help='text (find) / base64 (find-b64) / image path (read)')
    ap.add_argument('--lang', default='chi_sim+eng')
    ap.add_argument('--psm', type=int, default=3)
    ap.add_argument('--min-conf', type=float, default=60.0)
    ap.add_argument('--region', help='x,y,w,h')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    # find-b64: caller (PowerShell) sends UTF-8 base64 so argv stays ASCII
    text = None
    image = None
    if args.cmd == 'find-b64':
        import base64
        if not args.v1:
            sys.stderr.write('ERR: need base64 text\n')
            sys.exit(1)
        text = base64.b64decode(args.v1).decode('utf-8')
        cmd = 'find'
    elif args.cmd == 'find':
        if not args.v1:
            sys.stderr.write('ERR: need text\n')
            sys.exit(1)
        text = args.v1
        cmd = 'find'
    elif args.cmd == 'read':
        if not args.v1:
            sys.stderr.write('ERR: need image path\n')
            sys.exit(1)
        image = args.v1
        cmd = 'read'
    else:
        cmd = 'dump'

    args.text = text
    args.image = image

    texe = find_tesseract()

    if cmd == 'find':
        cmd_find(texe, args)
    elif cmd == 'dump':
        cmd_dump(texe, args)
    elif cmd == 'read':
        cmd_read(texe, args)


if __name__ == '__main__':
    main()
