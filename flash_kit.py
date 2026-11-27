"""
flash_kit.py  -  shared visual vocabulary for the FlashAttention series.

Put next to reducible_style.py. Everything here is built from real geometry
(grids, dies, pipes, packets, timelines, curves) so the picture carries the
idea and the text only labels it.   Palette comes from reducible_style:

  GOLD   the work being done / the query now
  RIDER  keys, the thing being consulted
  DRIVER values / the payload
  GREEN  the finished result
  AMBER  waiting for data
  BAD    cost, the slow path
"""
from reducible_style import *


# ------------------------------------------------------------------ small helpers
def ramp(v, lo, hi, a0=0.10, a1=0.85):
    return a0 + (a1 - a0) * (float(v) - lo) / (hi - lo + 1e-9)


def small(text, color=TEXT_DIM, size=16, weight=NORMAL, font=SANS):
    """A label. Use sparingly: the picture should do the talking."""
    return T(text, size, color, font, weight).set_z_index(12)


def live_text(fn, pos, color=GOLD, size=24, font=MONO):
    """Text that re-renders every frame from fn() -> str."""
    return always_redraw(lambda: T(fn(), size, color, font, BOLD)
                         .move_to(pos).set_z_index(12))


# ------------------------------------------------------------------ the grid of scores
def heat_grid(center, M, cell=0.8, gap=0.1, color=GOLD, numbers=False,
              nsize=16, z=7, fmt="{:.1f}"):
    """Heat-shaded grid. grid.cells[r][c] is a Square; grid.nums a VGroup."""
    M = np.asarray(M, float)
    R, C = M.shape
    lo, hi = float(M.min()), float(M.max())
    w = C * (cell + gap) - gap
    h = R * (cell + gap) - gap
    grid, nums, cells = VGroup(), VGroup(), []
    for r in range(R):
        row = []
        for c in range(C):
            sq = Square(cell, stroke_color=RING_IDLE, stroke_width=1.2,
                        stroke_opacity=0.6, fill_color=color,
                        fill_opacity=ramp(M[r, c], lo, hi)
                        ).move_to([center[0] - w / 2 + c * (cell + gap) + cell / 2,
                                   center[1] + h / 2 - r * (cell + gap) - cell / 2,
                                   0]).set_z_index(z)
            row.append(sq)
            grid.add(sq)
            if numbers:
                nums.add(T(fmt.format(M[r, c]), nsize, TEXT, MONO, BOLD
                           ).move_to(sq).set_z_index(z + 2))
        cells.append(row)
    grid.cells, grid.nums = cells, nums
    return grid


def pixel_grid(center, n, size, color=GOLD, seed=3, opacity=(0.10, 0.8), z=6):
    """n x n heat field with no per-cell strokes (cheap for big n)."""
    rng = np.random.default_rng(seed)
    cw = size / n
    g = VGroup()
    for r in range(n):
        for c in range(n):
            g.add(Square(cw * 0.9, stroke_width=0, fill_color=color,
                         fill_opacity=float(opacity[0] + (opacity[1] - opacity[0])
                                            * rng.random())
                         ).move_to([center[0] - size / 2 + (c + .5) * cw,
                                    center[1] + size / 2 - (r + .5) * cw, 0]
                                   ).set_z_index(z))
    return g


def vec_column(center, n=4, w=0.46, ch=0.24, gap=0.07, color=RIDER, seed=5,
               opacities=None):
    rng = np.random.default_rng(seed)
    g = VGroup()
    for k in range(n):
        op = float(opacities[k]) if opacities is not None else \
            0.25 + 0.5 * float(rng.random())
        g.add(Rectangle(width=w, height=ch, stroke_color=color, stroke_width=1.3,
                        fill_color=color, fill_opacity=op
                        ).move_to([center[0], center[1] + (n - 1) * (ch + gap) / 2
                                   - k * (ch + gap), 0]))
    return g.set_z_index(8)


def token_card(center, text, color=RIDER, w=1.9, h=0.72, size=19):
    box = RoundedRectangle(corner_radius=0.12, width=w, height=h,
                           stroke_color=color, stroke_width=2.4,
                           fill_color=CARD, fill_opacity=0.97)
    t = T(text, size, TEXT, MONO, BOLD).move_to(box)
    return VGroup(box, t).move_to(center).set_z_index(10)


