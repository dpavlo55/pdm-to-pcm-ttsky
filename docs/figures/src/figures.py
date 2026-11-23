"""Draw the data sheet's diagrams as SVG.

Run from anywhere: python3 docs/figures/src/figures.py
Writes one .svg per figure into docs/figures/. Standard library only, deterministic output.
"""

import math
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent

FONT = "Arial, Helvetica, sans-serif"
MONO = "Consolas, 'DejaVu Sans Mono', monospace"
INK = "#1f2933"
MUTED = "#52606d"
LINE = "#3e4c59"
FAINT = "#9aa5b1"
BLUE = "#8fa9c9"
LIGHT_BLUE = "#c9d6e8"
GREEN = "#81b29a"
LIGHT_GREEN = "#cfe6da"
ORANGE = "#e07a5f"
LIGHT_ORANGE = "#f6cdbf"
SAND = "#d8c38f"
LIGHT_SAND = "#efe5c9"
GREY = "#e4e7eb"
NOTE = "#fff6d5"


def text_width(s, size=12):
    return len(s) * size * 0.56


class Svg:
    def __init__(self, width, height):
        self.w = width
        self.h = height
        self.items = []

    def add(self, s):
        self.items.append(s)

    def rect(self, x, y, w, h, fill="#ffffff", stroke=LINE, rx=4, dash=None, sw=1.2):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, s, size=12, anchor="middle", weight="normal", color=INK, mono=False, italic=False):
        family = MONO if mono else FONT
        style = ' font-style="italic"' if italic else ""
        self.add(f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" text-anchor="{anchor}" '
                 f'font-weight="{weight}" fill="{color}"{style}>{escape(s)}</text>')

    def lines(self, x, y, rows, size=12, anchor="middle", gap=None):
        gap = gap or size * 1.3
        top = y - (len(rows) - 1) * gap / 2 + size * 0.35
        for i, (s, opts) in enumerate(rows):
            self.text(x, top + i * gap, s, size=opts.get("size", size), anchor=anchor,
                      weight=opts.get("weight", "normal"), mono=opts.get("mono", False),
                      color=opts.get("color", INK), italic=opts.get("italic", False))

    def box(self, x, y, w, h, title, sub=(), fill=LIGHT_BLUE, mono_title=True, dash=None, rx=4):
        self.rect(x, y, w, h, fill=fill, rx=rx, dash=dash)
        rows = [(title, {"weight": "bold", "mono": mono_title})]
        rows += [(s, {"size": 10.5, "color": MUTED}) for s in sub]
        self.lines(x + w / 2, y + h / 2, rows, gap=14)

    def path(self, pts, arrow_end=True, arrow_start=False, dash=None, color=LINE, sw=1.3):
        d = "M " + " L ".join(f"{x} {y}" for x, y in pts)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        me = ' marker-end="url(#arrow)"' if arrow_end else ""
        ms = ' marker-start="url(#arrow_start)"' if arrow_start else ""
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{da}{me}{ms}/>')

    def polyline(self, pts, color=LINE, sw=1.3, dash=None):
        self.path(pts, arrow_end=False, color=color, sw=sw, dash=dash)

    def line(self, x1, y1, x2, y2, color=LINE, sw=1.3, dash=None):
        self.path([(x1, y1), (x2, y2)], arrow_end=False, color=color, sw=sw, dash=dash)

    def polygon(self, pts, fill, stroke=LINE, sw=1.2):
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.add(f'<polygon points="{p}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def circle(self, x, y, r, fill="#ffffff", stroke=LINE, sw=1.3):
        self.add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def dot(self, x, y, r=3):
        self.add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{LINE}"/>')

    def save(self, name):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}">\n'
                '<defs>\n'
                f'<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
                f'orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="{LINE}"/></marker>\n'
                f'<marker id="arrow_start" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="8" '
                f'markerHeight="8" orient="auto"><path d="M 10 0 L 0 5 L 10 10 z" fill="{LINE}"/></marker>\n'
                '</defs>\n'
                f'<rect x="0" y="0" width="{self.w}" height="{self.h}" fill="#ffffff"/>\n')
        (OUT / f"{name}.svg").write_text(head + "\n".join(self.items) + "\n</svg>\n", encoding="utf-8")


