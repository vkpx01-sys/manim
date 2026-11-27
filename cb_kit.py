"""
cb_kit.py - shared pieces for cb_part1.py and cb_part2.py (continuous batching).
Keep it next to reducible_style.py and render with  KV_VIDEO_THEME=planetscale

Colour roles (identical in both parts):
    ORANGE  memory traffic, cost, the problem
    BLUE    tokens, idle compute
    YEL     active right now (one thing at a time)
    GRN     the fix, new arrivals
    DIM     idle, finished, not important

Transition device: content flows right-to-left as scenes change. CBScene.swap()
handles the eased handoff.
"""
from reducible_style import *

ORANGE, BLUE, GRN, YEL, DIM = BAD, RIDER, DRIVER, GOLD, TEXT_DIM


# ------------------------------------------------------------------ small pieces
def label(s, size=20, color=DIM, weight=W_REG):
    return T(s, size, color, MONO, weight)


def blk(w, h, color, fill=0.30, sw=1.4, at=None):
    """Flat block: coloured border, same colour tinted into the background."""
    r = Rectangle(width=w, height=h, stroke_color=color, stroke_width=sw,
                  fill_color=tint(color, fill), fill_opacity=1)
    return r.move_to(at) if at is not None else r


def card(s, color=BLUE, size=20, h=0.5):
    t = label(s, size, TEXT, W_MED)
    return VGroup(blk(t.width + 0.4, h, color, 0.22, 1.6), t).set_z_index(9)


def formula(*parts, size=26):
    """Terms share their colour with the picture they describe. part = str | (str, color)."""
    items = [T(p, size, TEXT, MONO, W_MED) if isinstance(p, str)
             else T(p[0], size, p[1], MONO, W_MED) for p in parts]
    return VGroup(*items).arrange(RIGHT, buff=0.14, aligned_edge=DOWN)


def pulse(mob, amount=1.08, rt=0.5):
    """Colourless 'look here' bump (never recolour a filled object)."""
    return mob.animate(rate_func=there_and_back, run_time=rt).scale(amount)


def counter(tr, fmt, pos, color=YEL, size=30):
    return always_redraw(lambda: T(fmt(tr.get_value()), size, color, MONO, W_MED
                                   ).move_to(pos).set_z_index(14))


def meter(tr, x0, y, w, color, name, size=20):
    """Horizontal meter driven by a ValueTracker (0..1). Returns (bar, label)."""
    def draw():
        v = max(tr.get_value(), 0.004)
        bar = Rectangle(width=w * v, height=0.3, stroke_width=0, fill_color=color,
                        fill_opacity=0.9).move_to([x0 + w * v / 2, y, 0])
        frame = dashed_rect(w, 0.3, RING_IDLE, sw=1.2).move_to([x0 + w / 2, y, 0])
        pct = label(f"{int(round(v * 100))}%", size, color, W_MED).next_to(frame, RIGHT, buff=0.2)
        return VGroup(frame, bar, pct).set_z_index(8)
    lab = label(name, size).next_to(np.array([x0, y, 0.0]), LEFT, buff=0.25)
    return always_redraw(draw), lab


def token_stack(m, n):
    """n thin token rows sitting on top of the machine's compute grid."""
    g = VGroup(*[Rectangle(width=m.grid.width, height=0.07, stroke_width=0,
                           fill_color=BLUE, fill_opacity=0.85) for _ in range(n)]
               ).arrange(DOWN, buff=0.04)
    return g.next_to(m.grid, UP, buff=0.22).set_z_index(8)