# ------------------------------------------------------------------ icons (pure geometry)
def icon_query(center, color=GOLD, s=1.0):
    ring = Circle(radius=0.17 * s, stroke_color=color, stroke_width=3.2)
    handle = Line([0.12 * s, -0.12 * s, 0], [0.30 * s, -0.30 * s, 0],
                  stroke_color=color, stroke_width=4)
    return VGroup(ring, handle).move_to(center).set_z_index(10)


def icon_key(center, color=RIDER, s=1.0):
    tag = Polygon([-0.28 * s, 0.16 * s, 0], [0.10 * s, 0.16 * s, 0],
                  [0.30 * s, 0, 0], [0.10 * s, -0.16 * s, 0],
                  [-0.28 * s, -0.16 * s, 0],
                  stroke_color=color, stroke_width=3, fill_opacity=0)
    hole = Dot([-0.18 * s, 0, 0], radius=0.04 * s, color=color)
    return VGroup(tag, hole).move_to(center).set_z_index(10)


def icon_value(center, color=DRIVER, s=1.0):
    box = Square(0.36 * s, stroke_color=color, stroke_width=3, fill_opacity=0)
    band_v = Line([0, 0.18 * s, 0], [0, -0.18 * s, 0], stroke_color=color,
                  stroke_width=2.4)
    band_h = Line([-0.18 * s, 0, 0], [0.18 * s, 0, 0], stroke_color=color,
                  stroke_width=2.4)
    return VGroup(box, band_v, band_h).move_to(center).set_z_index(10)


def napkin(center, w=7.0, h=3.6, tilt=-2.0):
    cut = 0.7
    pts = [[-w / 2, h / 2, 0], [w / 2, h / 2, 0], [w / 2, -h / 2 + cut, 0],
           [w / 2 - cut, -h / 2, 0], [-w / 2, -h / 2, 0]]
    paper = Polygon(*pts, stroke_color=TEXT_DIM, stroke_width=2,
                    fill_color=CARD, fill_opacity=0.75)
    fold = Polygon([w / 2, -h / 2 + cut, 0], [w / 2 - cut, -h / 2, 0],
                   [w / 2 - cut, -h / 2 + cut, 0],
                   stroke_color=TEXT_DIM, stroke_width=1.6,
                   fill_color=TEXT_DIM, fill_opacity=0.25)
    g = VGroup(paper, fold)
    g.rotate(tilt * DEGREES).move_to(center).set_z_index(4)
    return g


def bolt(center, s=1.0, color=GOLD):
    pts = [[0.10, 0.5, 0], [-0.22, -0.02, 0], [-0.02, -0.02, 0],
           [-0.12, -0.5, 0], [0.24, 0.08, 0], [0.04, 0.08, 0]]
    return Polygon(*[[p[0] * s, p[1] * s, 0] for p in pts], stroke_width=0,
                   fill_color=color, fill_opacity=1).move_to(center).set_z_index(10)


# ------------------------------------------------------------------ the GPU and its memory
def gpu_die(center, w=3.2, h=2.2, rows=5, cols=7, color=RING_IDLE):
    """A chip: frame, pins and a grid of small cores. die.cores is a VGroup."""
    frame = RoundedRectangle(corner_radius=0.14, width=w, height=h,
                             stroke_color=color, stroke_width=2.6,
                             fill_color=CARD, fill_opacity=0.97)
    pins = VGroup()
    for k in range(cols):
        x = -w / 2 + (k + 0.5) * w / cols
        pins.add(Line([x, h / 2, 0], [x, h / 2 + 0.14, 0], stroke_color=color,
                      stroke_width=2),
                 Line([x, -h / 2, 0], [x, -h / 2 - 0.14, 0], stroke_color=color,
                      stroke_width=2))
    pad = 0.28
    cw = (w - 2 * pad) / cols
    ch = (h - 2 * pad) / rows
    cores = VGroup()
    for r in range(rows):
        for c in range(cols):
            cores.add(Square(min(cw, ch) * 0.7, stroke_width=0, fill_color=GOLD,
                             fill_opacity=0.12
                             ).move_to([-w / 2 + pad + (c + .5) * cw,
                                        h / 2 - pad - (r + .5) * ch, 0]))
    die = VGroup(frame, pins, cores).move_to(center).set_z_index(8)
    die.cores, die.frame = cores, frame
    return die