# ---------------------------------------------------------------------------------------------
# Waveform helpers
# ---------------------------------------------------------------------------------------------

ROW_H = 22  # height of one waveform row (high to low level)


def wave_label(s, x, y, name):
    s.text(x, y + ROW_H / 2 + 4, name, anchor="end", mono=True, weight="bold", size=11.5)


def digital(s, x0, y, u, levels, color=LINE):
    """levels: string of '0'/'1', one character per unit of width u."""
    pts = []
    prev = None
    for i, c in enumerate(levels):
        yy = y if c == "1" else y + ROW_H
        x = x0 + i * u
        if prev is not None and prev != yy:
            pts.append((x, prev))
        pts.append((x, yy))
        prev = yy
    pts.append((x0 + len(levels) * u, prev))
    s.polyline(pts, color=color, sw=1.5)


def clock(s, x0, y, u, n, start_low=True):
    """n full periods, each 2 units wide (low then high, or high then low)."""
    digital(s, x0, y, u, ("01" if start_low else "10") * n)


def bus(s, x0, y, u, cells, size=10.5):
    """cells: (label, units, fill). label None draws an undefined (grey) segment."""
    x = x0
    k = 4
    for label, n, fill in cells:
        w = n * u
        pts = [(x, y + ROW_H / 2), (x + k, y), (x + w - k, y), (x + w, y + ROW_H / 2),
               (x + w - k, y + ROW_H), (x + k, y + ROW_H)]
        s.polygon(pts, fill if label is not None else GREY, sw=1.1)
        if label:
            s.text(x + w / 2, y + ROW_H / 2 + 4, label, size=size, mono=True)
        x += w


# ---------------------------------------------------------------------------------------------
# Block diagram
# ---------------------------------------------------------------------------------------------

def pin(s, x, y, name, port, side):
    """Pin marker on the chip boundary; side 'left' (input) or 'right' (output)."""
    s.rect(x - 4, y - 4, 8, 8, fill=LINE, rx=0)
    if side == "left":
        s.text(x - 10, y + 4, f"{name}  {port}", anchor="end", mono=True, size=10.5)
    else:
        s.text(x + 10, y + 4, f"{port}  {name}", anchor="start", mono=True, size=10.5)