# ------------------------------------------------------------------ the machine
class Machine(VGroup):
    """HBM (weights) --pipe--> grid of Tensor Cores.  Illustrative, not to scale.
    light(k) lights the first k cells; start_flow() streams weight packets."""

    def __init__(self, rows=5, cols=8, cell=0.34, gap=0.06):
        super().__init__()
        gw, gh = cols * (cell + gap) - gap, rows * (cell + gap) - gap
        cells = [Rectangle(width=cell, height=cell, stroke_color=BLUE, stroke_width=1.2,
                           fill_color=tint(BLUE, 0.12), fill_opacity=1
                           ).move_to([1.21 - gw / 2 + c * (cell + gap) + cell / 2,
                                      gh / 2 - r * (cell + gap) - cell / 2, 0])
                 for r in range(rows) for c in range(cols)]
        self.cells, self.grid = cells, VGroup(*cells)
        self.hbm = surface_box(1.4, gh + 0.5, color=ORANGE, accent_fill=True,
                               inset=0.1, sw=1.6).move_to([-2.55, 0, 0])
        self.pipe = DashedVMobject(Line([-1.85, 0, 0], [1.21 - gw / 2 - 0.1, 0, 0],
                                        stroke_color=ORANGE, stroke_width=2.4), num_dashes=12)
        self.hbm_lab = label("HBM · weights", 20, ORANGE).next_to(self.hbm, DOWN, buff=0.18)
        self.tc_lab = label("Tensor Cores", 20, BLUE).next_to(self.grid, DOWN, buff=0.18)
        self.add(self.hbm, self.pipe, *cells, self.hbm_lab, self.tc_lab)

    def light(self, k, color=YEL):
        out = []
        for i, b in enumerate(self.cells):
            if i < k:
                out.append(b.animate.set_fill(color, opacity=0.9).set_stroke(color, 1.4))
            else:
                out.append(b.animate.set_fill(tint(BLUE, 0.12), opacity=1).set_stroke(BLUE, 1.2))
        return out

    def start_flow(self, n=5, speed=0.55):
        """Continuous weight traffic. Caller adds the group and MUST freeze() it before removal."""
        pk = VGroup(*[Square(0.14, stroke_width=0, fill_color=ORANGE, fill_opacity=1)
                      for _ in range(n)]).set_z_index(12)
        t = [0.0]

        def upd(g, dt):
            s, e = self.pipe.get_left(), self.pipe.get_right()
            t[0] += dt * speed
            for i, p in enumerate(g):
                p.move_to(s + (e - s) * ((t[0] + i / n) % 1.0))
        pk.add_updater(upd)
        upd(pk, 0)
        return pk


# ------------------------------------------------------------------ the roofline
class Roofline(VGroup):
    """Log-log roofline for an H100 SXM (dense BF16). Static frame first; make() builds the curves.
    Position with move_to() BEFORE calling make() or pt()."""
    RIDGE, ROOF, BW = 295.2, 989.0, 3.35          # ops/byte, TFLOPS, TB/s
    XL, XH, YL, YH = -0.5, 3.5, 0.0, 3.0           # log10 ranges (ops/byte, TFLOPS)

    def __init__(self, w=4.6, h=3.2):
        super().__init__()
        self.w, self.h = w, h
        self.o = np.array([-w / 2 + 0.25, -h / 2 + 0.1, 0.0])
        self.box = surface_box(w + 1.2, h + 1.5, color=RING_IDLE, hatched=False, inset=0.1, sw=1.4)
        ax = VGroup(Line(self.o, self.o + RIGHT * w, stroke_color=DIM, stroke_width=1.6),
                    Line(self.o, self.o + UP * h, stroke_color=DIM, stroke_width=1.6))
        ticks = VGroup()
        for v, s in ((1, "1"), (10, "10"), (100, "100"), (1000, "1k")):
            ticks.add(label(s, 18).move_to(self.pt(v, 1) + DOWN * 0.3))
            ticks.add(label(s, 18).move_to(self.pt(10 ** self.XL, v) + LEFT * 0.4))
        self.x_title = label("ops per byte of weights", 18).move_to(self.o + np.array([w / 2, -0.7, 0]))
        self.y_title = label("TFLOPS", 18).move_to(self.o + np.array([0.35, h + 0.3, 0]))
        self.add(self.box, ax, ticks, self.x_title, self.y_title)

    def pt(self, ai, perf):
        x = (np.log10(ai) - self.XL) / (self.XH - self.XL) * self.w
        y = (np.log10(perf) - self.YL) / (self.YH - self.YL) * self.h
        return self.box.get_center() + self.o + np.array([x, y, 0.0])

    def perf(self, ai):
        return min(self.BW * ai, self.ROOF)

    def make(self):
        p = self.pt
        self.slope = Line(p(0.32, self.BW * 0.32), p(self.RIDGE, self.ROOF),
                          stroke_color=ORANGE, stroke_width=4)
        self.roof = Line(p(self.RIDGE, self.ROOF), p(3000, self.ROOF),
                         stroke_color=BLUE, stroke_width=4)
        self.ridge = DashedVMobject(Line(p(self.RIDGE, 1), p(self.RIDGE, self.ROOF),
                                         stroke_color=YEL, stroke_width=2), num_dashes=14)
        return self

    def dot(self, ai, color):
        return Dot(self.pt(ai, self.perf(ai)), radius=0.11, color=color).set_z_index(12)