def core_glow(die, opacity, color=GOLD):
    return die.cores.animate.set_fill(color, opacity)


def activity_strip(tr, x0, y, unit, h, segs, wait_color=AMBER, work_color=GOLD):
    """Timeline of what the chip is doing. segs = [(length, 'c'|'w'), ...] in
    time units; unit = screen width per time unit; tr = ValueTracker(time so far).
    The strip is drawn up to tr, so sweeping tr makes time visibly pass."""
    def draw():
        t = tr.get_value()
        g = VGroup()
        s = 0.0
        for ln, kind in segs:
            if t <= s:
                break
            e = min(t, s + ln)
            wd = max((e - s) * unit, 1e-3)
            g.add(Rectangle(width=wd, height=h, stroke_width=0,
                            fill_color=work_color if kind == 'c' else wait_color,
                            fill_opacity=0.95 if kind == 'c' else 0.55
                            ).move_to([x0 + s * unit + wd / 2, y, 0]))
            s += ln
        return g.set_z_index(9)
    return always_redraw(draw)


def strip_frame(x0, y, unit, h, total):
    return Rectangle(width=total * unit, height=h, stroke_color=RING_IDLE,
                     stroke_width=1.6, fill_opacity=0
                     ).move_to([x0 + total * unit / 2, y, 0]).set_z_index(8)


def busy_fraction(segs, t):
    """Fraction of elapsed time spent on arithmetic at time t."""
    s = busy = 0.0
    for ln, kind in segs:
        if t <= s:
            break
        e = min(t, s + ln)
        if kind == 'c':
            busy += e - s
        s += ln
    return busy / t if t > 1e-6 else 0.0


def pipe(a, b, width=4, color=TEXT_DIM, opacity=0.7):
    """A data pipe: stroke width = bandwidth."""
    return Line(a, b, stroke_color=color, stroke_width=width,
                stroke_opacity=opacity).set_z_index(5)


def packet(pos, color=GOLD, s=0.2):
    return Square(s, stroke_width=0, fill_color=color, fill_opacity=1
                  ).move_to(pos).set_z_index(11)


def shelf_block(center, w, h, rows, cols, color=TEXT_DIM, fill=0.35):
    """HBM drawn as a warehouse: a big frame full of little crates."""
    frame = RoundedRectangle(corner_radius=0.12, width=w, height=h,
                             stroke_color=color, stroke_width=2.4,
                             fill_color=CARD, fill_opacity=0.97)
    crates = VGroup()
    pad = 0.18
    cw = (w - 2 * pad) / cols
    ch = (h - 2 * pad) / rows
    for r in range(rows):
        for c in range(cols):
            crates.add(Rectangle(width=cw * 0.7, height=ch * 0.62,
                                 stroke_width=0, fill_color=color,
                                 fill_opacity=fill
                                 ).move_to([-w / 2 + pad + (c + .5) * cw,
                                            h / 2 - pad - (r + .5) * ch, 0]))
    g = VGroup(frame, crates).move_to(center).set_z_index(8)
    g.crates, g.frame = crates, frame
    return g


# ------------------------------------------------------------------ scene base
class FlashScene(ReducibleScene):
    """CUES[i] = END of narration paragraph i+1. at(i, dt) waits until dt seconds
    after paragraph i ended (= start of paragraph i+1). sync(i) waits for its end."""

    def at(self, i, dt=0.0):
        start = self.CUES[i - 1] if i > 0 else 0.0
        gap = start + dt - self.renderer.time
        if gap > 0.02:
            self.wait(gap)

    def live(self, *mobs):
        self._live.extend(mobs)
        self.add(*mobs)

    def kill_live(self):
        for m in self._live:
            try:
                m.clear_updaters()
            except Exception:
                pass
        self._live = []

    def out(self, *mobs, rt=0.7):
        """Fade specific things out (keeps everything else on screen)."""
        mobs = [m for m in mobs if m is not None]
        if mobs:
            self.play(FadeOut(*mobs), run_time=rt)