def block_diagram():
    s = Svg(1150, 470)
    s.rect(165, 20, 820, 420, fill="#f5f7fa", stroke=MUTED, rx=8, dash="6 4")
    s.text(185, 42, "tt_um_top", anchor="start", weight="bold", color=MUTED, mono=True)
    s.text(965, 430, "single clock domain: clk (50 MHz), asynchronous reset rst_n",
           anchor="end", size=10.5, color=MUTED)

    W, H = 170, 58
    B = {
        "sync": (180, 70), "spi": (390, 70), "adapt": (600, 70), "regs": (790, 70),
        "nco": (790, 200),
        "smp": (180, 330), "cic": (390, 330), "i2s": (790, 330),
    }
    info = {
        "sync": ("2-FF synchronizers", ("SCK, MOSI, CS_N",), LIGHT_SAND, False),
        "spi": ("spi", ("SPI slave, mode 0", "8-bit shift registers"), LIGHT_SAND, True),
        "adapt": ("spi_to_regs_adapter", ("2-byte command", "protocol"), LIGHT_SAND, True),
        "regs": ("regs", ("8 registers", "PCM read buffer"), LIGHT_GREEN, True),
        "nco": ("pdm_clk_gen", ("16-bit NCO", "f = f_clk * step / 2^17"), LIGHT_ORANGE, True),
        "smp": ("pdm_sampler", ("rising edge: left", "falling edge: right"), LIGHT_BLUE, True),
        "cic": ("cic_dual_folded", ("stereo CIC, N=4, R=32", "16-bit PCM"), LIGHT_BLUE, True),
        "i2s": ("i2s", ("I2S transmitter", "16 bits per channel"), LIGHT_BLUE, True),
    }
    for k, (x, y) in B.items():
        title, sub, fill, mono = info[k]
        w = 230 if k == "cic" else W
        s.box(x, y, w, H, title, sub, fill=fill, mono_title=mono)

    # input pins (left boundary x=150) and output pins (right boundary x=970)
    for name, port, y in (("SPI_SCK", "ui_in[0]", 80), ("SPI_MOSI", "ui_in[1]", 99), ("SPI_CS_N", "ui_in[2]", 118)):
        pin(s, 165, y, name, port, "left")
        s.path([(169, y), (180, y)])
    pin(s, 165, 165, "SPI_MISO", "uio[0]", "left")
    pin(s, 165, 359, "PDM_DATA", "ui_in[3]", "left")
    s.path([(169, 359), (180, 359)])
    pin(s, 985, 229, "PDM_CLK", "uo_out[0]", "right")
    for name, port, y in (("I2S_BCLK", "uo_out[1]", 340), ("I2S_LRCLK", "uo_out[2]", 359), ("I2S_SDATA", "uo_out[3]", 378)):
        pin(s, 985, y, name, port, "right")
        s.path([(960, y), (981, y)])

    # control path
    s.path([(350, 99), (390, 99)])
    s.path([(560, 99), (600, 99)])
    s.text(580, 92, "bytes", size=10, color=MUTED)
    s.path([(770, 99), (790, 99)])
    s.path([(475, 128), (475, 165), (169, 165)])
    s.text(320, 158, "MISO (driven while CS_N is low)", size=10, color=MUTED)
    s.path([(900, 128), (900, 200)])
    s.text(908, 168, "step, enable", size=10, color=MUTED, anchor="start")

    # clocking
    s.path([(960, 229), (981, 229)])
    s.polyline([(790, 229), (265, 229)])
    s.path([(265, 229), (265, 330)])
    s.text(520, 222, "PDM clock edges (rising, falling)", size=10, color=MUTED)
    s.path([(875, 258), (875, 330)])
    s.text(883, 300, "BCLK = PDM clock", size=10, color=MUTED, anchor="start")

    # audio path
    s.path([(350, 359), (390, 359)])
    s.text(370, 395, "1-bit L, R", size=10, color=MUTED)
    s.path([(620, 359), (790, 359)])
    s.text(705, 352, "16-bit PCM L, R", size=10, color=MUTED)
    s.path([(705, 359), (705, 160), (830, 160), (830, 128)])
    s.dot(705, 359)
    s.text(712, 185, "PCM samples", size=10, color=MUTED, anchor="start")
    s.save("block_diagram")


# ---------------------------------------------------------------------------------------------
# PDM input timing
# ---------------------------------------------------------------------------------------------

def pdm_timing():
    s = Svg(900, 230)
    x0, u = 150, 60
    y_clk, y_dat = 40, 100
    wave_label(s, x0 - 12, y_clk, "PDM_CLK")
    wave_label(s, x0 - 12, y_dat, "PDM_DATA")
    clock(s, x0, y_clk, u, 5)
    # The microphone driving the left channel changes its output after the falling edge, the
    # right-channel microphone after the rising edge; the sampler takes the value at each edge.
    cells = [(None, 0.5, GREY)]
    for i in range(5):
        cells += [(f"L{i}", 1, LIGHT_BLUE), (f"R{i}", 1, LIGHT_GREEN)]
    cells[-1] = ("R4", 0.5, LIGHT_GREEN)
    bus(s, x0, y_dat, u, cells)
    for i in range(5):
        xr = x0 + (2 * i + 1) * u
        xf = x0 + (2 * i + 2) * u
        s.line(xr, y_clk - 8, xr, y_dat + ROW_H + 30, color=FAINT, dash="4 4", sw=1)
        s.text(xr, y_dat + ROW_H + 44, "left", size=10, color=MUTED)
        if i < 4:
            s.line(xf, y_clk - 8, xf, y_dat + ROW_H + 30, color=FAINT, dash="4 4", sw=1)
            s.text(xf, y_dat + ROW_H + 44, "right", size=10, color=MUTED)
    s.text(x0 + 5 * u, 22, "PDM_DATA is sampled at every PDM_CLK edge: rising edge = left, falling edge = right",
           size=10.5, color=MUTED)
    s.text(x0 + 5 * u, 205, "one stereo PDM pair per PDM_CLK period; the CIC needs at least 8 system clocks per pair",
           size=10.5, color=MUTED)
    s.save("pdm_timing")