# ------------------------------------------------------------------ the request board
class Board:
    """32 request lanes. NOT to scale: short = 15 tokens, long = 2,000 tokens.
    Lane 31 (bottom) is the long request; pieces are plain blocks you animate yourself."""

    def __init__(self, n=32, w=9.4, lane=0.11, gap=0.03, x0=-5.6, ytop=2.45, short=1.4):
        self.n, self.w, self.lane, self.pitch = n, w, lane, lane + gap
        self.x0, self.ytop, self.short = x0, ytop, short

    def y(self, i):
        return self.ytop - i * self.pitch - self.lane / 2

    def height(self):
        return self.n * self.pitch - (self.pitch - self.lane)

    def piece(self, i, a, b, color=BLUE, fill=0.35):
        return blk(b - a, self.lane, color, fill, 1.0, [self.x0 + (a + b) / 2, self.y(i), 0])

    def idle_box(self):
        """Hatched region where lanes 0..n-2 have finished (static batching)."""
        h = (self.n - 1) * self.pitch - (self.pitch - self.lane)
        wd = self.w - self.short
        c = [self.x0 + self.short + wd / 2, self.ytop - h / 2, 0]
        return VGroup(hatch(wd, h, DIM, opacity=0.35).move_to(c),
                      dashed_rect(wd, h, DIM, sw=1.3).move_to(c)).set_z_index(5)


# ------------------------------------------------------------------ base scene
class CBScene(ReducibleScene):
    def at(self, i, dt=0.0):
        """Wait until dt seconds after paragraph i starts (i is 0-based)."""
        start = self.CUES[i - 1] if i > 0 else 0.0
        gap = start + dt - self.renderer.time
        if gap > 0.02:
            self.wait(gap)

    # --- bookkeeping: 'stage' = what swap() will slide away
    def put(self, *mobs):
        self.stage = list(getattr(self, "stage", None) or []) + list(mobs)
        return mobs[0] if len(mobs) == 1 else mobs

    def freeze(self, *mobs):
        for m in mobs:
            for s in m.get_family():
                s.clear_updaters()

    def swap(self, *new, keep=(), rt=0.9):
        """Clear the old scene and ease the next visual in from the right."""
        bg = getattr(self, "bg_img", None)
        old = [m for m in self.mobjects if m is not bg and m not in keep]
        for mob in (getattr(self, "_cap", None), getattr(self, "_note", None)):
            if mob is not None and mob not in keep and mob not in old:
                old.append(mob)
        self.freeze(*old)
        self.play(*[FadeOut(m, shift=LEFT * 1.2) for m in old],
                  *[FadeIn(n, shift=RIGHT * 0.8) for n in new],
                  run_time=rt, rate_func=smooth)
        self.remove(*old)
        if getattr(self, "_cap", None) not in keep:
            self._cap = None
        if getattr(self, "_note", None) not in keep:
            self._note = None
        self.stage = [m for m in keep if m in self.mobjects] + list(new)

    def say(self, s, key=None):
        """Caption: typed out, white with one gold keyword, same place every time."""
        t = Text(s, font=MONO, font_size=26, color=TEXT, t2c={key: YEL} if key else {})
        t.to_edge(DOWN, buff=0.45).to_edge(LEFT, buff=0.7).set_z_index(30)
        old = getattr(self, "_cap", None)
        if old is not None:
            self.play(FadeOut(old, shift=DOWN * 0.1), run_time=0.2)
        self.play(AddTextLetterByLetter(t, time_per_char=0.03), run_time=max(0.5, 0.03 * len(s)))
        self._cap = t

    # --- motion
    def burst(self, m, n=6, rt=1.1):
        """One read of the weights: packets cross the pipe once."""
        s, e = m.pipe.get_left(), m.pipe.get_right()
        ps = [Square(0.14, stroke_width=0, fill_color=ORANGE, fill_opacity=1
                     ).move_to(s).set_z_index(12) for _ in range(n)]
        self.add(*ps)
        self.play(LaggedStart(*[p.animate(rate_func=linear).move_to(e) for p in ps],
                              lag_ratio=0.18), run_time=rt)
        self.remove(*ps)