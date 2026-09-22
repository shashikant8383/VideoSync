#!/usr/bin/env python3
"""
Builds the Broadcast Channel POC documentation PDF.

Diagrams are drawn as vectors rather than embedded screenshots so they
stay sharp at any zoom and keep the file small.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Flowable, KeepTogether, NextPageTemplate,
)

# ---------------------------------------------------------------------------
# PALETTE
# ---------------------------------------------------------------------------

INK      = colors.HexColor('#111827')
BODY     = colors.HexColor('#27303F')
MUTED    = colors.HexColor('#6B7280')
FAINT    = colors.HexColor('#9CA3AF')
LINE     = colors.HexColor('#D8DEE7')
RULE     = colors.HexColor('#E7EBF0')
PANEL    = colors.HexColor('#F5F7FA')
ACCENT   = colors.HexColor('#0F766E')
ACCENTBG = colors.HexColor('#D6F0EC')
WARN     = colors.HexColor('#B45309')
WARNBG   = colors.HexColor('#FDF3E3')
SCREEN   = colors.HexColor('#12161D')

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

# ---------------------------------------------------------------------------
# STYLES
# ---------------------------------------------------------------------------

_ss = getSampleStyleSheet()

def style(name, **kw):
    base = dict(fontName='Helvetica', fontSize=9.5, leading=14.5,
                textColor=BODY, alignment=TA_LEFT, spaceAfter=0)
    base.update(kw)
    return ParagraphStyle(name, **base)

S_TITLE    = style('t',  fontName='Helvetica-Bold', fontSize=30, leading=34, textColor=INK)
S_SUB      = style('st', fontSize=12.5, leading=18, textColor=MUTED)
S_H1       = style('h1', fontName='Helvetica-Bold', fontSize=17, leading=21, textColor=INK, spaceAfter=3)
S_H2       = style('h2', fontName='Helvetica-Bold', fontSize=11.5, leading=15, textColor=INK, spaceAfter=3)
S_BODY     = style('b',  spaceAfter=7)
S_SMALL    = style('sm', fontSize=8.5, leading=12.5, textColor=MUTED)
S_MONO     = style('m',  fontName='Courier', fontSize=8.5, leading=12.5, textColor=BODY)
S_CAP      = style('cap',fontSize=8, leading=11.5, textColor=FAINT)
S_KICKER   = style('k',  fontName='Helvetica-Bold', fontSize=8, leading=11,
                   textColor=ACCENT)
S_TOC      = style('toc',fontSize=10, leading=17, textColor=BODY)

def P(text, s=S_BODY):
    return Paragraph(text, s)

# ---------------------------------------------------------------------------
# DRAWING HELPERS
# ---------------------------------------------------------------------------

def box(c, x, y, w, h, label=None, sub=None, fill=None, stroke=LINE,
        label_color=INK, sub_color=MUTED, radius=3, lw=0.8, bold=True,
        fs=8.5, sub_fs=7):
    """Rounded box with an optional centered label and sub-label."""
    if fill is not None:
        c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(lw)
    c.roundRect(x, y, w, h, radius, stroke=1, fill=1 if fill is not None else 0)

    if label:
        c.setFillColor(label_color)
        c.setFont('Helvetica-Bold' if bold else 'Helvetica', fs)
        ty = y + h / 2 - (1 if not sub else -3.5)
        c.drawCentredString(x + w / 2, ty, label)
    if sub:
        c.setFillColor(sub_color)
        c.setFont('Helvetica', sub_fs)
        c.drawCentredString(x + w / 2, y + h / 2 - 8, sub)


def arrow(c, x1, y1, x2, y2, color=MUTED, lw=0.9, head=4.0, dash=None):
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(lw)
    if dash:
        c.setDash(dash, 2)
    c.line(x1, y1, x2, y2)
    c.setDash()

    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    for s in (+1, -1):
        c.line(x2, y2,
               x2 - head * math.cos(ang - s * 0.42),
               y2 - head * math.sin(ang - s * 0.42))


def text(c, x, y, s, size=7.5, color=MUTED, font='Helvetica', anchor='l'):
    c.setFillColor(color)
    c.setFont(font, size)
    if anchor == 'c':
        c.drawCentredString(x, y, s)
    elif anchor == 'r':
        c.drawRightString(x, y, s)
    else:
        c.drawString(x, y, s)


class Diagram(Flowable):
    """Flowable wrapper: subclasses implement draw_on(c, w, h)."""
    def __init__(self, height, caption=None):
        Flowable.__init__(self)
        self.height = height
        self.width = CONTENT_W
        self.caption = caption

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        self.draw_on(self.canv, self.width, self.height)


# ---------------------------------------------------------------------------
# DIAGRAM 1 — SYSTEM ARCHITECTURE
# ---------------------------------------------------------------------------

class Architecture(Diagram):
    def draw_on(self, c, W, H):
        top = H - 12

        # --- server container ---
        sv_h = 74
        sv_y = top - sv_h
        box(c, 0, sv_y, W, sv_h, fill=PANEL, stroke=LINE, radius=5)
        text(c, 9, top - 12, 'CHANNEL SERVER  ·  node server.js', 7.5, ACCENT,
             'Helvetica-Bold')
        text(c, W - 9, top - 12, '18 MB  ·  0% CPU', 7, FAINT, anchor='r')

        # three internal modules
        mw = (W - 40) / 3
        my = sv_y + 12
        mods = [
            ('ChannelManager', 'engine.js'),
            ('HTTP server', 'server.js'),
            ('DeviceStore', 'store.js'),
        ]
        cx = []
        for i, (nm, fn) in enumerate(mods):
            x = 12 + i * (mw + 8)
            box(c, x, my, mw, 36, nm, fn, fill=colors.white, fs=8, sub_fs=6.8)
            cx.append(x + mw / 2)

        # --- ffmpeg row ---
        fy = sv_y - 58
        fw = 92
        gap = (W - 3 * fw) / 4
        chans = [('ffmpeg', 'cartoons'), ('ffmpeg', 'shorts'), ('ffmpeg', 'classics')]
        fxc = []
        for i, (nm, ch) in enumerate(chans):
            x = gap + i * (fw + gap)
            box(c, x, fy, fw, 34, nm, ch, fill=ACCENTBG, stroke=ACCENT,
                label_color=ACCENT, sub_color=ACCENT, fs=8, sub_fs=6.8)
            fxc.append(x + fw / 2)
            arrow(c, cx[0], my, x + fw / 2, fy + 34, ACCENT, 0.8)

        text(c, W / 2, fy - 11, 'one encoder per channel  —  60-90% CPU each',
             7, FAINT, anchor='c')

        # --- disk ---
        dy = fy - 48
        box(c, 0, dy, W, 26, fill=colors.white, stroke=LINE)
        text(c, 9, dy + 10, 'public/channels/<id>/live.m3u8  +  seg_*.ts', 8,
             BODY, 'Courier')
        text(c, W - 9, dy + 10, 'rolling 6-segment window', 7, FAINT, anchor='r')
        for x in fxc:
            arrow(c, x, fy, x, dy + 26, MUTED, 0.8)

        # --- TVs ---
        ty = dy - 56
        tw = 80
        tgap = (W - 3 * tw) / 4
        for i, nm in enumerate(['TV 1', 'TV 2', 'TV 3']):
            x = tgap + i * (tw + tgap)
            box(c, x, ty, tw, 32, nm, 'plays live edge', fill=colors.white,
                fs=8, sub_fs=6.5)
            arrow(c, W / 2, dy, x + tw / 2, ty + 32, MUTED, 0.8)

        text(c, W / 2, ty - 12,
             'plain HTTP GET  ·  no session  ·  no handshake  ·  cacheable',
             7.5, ACCENT, anchor='c')


# ---------------------------------------------------------------------------
# DIAGRAM 2 — MP4 TO HLS PIPELINE
# ---------------------------------------------------------------------------

class Pipeline(Diagram):
    def draw_on(self, c, W, H):
        top = H - 10
        bw = 108
        bh = 52
        y = top - bh
        step = (W - bw) / 3

        # 1 source
        box(c, 0, y, bw, bh, fill=colors.white)
        text(c, bw / 2, y + bh - 15, 'SOURCE MP4s', 7, MUTED, 'Helvetica-Bold', 'c')
        for i, s in enumerate(['big-buck-bunny', 'sintel', 'elephants-dream']):
            text(c, bw / 2, y + bh - 27 - i * 9, s, 6.8, BODY, 'Courier', 'c')

        # 2 ffmpeg
        x2 = step
        box(c, x2, y, bw, bh, fill=ACCENTBG, stroke=ACCENT)
        text(c, x2 + bw / 2, y + bh - 16, 'ffmpeg', 10, ACCENT, 'Helvetica-Bold', 'c')
        text(c, x2 + bw / 2, y + bh - 29, '-re  -stream_loop -1', 6.8, ACCENT, 'Courier', 'c')
        text(c, x2 + bw / 2, y + bh - 40, 'realtime, forever', 6.8, ACCENT, anchor='c')

        # 3 output
        x3 = 2 * step
        box(c, x3, y, bw, bh, fill=colors.white)
        text(c, x3 + bw / 2, y + bh - 15, 'OUTPUT', 7, MUTED, 'Helvetica-Bold', 'c')
        text(c, x3 + bw / 2, y + bh - 27, 'live.m3u8', 6.8, BODY, 'Courier', 'c')
        text(c, x3 + bw / 2, y + bh - 36, 'seg_000456.ts', 6.8, BODY, 'Courier', 'c')
        text(c, x3 + bw / 2, y + bh - 45, 'seg_000457.ts', 6.8, BODY, 'Courier', 'c')

        # 4 TV
        x4 = 3 * step
        box(c, x4, y, bw, bh, fill=colors.white)
        text(c, x4 + bw / 2, y + bh - 15, 'TV', 7, MUTED, 'Helvetica-Bold', 'c')
        text(c, x4 + bw / 2, y + bh - 29, 'reads the list,', 6.8, BODY, anchor='c')
        text(c, x4 + bw / 2, y + bh - 39, 'plays newest pieces', 6.8, BODY, anchor='c')

        for i in range(3):
            arrow(c, i * step + bw, y + bh / 2, (i + 1) * step - 3, y + bh / 2,
                  MUTED, 0.9)

        # loop-back
        c.setStrokeColor(ACCENT)
        c.setLineWidth(0.9)
        c.setDash(2, 2)
        ly = y - 15
        c.line(x2 + bw / 2, y, x2 + bw / 2, ly)
        c.line(x2 + bw / 2, ly, bw / 2, ly)
        c.setDash()
        arrow(c, bw / 2, ly, bw / 2, y - 1, ACCENT, 0.9)
        text(c, (x2 + bw / 2 + bw / 2) / 2, ly - 9,
             'loops back to the first clip — the channel never ends', 7, ACCENT,
             anchor='c')

        # every 4 seconds strip
        sy = ly - 44
        box(c, 0, sy, W, 30, fill=PANEL, stroke=LINE)
        text(c, 10, sy + 18, 'EVERY 4 SECONDS', 7, ACCENT, 'Helvetica-Bold')
        text(c, 10, sy + 7,
             'a new piece is written  ·  the manifest is rewritten  ·  the oldest piece is deleted',
             7.5, BODY)


# ---------------------------------------------------------------------------
# DIAGRAM 3 — DRIFT CORRECTION
# ---------------------------------------------------------------------------

class Sync(Diagram):
    def draw_on(self, c, W, H):
        top = H - 10
        # bands
        rows = [
            ('|drift| > 5000 ms', 'seek', WARNBG, WARN),
            ('300 - 5000 ms', 'playbackRate 0.98 / 1.02', PANEL, BODY),
            ('<= 300 ms', 'leave it alone', ACCENTBG, ACCENT),
        ]
        rh = 24
        y = top - rh
        for lbl, act, bg, fg in rows:
            box(c, 0, y, W, rh, fill=bg, stroke=LINE)
            text(c, 10, y + 9, lbl, 8, fg, 'Helvetica-Bold')
            text(c, 150, y + 9, act, 8, fg)
            y -= rh + 4

        # convergence chart
        cy = y - 8
        ch = 96
        cx0 = 34
        cw = W - cx0 - 10
        c.setStrokeColor(LINE)
        c.setLineWidth(0.8)
        c.rect(cx0, cy - ch, cw, ch, stroke=1, fill=0)

        samples = [-2364, -1740, -601, -287, -120]
        lo, hi = -2600, 400
        def yy(v):
            return cy - ch + (v - lo) / (hi - lo) * ch

        # zero + deadband
        c.setStrokeColor(ACCENT)
        c.setDash(2, 2)
        c.line(cx0, yy(0), cx0 + cw, yy(0))
        c.setDash()
        c.setFillColor(ACCENTBG)
        c.rect(cx0, yy(-300), cw, yy(300) - yy(-300), stroke=0, fill=1)
        text(c, cx0 - 4, yy(0) - 2, '0', 6.5, ACCENT, anchor='r')
        text(c, cx0 - 4, yy(-2364) - 2, '-2364', 6.5, FAINT, anchor='r')
        text(c, cx0 + cw - 4, yy(250), 'deadband ±300 ms', 6.5, ACCENT, anchor='r')

        # curve
        n = len(samples)
        pts = [(cx0 + 14 + i * (cw - 28) / (n - 1), yy(v)) for i, v in enumerate(samples)]
        c.setStrokeColor(ACCENT)
        c.setLineWidth(1.4)
        for i in range(n - 1):
            c.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
        for i, (px, py) in enumerate(pts):
            c.setFillColor(colors.white)
            c.circle(px, py, 2.6, stroke=1, fill=1)
            c.setFillColor(ACCENT)
            c.circle(px, py, 1.5, stroke=0, fill=1)
            if i < n - 1:
                text(c, px, py + 6, f'{samples[i]}', 6.2, MUTED, anchor='c')

        text(c, cx0 + cw / 2, cy - ch - 11,
             'measured on an Android TV emulator: drift closes at exactly the 2% that 1.02x predicts',
             6.8, FAINT, anchor='c')


# ---------------------------------------------------------------------------
# DIAGRAM 4 — PAIRING SEQUENCE
# ---------------------------------------------------------------------------

class Pairing(Diagram):
    def draw_on(self, c, W, H):
        top = H - 6
        lanes = ['TV', 'SERVER', 'OPERATOR']
        lx = [W * 0.14, W * 0.5, W * 0.86]

        for nm, x in zip(lanes, lx):
            box(c, x - 42, top - 18, 84, 18, nm, fill=PANEL, fs=7.5)
            c.setStrokeColor(LINE)
            c.setDash(1.5, 2.5)
            c.setLineWidth(0.7)
            c.line(x, top - 18, x, 14)
            c.setDash()

        steps = [
            (0, 1, 'POST /api/device/pair/start', 'deviceId', False),
            (1, 0, 'code "DEUKLH"  ·  15 min TTL', None, True),
            (0, 0, 'displays code, polls every 2s', None, False),
            (2, 1, 'POST /api/admin/claim', 'the only human step', False),
            (1, 0, 'token + channelUrl', None, True),
            (0, 0, 'stores token forever — never shows a code again', None, False),
            (0, 1, 'GET /api/device/config  (Bearer)', 'every 30s', False),
        ]

        y = top - 36
        for a, b, label, note, dashed in steps:
            if a == b:  # self-action
                x = lx[a]
                c.setStrokeColor(FAINT)
                c.setLineWidth(0.7)
                c.setDash(1.5, 2)
                c.rect(x - 3, y - 4, 6, 8, stroke=1, fill=0)
                c.setDash()
                text(c, x + 10, y - 2, label, 7, MUTED, 'Helvetica-Oblique')
            else:
                x1, x2 = lx[a], lx[b]
                d = (2, 2) if dashed else None
                col = ACCENT if dashed else BODY
                sign = 1 if x2 > x1 else -1
                arrow(c, x1 + sign * 44, y, x2 - sign * 44, y, col, 0.9, 4, d)
                mid = (x1 + x2) / 2
                text(c, mid, y + 5, label, 7, col,
                     'Courier' if '/' in label else 'Helvetica', 'c')
                if note:
                    text(c, mid, y - 8, note, 6.3, FAINT, anchor='c')
            y -= 26


# ---------------------------------------------------------------------------
# WIREFRAMES
# ---------------------------------------------------------------------------

class WirePairing(Diagram):
    def draw_on(self, c, W, H):
        sw = W * 0.62
        x0 = (W - sw) / 2
        sh = sw * 9 / 16
        y0 = H - sh - 16

        box(c, x0, y0, sw, sh, fill=SCREEN, stroke=colors.HexColor('#2A3140'), radius=4)
        c.setFillColor(ACCENT)
        c.rect(x0, y0 + sh - 3, sw, 3, stroke=0, fill=1)

        text(c, x0 + sw / 2, y0 + sh * 0.79, 'Connect this TV', 13,
             colors.HexColor('#E6E9EF'), 'Helvetica-Bold', 'c')
        text(c, x0 + sw / 2, y0 + sh * 0.70, 'Open the dashboard and enter this code',
             7, colors.HexColor('#949CAB'), anchor='c')

        pw, ph = sw * 0.48, sh * 0.30
        px, py = x0 + (sw - pw) / 2, y0 + sh * 0.31
        box(c, px, py, pw, ph, fill=colors.HexColor('#1B212B'),
            stroke=colors.HexColor('#2A3140'))
        text(c, x0 + sw / 2, py + ph - 14, 'PAIRING CODE', 6,
             colors.HexColor('#6B7280'), anchor='c')
        text(c, x0 + sw / 2, py + ph * 0.28, 'UDKB3M', 20, ACCENT,
             'Helvetica-Bold', 'c')

        text(c, x0 + sw / 2, y0 + sh * 0.20,
             'Waiting for an operator to pair this device', 7,
             colors.HexColor('#949CAB'), anchor='c')
        text(c, x0 + sw / 2, y0 + sh * 0.07, 'tv_q11sjcnk35je  |  http://10.0.2.2:4000',
             5.8, colors.HexColor('#4B5462'), 'Courier', 'c')

        # annotations
        text(c, x0, y0 - 12, 'Shown once per TV, ever. After pairing this screen is never seen again —',
             7, FAINT)
        text(c, x0, y0 - 21, 'not on reboot, not after a power cut, not after an app update.',
             7, FAINT)


class WirePlayer(Diagram):
    def draw_on(self, c, W, H):
        sw = W * 0.62
        x0 = (W - sw) / 2
        sh = sw * 9 / 16
        y0 = H - sh - 16

        box(c, x0, y0, sw, sh, fill=colors.HexColor('#0B0D11'),
            stroke=colors.HexColor('#2A3140'), radius=4)

        # video area placeholder with cross
        vx, vy, vw, vh = x0 + 6, y0 + 6, sw - 12, sh - 12
        c.setFillColor(colors.HexColor('#1A1F28'))
        c.setStrokeColor(colors.HexColor('#2A3140'))
        c.setLineWidth(0.6)
        c.rect(vx, vy, vw, vh, stroke=1, fill=1)
        c.setStrokeColor(colors.HexColor('#252C37'))
        c.line(vx, vy, vx + vw, vy + vh)
        c.line(vx, vy + vh, vx + vw, vy)
        text(c, x0 + sw / 2, y0 + sh * 0.46, 'FULL-SCREEN VIDEO', 8,
             colors.HexColor('#3C4553'), 'Helvetica-Bold', 'c')
        text(c, x0 + sw / 2, y0 + sh * 0.38, '<video> + hls.js  ·  z-index 1', 6.2,
             colors.HexColor('#3C4553'), 'Courier', 'c')

        # overlay strip
        ow, oh = sw * 0.60, 24
        c.setFillColor(colors.HexColor('#000000'))
        c.rect(x0, y0 + sh - oh, ow, oh, stroke=0, fill=1)
        text(c, x0 + 7, y0 + sh - 11, 'ON AIR   |   channel time 15:08:38', 7.2,
             colors.HexColor('#E6E9EF'))
        text(c, x0 + 7, y0 + sh - 20,
             'drift -287ms  |  rate 1.00x  |  clock +629771ms', 6.2, ACCENT)

        text(c, x0, y0 - 12,
             'Lightning canvas is layered ABOVE the video (z-index 2) so overlays draw on top.',
             7, FAINT)
        text(c, x0, y0 - 21,
             'It must stay transparent — an opaque root hides the picture while text still shows.',
             7, FAINT)


class WireDashboard(Diagram):
    def draw_on(self, c, W, H):
        sw = W * 0.72
        x0 = (W - sw) / 2
        sh = H - 30
        y0 = H - sh - 4

        box(c, x0, y0, sw, sh, fill=SCREEN, stroke=colors.HexColor('#2A3140'), radius=4)

        cur = y0 + sh - 16
        text(c, x0 + 10, cur, 'Channel Control', 10,
             colors.HexColor('#E6E9EF'), 'Helvetica-Bold')
        cur -= 10
        text(c, x0 + 10, cur, 'Each channel is its own continuously-encoded HLS stream.',
             5.8, colors.HexColor('#6B7280'))

        # channels panel
        cur -= 12
        ph = 62
        box(c, x0 + 8, cur - ph, sw - 16, ph, fill=colors.HexColor('#171B22'),
            stroke=colors.HexColor('#272D38'))
        text(c, x0 + 15, cur - 11, 'CHANNELS', 5.6, colors.HexColor('#6B7280'),
             'Helvetica-Bold')
        for i, (nm, vids) in enumerate([('Cartoons', '3 videos'),
                                        ('Animation Shorts', '3 videos'),
                                        ('Classics', '3 videos')]):
            ry = cur - 22 - i * 13
            c.setFillColor(ACCENT)
            c.circle(x0 + 17, ry + 2, 2, stroke=0, fill=1)
            text(c, x0 + 23, ry, nm, 6.8, colors.HexColor('#E6E9EF'))
            text(c, x0 + 110, ry, vids, 6, colors.HexColor('#6B7280'))
            text(c, x0 + sw - 15, ry, 'live · 0 restarts', 6,
                 colors.HexColor('#6B7280'), anchor='r')

        # pair panel
        cur -= ph + 8
        ph2 = 30
        box(c, x0 + 8, cur - ph2, sw - 16, ph2, fill=colors.HexColor('#171B22'),
            stroke=colors.HexColor('#272D38'))
        text(c, x0 + 15, cur - 11, 'PAIR A TV', 5.6, colors.HexColor('#6B7280'),
             'Helvetica-Bold')
        box(c, x0 + 15, cur - 26, 52, 12, fill=colors.HexColor('#0B0E13'),
            stroke=colors.HexColor('#272D38'), radius=2)
        text(c, x0 + 20, cur - 22, 'CODE', 6, colors.HexColor('#5A6170'), 'Courier')
        box(c, x0 + 71, cur - 26, 60, 12, fill=colors.HexColor('#0B0E13'),
            stroke=colors.HexColor('#272D38'), radius=2)
        text(c, x0 + 76, cur - 22, 'Cartoons  v', 6, colors.HexColor('#949CAB'))
        box(c, x0 + 135, cur - 26, 48, 12, 'Pair device', fill=ACCENT,
            stroke=ACCENT, label_color=colors.white, fs=6, radius=2)

        # devices panel
        cur -= ph2 + 8
        ph3 = cur - y0 - 10
        box(c, x0 + 8, y0 + 8, sw - 16, ph3, fill=colors.HexColor('#171B22'),
            stroke=colors.HexColor('#272D38'))
        text(c, x0 + 15, cur - 11, 'DEVICES', 5.6, colors.HexColor('#6B7280'),
             'Helvetica-Bold')
        hdr_y = cur - 21
        for lbl, off in [('NAME', 15), ('STATUS', 95), ('PLAYING', 160), ('', 230)]:
            text(c, x0 + off, hdr_y, lbl, 5.4, colors.HexColor('#6B7280'),
                 'Helvetica-Bold')
        c.setStrokeColor(colors.HexColor('#272D38'))
        c.setLineWidth(0.5)
        c.line(x0 + 15, hdr_y - 4, x0 + sw - 15, hdr_y - 4)

        for i, (nm, st, ch) in enumerate([('TV 1', 'online', 'Cartoons'),
                                          ('TV 2', 'online', 'Classics'),
                                          ('TV 3', 'waiting · A3CK47', '—')]):
            ry = hdr_y - 14 - i * 13
            text(c, x0 + 15, ry, nm, 6.6, colors.HexColor('#E6E9EF'))
            c.setFillColor(ACCENT if st == 'online' else colors.HexColor('#4B5462'))
            c.circle(x0 + 97, ry + 2, 1.8, stroke=0, fill=1)
            text(c, x0 + 102, ry, st, 6, colors.HexColor('#949CAB'))
            box(c, x0 + 160, ry - 3, 52, 11, fill=colors.HexColor('#0B0E13'),
                stroke=colors.HexColor('#272D38'), radius=2)
            text(c, x0 + 164, ry, ch + '   v', 5.8, colors.HexColor('#949CAB'))
            box(c, x0 + sw - 62, ry - 3, 40, 11, 'Remove',
                fill=None, stroke=colors.HexColor('#272D38'),
                label_color=colors.HexColor('#949CAB'), fs=5.5, radius=2, bold=False)



# ---------------------------------------------------------------------------
# DIAGRAM — CHANNEL / PLAYLIST MODEL
# ---------------------------------------------------------------------------

class ChannelModel(Diagram):
    def draw_on(self, c, W, H):
        top = H - 8
        chans = [
            ('cartoons', 'Cartoons', ['big-buck-bunny', 'sintel', 'elephants-dream']),
            ('shorts', 'Animation Shorts', ['big-buck-bunny', 'sintel', 'elephants-dream']),
            ('classics', 'Classics', ['big-buck-bunny', 'sintel', 'elephants-dream']),
        ]

        cw = (W - 24) / 3
        ch = 96
        y = top - ch

        centres = []
        for i, (cid, name, vids) in enumerate(chans):
            x = i * (cw + 12)
            box(c, x, y, cw, ch, fill=colors.white, stroke=LINE, radius=4)

            # header strip
            c.setFillColor(ACCENTBG)
            c.rect(x + 1, y + ch - 19, cw - 2, 18, stroke=0, fill=1)
            text(c, x + cw / 2, y + ch - 13, name, 8, ACCENT, 'Helvetica-Bold', 'c')

            text(c, x + 8, y + ch - 31, 'content/' + cid + '/', 6.2, FAINT, 'Courier')

            for j, v in enumerate(vids):
                vy = y + ch - 42 - j * 13
                box(c, x + 8, vy - 4, cw - 16, 11, fill=PANEL, stroke=RULE, radius=2)
                text(c, x + 12, vy - 1, f'{j + 1}. {v}', 6, BODY, 'Courier')

            text(c, x + cw / 2, y + 7, '3 minutes, looping', 6, FAINT, anchor='c')
            centres.append(x + cw / 2)

        # engine row
        ey = y - 42
        for i, cx in enumerate(centres):
            box(c, cx - 44, ey, 88, 26, 'ffmpeg', chans[i][0], fill=ACCENTBG,
                stroke=ACCENT, label_color=ACCENT, sub_color=ACCENT, fs=7.5, sub_fs=6)
            arrow(c, cx, y, cx, ey + 26, ACCENT, 0.8)

        # manifests
        my = ey - 34
        for i, cx in enumerate(centres):
            box(c, cx - 62, my, 124, 20, fill=colors.white, stroke=LINE, radius=3)
            text(c, cx, my + 7, f'/channels/{chans[i][0]}/live.m3u8', 5.8, BODY,
                 'Courier', 'c')
            arrow(c, cx, ey, cx, my + 20, MUTED, 0.8)

        # TVs assigned
        ty = my - 40
        assign = [('TV 1', 0), ('TV 2', 2), ('TV 3', 0)]
        tw = 66
        tgap = (W - 3 * tw) / 4
        for i, (nm, ci) in enumerate(assign):
            x = tgap + i * (tw + tgap)
            box(c, x, ty, tw, 22, nm, fill=colors.white, fs=7.5)
            arrow(c, centres[ci], my, x + tw / 2, ty + 22, MUTED, 0.7)

        text(c, W / 2, ty - 11,
             'a television is assigned to one channel; changing it is a dashboard dropdown',
             6.8, FAINT, anchor='c')


# ---------------------------------------------------------------------------
# DIAGRAM — ENCODER SUPERVISION
# ---------------------------------------------------------------------------

class Supervision(Diagram):
    def draw_on(self, c, W, H):
        top = H - 8
        bw = (W - 30) / 2
        bh = 30

        # running state
        y1 = top - bh
        box(c, 0, y1, bw, bh, 'ENCODER RUNNING', 'writing a segment every 4s',
            fill=ACCENTBG, stroke=ACCENT, label_color=ACCENT, sub_color=ACCENT,
            fs=8, sub_fs=6.5)

        # watchdog
        y2 = y1 - 46
        box(c, 0, y2, bw, bh, 'WATCHDOG  ·  every 5s', 'has live.m3u8 advanced?',
            fill=PANEL, stroke=LINE, fs=8, sub_fs=6.5)
        arrow(c, bw / 2, y1, bw / 2, y2 + bh, MUTED, 0.8)

        # decision outcomes
        y3 = y2 - 52
        box(c, 0, y3, bw, bh, 'YES  —  leave it alone', fill=colors.white,
            stroke=LINE, label_color=ACCENT, fs=8)
        arrow(c, bw * 0.3, y2, bw * 0.3, y3 + bh, ACCENT, 0.8)

        box(c, bw + 30, y3, bw, bh, 'NO for 20s  —  SIGKILL', fill=WARNBG,
            stroke=WARN, label_color=WARN, fs=8)
        arrow(c, bw * 0.7, y2, bw + 30, y3 + bh / 2, WARN, 0.8)

        # restart
        y4 = y3 - 46
        box(c, bw + 30, y4, bw, bh, 'RESTART with backoff', '2s -> 4s -> 8s, capped at 30s',
            fill=colors.white, stroke=LINE, fs=8, sub_fs=6.5)
        arrow(c, bw + 30 + bw / 2, y3, bw + 30 + bw / 2, y4 + bh, MUTED, 0.8)

        # loop back to running
        c.setStrokeColor(MUTED)
        c.setLineWidth(0.8)
        c.setDash(2, 2)
        lx = W - 6
        c.line(bw + 30 + bw, y4 + bh / 2, lx, y4 + bh / 2)
        c.line(lx, y4 + bh / 2, lx, y1 + bh / 2)
        c.setDash()
        arrow(c, lx, y1 + bh / 2, bw + 2, y1 + bh / 2, MUTED, 0.8)

        # note
        ny = y4 - 40
        box(c, 0, ny, W, 30, fill=PANEL, stroke=LINE)
        text(c, 10, ny + 18, 'WHY SEGMENT PRODUCTION, NOT PROCESS LIVENESS', 7,
             ACCENT, 'Helvetica-Bold')
        text(c, 10, ny + 7,
             'An ffmpeg that wedges stays alive and passes every "is it running?" check while producing nothing.',
             7, BODY)


# ---------------------------------------------------------------------------
# PAGE FURNITURE
# ---------------------------------------------------------------------------

def later_pages(c, doc):
    c.saveState()
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    c.line(MARGIN, PAGE_H - MARGIN + 8, PAGE_W - MARGIN, PAGE_H - MARGIN + 8)
    c.setFont('Helvetica', 7)
    c.setFillColor(FAINT)
    c.drawString(MARGIN, PAGE_H - MARGIN + 13, 'Broadcast Channel POC')
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 13,
                      'github.com/shashikant8383/VideoSync')
    c.line(MARGIN, MARGIN - 10, PAGE_W - MARGIN, MARGIN - 10)
    c.drawCentredString(PAGE_W / 2, MARGIN - 19, str(doc.page))
    c.restoreState()


def cover_page(c, doc):
    c.saveState()
    c.setFillColor(ACCENT)
    c.rect(0, PAGE_H - 10, PAGE_W, 10, stroke=0, fill=1)
    c.restoreState()


# ---------------------------------------------------------------------------
# TABLE HELPER
# ---------------------------------------------------------------------------

def table(rows, widths, header=True, mono_cols=(), fs=8.3):
    data = []
    for r in rows:
        data.append([Paragraph(str(cell), style('c', fontSize=fs, leading=fs + 3.4,
                                                fontName='Courier' if i in mono_cols else 'Helvetica'))
                     if not (header and rows.index(r) == 0)
                     else Paragraph(f'<b>{cell}</b>', style('ch', fontSize=fs - 0.3,
                                                            leading=fs + 3, textColor=INK))
                     for i, cell in enumerate(r)])

    t = Table(data, colWidths=widths, hAlign='LEFT')
    cmds = [
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('LINEBELOW', (0, 0), (-1, -2), 0.4, RULE),
    ]
    if header:
        cmds += [('BACKGROUND', (0, 0), (-1, 0), PANEL),
                 ('LINEBELOW', (0, 0), (-1, 0), 0.7, LINE)]
    t.setStyle(TableStyle(cmds))
    return t


def callout(title, body, warn=False):
    bg = WARNBG if warn else ACCENTBG
    fg = WARN if warn else ACCENT
    inner = [[Paragraph(f'<b>{title}</b>', style('ct', fontSize=8.3, leading=12,
                                                 textColor=fg))],
             [Paragraph(body, style('cb', fontSize=8.3, leading=12.5, textColor=BODY))]]
    t = Table(inner, colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (0, 0), 8),
        ('BOTTOMPADDING', (0, 0), (0, 0), 1),
        ('TOPPADDING', (0, 1), (0, 1), 0),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('LINEBEFORE', (0, 0), (0, -1), 2.2, fg),
    ]))
    return t


def code_block(lines):
    txt = '<br/>'.join(l.replace('&', '&amp;').replace('<', '&lt;').replace(' ', '&nbsp;')
                       for l in lines)
    t = Table([[Paragraph(txt, style('cd', fontName='Courier', fontSize=7.8,
                                     leading=11.5, textColor=BODY))]],
              colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PANEL),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return t


def heading(kicker, title):
    return KeepTogether([P(kicker.upper(), S_KICKER), Spacer(1, 2),
                         P(title, S_H1), Spacer(1, 7)])


# ---------------------------------------------------------------------------
# BUILD
# ---------------------------------------------------------------------------

OUT = '/Users/shashikantraghuvanshi/Desktop/pocvideo/Broadcast-Channel-POC.pdf'

doc = BaseDocTemplate(OUT, pagesize=A4,
                      leftMargin=MARGIN, rightMargin=MARGIN,
                      topMargin=MARGIN, bottomMargin=MARGIN,
                      title='Broadcast Channel POC',
                      author='Shashikant Raghuvanshi',
                      subject='Synchronised multi-TV playback via a linear HLS channel')

frame = Frame(MARGIN, MARGIN, CONTENT_W, PAGE_H - 2 * MARGIN, id='f')
doc.addPageTemplates([
    PageTemplate(id='cover', frames=[frame], onPage=cover_page),
    PageTemplate(id='body', frames=[frame], onPage=later_pages),
])

E = []

# ---- COVER ----------------------------------------------------------------
E += [Spacer(1, 92)]
E += [P('Broadcast Channel', S_TITLE), Spacer(1, 10)]
E += [P('A linear TV channel: one continuously-encoded live HLS stream, and '
        'televisions that tune it the way a television tunes a broadcast.', S_SUB)]
E += [Spacer(1, 26)]

E += [table([
    ['Component', 'Technology'],
    ['TV application', 'LightningJS (Blits 2.10) + hls.js, packaged with Capacitor'],
    ['Channel server', 'Node.js, zero dependencies'],
    ['Encoder', 'ffmpeg - one process per channel'],
    ['Transport', 'HLS with EXT-X-PROGRAM-DATE-TIME'],
    ['Targets', 'Android TV today; webOS and Tizen share the same build'],
], [92, CONTENT_W - 92])]

E += [Spacer(1, 22)]
E += [callout('What this system does',
              'Several televisions show the same content at the same moment. A television '
              'switched on at any time joins whatever is already playing, never from the '
              'beginning. After a single setup step, no screen is ever configured again - '
              'through reboots, power cuts and app updates.')]

E += [Spacer(1, 18)]
E += [P('Contents', S_H2), Spacer(1, 4)]
for i, (n, t) in enumerate([
    ('1', 'How the system works'),
    ('2', 'System architecture'),
    ('3', 'Channels and playlists'),
    ('4', 'How an MP4 becomes a channel'),
    ('5', 'The encoder and its supervision'),
    ('6', 'Keeping televisions in sync'),
    ('7', 'Pairing a television'),
    ('8', 'Screen wireframes'),
    ('9', 'API reference'),
    ('10', 'Running the system'),
    ('11', 'Operating it'),
    ('12', 'Known limitations'),
]):
    E += [P(f'<font color="#9CA3AF">{n}</font> &nbsp;&nbsp; {t}', S_TOC)]

E += [NextPageTemplate('body'), PageBreak()]

# ---- 1. HOW IT WORKS ------------------------------------------------------
E += [heading('Section 1', 'How the system works')]
E += [P('The server behaves like a television station. It plays a playlist of videos '
        'continuously, around the clock, whether any television is switched on or not. '
        'Televisions do not request content, schedule anything, or coordinate with each '
        'other - they simply display whatever is currently being broadcast.')]

E += [Spacer(1, 6)]
E += [P('The three ideas behind it', S_H2)]

E += [Spacer(1, 3)]
E += [table([
    ['Idea', 'Consequence'],
    ['The stream is produced once, centrally',
     'What is on air is decided in exactly one place. There is no agreement to maintain '
     'between devices, because there is nothing for them to disagree about.'],
    ['Video is delivered as ordinary static files',
     'No sessions, no handshakes, no per-viewer state. The origin does not know or care '
     'how many televisions exist, which is what allows a CDN to absorb any number of them.'],
    ['Televisions hold a fixed delay behind a shared clock',
     'Every screen targets the same instant, so independent devices that never communicate '
     'still land on the same frame.'],
], [118, CONTENT_W - 118])]

E += [Spacer(1, 12)]
E += [P('Why the stream is continuous', S_H2)]
E += [P('A file has a beginning, so opening one starts at zero. A broadcast has no beginning - '
        'you join whatever is happening now. Producing the stream continuously is what turns '
        'playback position from something each television must calculate into something it '
        'simply receives.')]
E += [P('This is also why clip transitions are invisible. The encoder treats the whole playlist '
        'as one endless input, so moving from one video to the next is not an event on the '
        'television at all - it is just the next four seconds of the same stream.')]

E += [Spacer(1, 8)]
E += [callout('The one thing to internalise',
              'Cost scales with the number of channels, not the number of viewers. A thousand '
              'televisions watching one channel is the same work as one television watching it. '
              'Adding a second channel costs an entire additional encoder.')]

E += [PageBreak()]

# ---- 2. ARCHITECTURE ------------------------------------------------------
E += [heading('Section 2', 'System architecture')]
E += [P('One Node process supervises everything and serves files. It never touches video '
        'data - that is entirely ffmpeg\'s job.')]
E += [Spacer(1, 5), Architecture(292), Spacer(1, 8)]

E += [P('The measurement that explains the design', S_H2)]
E += [P('On a running system, Node uses <b>0% CPU and 18 MB</b> of memory, while the three '
        'ffmpeg processes use <b>60-90% of a core each</b>. Everything expensive happens inside '
        'ffmpeg.')]

E += [Spacer(1, 4)]
E += [table([
    ['Adding...', 'Cost'],
    ['1,000 more televisions', 'Almost nothing. Static file reads, and a CDN absorbs them entirely.'],
    ['One more channel', 'A whole additional encoder - 60-90% of a CPU core.'],
], [110, CONTENT_W - 110])]

E += [Spacer(1, 12)]
E += [P('Three independent concerns', S_H2)]
E += [Spacer(1, 3)]
E += [table([
    ['Concern', 'File', 'Responsibility'],
    ['Encoding', 'engine.js', 'Spawns and supervises one ffmpeg per channel. No HTTP at all.'],
    ['Serving', 'server.js', 'All APIs, static file serving, and cache policy. No video logic.'],
    ['State', 'store.js', 'Device records: pairing codes, tokens, last-seen timestamps.'],
], [58, 62, CONTENT_W - 120], mono_cols=(1,))]

E += [Spacer(1, 12)]
E += [P('The video path depends on nothing', S_H2)]
E += [P('If the device store and the API layer were both deleted, every already-paired '
        'television would keep playing indefinitely - playback is nothing more than repeated '
        'GETs of static files. Losing the control plane costs you the dashboard, not the '
        'picture.')]

E += [PageBreak()]

# ---- 3. CHANNELS ----------------------------------------------------------
E += [heading('Section 3', 'Channels and playlists')]
E += [P('A channel is a directory of video clips plus one encoder process. Three exist in this '
        'system, each with three videos.')]
E += [Spacer(1, 6), ChannelModel(245), Spacer(1, 10)]

E += [P('Adding a channel', S_H2)]
E += [P('Create a directory of clips under <font face="Courier">content/</font>, write a '
        '<font face="Courier">playlist.txt</font> concat list, and add an entry to '
        '<font face="Courier">channels.json</font>. The server spawns an encoder for it on next '
        'start.')]
E += [Spacer(1, 4)]
E += [code_block([
    '{',
    '  "channels": [',
    '    { "id": "cartoons",  "name": "Cartoons" },',
    '    { "id": "shorts",    "name": "Animation Shorts" },',
    '    { "id": "classics",  "name": "Classics" }',
    '  ]',
    '}',
])]

E += [Spacer(1, 10)]
E += [P('Source clips must match exactly', S_H2)]
E += [P('Every clip within a channel must share identical codec, resolution, frame rate and '
        'audio layout. The concat demuxer joins them without renegotiating, so a mismatch is '
        'the usual reason a channel dies at a clip boundary.')]

E += [Spacer(1, 4)]
E += [table([
    ['Parameter', 'Value used here'],
    ['Video', 'H.264 (libx264), main profile, yuv420p'],
    ['Resolution', '1280 x 720'],
    ['Frame rate', '25 fps, keyframe every 2 seconds'],
    ['Bitrate', '2000 kbps, capped'],
    ['Audio', 'AAC, 128 kbps, 48 kHz stereo'],
], [88, CONTENT_W - 88])]

E += [Spacer(1, 10)]
E += [P('The preparation script normalises every source to these values regardless of what it '
        'started as, which is what makes arbitrary input files safe to drop in.')]

E += [Spacer(1, 8)]
E += [P('Assigning a television to a channel', S_H2)]
E += [P('Each paired television carries a channel assignment. Changing it is a dropdown in the '
        'dashboard. Nothing is pushed to the television - it discovers the new channel URL on '
        'its next heartbeat, within 30 seconds, and reattaches itself.')]

E += [PageBreak()]

# ---- 4. PIPELINE ----------------------------------------------------------
E += [heading('Section 4', 'How an MP4 becomes a channel')]
E += [P('A television cannot join the middle of a file. So ffmpeg continuously chops the '
        'source video into small pieces and maintains a short list of the newest ones.')]
E += [Spacer(1, 6), Pipeline(140), Spacer(1, 8)]

E += [P('This is not ordinary conversion', S_H2)]
E += [P('Normal conversion runs once and produces a complete set of files. This runs '
        '<b>at realtime speed, forever</b>, and keeps only the newest handful of pieces.')]

E += [Spacer(1, 4)]
E += [table([
    ['Observed on a running channel', ''],
    ['Time on air', '30 minutes'],
    ['Pieces created', '457  (seg_000000 -> seg_000456)'],
    ['Pieces still on disk', '7'],
    ['Disk used by all three channels', '23 MB'],
    ['Source MP4s', 'never modified - read again and again'],
], [130, CONTENT_W - 130])]

E += [Spacer(1, 10)]
E += [P('The command', S_H2)]
E += [code_block([
    'ffmpeg -re -stream_loop -1 -f concat -safe 0 -i playlist.txt \\',
    '       -c:v libx264 -g 50 -c:a aac \\',
    '       -f hls -hls_time 4 -hls_list_size 6 \\',
    '       -hls_flags delete_segments+append_list+program_date_time \\',
    '       public/channels/cartoons/live.m3u8',
])]
E += [Spacer(1, 8)]
E += [table([
    ['Flag', 'Why it matters'],
    ['-re', 'Paces reading at realtime. Without it ffmpeg races through the files and nothing is live.'],
    ['-stream_loop -1', 'Loops the playlist forever - the channel never ends.'],
    ['-f concat', 'Treats the playlist as one continuous input, which is why clip transitions are invisible.'],
    ['-hls_time 4', 'Four-second pieces; -g 50 places a keyframe every two seconds so pieces always split cleanly.'],
    ['-hls_list_size 6', 'A rolling window of roughly 24 seconds.'],
    ['delete_segments', 'Stops the disk filling over days of uptime.'],
    ['append_list', 'Survives a restart without resetting the media sequence.'],
    ['program_date_time', 'Stamps every piece with a wall-clock time. This is what makes frame-accurate sync possible.'],
], [92, CONTENT_W - 92])]

E += [Spacer(1, 8)]
E += [callout('Why re-encode instead of -c copy',
              'Copying is far cheaper and is the right choice once all source files share '
              'identical parameters. But looping a concatenated playlist with -c copy produces '
              'timestamp discontinuities at every wrap, which some players show as a stutter. '
              'Re-encoding regenerates clean timestamps. Switching is a one-word change once '
              'sources are known-identical, and drops CPU use to almost nothing.')]

E += [PageBreak()]

# ---- 5. SUPERVISION -------------------------------------------------------
E += [heading('Section 5', 'The encoder and its supervision')]
E += [P('Encoders die. A malformed source file, a disk hiccup, an out-of-memory kill. A channel '
        'without a restart policy is a channel that goes dark at three in the morning.')]
E += [P('The harder failure is subtler: an encoder that <b>stops producing output while staying '
        'alive</b>. It has not crashed, has not exited, and passes every conventional health '
        'check - while every viewer sees a frozen screen.')]
E += [Spacer(1, 6), Supervision(270), Spacer(1, 10)]

E += [P('This is not hypothetical', S_H2)]
E += [P('During testing, one encoder ran normally for eighteen minutes and then stopped writing '
        'segments while remaining alive. The watchdog noticed the manifest had not advanced, '
        'killed the process, and restarted it. The channel recovered without intervention.')]
E += [Spacer(1, 4)]
E += [code_block([
    '[cartoons] manifest has not advanced in 20s - killing wedged ffmpeg',
    '[cartoons] ffmpeg exited code=null signal=SIGKILL after 1086s',
    '[cartoons] restarting in 2000ms (restart #1)',
])]

E += [Spacer(1, 10)]
E += [P('Backoff behaviour', S_H2)]
E += [P('Restart delay doubles on each consecutive failure up to a 30-second ceiling, then '
        'resets to two seconds once a process has survived a full minute. A single transient '
        'failure therefore does not leave the channel waiting half a minute to recover, while a '
        'genuinely broken channel does not spin in a tight restart loop.')]

E += [Spacer(1, 8)]
E += [callout('What a restart costs viewers',
              'Televisions on that channel rebuffer for a segment or two and then continue. '
              'Because the restart appends to the existing manifest rather than resetting the '
              'media sequence, players recover on their own without being reloaded.')]

E += [PageBreak()]

# ---- 6. SYNC --------------------------------------------------------------
E += [heading('Section 6', 'Keeping televisions in sync')]
E += [P('Every television pulling the same manifest guarantees they show the same <b>content</b>. '
        'It does not put them on the same <b>frame</b>. Each player picks its own start point near '
        'the live edge, and once two televisions drift apart nothing pulls them back - live HLS '
        'has no restoring force.')]
E += [P('So each television holds a fixed latency behind a shared clock:')]
E += [Spacer(1, 4)]
E += [code_block([
    'target = serverNow() - 12000ms',
    'drift  = hls.playingDate - target        // playingDate comes from PDT',
])]
E += [Spacer(1, 8), Sync(230), Spacer(1, 12)]

E += [P('The server clock', S_H2)]
E += [P('<font face="Courier">serverNow()</font> is round-trip corrected: t0 is recorded <b>before</b> '
        'the request and the offset is taken from the midpoint, sampled several times with the '
        'lowest-latency result kept. Measuring after the response arrives bakes in half the round '
        'trip and biases every television differently.')]

E += [Spacer(1, 6)]
E += [callout('Why this matters more than it sounds',
              'During testing an Android emulator had a clock 10.5 minutes out from the host. '
              'Without correction that television would have shown content ten minutes away from '
              'every other screen. The correction absorbed it silently, and the two clients still '
              'agreed on frame.')]

E += [Spacer(1, 10)]
E += [P('Why the rate correction is gentle', S_H2)]
E += [P('Corrections use plus or minus two percent. Larger adjustments close the gap faster but '
        'are audible as a pitch shift on anything with sound, and visible as judder. Two percent '
        'closes a two-second error in roughly a hundred seconds, which is imperceptible and still '
        'fast enough in practice.')]

E += [PageBreak()]

# ---- 7. PAIRING -----------------------------------------------------------
E += [heading('Section 7', 'Pairing a television')]
E += [P('A television is an appliance, not a personal device. It is authorised once by an '
        'operator and never asks anyone for anything again.')]
E += [Spacer(1, 6), Pairing(215), Spacer(1, 10)]

E += [P('The code is a doorbell, not a key', S_H2)]
E += [P('The six-character code grants nothing. It exists only so a human can point at one '
        'specific television among many. The real credential is the token, which the server '
        'creates <b>after</b> approval.')]

E += [Spacer(1, 4)]
E += [table([
    ['Property', 'Value', 'Reason'],
    ['Alphabet', 'A-Z and 2-9, minus I, O, 0, 1', 'Read off a screen across a room and typed elsewhere'],
    ['Length', '6 characters', '32<super>6</super> ~ 1.07 billion combinations'],
    ['Lifetime', '15 minutes', 'Long enough for setup, short enough to expire'],
    ['Generated with', 'crypto.randomInt', 'Math.random is not suitable for credentials'],
    ['Token', '48 hex characters', 'Issued only on approval; stored permanently'],
], [66, 104, CONTENT_W - 170])]

E += [Spacer(1, 10)]
E += [P('Why not a login screen', S_H2)]
E += [P('Consider a building-wide power cut at 6am. With a login screen, somebody walks to every '
        'television and types an email address using a remote control on an on-screen keyboard. '
        'With pairing, every screen returns on its own. This single consideration drives the '
        'entire design.')]

E += [Spacer(1, 8)]
E += [P('Unpairing', S_H2)]
E += [P('Removing a device deletes its record and token. The television is not notified - nothing '
        'is ever pushed to a television. Within 30 seconds its heartbeat returns 401, at which '
        'point it clears its stored token and displays a fresh pairing code.')]

E += [Spacer(1, 8)]
E += [P('Knowing a television is online', S_H2)]
E += [P('There is no connection to monitor, so the television reports in. Its 30-second heartbeat '
        'stamps a last-seen time, and the dashboard marks a screen online if it has been seen '
        'within 90 seconds - three missed beats. The heartbeat is not on the video path: if it '
        'fails entirely, playback continues and the television merely goes grey in the dashboard.')]

E += [PageBreak()]

# ---- 8. WIREFRAMES --------------------------------------------------------
E += [heading('Section 8', 'Screen wireframes')]
E += [P('Three screens exist in the entire system. Most televisions only ever display the second '
        'one.')]

E += [Spacer(1, 10)]
E += [P('8.1  Television - pairing (first boot only)', S_H2), Spacer(1, 4)]
E += [WirePairing(238)]

E += [Spacer(1, 14)]
E += [P('8.2  Television - player (every boot thereafter)', S_H2), Spacer(1, 4)]
E += [WirePlayer(238)]

E += [PageBreak()]
E += [P('8.3  Operator dashboard (browser)', S_H2), Spacer(1, 4)]
E += [WireDashboard(300)]
E += [Spacer(1, 10)]
E += [P('The dashboard is the only place a television can be authorised, moved between channels, '
        'or removed. Channel health, uptime and restart counts are shown per channel, and each '
        'paired television carries a dropdown that reassigns it to a different playlist. The '
        'change reaches the television on its next heartbeat, within 30 seconds.')]

E += [PageBreak()]

# ---- 9. API ---------------------------------------------------------------
E += [heading('Section 9', 'API reference')]
E += [P('Every endpoint lives in one file, <font face="Courier">channel-server/server.js</font>, '
        'matched by a plain "METHOD /path" string - no framework, no router library.')]

E += [Spacer(1, 8)]
E += [P('Device endpoints', S_H2), Spacer(1, 3)]
E += [table([
    ['Endpoint', 'Purpose'],
    ['POST /api/device/pair/start', 'TV requests a pairing code. Unauthenticated.'],
    ['GET /api/device/pair/status', 'TV polls every 2s until an operator claims it.'],
    ['GET /api/device/config', 'Boot config and 30s heartbeat. Bearer token. The only authenticated call.'],
], [148, CONTENT_W - 148], mono_cols=(0,))]

E += [Spacer(1, 10)]
E += [P('Operator endpoints', S_H2), Spacer(1, 3)]
E += [table([
    ['Endpoint', 'Purpose'],
    ['POST /api/admin/claim', 'Authorise a device onto a channel. The system\'s trust boundary.'],
    ['POST /api/admin/unpair', 'Delete a device and its token.'],
    ['POST /api/admin/device/channel', 'Move a television to another channel.'],
    ['GET /api/admin/devices', 'Fleet list with online state.'],
    ['GET /api/admin/channels', 'Channel list with health.'],
    ['POST /api/admin/reload', 'Restart one encoder after a playlist change.'],
    ['GET /api/status', 'All channel health plus server time.'],
], [148, CONTENT_W - 148], mono_cols=(0,))]

E += [Spacer(1, 10)]
E += [P('The video path', S_H2), Spacer(1, 3)]
E += [table([
    ['Endpoint', 'Purpose'],
    ['GET /channels/&lt;id&gt;/live.m3u8', 'The channel. No token, no session, no headers.'],
    ['GET /channels/&lt;id&gt;/seg_*.ts', 'Media segments. Immutable once written.'],
], [148, CONTENT_W - 148], mono_cols=(0,))]

E += [Spacer(1, 10)]
E += [P('Cache policy', S_H2), Spacer(1, 3)]
E += [table([
    ['File', 'Header', 'Reason'],
    ['*.m3u8', 'no-cache, no-store', 'Rewritten every four seconds'],
    ['*.ts', 'max-age=31536000, immutable', 'Never changes once written'],
], [56, 128, CONTENT_W - 184], mono_cols=(0, 1))]

E += [Spacer(1, 8)]
E += [callout('Cache headers decide whether this works',
              'A CDN caching the manifest stalls every television at once, and looks exactly '
              'like an encoder failure while you debug it.', warn=True)]

E += [PageBreak()]

# ---- 10. RUNNING ----------------------------------------------------------
E += [heading('Section 10', 'Running the system')]

E += [P('Prepare content, once', S_H2), Spacer(1, 3)]
E += [code_block(['cd channel-server && ./fetch-content.sh'])]
E += [P('Downloads 60-second excerpts from three Blender open movies and normalises them to '
        'identical encoding parameters.', S_SMALL)]

E += [Spacer(1, 10)]
E += [P('Start the channels', S_H2), Spacer(1, 3)]
E += [code_block(['cd channel-server && node server.js'])]
E += [P('Starts one ffmpeg per channel and serves the dashboard on port 4000. Stop with Ctrl+C; '
        'the server shuts its encoders down cleanly rather than orphaning them.', S_SMALL)]

E += [Spacer(1, 10)]
E += [P('Build and install the television app', S_H2), Spacer(1, 3)]
E += [code_block([
    'cd tv-app && npm install',
    'npm run android:apk',
    'adb install -r android/app/build/outputs/apk/debug/app-debug.apk',
])]

E += [Spacer(1, 12)]
E += [P('Project layout', S_H2), Spacer(1, 3)]
E += [table([
    ['Path', 'Contents'],
    ['channel-server/server.js', 'All APIs, static serving, cache policy'],
    ['channel-server/engine.js', 'ffmpeg supervision, one engine per channel'],
    ['channel-server/store.js', 'Device records: codes, tokens, last-seen'],
    ['channel-server/channels.json', 'Channel definitions'],
    ['channel-server/fetch-content.sh', 'Downloads and normalises source clips'],
    ['channel-server/public/admin.html', 'Operator dashboard'],
    ['tv-app/src/pages/Pairing.js', 'First-boot pairing screen'],
    ['tv-app/src/pages/Player.js', 'The entire client: player and latency hold'],
    ['tv-app/src/utils/device.js', 'Identity, credentials, server clock'],
], [148, CONTENT_W - 148], mono_cols=(0,))]

E += [Spacer(1, 12)]
E += [P('Porting to webOS and Tizen', S_H2)]
E += [P('The television app builds to three plain web files. Nothing platform-specific lives in '
        'the player - it is a video element, hls.js and a drift loop. The Android-only pieces are '
        'the Capacitor wrapper, MainActivity, and one branch inside '
        '<font face="Courier">getApiBase()</font>. Adding a platform means adding a packaging '
        'directory and a branch in that one function.')]

E += [Spacer(1, 8)]
E += [callout('Two LightningJS details that cost real debugging time',
              'Dynamic bindings need the colon prefix - content="$code" renders once and never '
              'updates, while :content="$code" is reactive. And nothing layered above the video '
              'may be painted opaque: the canvas sits above the video element, so an opaque root '
              'hides the picture while overlay text still draws, which looks exactly like '
              'playback failure.')]

E += [PageBreak()]

# ---- 11. OPERATING --------------------------------------------------------
E += [heading('Section 11', 'Operating it')]

E += [P('What to watch', S_H2)]
E += [P('The dashboard surfaces everything that matters, and the same data is available from '
        '<font face="Courier">GET /api/status</font> for external monitoring.')]
E += [Spacer(1, 4)]
E += [table([
    ['Signal', 'Healthy', 'What it means if not'],
    ['onAir', 'true', 'The manifest has not been written in the last 15 seconds.'],
    ['manifestAgeSeconds', 'under 5', 'Segment production is falling behind or has stopped.'],
    ['restartCount', 'stable', 'A climbing count means an encoder is failing repeatedly.'],
    ['segmentsOnDisk', '6 to 8', 'Far more suggests deletion is failing and the disk will fill.'],
    ['device online', 'true', 'No heartbeat for 90 seconds. The screen may still be playing.'],
], [78, 52, CONTENT_W - 130])]

E += [Spacer(1, 12)]
E += [P('Changing what is on air', S_H2)]
E += [Spacer(1, 3)]
E += [table([
    ['Task', 'How', 'Effect on viewers'],
    ['Move a TV to another channel', 'Dashboard dropdown',
     'That screen switches within 30 seconds. Others unaffected.'],
    ['Add or remove a video', 'Edit the directory and playlist, then reload that channel',
     'Televisions on that channel rebuffer briefly. Other channels unaffected.'],
    ['Add a channel', 'New content directory plus a channels.json entry, then restart',
     'All channels restart. Plan for a quiet period.'],
], [86, 128, CONTENT_W - 214])]

E += [Spacer(1, 12)]
E += [P('Capacity planning', S_H2)]
E += [P('Encoding is the only meaningful cost: each channel consumes most of one CPU core. '
        'Viewers cost almost nothing, because every television is served the same static files. '
        'If encoder CPU becomes the constraint, normalise all source clips to identical '
        'parameters and switch the engine to stream copying, which removes the encode entirely.')]

E += [Spacer(1, 12)]
E += [P('Recovering from problems', S_H2)]
E += [Spacer(1, 3)]
E += [table([
    ['Symptom', 'Likely cause', 'Action'],
    ['One channel frozen, others fine', 'Wedged encoder',
     'The watchdog restarts it within 20 seconds. A rising restart count means the source files need checking.'],
    ['All televisions stall at once', 'Manifest being cached',
     'Check cache headers at every hop. This almost always means a proxy or CDN.'],
    ['A television shows a pairing code unexpectedly',
     'Its record was removed', 'Re-pair it from the dashboard.'],
    ['A television is stuck reconnecting', 'Server unreachable at boot',
     'It retries indefinitely and recovers on its own once the server returns.'],
], [92, 82, CONTENT_W - 174])]

E += [PageBreak()]

# ---- 12. LIMITATIONS ------------------------------------------------------
E += [heading('Section 12', 'Known limitations')]
E += [P('This is a proof of concept. The architecture is sound; the following must be addressed '
        'before production use.')]

E += [Spacer(1, 6)]
E += [table([
    ['#', 'Limitation', 'Impact'],
    ['1', 'Operator APIs have no authentication',
     'Anyone who can reach the port can remove televisions or reassign channels. Fix this first.'],
    ['2', 'Playlist changes restart the encoder',
     'The concat demuxer reads its list once, so changing content is a visible cut on air for that channel.'],
    ['3', 'Device registry is a JSON file',
     'Cannot be shared between instances: no horizontal scaling, and a deploy drops pairing state.'],
    ['4', 'One origin, no CDN',
     'Every television pulls segments from a single Node process.'],
    ['5', 'No alerting',
     'The supervisor recovers a wedged encoder silently. If it failed to restart, nobody would be paged.'],
    ['6', 'Audio is muted in the player',
     'A television has no user gesture to unlock audio. The Android WebView flag is already set, so removing one line should suffice.'],
    ['7', 'No HTTPS',
     'Fine on a controlled network, unacceptable across the internet.'],
], [16, 132, CONTENT_W - 148])]

E += [Spacer(1, 14)]
E += [P('Verified behaviour', S_H2)]
E += [P('The following were observed on a running system rather than assumed.')]
E += [Spacer(1, 4)]
E += [table([
    ['Behaviour', 'Evidence'],
    ['Drift correction converges',
     'Drift closed from -2364 ms to within the 300 ms deadband, at exactly the 2% that 1.02x predicts.'],
    ['Clock skew is absorbed',
     'A client whose device clock was 10.5 minutes out still agreed on frame with a correctly-set one.'],
    ['Two platforms stay together',
     'An Android TV and a browser client showed the same frame with no communication between them.'],
    ['Wedged encoders are caught',
     'An ffmpeg process stopped producing output while still alive; the watchdog detected the stalled manifest and restarted it.'],
    ['Late joiners land correctly',
     'A television started mid-stream joined the live edge rather than the beginning.'],
    ['Clip transitions are seamless',
     'A channel moved between videos with no gap and no action on any television.'],
], [118, CONTENT_W - 118])]

E += [Spacer(1, 16)]
E += [P('Source: github.com/shashikant8383/VideoSync', S_CAP)]

doc.build(E)
print('written:', OUT)