# ---------------------------------------------------------------------------------------------
# CIC structure
# ---------------------------------------------------------------------------------------------

def cic_structure():
    s = Svg(1040, 470)
    # control
    s.box(30, 40, 200, 86, "sequencing", ("slot 0..7: word at the head", "j 0..31: sample in period",
                                          "phase: age of word 0"), fill=LIGHT_ORANGE, mono_title=False)
    s.box(30, 190, 200, 58, "PDM pair", ("1 bit left, 1 bit right", "waits for the next rotation"),
          fill=LIGHT_BLUE, mono_title=False)

    # weight table
    s.box(560, 40, 230, 72, "tap weight table", ("70 x 15 bit, h[k] of the CIC", "ages 2-3 mirror ages 1-0"),
          fill=LIGHT_SAND, mono_title=False)
    s.path([(230, 76), (560, 76)])
    s.text(395, 69, "j, age of head word", size=10, color=MUTED)

    # gating (AND)
    s.rect(645, 150, 60, 40, fill="#ffffff")
    s.text(675, 175, "AND", size=11, weight="bold")
    s.path([(675, 112), (675, 150)])
    s.text(683, 135, "weight", size=10, color=MUTED, anchor="start")
    s.path([(230, 219), (420, 219), (420, 170), (645, 170)])
    s.text(430, 162, "PDM bit of the head word's channel", size=10, color=MUTED, anchor="start")

    # adder
    s.circle(675, 290, 20)
    s.text(675, 297, "+", size=20, weight="bold")
    s.path([(675, 190), (675, 270)])

    # ring: eight 20-bit words, data moves right, head at the right end
    rx, ry, cw, ch = 250, 270, 46, 40
    labels = ["7", "6", "5", "4", "3", "2", "1", "0"]
    for i, lab in enumerate(labels):
        s.rect(rx + i * cw, ry, cw, ch, fill=LIGHT_BLUE if i >= 0 else GREY, rx=2)
        s.text(rx + i * cw + cw / 2, ry + 25, lab, size=11, mono=True)
    s.text(rx + 4 * cw, ry - 10, "accumulator ring: 8 words x 20 bit, rotates one word per clock",
           size=10.5, color=MUTED)
    s.text(rx + 8 * cw - 2, ry + ch + 16, "head", size=10, color=MUTED, anchor="end")
    s.text(rx + 2, ry + ch + 16, "tail", size=10, color=MUTED, anchor="start")
    s.path([(rx + 8 * cw, 290), (655, 290)])

    # write-back through the restart mux
    s.path([(695, 290), (740, 290), (740, 400), (160, 400), (160, 300), (190, 300)])
    s.rect(190, 275, 40, 50, fill="#ffffff")
    s.text(210, 296, "0", size=11, mono=True)
    s.text(210, 312, "sum", size=9.5, mono=True)
    s.path([(230, 290), (250, 290)])
    s.text(176, 345, "0: clear after reset,", size=10, color=MUTED, anchor="start")
    s.text(176, 358, "restart after output", size=10, color=MUTED, anchor="start")
    s.dot(740, 290)

    # output
    s.path([(740, 290), (800, 290)])
    s.box(800, 255, 210, 70, "output stage", ("age 3 at j = 31: S = sum", "PCM = top 16 bits of 2S - 2^20",
                                              "saturate S = 2^20 to +32767"), fill=LIGHT_GREEN, mono_title=False)
    s.path([(905, 325), (905, 400)])
    s.box(800, 400, 210, 50, "sig_out_left / sig_out_right", ("held until the next sample",),
          fill=LIGHT_GREEN, mono_title=True)
    s.text(520, 430, "words 0-3 belong to the left channel, 4-7 to the right; each channel's four words",
           size=10.5, color=MUTED)
    s.text(520, 446, "are partial outputs of different age (0..3 output periods old)", size=10.5, color=MUTED)
    s.save("cic_structure")


