#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
bgauto.py - background window automation for Windows.

Three capabilities that work while the target window is NOT in the foreground:

  1. capture  - Windows Graphics Capture (WGC) grabs the window from the DWM
                compositor, so occlusion/minimisation does not matter.
  2. click/key- PostMessage delivers input straight to the window's message
                queue. No focus steal, no cursor hijack.
  3. find     - OpenCV template matching locates a UI element and returns its
                window-relative centre, ready to feed into click.

Everything degrades gracefully: if WGC is unavailable it falls back to
PrintWindow, then to a screen-region grab. A removed dependency never crashes
the tool - it prints the exact install command instead.

Usage:
  python bgauto.py deps                          check/install dependencies
  python bgauto.py list [--filter TEXT]          list candidate windows
  python bgauto.py capture --title T --out F     background screenshot
  python bgauto.py grab --title T --box X,Y,W,H --out F    save a template
  python bgauto.py find --title T --template F [--threshold 0.8]
  python bgauto.py click --title T --x N --y N
  python bgauto.py key --title T --key f
  python bgauto.py clickfind --title T --template F     find then click

All coordinates are WINDOW-RELATIVE (client area), which is what PostMessage
needs. This keeps scripts resolution-independent.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wintypes
import os
import subprocess
import sys
import time

# ---------------------------------------------------------------- deps


REQUIRED = {
    'cv2': 'opencv-python',
    'numpy': 'numpy',
    'windows_capture': 'windows-capture',
}


def missing_deps() -> list:
    out = []
    for mod, pkg in REQUIRED.items():
        try:
            __import__(mod)
        except ImportError:
            out.append(pkg)
    return out


def cmd_deps(args):
    miss = missing_deps()
    print('python      : %s' % sys.version.split()[0])
    for mod, pkg in REQUIRED.items():
        try:
            m = __import__(mod)
            ver = getattr(m, '__version__', '?')
            print('  OK      %-18s (%s) %s' % (pkg, mod, ver))
        except ImportError:
            print('  MISSING %-18s (%s)' % (pkg, mod))
    if not miss:
        print('\nall dependencies present')
        return 0
    cmd = [sys.executable, '-m', 'pip', 'install'] + miss
    print('\ninstall with:\n  ' + ' '.join(cmd))
    if args.install:
        print('\ninstalling...')
        r = subprocess.run(cmd)
        return r.returncode
    return 1


# ---------------------------------------------------------------- win32


user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MOUSEMOVE = 0x0200
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
WM_ACTIVATE = 0x0006
WA_ACTIVE = 1
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002


