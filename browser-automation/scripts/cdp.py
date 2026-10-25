#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
cdp.py - Chrome DevTools Protocol client for browser automation.
No mouse, no screenshot: talks to the browser over WebSocket and runs JS.

Usage:
  python cdp.py targets                     list open tabs
  python cdp.py eval "<js>"                 run JS in the active tab
  python cdp.py find "<text>"               locate element by visible text, return center coords
  python cdp.py click "<text>"              click element by visible text
  python cdp.py type "<text>" "[value]"     fill input by placeholder/label text
  python cdp.py text                        dump page text
  python cdp.py nav "<url>"                 navigate active tab
  python cdp.py shot "<path>"               screenshot via CDP (works even when covered)
  python cdp.py open                        launch Edge with debug port
  python cdp.py close                       kill the debug Edge instance

Env:
  CDP_PORT   default 9222
"""
import json
import os
import sys
import time
import urllib.request
import subprocess

PORT = int(os.environ.get('CDP_PORT', '9222'))
BASE = 'http://127.0.0.1:%d' % PORT

EDGE_PATHS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]


def http_get(path, timeout=5):
    req = urllib.request.Request(BASE + path, headers={'Host': 'localhost:%d' % PORT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def list_targets():
    return [t for t in http_get('/json/list') if t.get('type') == 'page']


def pick_target(target_id=None):
    ts = list_targets()
    if not ts:
        die('no page targets. run "cdp.py open" first, then open a tab.')
    if target_id:
        for t in ts:
            if t['id'] == target_id:
                return t
        die('target not found: %s' % target_id)
    # prefer http(s) pages over blank/devtools
    for t in ts:
        u = t.get('url', '')
        if u.startswith('http'):
            return t
    return ts[0]


def die(msg):
    sys.stderr.write('ERR: %s\n' % msg)
    sys.exit(1)


# ---------------- websocket ----------------
try:
    import websocket
except ImportError:
    die('missing websocket-client. run: python -m pip install websocket-client')


class Session:
    def __init__(self, ws_url):
        # Chromium rejects WS handshakes carrying an Origin header unless
        # --remote-allow-origins was passed. Create a request without one.
        try:
            self.ws = websocket.create_connection(
                ws_url, timeout=30,
                suppress_origin=True,
                enable_multithread=True)
        except websocket.WebSocketBadStatusException as e:
            die('WS handshake failed (403). Chromium now requires an allow-list.\n'
                'Fix: relaunch with --remote-allow-origins=*, or run "cdp.py close" then "cdp.py open".\n'
                'Raw: %s' % str(e)[:200])
        self.mid = 0

    def send(self, method, params=None):
        self.mid += 1
        mid = self.mid
        self.ws.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
        deadline = time.time() + 30
        while time.time() < deadline:
            raw = self.ws.recv()
            if not raw:
                continue
            msg = json.loads(raw)
            if msg.get('id') == mid:
                if 'error' in msg:
                    die('%s -> %s' % (method, msg['error']))
                return msg.get('result', {})
        die('timeout waiting for %s' % method)

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def connect(target=None):
    t = pick_target(target)
    return Session(t['webSocketDebuggerUrl']), t


def js(expr, await_promise=True):
    sess, _ = connect()
    try:
        r = sess.send('Runtime.evaluate', {
            'expression': expr,
            'returnByValue': True,
            'awaitPromise': await_promise,
        })
        if 'exceptionDetails' in r:
            die('JS error: %s' % json.dumps(r['exceptionDetails'], ensure_ascii=False)[:400])
        return r.get('result', {}).get('value')
    finally:
        sess.close()


# ---------------- helpers ----------------
FIND_JS = r"""
(function(txt, opts){
  opts = opts || {};
  const norm = s => (s||'').replace(/\s+/g,' ').trim();
  const target = norm(txt);

  const visible = e => {
    if (!e || !e.getBoundingClientRect) return false;
    const r = e.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    const cs = getComputedStyle(e);
    if (cs.visibility === 'hidden' || cs.display === 'none' || cs.opacity === '0') return false;
    return true;
  };

  // Only look at elements that can actually show text: skip IMG/SVG/CANVAS/SCRIPT.
  const SKIP = new Set(['IMG','SVG','CANVAS','SCRIPT','STYLE','NOSCRIPT','VIDEO','AUDIO','IFRAME']);
  const all = Array.from(document.querySelectorAll('body *'))
    .filter(e => visible(e) && !SKIP.has(e.tagName));

  const ownText = e => {
    // text directly in this element, ignoring child element text
    let s = '';
    for (const n of e.childNodes) {
      if (n.nodeType === 3) s += n.nodeValue;
    }
    return norm(s);
  };

  // Tier 1: element whose OWN text (not descendants) equals target.
  // This is how you find the leaf around a label, not the wrapper around it.
  let hits = all.filter(e => ownText(e) === target);

  // Tier 2: own text contains target, and element is not a big container
  if (!hits.length) {
    hits = all.filter(e => {
      const t = ownText(e);
      if (!t || !t.includes(target)) return false;
      const r = e.getBoundingClientRect();
      return (r.width * r.height) < 60000;   // cap: not a page-level wrapper
    });
  }

  // Tier 3: full innerText equals target (covers elements whose text is split across nodes)
  if (!hits.length) {
    hits = all.filter(e => norm(e.innerText) === target);
  }

  // Tier 4: attributes
  if (!hits.length) {
    hits = all.filter(e => {
      const a = ['placeholder','aria-label','title','alt'];
      return a.some(k => {
        const v = e.getAttribute && e.getAttribute(k);
        return v && norm(v).includes(target);
      });
    });
  }

  if (!hits.length) return {found:false, reason:'no visible element matched'};

  // Ranking: the same label often appears several times on a page
  // (top nav "番剧" vs a card lower down). Users mean the one they can see
  // without scrolling, reading top-to-bottom, and the leaf rather than a wrapper.
  const vh = innerHeight, vw = innerWidth;
  const scored = hits.map(e => {
    const r = e.getBoundingClientRect();
    const fullyVisible = r.top >= 0 && r.left >= 0 && r.right <= vw && r.bottom <= vh;
    const partlyVisible = r.bottom > 0 && r.top < vh;
    const area = Math.max(1, r.width * r.height);
    return { e, r, fullyVisible, partlyVisible, area,
             score: (fullyVisible ? 0 : (partlyVisible ? 10000 : 1000000)) + r.top * 2 + r.left * 0.1 + area * 0.002 };
  }).sort((a, b) => a.score - b.score);

  const best = scored[0];
  const el = best.e;
  const r = best.r;
  const cx = Math.round(r.left + r.width/2);
  const cy = Math.round(r.top + r.height/2);
  document.querySelectorAll('[data-cdp-hit]').forEach(n => n.removeAttribute('data-cdp-hit'));
  el.setAttribute('data-cdp-hit','1');
  return {found:true, x:cx, y:cy, w:Math.round(r.width), h:Math.round(r.height),
          tag:el.tagName, cls:(el.className||'').toString().slice(0,60),
          text:norm(el.innerText || el.value || '').slice(0,60),
          candidates: hits.length,
          inViewport: best.fullyVisible,
          others: scored.slice(1,4).map(s => ({y:Math.round(s.r.top), x:Math.round(s.r.left),
                                               w:Math.round(s.r.width), h:Math.round(s.r.height),
                                               t:norm(s.e.innerText||'').slice(0,20)}))};
})(%s)
"""


def norm_text(s):
    return json.dumps(s, ensure_ascii=False)


def cmd_targets():
    ts = list_targets()
    if not ts:
        print('(no page targets)')
        return
    for t in ts:
        print('%-34s %s' % (t['id'][:34], t.get('url', '')[:100]))


def cmd_eval(expr):
    v = js(expr)
    if isinstance(v, (dict, list)):
        print(json.dumps(v, ensure_ascii=False, indent=2))
    else:
        print(v)


def cmd_find(txt):
    expr = FIND_JS % norm_text(txt)
    v = js(expr)
    if not v or not v.get('found'):
        print('NOT FOUND: %s' % txt)
        sys.exit(2)
    print('%d,%d  <%s> w=%d h=%d  "%s"' % (v['x'], v['y'], v['tag'], v['w'], v['h'], v['text']))


def cmd_click(txt):
    """Click the element matching txt.

    Order of fire:
      1. CDP Input.dispatchMouseEvent -- a real browser-level mouse event that
         the page cannot ignore. SPAs (bilibili SPAPP, React routers) swallow
         synthetic el.click() but always honour this.
      2. Fallback to el.click() only if the native event reports no navigation.
    """
    v = js(FIND_JS % norm_text(txt))
    if not v or not v.get('found'):
        print('NOT FOUND: %s' % txt)
        sys.exit(2)

    x, y = v['x'], v['y']
    sess, _ = connect()
    try:
        sess.send('Input.dispatchMouseEvent',
                  {'type': 'mouseMoved', 'x': x, 'y': y, 'button': 'none'})
        time.sleep(0.05)
        sess.send('Input.dispatchMouseEvent',
                  {'type': 'mousePressed', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1})
        time.sleep(0.08)
        sess.send('Input.dispatchMouseEvent',
                  {'type': 'mouseReleased', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1})
    finally:
        sess.close()

    time.sleep(1.2)
    new_url = js('location.href')
    print('clicked "%s" at %d,%d  <%s>  (%d candidates)'
          % (txt, x, y, v['tag'], v.get('candidates', 1)))
    if new_url and new_url != 'about:blank':
        print('  url: %s' % new_url)


def cmd_type(txt, value):
    expr = r"""
    (function(){
      const el = document.querySelector('[data-cdp-hit="1"]');
      if(!el) return 'no hit';
      const setter = el.tagName === 'TEXTAREA'
        ? Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set
        : Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
      el.focus();
      if (setter) setter.call(el, %s); else el.value = %s;
      el.dispatchEvent(new Event('input',{bubbles:true}));
      el.dispatchEvent(new Event('change',{bubbles:true}));
      el.removeAttribute('data-cdp-hit');
      return el.value;
    })()
    """ % (norm_text(value), norm_text(value))
    # mark first
    v = js(FIND_JS % norm_text(txt))
    if not v or not v.get('found'):
        print('NOT FOUND: %s' % txt)
        sys.exit(2)
    out = js(expr)
    print('filled <%s> with: %s' % (v['tag'], out))


def cmd_text():
    v = js("document.body ? document.body.innerText : ''")
    print((v or '')[:8000])


def cmd_nav(url):
    sess, t = connect()
    try:
        sess.send('Page.navigate', {'url': url})
        time.sleep(1.5)
        print('navigated -> %s' % url)
    finally:
        sess.close()


def cmd_shot(path):
    sess, t = connect()
    try:
        r = sess.send('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
        import base64
        data = base64.b64decode(r['data'])
        with open(path, 'wb') as f:
            f.write(data)
        print('%s  %d bytes' % (path, len(data)))
    finally:
        sess.close()


def cmd_open():
    # check if already listening
    try:
        http_get('/json/version', timeout=2)
        print('already running on port %d' % PORT)
        return
    except Exception:
        pass
    edge = None
    for p in EDGE_PATHS:
        if os.path.isfile(p):
            edge = p
            break
    if not edge:
        die('Edge not found')
    # separate profile so the user's normal Edge is untouched
    profile = os.path.join(os.environ['LOCALAPPDATA'], 'cdp-automation-profile')
    os.makedirs(profile, exist_ok=True)
    args = [edge,
            '--remote-debugging-port=%d' % PORT,
            '--remote-allow-origins=*',
            '--user-data-dir=%s' % profile,
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-features=msEdgeFirstRunExperience']
    subprocess.Popen(args, close_fds=True)
    for _ in range(40):
        time.sleep(0.4)
        try:
            v = http_get('/json/version', timeout=2)
            print('CDP ready: %s' % v.get('Browser'))
            print('profile: %s' % profile)
            return
        except Exception:
            continue
    die('started Edge but CDP did not come up on port %d' % PORT)


def cmd_close():
    try:
        ts = list_targets()
    except Exception:
        print('CDP not running')
        return
    for t in ts:
        try:
            http_get('/json/close/%s' % t['id'], timeout=3)
        except Exception:
            pass
    print('closed %d targets' % len(ts))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1].lower()
    a = sys.argv[2:]

    if cmd == 'targets':
        cmd_targets()
    elif cmd == 'eval':
        if not a: die('need JS expression')
        cmd_eval(a[0])
    elif cmd == 'find':
        if not a: die('need text')
        cmd_find(a[0])
    elif cmd == 'click':
        if not a: die('need text')
        cmd_click(a[0])
    elif cmd == 'type':
        if len(a) < 2: die('need text and value')
        cmd_type(a[0], a[1])
    elif cmd == 'text':
        cmd_text()
    elif cmd == 'nav':
        if not a: die('need url')
        cmd_nav(a[0])
    elif cmd == 'shot':
        if not a: die('need path')
        cmd_shot(a[0])
    elif cmd == 'open':
        cmd_open()
    elif cmd == 'close':
        cmd_close()
    else:
        die('unknown command: %s' % cmd)


if __name__ == '__main__':
    main()