# ---------------------------------------------------------------------------------------------
# CIC frequency response
# ---------------------------------------------------------------------------------------------

def cic_mag_db(x, n=4, r=32):
    """Magnitude in dB at frequency x, relative to the output sample rate."""
    if x == 0:
        return 0.0
    f = x / r
    v = abs(math.sin(math.pi * f * r) / (r * math.sin(math.pi * f))) ** n
    return 20 * math.log10(v) if v > 1e-12 else -240.0


def plot_panel(s, x, y, w, h, xmax, ymin, xticks, yticks, xlabel, shade):
    s.rect(x, y, w, h, fill="#ffffff", rx=0, sw=1)
    sx = lambda v: x + v / xmax * w
    sy = lambda d: y + (0 - max(d, ymin)) / (0 - ymin) * h
    for lo, hi, fill in shade:
        s.add(f'<rect x="{sx(lo):.1f}" y="{y}" width="{sx(hi) - sx(lo):.1f}" height="{h}" fill="{fill}" '
              f'stroke="none" opacity="0.7"/>')
    for t in xticks:
        s.line(sx(t), y, sx(t), y + h, color=GREY, sw=1)
        s.text(sx(t), y + h + 16, f"{t:g}", size=10.5, color=MUTED)
    for t in yticks:
        s.line(x, sy(t), x + w, sy(t), color=GREY, sw=1)
        s.text(x - 6, sy(t) + 4, f"{t:g}", size=10.5, color=MUTED, anchor="end")
    pts = []
    steps = 900
    for i in range(steps + 1):
        v = xmax * i / steps
        pts.append((round(sx(v), 1), round(sy(cic_mag_db(v)), 1)))
    s.polyline(pts, color=LINE, sw=1.6)
    s.rect(x, y, w, h, fill="none", rx=0, sw=1)
    s.text(x + w / 2, y + h + 34, xlabel, size=11, color=INK)


def cic_response():
    s = Svg(1000, 420)
    s.text(40, 24, "Magnitude (dB)", anchor="start", size=11, weight="bold")
    band = 0.2
    shade = [(0, band, LIGHT_GREEN)] + [(k - band, k + band, LIGHT_ORANGE) for k in (1, 2, 3)]
    plot_panel(s, 70, 40, 520, 290, 3.25, -120, [0, 0.5, 1, 1.5, 2, 2.5, 3], [0, -20, -40, -60, -80, -100, -120],
               "frequency / output sample rate f_s", shade)
    plot_panel(s, 680, 40, 280, 290, 0.5, -16, [0, 0.1, 0.2, 0.3, 0.4, 0.5], [0, -4, -8, -12, -16],
               "frequency / f_s (passband detail)", [(0, band, LIGHT_GREEN)])
    s.rect(70, 392, 14, 10, fill=LIGHT_GREEN, rx=0, sw=0.8)
    s.text(90, 401, "band 0 .. 0.2 f_s (20 kHz at f_s = 96 kHz)", anchor="start", size=10.5, color=MUTED)
    s.rect(390, 392, 14, 10, fill=LIGHT_ORANGE, rx=0, sw=0.8)
    s.text(410, 401, "bands that alias into it after decimation (k f_s +/- 0.2 f_s): below -50 dB",
           anchor="start", size=10.5, color=MUTED)
    s.save("cic_response")


# ---------------------------------------------------------------------------------------------
# SPI transactions
# ---------------------------------------------------------------------------------------------