def set_dpi_aware():
    """Without this, GetWindowRect returns scaled values on HiDPI displays and
    every coordinate is silently wrong."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PER_MONITOR_AWARE_V2
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def win_title(hwnd) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ''
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def win_class(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def win_pid(hwnd) -> int:
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def list_windows(visible_only=True):
    out = []

    def cb(hwnd, _):
        if visible_only and not user32.IsWindowVisible(hwnd):
            return True
        t = win_title(hwnd)
        if t:
            out.append({'hwnd': hwnd, 'title': t, 'class': win_class(hwnd), 'pid': win_pid(hwnd)})
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def find_window(title=None, class_name=None, pid=None, exact=False):
    """Locate a window. Returns dict or None. Raises on ambiguous title match
    only when exact=False and several candidates look equally good - we pick
    the first and report the count so callers can narrow it down."""
    cands = list_windows()
    if pid:
        cands = [c for c in cands if c['pid'] == pid]
    if class_name:
        cands = [c for c in cands if c['class'] == class_name]
    if title:
        if exact:
            cands = [c for c in cands if c['title'] == title]
        else:
            cands = [c for c in cands if title.lower() in c['title'].lower()]
    if not cands:
        return None
    c = cands[0]
    c['candidates'] = len(cands)
    return c


def client_rect(hwnd):
    r = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def get_foreground():
    return user32.GetForegroundWindow()


def is_foreground(hwnd):
    return get_foreground() == hwnd


# ---------------------------------------------------------------- capture


def capture_wgc(hwnd, timeout=6.0, retries=4):
    """Windows Graphics Capture. Works on occluded / background windows.

    Returns (ndarray BGRA or None, note).

    Retries matter: a window that was just created often fails with
    "Failed to convert item to GraphicsCaptureItem" because its composition
    surface is not ready yet. Backing off and retrying fixes it.
    """
    try:
        import windows_capture
    except ImportError:
        return None, 'windows_capture not installed'
    try:
        import numpy as np
    except ImportError:
        return None, 'numpy not installed'

    last_err = None
    for attempt in range(retries):
        holder = {'frame': None, 'err': None}
        try:
            cap = windows_capture.WindowsCapture(
                window_hwnd=int(hwnd),
                cursor_capture=False,
                draw_border=False,
            )
        except Exception as e:
            last_err = 'WGC init: %s' % e
            time.sleep(0.4 * (attempt + 1))
            continue

        @cap.event
        def on_frame_arrived(frame, control):
            try:
                holder['frame'] = np.asarray(frame.frame_buffer).copy()
            except Exception as e:
                holder['err'] = 'frame decode: %s' % e
            try:
                control.stop()
            except Exception:
                pass

        @cap.event
        def on_closed():
            pass

        try:
            cap.start()
        except Exception as e:
            last_err = str(e)
            # the classic not-ready-yet error; wait and retry
            time.sleep(0.5 * (attempt + 1))
            continue

        if holder['frame'] is not None:
            return holder['frame'], 'wgc'
        last_err = holder['err'] or 'no frame delivered'
        time.sleep(0.3)

    return None, 'wgc failed after %d tries: %s' % (retries, last_err)


def capture_geometry(hwnd, cap_shape):
    """Work out how capture pixels map onto the window's CLIENT area.

    WGC returns the window's *visual* bounds, which exclude the invisible
    resize borders that GetWindowRect includes (Windows 11 reserves ~7-8px on
    the left, right and bottom). Client coordinates therefore sit at a small
    positive offset inside the capture - measured as (1, 51) on a 100%-scaled
    1920x1023 Win11 notepad, where 51 is the title-bar height.

    Getting this wrong silently clicks the wrong place, so it is computed from
    the window metrics rather than assumed, and `calibrate` can verify it.
    """
    wr = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(wr))
    org = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(org))
    cr = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(cr))

    win_w = wr.right - wr.left
    win_h = wr.bottom - wr.top
    cli_w = cr.right - cr.left
    cli_h = cr.bottom - cr.top

    cap_h, cap_w = cap_shape[0], cap_shape[1]

    # invisible resize border, split evenly between left and right
    border_x = max(0, (win_w - cap_w) // 2)
    border_y = 0

    off_x = org.x - wr.left - border_x
    off_y = org.y - wr.top - border_y

    return {
        'client_offset': (off_x, off_y),
        'window_size': (win_w, win_h),
        'client_size': (cli_w, cli_h),
        'capture_size': (cap_w, cap_h),
        'border': (border_x, border_y),
    }


def cap_to_client(geo, x, y):
    ox, oy = geo['client_offset']
    return x - ox, y - oy


def client_to_cap(geo, x, y):
    ox, oy = geo['client_offset']
    return x + ox, y + oy


def capture_printwindow(hwnd):
    """GDI PrintWindow with PW_RENDERFULLCONTENT. Works for some GPU windows
    when WGC is unavailable; returns black for others."""
    try:
        from PIL import Image
    except ImportError:
        return None, 'PIL not installed'

    l, t, w, h = client_rect(hwnd)
    if w <= 0 or h <= 0:
        return None, 'zero-size client area'

    hdc = user32.GetDC(hwnd)
    if not hdc:
        return None, 'GetDC failed'
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(memdc, bmp)
    # PW_RENDERFULLCONTENT = 0x2
    ok = user32.PrintWindow(hwnd, memdc, 0x2)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [('biSize', ctypes.c_uint32), ('biWidth', ctypes.c_int32),
                    ('biHeight', ctypes.c_int32), ('biPlanes', ctypes.c_uint16),
                    ('biBitCount', ctypes.c_uint16), ('biCompression', ctypes.c_uint32),
                    ('biSizeImage', ctypes.c_uint32), ('biXPelsPerMeter', ctypes.c_int32),
                    ('biYPelsPerMeter', ctypes.c_int32), ('biClrUsed', ctypes.c_uint32),
                    ('biClrImportant', ctypes.c_uint32)]

    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bi), 0)

    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(memdc)
    user32.ReleaseDC(hwnd, hdc)

    if not ok:
        return None, 'PrintWindow returned 0'
    img = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1)
    return img, 'printwindow'


def capture_any(hwnd, prefer='wgc'):
    """Try capture backends in order. Returns (PIL.Image | ndarray, backend)."""
    order = []
    if prefer == 'wgc':
        order = ['wgc', 'printwindow']
    else:
        order = ['printwindow', 'wgc']

    notes = []
    for method in order:
        if method == 'wgc':
            arr, note = capture_wgc(hwnd)
            if arr is not None:
                return arr, 'wgc'
            notes.append('wgc: ' + str(note))
        else:
            img, note = capture_printwindow(hwnd)
            if img is not None:
                # reject all-black results: that is the classic failure mode
                try:
                    import numpy as np
                    a = np.asarray(img)
                    if float(a[:, :, :3].mean()) < 2.0:
                        notes.append('printwindow: black frame')
                        continue
                except Exception:
                    pass
                return img, 'printwindow'
            notes.append('printwindow: ' + str(note))
    return None, '; '.join(notes)


def to_bgr(frame):
    """Normalise whatever capture returned into a BGR uint8 array."""
    import numpy as np
    if isinstance(frame, np.ndarray):
        a = frame
    else:
        a = np.asarray(frame)
    if a.ndim == 2:
        import cv2
        return cv2.cvtColor(a, cv2.COLOR_GRAY2BGR)
    if a.shape[2] == 4:
        return a[:, :, :3]
    return a


def save_image(frame, path):
    import cv2
    bgr = to_bgr(frame)
    ok = cv2.imwrite(path, bgr)
    # cv2.imwrite silently fails on non-ASCII paths in some builds
    if not ok or not os.path.isfile(path):
        import numpy as np
        from PIL import Image
        Image.fromarray(bgr[:, :, ::-1]).save(path)
    return path


# ---------------------------------------------------------------- matching


def template_match(haystack_bgr, template_path, threshold=0.8, method=None):
    """Return the best match of template inside haystack.

    Uses multi-scale matching because the same UI element renders at different
    pixel sizes across resolutions and in-game scale settings.
    """
    import cv2
    import numpy as np

    tpl = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if tpl is None:
        # non-ASCII path fallback
        from PIL import Image
        tpl = np.asarray(Image.open(template_path).convert('RGB'))[:, :, ::-1]

    hay_h, hay_w = haystack_bgr.shape[:2]
    best = {'score': -1.0, 'x': 0, 'y': 0, 'w': 0, 'h': 0, 'scale': 1.0,
            'method': 'none'}

    scales = (1.0, 0.9, 1.1, 0.8, 1.25, 0.7, 1.4)

    def consider(score, loc, tw, th, scale, method_name):
        if score > best['score']:
            best.update({'score': float(score), 'x': int(loc[0]), 'y': int(loc[1]),
                         'w': int(tw), 'h': int(th), 'scale': scale,
                         'method': method_name})

    # ---- pass 1: plain template matching (best for static UI) ----
    for scale in scales:
        t = tpl if scale == 1.0 else cv2.resize(
            tpl, (max(4, int(tpl.shape[1] * scale)), max(4, int(tpl.shape[0] * scale))),
            interpolation=cv2.INTER_AREA)
        if t.shape[0] > hay_h or t.shape[1] > hay_w:
            continue
        res = cv2.matchTemplate(haystack_bgr, t, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, maxloc = cv2.minMaxLoc(res)
        consider(maxv, maxloc, t.shape[1], t.shape[0], scale, 'template')

    # ---- pass 2: edge-based matching (best for animated / lit scenes) ----
    # Games re-render every frame, so raw pixels shift. Comparing Canny edges
    # ignores lighting and particle animation, which is exactly what breaks
    # plain matching on a 3D scene.
    try:
        tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
        hay_gray = cv2.cvtColor(haystack_bgr, cv2.COLOR_BGR2GRAY)
        tpl_edge = cv2.Canny(tpl_gray, 60, 160)
        hay_edge = cv2.Canny(hay_gray, 60, 160)
        if tpl_edge.sum() > 0:
            for scale in scales:
                t = tpl_edge if scale == 1.0 else cv2.resize(
                    tpl_edge,
                    (max(4, int(tpl_edge.shape[1] * scale)), max(4, int(tpl_edge.shape[0] * scale))),
                    interpolation=cv2.INTER_AREA)
                if t.shape[0] > hay_h or t.shape[1] > hay_w:
                    continue
                res = cv2.matchTemplate(hay_edge, t, cv2.TM_CCOEFF_NORMED)
                _, maxv, _, maxloc = cv2.minMaxLoc(res)
                # edge matches score differently; require a slightly lower bar
                consider(maxv * 0.98, maxloc, t.shape[1], t.shape[0], scale, 'edge')
    except Exception:
        pass

    # ---- pass 3: normalised cross-correlation on smoothed images ----
    # Handles gradients / glow around game UI panels.
    try:
        tpl_blur = cv2.GaussianBlur(tpl, (5, 5), 0)
        hay_blur = cv2.GaussianBlur(haystack_bgr, (5, 5), 0)
        for scale in scales:
            t = tpl_blur if scale == 1.0 else cv2.resize(
                tpl_blur,
                (max(4, int(tpl_blur.shape[1] * scale)), max(4, int(tpl_blur.shape[0] * scale))),
                interpolation=cv2.INTER_AREA)
            if t.shape[0] > hay_h or t.shape[1] > hay_w:
                continue
            res = cv2.matchTemplate(hay_blur, t, cv2.TM_CCOEFF_NORMED)
            _, maxv, _, maxloc = cv2.minMaxLoc(res)
            consider(maxv * 0.99, maxloc, t.shape[1], t.shape[0], scale, 'blur')
    except Exception:
        pass

    best['cx'] = best['x'] + best['w'] // 2
    best['cy'] = best['y'] + best['h'] // 2
    best['ok'] = best['score'] >= threshold
    return best


# ---------------------------------------------------------------- input


def make_lparam(x, y):
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


def post_click(hwnd, x, y, button='left', activate=True):
    """Deliver a click via PostMessage. The window does NOT need focus.

    A synthetic WM_ACTIVATE is sent first because some applications ignore
    mouse messages while they believe they are inactive.
    """
    if activate:
        user32.PostMessageW(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)
        time.sleep(0.02)
    lp = make_lparam(x, y)
    if button == 'right':
        dn, up, mk = WM_RBUTTONDOWN, WM_RBUTTONUP, MK_RBUTTON
    else:
        dn, up, mk = WM_LBUTTONDOWN, WM_LBUTTONUP, MK_LBUTTON
    a = user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lp)
    b = user32.PostMessageW(hwnd, dn, mk, lp)
    time.sleep(0.05)
    c = user32.PostMessageW(hwnd, up, 0, lp)
    return bool(a or b or c)


def find_input_child(hwnd):
    """Find the deepest child control that receives keyboard input.

    Measured behaviour: posting WM_CHAR to the TOP-LEVEL window does nothing,
    while posting to the actual Edit control works. Most apps have one
    input-hungry child, so locate it once and target that.
    """
    found = []

    def walk(h, depth=0):
        if depth > 8:
            return
        child = user32.FindWindowExW(h, 0, None, None)
        while child:
            cls = win_class(child).lower()
            if cls in ('edit', 'richedit20w', 'richedit50w', 'textfield',
                       'scintilla', 'editcontrol'):
                found.append((0, child))
            elif 'edit' in cls or 'text' in cls:
                found.append((1, child))
            walk(child, depth + 1)
            child = user32.FindWindowExW(h, child, None, None)

    walk(hwnd)
    found.sort(key=lambda x: x[0])
    return found[0][1] if found else 0


def post_text(hwnd, text, activate=True):
    """Type text into a background window via WM_CHAR on its input child."""
    edit = find_input_child(hwnd)
    target = edit if edit else hwnd
    if activate:
        user32.PostMessageW(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)
        time.sleep(0.02)
    try:
        for ch in text:
            user32.PostMessageW(target, WM_CHAR, ord(ch), 0)
            time.sleep(0.005)
        return True, target
    except Exception:
        return False, target


def post_key(hwnd, key, down_time=0.05):
    """PostMessage a virtual key to the window's input child.

    Keys must target the child control - posting to the frame is silently
    dropped by most applications.
    """
    vk = 0
    if len(key) == 1:
        vk = user32.VkKeyScanW(ord(key)) & 0xFF
    else:
        name = key.upper()
        special = {
            'ENTER': 0x0D, 'RETURN': 0x0D, 'ESC': 0x1B, 'ESCAPE': 0x1B,
            'SPACE': 0x20, 'TAB': 0x09, 'BACKSPACE': 0x08,
            'UP': 0x26, 'DOWN': 0x28, 'LEFT': 0x25, 'RIGHT': 0x27,
        }
        if name in special:
            vk = special[name]
        elif len(name) == 2 and name[0] == 'F' and name[1].isdigit():
            vk = 0x6F + int(name[1])
        elif len(name) == 2 and name[0] == 'F' and name[1:].isdigit():
            vk = 0x6F + int(name[1:])
        elif len(name) == 1 and name.isalnum():
            vk = ord(name)
        elif name.startswith('VK'):
            vk = int(name[2:], 16)
    if not vk:
        return False, 'unknown key: %s' % key

    edit = find_input_child(hwnd)
    target = edit if edit else hwnd

    user32.PostMessageW(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)
    scan = user32.MapVirtualKeyW(vk, 0)
    lp_down = (scan << 16) | 1
    lp_up = lp_down | (1 << 30) | (1 << 31)
    user32.PostMessageW(target, WM_KEYDOWN, vk, lp_down)
    # text controls usually need the character message as well
    user32.PostMessageW(target, WM_CHAR, vk, lp_down)
    time.sleep(down_time)
    user32.PostMessageW(target, WM_KEYUP, vk, lp_up)
    return True, 'vk=0x%02X -> %d' % (vk, target)


# ---------------------------------------------------------------- commands


def _resolve(args):
    w = find_window(title=args.title, class_name=getattr(args, 'class_name', None),
                    pid=getattr(args, 'pid', None), exact=getattr(args, 'exact', False))
    if not w:
        print('WINDOW NOT FOUND')
        print('  filter: title~%r class=%r pid=%r'
              % (getattr(args, 'title', None), getattr(args, 'class_name', None),
                 getattr(args, 'pid', None)))
        print('  use "list" to see candidates')
        sys.exit(2)
    return w


def cmd_list(args):
    wins = list_windows()
    if args.filter:
        wins = [w for w in wins if args.filter.lower() in w['title'].lower()]
    if not wins:
        print('(no windows)')
        return 0
    for w in wins:
        print('%-10d %-22s pid=%-7d %s' % (w['hwnd'], w['class'][:22], w['pid'], w['title'][:70]))
    print('\n%d window(s)' % len(wins))
    return 0


def cmd_capture(args):
    w = _resolve(args)
    frame, backend = capture_any(w['hwnd'])
    if frame is None:
        print('CAPTURE FAILED: %s' % backend)
        return 1
    save_image(frame, args.out)
    bgr = to_bgr(frame)
    print('%s  %dx%d  backend=%s' % (args.out, bgr.shape[1], bgr.shape[0], backend))
    print('  window: %s' % w['title'][:60])
    print('  foreground: %s (background capture %s)'
          % (is_foreground(w['hwnd']), 'ok' if not is_foreground(w['hwnd']) else 'n/a'))
    if args.verify:
        import numpy as np
        m = float(bgr.mean())
        print('  mean px = %.1f  %s' % (m, '(valid)' if m >= 2 else '(BLACK - suspect)'))
    return 0


def cmd_grab(args):
    """Capture a window and crop a region out of it to use as a template."""
    w = _resolve(args)
    frame, backend = capture_any(w['hwnd'])
    if frame is None:
        print('CAPTURE FAILED: %s' % backend)
        return 1
    bgr = to_bgr(frame)
    x, y, cw, ch = (int(v) for v in args.box.split(','))
    crop = bgr[y:y + ch, x:x + cw]
    if crop.size == 0:
        print('CROP EMPTY: box %s outside %dx%d' % (args.box, bgr.shape[1], bgr.shape[0]))
        return 1
    save_image(crop, args.out)
    print('%s  %dx%d crop from (%d,%d)' % (args.out, crop.shape[1], crop.shape[0], x, y))
    return 0


def cmd_find(args):
    w = _resolve(args)
    frame, backend = capture_any(w['hwnd'])
    if frame is None:
        print('CAPTURE FAILED: %s' % backend)
        return 1
    bgr = to_bgr(frame)
    geo = capture_geometry(w['hwnd'], bgr.shape)
    r = template_match(bgr, args.template, threshold=args.threshold)
    cx, cy = cap_to_client(geo, r['cx'], r['cy'])
    if not r['ok']:
        print('NOT FOUND  best=%.3f (need %.2f)  nearest=%d,%d  backend=%s'
              % (r['score'], args.threshold, cx, cy, backend))
        return 2
    print('%d,%d  score=%.3f  %dx%d  scale=%.2f'
          % (cx, cy, r['score'], r['w'], r['h'], r['scale']))
    print('  CLIENT coords (ready for click)  backend=%s  cap-offset=%s  cap=%dx%d'
          % (backend, geo['client_offset'], bgr.shape[1], bgr.shape[0]))
    return 0


def cmd_click(args):
    w = _resolve(args)
    fg_before = get_foreground()
    ok = post_click(w['hwnd'], args.x, args.y, button=args.button)
    time.sleep(0.15)
    fg_after = get_foreground()
    print('%s click (%d,%d) on "%s"' % ('sent' if ok else 'FAILED', args.x, args.y, w['title'][:40]))
    print('  focus stolen: %s' % (fg_after != fg_before))
    return 0 if ok else 1


def cmd_key(args):
    w = _resolve(args)
    fg_before = get_foreground()
    ok, info = post_key(w['hwnd'], args.key)
    time.sleep(0.1)
    fg_after = get_foreground()
    print('%s key=%s %s' % ('sent' if ok else 'FAILED', args.key, info))
    print('  focus stolen: %s' % (fg_after != fg_before))
    return 0 if ok else 1


def cmd_type(args):
    """Type a whole string into the window's input child."""
    w = _resolve(args)
    fg_before = get_foreground()
    ok, target = post_text(w['hwnd'], args.text)
    time.sleep(0.15)
    fg_after = get_foreground()
    edit = find_input_child(w['hwnd'])
    print('%s typed %d chars -> child %d' % ('sent' if ok else 'FAILED',
                                             len(args.text), target))
    print('  input child detected: %s' % (edit or 'none (fell back to frame)'))
    print('  focus stolen: %s' % (fg_after != fg_before))
    if not edit:
        print('  WARNING: no input child found. Text may be dropped.')
        print('           Some apps require real focus - see skill notes.')
    return 0 if ok else 1


