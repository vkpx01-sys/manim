"""
reducible_style.py - shared Manim helpers for the series' visual themes.

Usage in any scene file (keep this file next to it):

    from reducible_style import *

    class MyScene(ReducibleScene):
        CUES = [20, 48, 75]            # END time (s) of each narration paragraph
        def construct(self):
            ...
            self.sync(0)               # pad to end of paragraph 1

Edit or add a module in kv_video_themes/ to customize a theme without changing
the other themes. Select it with render_parts.py --theme <name>.
"""
import os

import numpy as np
from manim import *

from kv_video_themes import load_theme

STYLE_THEME = os.environ.get("KV_VIDEO_THEME", "purple").strip().lower()
THEME = load_theme(STYLE_THEME)

BG_TOP = THEME.BG_TOP
BG_BOTTOM = THEME.BG_BOTTOM
BG_HEX = THEME.BG_HEX
NODE_FILL = THEME.NODE_FILL
RING_IDLE = THEME.RING_IDLE
STREET = THEME.STREET
CARD = THEME.CARD
TEXT = THEME.TEXT
TEXT_DIM = THEME.TEXT_DIM
RIDER = THEME.RIDER
DRIVER = THEME.DRIVER
GOLD = THEME.GOLD
GREEN = THEME.GREEN
AMBER = THEME.AMBER
BAD = THEME.BAD
PIN = THEME.PIN
SANS = THEME.SANS
MONO = THEME.MONO
DISPLAY = THEME.DISPLAY
TITLE_ALIGN = THEME.TITLE_ALIGN
CARD_RADIUS = THEME.CARD_RADIUS
CHIP_RADIUS = THEME.CHIP_RADIUS
CHIP_STROKE_WIDTH = THEME.CHIP_STROKE_WIDTH
CHIP_FILL_OPACITY = THEME.CHIP_FILL_OPACITY
NODE_GLOW = THEME.NODE_GLOW
NODE_IDLE_STROKE_WIDTH = THEME.NODE_IDLE_STROKE_WIDTH
NODE_ACTIVE_STROKE_WIDTH = THEME.NODE_ACTIVE_STROKE_WIDTH
FLAT_ACCENT_CHIPS = getattr(THEME, "FLAT_ACCENT_CHIPS", False)
DASH_RATIO = getattr(THEME, "DASH_RATIO", 0.55)
DASH_PER_UNIT = getattr(THEME, "DASH_PER_UNIT", 6)
HATCH_STEP = getattr(THEME, "HATCH_STEP", 0.14)

_ManimRoundedRectangle = RoundedRectangle


def RoundedRectangle(corner_radius=0.1, **kwargs):
    """Use square corners in themes that set CARD_RADIUS to zero."""
    if CARD_RADIUS <= 0:
        return Rectangle(**kwargs)
    return _ManimRoundedRectangle(corner_radius=corner_radius, **kwargs)

# semantic aliases - prefer these in algorithm scenes
STATUS = dict(idle=RING_IDLE, start=PIN, goal=DRIVER, frontier=GOLD,
              visited=GREEN, bad=BAD, wait=AMBER, dim=TEXT_DIM)