def spi_frame(s, y, title, mosi, miso):
    x0, u = 150, 26  # one SCK period = 2u
    s.text(20, y + 4, title, anchor="start", weight="bold")
    rows = {"CS_N": y + 20, "SCK": y + 58, "MOSI": y + 96, "MISO": y + 134}
    for name, yy in rows.items():
        wave_label(s, x0 - 12, yy, name)
    n = 16
    digital(s, x0, rows["CS_N"], u, "1" + "0" * (2 * n + 1) + "11")
    digital(s, x0, rows["SCK"], u, "00" + "10" * n + "00")
    for name, bits in (("MOSI", mosi), ("MISO", miso)):
        cells = [(None, 1, GREY)] + [(lab, 2, fill) for lab, fill in bits] + [(None, 2, GREY)]
        bus(s, x0, rows[name], u, cells, size=10)
    for i in range(n):
        xr = x0 + (2 + 2 * i) * u
        s.line(xr, rows["SCK"] - 4, xr, rows["MISO"] + ROW_H + 4, color=FAINT, dash="2 4", sw=0.8)
    xb = x0 + 17 * u
    s.line(xb, rows["CS_N"], xb, rows["MISO"] + ROW_H + 10, color=MUTED, dash="5 3", sw=1)
    s.text(x0 + 9 * u, rows["MISO"] + ROW_H + 24, "byte 0: command", size=10.5, color=MUTED)
    s.text(x0 + 25 * u, rows["MISO"] + ROW_H + 24, "byte 1: data", size=10.5, color=MUTED)


def spi_figures():
    s = Svg(1110, 470)
    cmd = lambda w: [("0", GREY), ("0", GREY), ("0", GREY), (w, LIGHT_SAND), ("0", GREY),
                     ("A2", LIGHT_SAND), ("A1", LIGHT_SAND), ("A0", LIGHT_SAND)]
    data = [(f"D{i}", LIGHT_GREEN) for i in range(7, -1, -1)]
    dont = [("x", "#ffffff")] * 8
    spi_frame(s, 20, "Register write", cmd("1") + data, dont + dont)
    spi_frame(s, 245, "Register read", cmd("0") + dont, dont + data)
    s.text(600, 460, "MSB first. The slave samples MOSI on rising SCK edges and updates MISO after falling edges; x = ignored / not valid",
           size=10.5, color=MUTED)
    s.save("spi_transactions")


# ---------------------------------------------------------------------------------------------
# I2S frame
# ---------------------------------------------------------------------------------------------

def i2s_frame():
    s = Svg(960, 250)
    x0, u = 150, 19  # one BCLK period = 2u; data slots start at falling edges
    rows = {"BCLK": 40, "LRCLK": 90, "SDATA": 140}
    for name, yy in rows.items():
        wave_label(s, x0 - 12, yy, name)
    slots = [("R0", "r"), ("L15", "l"), ("L14", "l"), ("L13", "l"), ("...", "l"), ("L1", "l"), ("L0", "l"),
             ("R15", "r"), ("R14", "r"), ("R13", "r"), ("...", "r"), ("R1", "r"), ("R0", "r"), ("L15", "l")]
    n = len(slots)
    digital(s, x0, rows["BCLK"], u, "0" + "10" * n)
    # LRCLK announces the next word: it switches at the start of the previous word's LSB
    nxt = [slots[i + 1][1] if i + 1 < n else "l" for i in range(n)]
    digital(s, x0, rows["LRCLK"], u, "1" + "".join(("1" if c == "r" else "0") * 2 for c in nxt))
    cells = [(None, 1, GREY)] + [(lab, 2, LIGHT_BLUE if ch == "l" else LIGHT_GREEN) for lab, ch in slots]
    bus(s, x0, rows["SDATA"], u, cells, size=10)
    s.text(x0 + 8 * u, 26, "left word: 16 BCLK", size=10.5, color=MUTED)
    s.text(x0 + 21 * u, 26, "right word: 16 BCLK", size=10.5, color=MUTED)
    s.text(530, 200, "Philips I2S: SDATA and LRCLK change on falling BCLK edges and are sampled on rising edges.",
           size=10.5, color=MUTED)
    s.text(530, 216, "LRCLK switches one BCLK before the MSB. LRCLK = 0: left, 1: right. 32 BCLK per frame "
           "(... = bits 12 to 2).", size=10.5, color=MUTED)
    s.save("i2s_frame")


