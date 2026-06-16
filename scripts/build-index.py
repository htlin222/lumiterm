#!/usr/bin/env python3
"""build-index.py — patch ttyd's default index.html for the demo.

Two injections into ttyd's own page (so they run in the same JS context as the
terminal, where `window.term` — the xterm instance — is reachable):

  1. <style> with @font-face for "JetBrainsMono NF" (Ghostty's font), the woff2
     base64-embedded so there's no cross-origin font CORS to deal with.
  2. <script> that (a) re-measures the terminal once web fonts are ready — the
     fix for xterm rendering glyphs in over-wide cells when it measured before
     the font loaded — and (b) accepts postMessage commands from the wrapper
     page to live-change font size/family (the settings dialog).

Mirrors the harvest-and-inject idea from github.com/htlin222/ttyd-tmux-cf.

Inputs : scripts/ttyd-default.html, fonts/jbmono-nf-{regular,bold}.woff2
Output : ttyd-index.html   (pass to ttyd via -I)
"""
import base64
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = ROOT / "scripts" / "ttyd-default.html"
OUT = ROOT / "ttyd-index.html"
FAMILY = "JetBrainsMono NF"          # must match -t fontFamily in serve.sh
FONTS = {
    400: ROOT / "fonts" / "jbmono-nf-regular.woff2",
    700: ROOT / "fonts" / "jbmono-nf-bold.woff2",
}

# Runs inside ttyd's page. Fixes the web-font cell-measure race and bridges the
# settings dialog (postMessage) to the live xterm instance.
CONTROL_JS = """
<script>
(function () {
  function term() { return window.term; }
  function fit() {                   // recompute cols/rows + resize the PTY
    var t = term(); if (!t) return;
    try {
      var am = t._addonManager;
      var addons = am && (am._addons || am.addons);
      if (addons) addons.forEach(function (a) {
        var inst = a && (a.instance || a);
        if (inst && typeof inst.fit === 'function') inst.fit();
      });
    } catch (e) {}
  }
  function reflow() {                // run a fit now and after layout settles
    requestAnimationFrame(fit);
    setTimeout(fit, 60);
    setTimeout(fit, 180);
  }
  function remeasure() {             // re-measure cell width after font load
    var t = term(); if (!t) return;
    try {
      var fam = t.options.fontFamily;
      t.options.fontFamily = fam + ', monospace';
      t.options.fontFamily = fam;
    } catch (e) {}
    reflow();
  }
  function whenTerm(cb, n) {
    n = n || 0;
    if (term()) return cb();
    if (n > 200) return;
    setTimeout(function () { whenTerm(cb, n + 1); }, 50);
  }
  if (document.fonts) {
    if (document.fonts.ready) document.fonts.ready.then(function () { whenTerm(remeasure); });
    try { document.fonts.addEventListener('loadingdone', function () { whenTerm(remeasure); }); } catch (e) {}
  }
  // safety net: a few delayed re-measures catch slow (1MB) web-font decode
  whenTerm(function () { [150, 400, 900, 1800].forEach(function (t) { setTimeout(remeasure, t); }); });

  // --- spotlight: magnify the cursor's line and center it (presentation aid) ---
  var spot = { on: false, factor: 2 };
  function applySpot() {
    var t = term(); if (!t || !t.element) return;
    var el = t.element;
    if (!spot.on) {
      el.style.transition = 'transform 140ms ease';
      el.style.transform = '';
      el.style.transformOrigin = '';
      return;
    }
    var cols = t.cols || 80, rows = t.rows || 24;
    var buf = t.buffer && t.buffer.active;
    var cx = buf ? buf.cursorX : 0;
    var cy = buf ? buf.cursorY : 0;
    var cell = null;
    try { cell = t._core._renderService.dimensions.css.cell; } catch (e) {}
    var cw = cell ? cell.width : el.clientWidth / cols;
    var ch = cell ? cell.height : el.clientHeight / rows;
    var vw = el.clientWidth, vh = el.clientHeight;
    var px = (cx + 0.5) * cw;          // cursor cell center, x
    var py = (cy + 0.5) * ch;          // cursor cell center, y
    var tx = vw / 2 - px, ty = vh / 2 - py;   // move cursor to viewport center (both axes)
    el.style.transformOrigin = px + 'px ' + py + 'px';
    el.style.transition = 'transform 140ms ease';
    el.style.transform = 'translate(' + tx + 'px,' + ty + 'px) scale(' + (spot.factor || 2) + ')';
  }
  function bindSpot() {
    var t = term(); if (!t) return;
    try { t.onCursorMove(applySpot); } catch (e) {}
    try { t.onRender(applySpot); } catch (e) {}
    try { t.onResize(applySpot); } catch (e) {}
  }
  whenTerm(bindSpot);

  // --- text selection -> tell the wrapper (powers the ELI5 toolbar) ---
  function sendSelection() {
    var t = term(); if (!t) return;
    var text = '';
    try { text = t.getSelection() || ''; } catch (e) {}
    if (!text.trim()) { parent.postMessage({ type: 'demo:selection', text: '' }, '*'); return; }
    var x = 0, y = 0;
    try {
      var pos = t.getSelectionPosition();          // {start:{x,y}, end:{x,y}}, y = absolute line
      var cell = t._core._renderService.dimensions.css.cell;
      var vpY = t.buffer.active.viewportY;
      x = pos.start.x * cell.width;
      y = (pos.start.y - vpY) * cell.height;       // top of selection, px in viewport
    } catch (e) {}
    parent.postMessage({ type: 'demo:selection', text: text, x: x, y: y }, '*');
  }
  whenTerm(function () { try { term().onSelectionChange(sendSelection); } catch (e) {} });

  window.addEventListener('message', function (ev) {
    var d = ev.data || {};
    if (d.type === 'demo:font') {
      whenTerm(function () {
        try {
          if (typeof d.fontSize === 'number') term().options.fontSize = d.fontSize;
          // always toggle family so xterm re-measures the cell even if unchanged
          if (typeof d.fontFamily === 'string') {
            term().options.fontFamily = d.fontFamily + ', monospace';
            term().options.fontFamily = d.fontFamily;
          }
        } catch (e) {}
        reflow();   // recompute cols/rows for the new cell size + resize PTY
      });
    } else if (d.type === 'demo:spotlight') {
      spot.on = !!d.on;
      if (typeof d.factor === 'number') spot.factor = d.factor;
      whenTerm(applySpot);
    }
  });
})();
</script>
"""


def data_uri(path: pathlib.Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:font/woff2;base64,{b64}"


def main() -> int:
    if not BASE.exists():
        sys.exit(f"missing {BASE} — harvest it (see Makefile `index`)")
    for p in FONTS.values():
        if not p.exists():
            sys.exit(f"missing font {p} — run `make fonts`")

    faces = []
    for weight, path in FONTS.items():
        faces.append(
            f'@font-face{{font-family:"{FAMILY}";font-style:normal;'
            f'font-weight:{weight};font-display:swap;'
            f'src:url({data_uri(path)}) format("woff2");}}'
        )
    style = "<style>\n" + "\n".join(faces) + "\n</style>\n"

    html = BASE.read_text(encoding="utf-8")
    if "</head>" not in html or "</body>" not in html:
        sys.exit("unexpected ttyd layout (no </head>/</body>)")
    html = html.replace("</head>", style + "</head>", 1)
    html = html.replace("</body>", CONTROL_JS + "</body>", 1)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB, font={FAMILY})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