def _hex_rgb(color):
    return np.array([int(color[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float32)


# Pango falls back silently when a font is missing. Never use LaTeX (Tex/MathTex/
# DecimalNumber) unless the user explicitly asks for equations.
# ------------------------------------------------------------------ typography
EXCALIFONT = "Excalifont"

TEXT_SIZE = {
    "note": 13,
    "label": 16,
    "body": 22,
    "caption": 28,
    "section": 34,
    "title": 42,
    "hero": 54,
}
MIN_SIZE = 18

W_LIGHT = "LIGHT"      # 300
W_BOOK  = "BOOK"       # 380
W_REG   = "NORMAL"     # 400
W_MED   = "MEDIUM"     # 500
W_SEMI  = "SEMIBOLD"   # 600
W_BOLD  = "BOLD"       # 700 - thumbnail hero only

_WEIGHTS = ["THIN", "ULTRALIGHT", "LIGHT", "BOOK", "NORMAL", "MEDIUM",
            "SEMIBOLD", "BOLD", "ULTRABOLD", "HEAVY", "ULTRAHEAVY"]
MAX_WEIGHT = getattr(THEME, "MAX_WEIGHT", W_MED)


def _clamp_weight(w):
    name = str(w).upper()
    if name not in _WEIGHTS or MAX_WEIGHT not in _WEIGHTS:
        return W_REG
    return _WEIGHTS[min(_WEIGHTS.index(name), _WEIGHTS.index(MAX_WEIGHT))]


def T(s, size=TEXT_SIZE["body"], color=TEXT, font=DISPLAY, weight=W_REG, hero=False,
      t2c=None):
    """The only way to make text. hero=True bypasses the ceiling (thumbnails)."""
    w = str(weight).upper() if hero else _clamp_weight(weight)
    return Text(s, font=font, font_size=size, color=color, weight=w, t2c=t2c)


def halo(t, w=None):
    """Outline scaled to glyph size. The old fixed w=6 fattened small labels."""
    if w is None:
        size = float(getattr(t, "font_size", 24) or 24)
        w = max(1.8, min(3.6, size * 0.13))
    return t.set_stroke(BG_HEX, w, background=True)


def caption(s, color=TEXT, size=TEXT_SIZE["caption"]):
    return halo(T(s, size, color, SANS, W_MED)).to_edge(DOWN, buff=0.5).set_z_index(20)


def display_title(s, size=TEXT_SIZE["title"]):
    title = T(s, size, TEXT, DISPLAY, W_REG).to_edge(UP, buff=0.5)
    if TITLE_ALIGN == "left":
        title.to_edge(LEFT, buff=0.65)
    return title.set_z_index(20)


def labeled(obj, text, color=TEXT_DIM, size=18, side=UP):
    lab = T(text, max(size, MIN_SIZE), color, MONO, W_REG).next_to(
        obj, side, buff=0.22, aligned_edge=LEFT
    )
    return VGroup(lab, obj)


def formula(*parts, size=30):
    terms = []
    for part in parts:
        text, color = (part, TEXT) if isinstance(part, str) else part
        terms.append(T(text, max(size, MIN_SIZE), color, MONO, W_MED))
    return VGroup(*terms).arrange(RIGHT, buff=0.14, aligned_edge=DOWN)


def beat(*groups, gap=0.7, region=(12.0, 5.6)):
    if not groups or region[0] <= 0 or region[1] <= 0:
        raise ValueError("beat requires content and a positive safe region")
    group = VGroup(*groups).arrange(DOWN, buff=gap)
    if group.width <= 0 or group.height <= 0:
        raise ValueError("beat content must have positive dimensions")
    group.scale(min(1, region[0] / group.width, region[1] / group.height))
    return group.move_to(UP * 0.2)


def marching_border(center, w, h, color=GOLD, n=40, ratio=0.55,
                    speed=0.06, sw=2.0):
    """Create a stationary border whose dashes travel around its perimeter."""
    if w <= 0 or h <= 0 or n <= 0 or not 0 < ratio <= 1:
        raise ValueError("border dimensions, segment count, and ratio must be positive")
    base = Rectangle(width=w, height=h).move_to(center)
    segments = VGroup(*[
        VMobject().set_stroke(color, sw) for _ in range(n)
    ])
    phase = [0.0]

    def update(group, dt):
        phase[0] = (phase[0] + speed * dt) % 1.0
        for i, segment in enumerate(group):
            start = (i / n + phase[0]) % 1.0
            end = min(start + ratio / n, 1.0)
            segment.pointwise_become_partial(base, start, end)

    segments.add_updater(update)
    update(segments, 0)
    return segments.set_z_index(11)


def typewriter(mob, cps=34):
    """Reveal text one letter at a time instead of tracing glyph outlines."""
    if cps <= 0:
        raise ValueError("characters per second must be positive")
    return AddTextLetterByLetter(mob, time_per_char=1 / cps)


def pulse(mob, amount=1.06, rt=0.5):
    """Draw attention with a brief scale pulse without recoloring the object."""
    if amount <= 0 or rt <= 0:
        raise ValueError("pulse scale and run time must be positive")
    return mob.animate(rate_func=there_and_back, run_time=rt).scale(amount)


def packet(color=GOLD, s=0.16):
    """Create a compact square packet for flow animations."""
    return Square(s, stroke_width=0, fill_color=color,
                  fill_opacity=1).set_z_index(12)


# ------------------------------------------------------------------ nodes
class Node(VGroup):
    """Dark disc + status ring + label.
    NEVER animate .set_opacity on a Node (it fills the glow). Use .state()/.idle().
    Usage:  self.play(*node.state(GOLD))   /   self.play(*node.idle())"""

    def __init__(self, label="", pos=ORIGIN, r=0.3, ring=RING_IDLE):
        super().__init__()
        self.r = r
        self.glow = Circle(r * 1.75, stroke_width=0, fill_color=ring, fill_opacity=0)
        self.core = Circle(r, fill_color=NODE_FILL, fill_opacity=1,
                           stroke_color=ring, stroke_width=NODE_IDLE_STROKE_WIDTH)
        self.add(self.glow, self.core)
        if label:
            self.add(Text(str(label), font=SANS, weight=BOLD,
                          font_size=int(r * 68), color=TEXT))
        self.move_to(pos)
        self.set_z_index(5)

    def state(self, color, glow=NODE_GLOW):
        return (self.core.animate.set_stroke(color, width=NODE_ACTIVE_STROKE_WIDTH),
                self.glow.animate.set_fill(color, opacity=glow))

    def idle(self, color=RING_IDLE):
        return (self.core.animate.set_stroke(color, width=NODE_IDLE_STROKE_WIDTH),
                self.glow.animate.set_fill(color, opacity=0))


# ------------------------------------------------------------------ edges
def base_edge(a, b, opacity=0.5, width=2.5):
    """Faint straight edge between two nodes."""
    return Line(a.get_center(), b.get_center(), stroke_color=WHITE,
                stroke_width=width, stroke_opacity=opacity).set_z_index(1)


def arc_edge(a, b, angle=PI / 3, opacity=0.5, width=2.5):
    """Faint curved edge. angle>0 bulges below when going left->right."""
    return ArcBetweenPoints(a.get_center(), b.get_center(), angle=angle) \
        .set_stroke(WHITE, width, opacity).set_z_index(1)


def hl(edge, color, w=6.5):
    """Bright copy of an edge; Create() it on top of the faint base edge.
    Highlight = draw a copy, never recolor the base edge."""
    return edge.copy().set_stroke(color, w, 1.0).set_z_index(3)


def weight_label(edge, text, color=TEXT_DIM, size=17, offset=UP * 0.32, t=0.5):
    """Small mono weight sitting on an edge (haloed)."""
    lab = halo(T(text, size, color, MONO, BOLD))
    return lab.move_to(edge.point_from_proportion(t) + offset)


# ------------------------------------------------------------------ props
def make_pin(color=PIN, s=0.2):
    """Map pin. Place with .next_to(point, UP, buff=0) so the tip is on the point."""
    head = Circle(s, fill_color=color, fill_opacity=1, stroke_width=0)
    tip = (Triangle(fill_color=color, fill_opacity=1, stroke_width=0)
           .scale(s * 0.95).rotate(PI).next_to(head, DOWN, buff=-s * 0.5))
    hole = Circle(s * 0.38, fill_opacity=0, stroke_width=0).move_to(head)
    return VGroup(tip, head, hole).set_z_index(6)


def street_grid(w=14.5, h=8.2, nx=17, ny=10, seed=3):
    """Wobbly street network (opening-shot look). Deterministic per seed."""
    rng = np.random.default_rng(seed)
    xs = np.linspace(-w / 2, w / 2, nx)
    ys = np.linspace(-h / 2, h / 2, ny)
    P = [[np.array([x, y, 0]) + np.append(rng.normal(0, 0.08, 2), 0)
          for x in xs] for y in ys]
    g = VGroup()
    for row in P:
        m = VMobject()
        m.set_points_smoothly(row)
        g.add(m)
    for j in range(nx):
        m = VMobject()
        m.set_points_smoothly([P[i][j] for i in range(ny)])
        g.add(m)
    return g.set_stroke(STREET, 1.6, 0.9).set_z_index(-40)


def rain(center=ORIGIN, w=14, h=8, n=26, seed=7, opacity=0.22):
    rng = np.random.default_rng(seed)
    g = VGroup()
    for _ in range(n):
        x = center[0] + rng.uniform(-w / 2, w / 2)
        y = center[1] + rng.uniform(-h / 2, h / 2)
        g.add(Line([x, y, 0], [x - 0.15, y - 0.45, 0]))
    return g.set_stroke(RIDER, 1.3, opacity).set_z_index(-30)


def phone(center=ORIGIN, w=2.4, h=4.2):
    return panel_box(w, h, stroke_color=RING_IDLE, stroke_width=3,
                     fill_color=CARD, fill_opacity=0.97,
                     corner_radius=CARD_RADIUS).move_to(center).set_z_index(10)


def panel_box(width, height, stroke_color=RING_IDLE, stroke_width=2.5,
              fill_color=CARD, fill_opacity=0.97, corner_radius=None):
    radius = CARD_RADIUS if corner_radius is None else corner_radius
    if radius <= 0:
        return Rectangle(width=width, height=height, stroke_color=stroke_color,
                         stroke_width=stroke_width, fill_color=fill_color,
                         fill_opacity=fill_opacity)
    return RoundedRectangle(corner_radius=min(radius, width / 2, height / 2),
                            width=width, height=height, stroke_color=stroke_color,
                            stroke_width=stroke_width, fill_color=fill_color,
                            fill_opacity=fill_opacity)


def tint(color, amount=0.16):
    if not 0 <= amount <= 1:
        raise ValueError("tint amount must be between 0 and 1")
    return interpolate_color(ManimColor(BG_HEX), ManimColor(color), amount)


def dashed_rect(w, h, color=RING_IDLE, sw=1.4, dash_ratio=None,
                dash_per_unit=None):
    if w <= 0 or h <= 0:
        raise ValueError("dashed rectangle dimensions must be positive")
    ratio = DASH_RATIO if dash_ratio is None else dash_ratio
    density = DASH_PER_UNIT if dash_per_unit is None else dash_per_unit
    if not 0 < ratio <= 1 or density <= 0:
        raise ValueError("dash ratio must be in (0, 1] and density must be positive")
    outline = Rectangle(width=w, height=h, stroke_color=color, stroke_width=sw,
                        fill_opacity=0)
    count = max(1, int(round(2 * (w + h) * density)))
    return DashedVMobject(outline, num_dashes=count, dashed_ratio=ratio)


def hatch(w, h, color=TEXT_DIM, step=None, sw=1.0, opacity=0.55):
    if w <= 0 or h <= 0:
        raise ValueError("hatch dimensions must be positive")
    spacing = HATCH_STEP if step is None else step
    if spacing <= 0:
        raise ValueError("hatch step must be positive")
    lines = VGroup()
    offset = -(w + h) / 2
    while offset <= (w + h) / 2:
        x0 = max(-w / 2, -h / 2 - offset)
        x1 = min(w / 2, h / 2 - offset)
        if x0 < x1:
            lines.add(Line([x0, x0 + offset, 0], [x1, x1 + offset, 0],
                           stroke_color=color, stroke_width=sw,
                           stroke_opacity=opacity))
        offset += spacing
    return lines.set_z_index(8)


def surface_box(w, h, color=RING_IDLE, hatched=False, inset=0.12, sw=1.8,
                accent_fill=False):
    inner_w, inner_h = w - 2 * inset, h - 2 * inset
    if w <= 0 or h <= 0 or inner_w <= 0 or inner_h <= 0:
        raise ValueError("surface dimensions must exceed twice the inset")
    fill = tint(color, 0.16) if accent_fill else BG_HEX
    outer = panel_box(w, h, stroke_color=color, stroke_width=sw,
                      fill_color=fill, fill_opacity=1, corner_radius=0)
    center = outer.get_center()
    parts = [outer]
    if hatched:
        parts.append(hatch(inner_w, inner_h, color=color, sw=1.0)
                     .move_to(center))
    parts.append(dashed_rect(inner_w, inner_h, color=RING_IDLE, sw=1.0)
                 .move_to(center))
    return VGroup(*parts).set_z_index(6)


def badge(label, center, r=0.2):
    circle = Circle(radius=r, stroke_color=BG_HEX, stroke_width=1.2,
                    fill_color=TEXT, fill_opacity=1)
    text = T(str(label), 13, BG_HEX, MONO, W_SEMI).move_to(circle)
    return VGroup(circle, text).move_to(center).set_z_index(10)


def dashed_arrow(start, end, color=RING_IDLE, sw=1.8):
    arrow = Arrow(start, end, buff=0.1, stroke_color=color, stroke_width=sw,
                  max_tip_length_to_length_ratio=0.22)
    shaft = DashedVMobject(
        Line(arrow.get_start(), arrow.get_end(), stroke_color=color,
             stroke_width=sw),
        num_dashes=max(1, int(round(arrow.get_length() * DASH_PER_UNIT))),
        dashed_ratio=DASH_RATIO,
    )
    return VGroup(shaft, arrow.tip.copy()).set_z_index(8)


def chip(text, color=TEXT, size=18, w_pad=0.5, h=0.6):
    """Label card with centred text (e.g. 'matching service')."""
    t = T(text, size, color, SANS, BOLD)
    if FLAT_ACCENT_CHIPS:
        neutral = color in (TEXT, TEXT_DIM, RING_IDLE)
        border = RING_IDLE if neutral else color
        fill = BG_HEX if neutral else tint(color, 0.16)
        bg = Rectangle(width=t.width + w_pad * 2, height=h, stroke_width=0,
                       fill_color=fill, fill_opacity=1)
        if neutral:
            outline = dashed_rect(bg.width, h, color=RING_IDLE,
                                  sw=CHIP_STROKE_WIDTH)
            return VGroup(bg, outline, t).set_z_index(10)
        t.set_color(TEXT)
        box = Rectangle(width=bg.width, height=h, stroke_color=border,
                        stroke_width=CHIP_STROKE_WIDTH, fill_color=fill,
                        fill_opacity=CHIP_FILL_OPACITY)
        return VGroup(box, t).set_z_index(10)
    box = panel_box(t.width + w_pad * 2, h, stroke_color=RING_IDLE,
                    stroke_width=CHIP_STROKE_WIDTH, fill_color=CARD,
                    fill_opacity=CHIP_FILL_OPACITY, corner_radius=CHIP_RADIUS)
    return VGroup(box, t).set_z_index(10)


def hold_ring(center, radius=0.5, color=AMBER, dashes=14):
    """Dashed spinning ring. Caller adds: ring.add_updater(lambda m,dt: m.rotate(.9*dt))
    and MUST call ring.clear_updaters() before fading it out."""
    return DashedVMobject(Circle(radius, color=color, stroke_width=3.5),
                          num_dashes=dashes).move_to(center).set_z_index(7)


def rewind_icon(color=GOLD, label="rewind"):
    tri = VGroup(*[Triangle(fill_color=color, fill_opacity=1, stroke_width=0)
                   .scale(0.13).rotate(-PI / 2) for _ in range(2)]).arrange(RIGHT, buff=0.04)
    return VGroup(tri, T(label, 22, color, MONO, BOLD)).arrange(RIGHT, buff=0.2)


def bipartite(n_left=5, n_right=5, gap=0.8, x=3.0, top=1.6):
    """Riders (left, blue) x drivers (right, teal) with a faint full web."""
    R = VGroup(*[Node("", [-x, top - i * gap, 0], r=0.17, ring=RIDER) for i in range(n_left)])
    D = VGroup(*[Node("", [x, top - i * gap, 0], r=0.17, ring=DRIVER) for i in range(n_right)])
    web = VGroup(*[Line(r.get_center(), d.get_center(), stroke_width=1.2,
                        stroke_color=WHITE, stroke_opacity=0.18) for r in R for d in D])
    return R, D, web


def signal_trace(points, color=RIDER, width=3.2, glow=0.18):
    """Smooth waveform with a restrained halo. Points may be 2D or 3D."""
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[0] < 3 or points.shape[1] not in (2, 3):
        raise ValueError("signal_trace expects at least three 2D or 3D points")
    if not np.isfinite(points).all():
        raise ValueError("signal_trace points must be finite")
    if points.shape[1] == 2:
        points = np.column_stack((points, np.zeros(len(points))))

    line = VMobject().set_points_smoothly(points)
    halo_line = line.copy().set_stroke(color, width * 3, glow).set_z_index(3)
    core_line = line.copy().set_stroke(color, width, 0.96).set_z_index(4)
    return VGroup(halo_line, core_line)


def spectrum_bars(values, center=ORIGIN, width=8.0, height=2.4,
                  color=GOLD, gap=0.08):
    """Rounded, softly glowing frequency bars, normalized to the largest value."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("spectrum_bars expects a non-empty sequence")
    if not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError("spectrum_bars values must be finite and non-negative")
    if width <= 0 or height <= 0 or gap < 0:
        raise ValueError("spectrum_bars width and height must be positive; gap non-negative")

    bar_width = (width - gap * (len(values) - 1)) / len(values)
    if bar_width <= 0:
        raise ValueError("spectrum_bars width is too small for the requested gap")

    peak = float(values.max())
    base_y = center[1] - height / 2
    bars, glows = VGroup(), VGroup()
    for index, value in enumerate(values):
        bar_height = height * float(value) / peak if peak else 0.04
        bar_height = max(bar_height, 0.04)
        x = center[0] - width / 2 + bar_width / 2 + index * (bar_width + gap)
        bar = RoundedRectangle(
            corner_radius=min(0.08, bar_width * 0.25, bar_height * 0.25),
            width=bar_width,
            height=bar_height,
            stroke_width=0,
            fill_color=color,
            fill_opacity=0.94,
        ).move_to([x, base_y + bar_height / 2, center[2]])
        glow_bar = bar.copy().scale(1.25).set_fill(color, opacity=0.12)
        glows.add(glow_bar)
        bars.add(bar)

    baseline = Line(
        [center[0] - width / 2, base_y, center[2]],
        [center[0] + width / 2, base_y, center[2]],
        stroke_color=TEXT_DIM,
        stroke_width=1.5,
        stroke_opacity=0.65,
    )
    return VGroup(baseline, glows.set_z_index(2), bars.set_z_index(3)).set_z_index(3)


# ------------------------------------------------------------------ base scene
class ReducibleScene(MovingCameraScene):
    """Gives the selected background, camera helpers, sync-to-narration, meters.

    CUES: list of cumulative END times (seconds) of each narration paragraph.
    Optionally set AUDIO = "part1.wav" to attach audio automatically."""
    CUES = []
    AUDIO = None

    def setup(self):
        super().setup()
        self.camera.background_color = BG_HEX
        self.add(self._bg())

    def _bg(self, w=320, h=180):
        top = _hex_rgb(BG_TOP)
        bottom = _hex_rgb(BG_BOTTOM)
        mix = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None, None]
        rows = np.rint(top * (1.0 - mix) + bottom * mix).astype(np.uint8)
        rgb = np.broadcast_to(rows, (h, w, 3)).copy()
        img = ImageMobject(rgb)
        img.stretch_to_fit_width(config.frame_width * 2.6)
        img.stretch_to_fit_height(config.frame_height * 2.6)
        img.set_z_index(-100)
        self.bg_img = img
        return img

    def start_audio(self):
        import os
        if self.AUDIO and os.path.exists(self.AUDIO):
            self.add_sound(self.AUDIO)

    # ---- timing
    def sync(self, i):
        """Wait until paragraph i (0-based) ends. Prints a warning on overrun."""
        now, target = self.renderer.time, self.CUES[i]
        if now < target:
            self.wait(target - now)
        else:
            print(f"[sync] paragraph {i + 1} overran by {now - target:.1f}s")

    # ---- camera
    def zoom(self, center, width):
        """Animation: move + zoom the camera. Reset with zoom(ORIGIN, config.frame_width)."""
        return self.camera.frame.animate.set_width(width).move_to(center)

    # ---- effects
    def ping(self, pt, color, r=1.0, rt=1.5):
        """Expanding ring, used when something 'arrives' (rider, car, request)."""
        ring = Circle(0.08, color=color, stroke_width=3).move_to(pt)
        self.add(ring)
        self.play(ring.animate.scale(r / 0.08).set_stroke(opacity=0),
                  run_time=rt, rate_func=rush_from)
        self.remove(ring)

    def send(self, path, color=GOLD, rt=0.9, trail=True):
        """Animate a data packet along a line or arc."""
        moving_packet = packet(color).move_to(path.get_start())
        self.add(moving_packet)
        animations = [MoveAlongPath(moving_packet, path)]
        if trail:
            flash = path.copy().set_stroke(color, width=3)
            animations.append(ShowPassingFlash(flash))
        self.play(*animations, run_time=rt, rate_func=smooth)
        self.play(FadeOut(moving_packet, scale=0.4), run_time=0.15)

    def dim(self, *mobs, to=0.2, rt=0.5):
        for mob in mobs:
            mob.save_state()
        if mobs:
            self.play(*[mob.animate.set_opacity(to) for mob in mobs],
                      run_time=rt)

    def undim(self, *mobs, rt=0.5):
        if mobs:
            self.play(*[Restore(mob) for mob in mobs], run_time=rt)

    def section(self, title, i, n=8):
        """Move out old content, then reveal a title and episode progress rail."""
        if n <= 0 or not 0 <= i < n:
            raise ValueError("section index must be within a positive section count")
        old = [mob for mob in self.mobjects if mob is not self.bg_img]
        for mob in old:
            mob.clear_updaters()
        rule = DashedVMobject(
            Line([-7.1, 3.0, 0], [7.1, 3.0, 0],
                 stroke_color=RING_IDLE, stroke_width=1.4),
            num_dashes=70,
        ).set_z_index(15)
        rail = VGroup(*[
            Rectangle(
                width=0.5, height=0.07, stroke_width=0,
                fill_color=GOLD if k == i else RING_IDLE,
                fill_opacity=1 if k == i else 0.35,
            )
            for k in range(n)
        ]).arrange(RIGHT, buff=0.12).to_corner(UR, buff=0.45).set_z_index(20)
        title_mob = display_title(title)
        animations = [
            FadeOut(Group(*old), shift=LEFT * 0.4) if old else Wait(0.01),
            Create(rule, run_time=0.5),
            self.camera.frame.animate.set_width(config.frame_width).move_to(ORIGIN),
        ]
        self.play(*animations, run_time=0.6)
        if old:
            self.remove(*old)
        self.play(typewriter(title_mob), FadeIn(rail), run_time=0.7)
        self.add(rule)
        return title_mob

    def clear_all(self, rt=0.55):
        """Quick cut to a clean full-frame composition, stopping updaters first."""
        fg = [m for m in self.mobjects if m is not self.bg_img]
        for m in fg:
            m.clear_updaters()
        if fg:
            self.play(FadeOut(Group(*fg), shift=UP * 0.12),
                      self.camera.frame.animate.set_width(config.frame_width).move_to(ORIGIN),
                      run_time=rt)
            self.remove(*fg)

    # ---- live meter (bar that grows with a ValueTracker; no LaTeX)
    def make_meter(self, label, x0=-4.6, y=-2.9, unit=0.5, unit_name="min",
                   bad_above=None):
        """Returns (tracker, bar_mobject, label_mobject). Animate with
        self.play(tracker.animate.set_value(v)). Bar turns BAD above bad_above."""
        tr = ValueTracker(0)

        def draw():
            v = tr.get_value()
            w = max(v * unit, 0.002)
            col = BAD if (bad_above is not None and v > bad_above) else DRIVER
            r = Rectangle(width=w, height=0.36, stroke_width=0,
                          fill_color=col, fill_opacity=0.9).move_to([x0 + w / 2, y, 0])
            t = T(f"{v:.0f} {unit_name}", 20, TEXT, MONO, BOLD).next_to(r, RIGHT, buff=0.2)
            return VGroup(r, t)

        bar = always_redraw(draw)
        lab = T(label, 16, TEXT_DIM, SANS).move_to([x0 - 1.5, y, 0])
        self.add(bar)
        return tr, bar, lab

    def ghost_bar(self, value, color=BAD, x0=-4.6, y=-2.9, unit=0.5, tag=""):
        """Dashed-look outline of a previous result to compare against."""
        r = Rectangle(width=value * unit, height=0.36, stroke_color=color, stroke_width=2)
        r.set_fill(opacity=0).move_to([x0 + value * unit / 2, y, 0])
        t = T(tag, 14, color, MONO).next_to(r, UP, buff=0.12, aligned_edge=LEFT)
        return VGroup(r, t)

    def countdown(self, node, seconds=3.0, prefix="hold", color=AMBER):
        """Returns (tracker, mobject) - label under `node` that counts down."""
        tr = ValueTracker(seconds)
        lab = always_redraw(lambda: halo(T(f"{prefix}  {tr.get_value():.1f} s", 18, color,
                                           MONO, BOLD)).next_to(node, DOWN, buff=0.6))
        self.add(lab)
        return tr, lab