# ---------------------------------------------------------------------------------------------
# External connections
# ---------------------------------------------------------------------------------------------

def ext_pin(s, x, y, name, side):
    s.rect(x - 4, y - 4, 8, 8, fill=LINE, rx=0)
    if side == "left":
        s.text(x + 10, y + 4, name, anchor="start", mono=True, size=11, weight="bold")
    else:
        s.text(x - 10, y + 4, name, anchor="end", mono=True, size=11, weight="bold")


def external_circuit():
    s = Svg(1100, 470)
    s.rect(370, 40, 360, 390, fill=LIGHT_BLUE, rx=6)
    s.text(550, 30, "Tiny Tapeout: tt_um_top", weight="bold")
    for name, y in {"ui_in[3]  PDM_DATA": 90, "uo_out[0] PDM_CLK": 130, "ui_in[0]  SPI_SCK": 250,
                    "ui_in[1]  SPI_MOSI": 285, "ui_in[2]  SPI_CS_N": 320, "uio[0]    SPI_MISO": 355}.items():
        ext_pin(s, 370, y, name, "left")
    for name, y in {"I2S_BCLK  uo_out[1]": 250, "I2S_LRCLK uo_out[2]": 285, "I2S_SDATA uo_out[3]": 320}.items():
        ext_pin(s, 730, y, name, "right")

    s.rect(30, 50, 210, 120, fill=GREY, rx=6)
    s.text(135, 40, "PDM MEMS microphone(s)", weight="bold")
    for name, y in {"DATA": 90, "CLK": 130}.items():
        s.text(230, y + 4, name, anchor="end", mono=True, size=11, weight="bold")
    s.text(135, 158, "SELECT: channel slot", size=10.5, color=MUTED)
    s.path([(240, 90), (366, 90)])
    s.path([(366, 130), (240, 130)])
    s.text(135, 192, "stereo: two microphones share CLK and DATA,", size=10, color=MUTED)
    s.text(135, 205, "one per SELECT level", size=10, color=MUTED)

    s.rect(30, 230, 210, 150, fill=LIGHT_GREEN, rx=6)
    s.text(135, 400, "SPI master (MCU)", weight="bold")
    for name, y in {"SCK": 250, "MOSI": 285, "CS": 320, "MISO": 355}.items():
        s.text(230, y + 4, name, anchor="end", mono=True, size=11, weight="bold")
    for y in (250, 285, 320):
        s.path([(240, y), (366, y)])
    s.path([(366, 355), (240, 355)])
    s.text(303, 372, "mode 0, MSB first", size=10, color=MUTED)

    s.rect(860, 230, 210, 120, fill=LIGHT_SAND, rx=6)
    s.text(965, 220, "I2S receiver (optional)", weight="bold")
    for name, y in {"BCLK": 250, "LRCLK / WS": 285, "DIN": 320}.items():
        s.text(870, y + 4, name, anchor="start", mono=True, size=11, weight="bold")
    for y in (250, 285, 320):
        s.path([(734, y), (860, y)])
    s.text(965, 340, "DAC, codec or logic analyzer", size=10.5, color=MUTED)
    s.text(550, 455, "SPI_SCK must stay idle while CS_N is high: the SPI slave counts every SCK edge (no bus sharing)",
           size=10.5, color=MUTED)
    s.save("external_circuit")


if __name__ == "__main__":
    block_diagram()
    pdm_timing()
    cic_structure()
    cic_response()
    spi_figures()
    i2s_frame()
    external_circuit()
    print("figures written to", OUT)