def cmd_clickfind(args):
    w = _resolve(args)
    frame, backend = capture_any(w['hwnd'])
    if frame is None:
        print('CAPTURE FAILED: %s' % backend)
        return 1
    bgr = to_bgr(frame)
    geo = capture_geometry(w['hwnd'], bgr.shape)
    r = template_match(bgr, args.template, threshold=args.threshold)
    if not r['ok']:
        print('NOT FOUND  best=%.3f (need %.2f)' % (r['score'], args.threshold))
        return 2
    cx, cy = cap_to_client(geo, r['cx'], r['cy'])
    fg_before = get_foreground()
    post_click(w['hwnd'], cx, cy)
    time.sleep(0.2)
    fg_after = get_foreground()
    print('clicked (%d,%d) score=%.3f on "%s"'
          % (cx, cy, r['score'], w['title'][:40]))
    print('  focus stolen: %s' % (fg_after != fg_before))


def cmd_geom(args):
    """Print how capture pixels map to client coordinates."""
    w = _resolve(args)
    frame, backend = capture_any(w['hwnd'])
    if frame is None:
        print('CAPTURE FAILED: %s' % backend)
        return 1
    bgr = to_bgr(frame)
    geo = capture_geometry(w['hwnd'], bgr.shape)
    print('window   : %s' % w['title'][:60])
    print('  window size   : %dx%d' % geo['window_size'])
    print('  client size   : %dx%d' % geo['client_size'])
    print('  capture size  : %dx%d  (backend=%s)' % (geo['capture_size'] + (backend,)))
    print('  invisible brdr: %s' % (geo['border'],))
    print('  client offset in capture: %s' % (geo['client_offset'],))
    print()
    print('  capture(x,y) -> client(x,y):  client = capture - %s' % (geo['client_offset'],))
    print('  use "calibrate" to verify this empirically')
    return 0


def cmd_calibrate(args):
    """Verify the computed offset by locating the on-screen client area inside
    the capture. Requires the window to be visible (not occluded), so it is a
    diagnostic, not something the normal path depends on."""
    w = _resolve(args)
    frame, backend = capture_any(w['hwnd'])
    if frame is None:
        print('CAPTURE FAILED: %s' % backend)
        return 1
    bgr = to_bgr(frame)
    geo = capture_geometry(w['hwnd'], bgr.shape)

    if not user32.IsWindowVisible(w['hwnd']):
        print('window is not visible; calibration needs it on screen')
        return 1

    wr = wintypes.RECT()
    user32.GetWindowRect(w['hwnd'], ctypes.byref(wr))
    org = wintypes.POINT(0, 0)
    user32.ClientToScreen(w['hwnd'], ctypes.byref(org))
    cli_w, cli_h = geo['client_size']

    try:
        from PIL import ImageGrab
        import cv2
        import numpy as np
    except ImportError as e:
        print('needs PIL/cv2: %s' % e)
        return 1

    time.sleep(0.3)
    scr = ImageGrab.grab(bbox=(org.x, org.y, org.x + cli_w, org.y + cli_h),
                         all_screens=True)
    cli = np.asarray(scr.convert('RGB'))[:, :, ::-1].copy()

    votes = []
    ph, pw = 40, 160
    gray = cv2.cvtColor(cli, cv2.COLOR_BGR2GRAY)
    for y in range(0, max(1, cli_h - ph), 20):
        for x in range(0, max(1, cli_w - pw), 60):
            patch = cli[y:y + ph, x:x + pw]
            if patch.std() < 15:
                continue
            res = cv2.matchTemplate(bgr, patch, cv2.TM_CCOEFF_NORMED)
            _, mx, _, loc = cv2.minMaxLoc(res)
            if mx > 0.95:
                votes.append((loc[0] - x, loc[1] - y, mx))

    print('computed offset : %s' % (geo['client_offset'],))
    if not votes:
        print('measured        : (no high-contrast patch matched)')
        print('=> cannot verify; if clicks land off-target, re-run when the window is on screen')
        return 1

    dxs = sorted(v[0] for v in votes)
    dys = sorted(v[1] for v in votes)
    med = (dxs[len(dxs) // 2], dys[len(dys) // 2])
    print('measured offset : %s  (%d patches, best score %.4f)'
          % (med, len(votes), max(v[2] for v in votes)))
    if abs(med[0] - geo['client_offset'][0]) <= 2 and abs(med[1] - geo['client_offset'][1]) <= 2:
        print('=> CONSISTENT: coordinate mapping verified')
        return 0
    print('=> MISMATCH: use %s instead of %s' % (med, geo['client_offset']))
    return 1


def main():
    set_dpi_aware()

    ap = argparse.ArgumentParser(description='background window automation')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('deps', help='check dependencies')
    p.add_argument('--install', action='store_true', help='install what is missing')
    p.set_defaults(func=cmd_deps)

    p = sub.add_parser('list', help='list windows')
    p.add_argument('--filter')
    p.set_defaults(func=cmd_list)

    def add_target(sp):
        sp.add_argument('--title', help='window title substring')
        sp.add_argument('--class-name', dest='class_name')
        sp.add_argument('--pid', type=int)
        sp.add_argument('--exact', action='store_true')

    p = sub.add_parser('capture', help='background screenshot')
    add_target(p)
    p.add_argument('--out', required=True)
    p.add_argument('--verify', action='store_true')
    p.set_defaults(func=cmd_capture)

    p = sub.add_parser('grab', help='crop a template out of a capture')
    add_target(p)
    p.add_argument('--box', required=True, help='x,y,w,h')
    p.add_argument('--out', required=True)
    p.set_defaults(func=cmd_grab)

    p = sub.add_parser('find', help='locate a template, print CLIENT coords')
    add_target(p)
    p.add_argument('--template', required=True)
    p.add_argument('--threshold', type=float, default=0.8)
    p.set_defaults(func=cmd_find)

    p = sub.add_parser('geom', help='show capture -> client coordinate mapping')
    add_target(p)
    p.set_defaults(func=cmd_geom)

    p = sub.add_parser('calibrate', help='verify the coordinate mapping on screen')
    add_target(p)
    p.set_defaults(func=cmd_calibrate)

    p = sub.add_parser('click', help='background click at client coords')
    add_target(p)
    p.add_argument('--x', type=int, required=True)
    p.add_argument('--y', type=int, required=True)
    p.add_argument('--button', choices=['left', 'right'], default='left')
    p.set_defaults(func=cmd_click)

    p = sub.add_parser('key', help='background key press')
    add_target(p)
    p.add_argument('--key', required=True)
    p.set_defaults(func=cmd_key)

    p = sub.add_parser('type', help='type text into the input child')
    add_target(p)
    p.add_argument('--text', required=True)
    p.set_defaults(func=cmd_type)

    p = sub.add_parser('clickfind', help='find a template then click it')
    add_target(p)
    p.add_argument('--template', required=True)
    p.add_argument('--threshold', type=float, default=0.8)
    p.set_defaults(func=cmd_clickfind)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == '__main__':
    main()
