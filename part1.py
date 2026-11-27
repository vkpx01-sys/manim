"""
Continuous batching - Part 1: opening, setup, the static batching trap   (PlanetScale theme)

Keep together:  cb_part1.py + cb_kit.py + reducible_style.py + kv_video_themes/ + cb_part1.wav
Render:
    KV_VIDEO_THEME=planetscale manim -pqh cb_part1.py CBPart1
    KV_VIDEO_THEME=planetscale manim -sqh cb_part1.py CBPart1Thumb

TIMING
CUES = END time (s) of each narration paragraph. ESTIMATES from word counts and the
<prosody> rates. Replace with the real ends of cb_part1.wav:
    ffmpeg -i cb_part1.wav -af silencedetect=noise=-35dB:d=0.35 -f null - 2>&1 | grep silence_start
(keep the 11 longest gaps; each marks a paragraph end)

PARAGRAPH MAP
P1   hook: 989 trillion ops/s on paper, profiler says the math waits
P2   a race: fast readers wait for one slow essay; Tetris teaser
P3   prefill: read the weights once, reuse them across 1,000 tokens
P4   roofline: 989 TFLOPS / 3.35 TB/s = 295 ops per byte
P5   decode: one token per step, weights re-read every step, ~1 op/byte
P6   batch 32: one weight read serves 32 requests, still < 295
P7   obvious fix: batch more users -> but whole-request batching blocks
P8   static batch: 31 requests done at 15 tokens, one runs 2,000
P9   1,985 steps with one active request; idle, padding, KV held, queue waits
P10  Orca 2022: schedule every iteration, not every request
P11  rebuild the batch each step: finished leave, waiting enter -> but lengths differ

Illustrative on screen (labelled): lit-cell counts, meter values, board lengths.
"""
from cb_kit import *


class CBPart1(CBScene):
    AUDIO = "cb_part1.wav"
    N = 11
    CUES = [27, 52, 84, 120, 160, 193, 214, 240, 267, 284, 313]

    def construct(self):
        self.start_audio()
        self.p1_hook()
        self.p2_race()
        self.p3_prefill()
        self.p4_roofline()
        self.p5_decode()
        self.p6_batch()
        self.p7_fix()
        self.p8_static()
        self.p9_blocked()
        self.p10_iteration()
        self.p11_refill()

    # =================================================================
    # P1  payoff first: huge peak, tiny use
    # =================================================================
    def p1_hook(self):
        m = self.put(Machine().scale(1.25).move_to([0, 1.0, 0]))
        self.play(FadeIn(m, lag_ratio=0.03), run_time=2.4)

        self.at(0, 3.0)
        tr = ValueTracker(0)
        big = self.put(counter(tr, lambda v: f"{int(v)} trillion ops / second", [0, -1.1, 0], YEL, 30))
        self.add(big)
        near = self.put(label("on paper, if every core is busy", 20).move_to([0, -1.6, 0]))
        self.play(tr.animate.set_value(989), *m.light(40), FadeIn(near), run_time=2.2)

        self.at(0, 8.0)
        pk = self.put(m.start_flow())
        self.add(pk)
        tc, tm = ValueTracker(0), ValueTracker(0)
        bar_c, lab_c = meter(tc, -2.0, -2.15, 4.2, BLUE, "Tensor Cores")
        bar_m, lab_m = meter(tm, -2.0, -2.65, 4.2, ORANGE, "Memory")
        self.put(bar_c, bar_m, lab_c, lab_m)
        self.add(bar_c, bar_m)
        self.play(*m.light(1), FadeOut(near), FadeIn(lab_c), FadeIn(lab_m), run_time=0.8)
        self.play(tm.animate.set_value(1.0), tc.animate.set_value(0.07), run_time=2.0)

        self.at(0, 14.0)
        g = m.grid
        unused = self.put(hatch(g.width, g.height, BLUE, opacity=0.4).move_to(g.get_center()).set_z_index(9))
        why = self.put(chip("peak math goes unused", BLUE, 20).next_to(g, UP, buff=0.3))
        self.play(FadeIn(unused), FadeIn(why, shift=DOWN * 0.1), run_time=0.9)

        self.at(0, 19.0)
        self.say("Memory is flat out. The math waits.", "math waits")
        self.sync(0)

    # =================================================================
    # P2  fast readers wait for one slow writer; Tetris teaser
    # =================================================================
    def p2_race(self):
        n, y0, dy = 8, 1.7, 0.45
        yb = y0 - (n - 1) * dy
        track = VGroup(*[Line([-5.6, y0 - k * dy, 0], [5.0, y0 - k * dy, 0], stroke_color=RING_IDLE,
                              stroke_width=1, stroke_opacity=0.4) for k in range(n)])
        fin = VGroup(*[DashedVMobject(Line([x, y0 + 0.3, 0], [x, yb - 0.3, 0], stroke_color=DIM,
                                           stroke_width=1.5), num_dashes=22) for x in (-2.8, 5.0)])
        ftag = VGroup(label("15 tokens", 18).move_to([-2.8, y0 + 0.6, 0]),
                      label("2,000 tokens", 18).move_to([5.0, y0 + 0.6, 0]))
        racers = VGroup(*[Square(0.26, stroke_width=0, fill_color=ORANGE if k == n - 1 else BLUE,
                                 fill_opacity=1).move_to([-5.6, y0 - k * dy, 0])
                          for k in range(n)]).set_z_index(8)
        who = VGroup(chip("fast readers", BLUE, 20).move_to([-3.6, yb - 0.9, 0]),
                     chip("one slow essay", ORANGE, 20).move_to([2.6, yb - 0.9, 0]))
        self.swap(track, fin, ftag, racers, who)

        self.at(1, 2.0)
        fast, slow = racers[:7], racers[7]
        self.play(*[r.animate.set_x(-2.8) for r in fast], slow.animate.set_x(-3.9), run_time=1.6)
        self.play(*[r.animate.set_fill(DIM, opacity=0.5) for r in fast], run_time=0.5)
        wait = self.put(chip("waiting for the slowest", DIM, 20).move_to([-0.4, 0.2, 0]))
        self.play(slow.animate(rate_func=linear, run_time=5.0).set_x(5.0),
                  FadeIn(wait, run_time=0.6))

        self.at(1, 11.0)
        qc = self.put(chip("Why does the chip wait?", ORANGE, 26).move_to([0, 2.9, 0]))
        self.play(FadeIn(qc, shift=DOWN * 0.15), run_time=0.8)

        self.at(1, 14.5)
        cols, rows, s, cy = 6, 4, 0.55, 0.1
        c0 = np.array([-cols * s / 2, cy - rows * s / 2, 0.0])
        well = surface_box(cols * s + 0.3, rows * s + 0.3, color=RING_IDLE, hatched=False,
                           inset=0.08, sw=1.4).move_to([0, cy, 0])
        shapes = [([(0, 0), (1, 0), (2, 0)], YEL), ([(3, 0), (4, 0), (5, 0), (5, 1)], BLUE),
                  ([(0, 1), (1, 1), (0, 2), (1, 2)], GRN), ([(2, 1), (3, 1), (4, 1)], YEL),
                  ([(2, 2), (3, 2), (4, 2), (5, 2)], GRN)]
        pieces = [VGroup(*[blk(s - 0.04, s - 0.04, col, 0.45, 1.4, c0 + np.array([(c + .5) * s, (r + .5) * s, 0]))
                           for c, r in cells]) for cells, col in shapes]
        tag = chip("a Tetris-style scheduler", GRN, 22).move_to([0, -2.0, 0])
        self.swap(well, tag)
        for p in pieces:
            p.shift(UP * 4)
            self.add(p)
            self.play(p.animate.shift(DOWN * 4), run_time=0.5, rate_func=rush_into)
        self.put(*pieces)

        self.at(1, 19.5)
        self.say("Why wait? Play Tetris instead.", "Tetris")
        self.sync(1)

    # =================================================================
    # P3  prefill: read once, reuse a thousand times
    # =================================================================
    def p3_prefill(self):
        m = Machine().move_to([0, -0.15, 0])
        tk = token_stack(m, 12)
        self.swap(m, tk)
        self.m, self.tk = m, tk

        self.at(2, 3.0)
        n1k = chip("1,000 tokens", BLUE, 20).next_to(tk, RIGHT, buff=0.3)
        self.play(FadeIn(n1k, shift=LEFT * 0.2), run_time=0.7)

        self.at(2, 6.0)
        self.burst(m)
        self.play(*m.light(40), run_time=0.8)

        self.at(2, 13.0)
        a = chip("read weights once", ORANGE, 20)
        b = chip("reused for 1,000 positions", YEL, 20)
        row = VGroup(a, b).arrange(RIGHT, buff=0.9).move_to([0, -2.3, 0])
        arr = dashed_arrow(a.get_right(), b.get_left(), color=DIM, sw=1.8)
        self.play(FadeIn(row, lag_ratio=0.3), Create(arr), run_time=1.2)
        self.c3 = VGroup(n1k, row, arr)
        self.put(self.c3)

        self.at(2, 22.0)
        self.say("Read once. Use it a thousand times.", "thousand times")
        self.sync(2)

    # =================================================================
    # P4  the roofline: 989 / 3.35 = 295
    # =================================================================
    def p4_roofline(self):
        m, tk = self.m, self.tk
        rf = Roofline().move_to([3.6, 0.15, 0]).make()
        self.rf = rf
        self.put(rf)
        self.play(VGroup(m, tk).animate.shift(LEFT * 3.35), FadeOut(self.c3), FadeIn(rf), run_time=1.8)

        self.at(3, 3.0)
        pl = label("3.35 TB/s", 18, ORANGE).next_to(m.pipe, DOWN, buff=0.15)
        sl = label("memory-bound", 18, ORANGE).move_to(rf.pt(0.9, 40))
        self.play(Create(rf.slope), FadeIn(pl), FadeIn(sl), run_time=1.6)

        self.at(3, 9.0)
        tl = label("989 TFLOPS", 18, BLUE).next_to(m.tc_lab, DOWN, buff=0.1)
        rl = label("compute roof", 18, BLUE).move_to(rf.pt(500, 989) + DOWN * 0.32)
        self.play(Create(rf.roof), FadeIn(tl), FadeIn(rl), run_time=1.4)

        self.at(3, 15.0)
        rg = chip("ridge ≈ 295", YEL, 18).move_to(rf.pt(295, 12))
        self.play(Create(rf.ridge), FadeIn(rg), run_time=1.0)
        self.put(rf.slope, rf.roof, rf.ridge, pl, sl, tl, rl, rg)

        self.at(3, 21.0)
        f = formula(("989 TFLOPS", BLUE), " ÷ ", ("3.35 TB/s", ORANGE), " ≈ ", ("295", YEL), size=24
                    ).move_to([3.6, -2.75, 0])
        self.play(FadeIn(f, shift=UP * 0.15), run_time=0.9)

        self.at(3, 27.0)
        d = rf.dot(1000, YEL)
        pc = chip("prefill: compute-bound", YEL, 18).move_to(rf.pt(90, 230))
        self.play(FadeIn(d, scale=2), FadeIn(pc), run_time=1.0)
        self.f, self.pdot, self.pchip = f, d, pc
        self.put(f, d, pc)

        self.at(3, 32.0)
        self.say("Prefill sits on the compute roof.", "compute roof")
        self.sync(3)

    # =================================================================
    # P5  decode: one token, weights read again, ~1 op per byte
    # =================================================================
    def p5_decode(self):
        m, rf = self.m, self.rf
        tk1 = token_stack(m, 1)
        self.play(FadeOut(self.f), FadeOut(self.pdot), FadeOut(self.pchip),
                  ReplacementTransform(self.tk, tk1), *m.light(1), run_time=1.0)
        self.tk = tk1
        self.put(tk1)

        pk = self.put(m.start_flow(n=4, speed=0.4))
        self.add(pk)
        step, outs = None, []
        for s, word in enumerate(["The", "cat", "sat"]):
            self.at(4, 2.0 + 5 * s)
            new_step = chip(f"step {s + 1}: weights read again", ORANGE, 18).move_to([-3.35, 2.4, 0])
            c = card(word, BLUE, 20).move_to([-5.7 + s * 1.3, -2.5, 0])
            gone = [FadeOut(step)] if step else []
            self.play(*gone, FadeIn(new_step), FadeIn(c, shift=RIGHT * 0.2), run_time=0.6)
            step = new_step
            outs.append(c)
        self.step5, self.outs5 = step, outs
        self.put(step, *outs)

        self.at(4, 17.0)
        dot = rf.dot(1, ORANGE)
        dl = label("decode: ~1", 18, ORANGE).move_to(rf.pt(1, 3.35) + UP * 0.4 + RIGHT * 0.7)
        gap = dashed_arrow(rf.pt(1.6, 3.35), rf.pt(250, 3.35), color=YEL, sw=1.8)
        gl = label("far from 295", 18, YEL).move_to(rf.pt(25, 7.0))
        self.play(FadeIn(dot, scale=2), FadeIn(dl), Create(gap), FadeIn(gl), run_time=1.4)
        self.dot, self.dl, self.gap, self.gl = dot, dl, gap, gl
        self.put(dot, dl, gap, gl)

        self.at(4, 24.0)
        f2 = formula(("2 B/weight", ORANGE), " · ", ("2 FLOPs", BLUE), " ≈ ", ("1 per byte", YEL), size=22
                     ).move_to([3.6, -2.75, 0])
        self.play(FadeIn(f2, shift=UP * 0.15), run_time=0.9)
        self.f2 = f2
        self.put(f2)

        self.at(4, 34.0)
        self.say("One new token. Weights read again.", "read again")
        self.sync(4)

    # =================================================================
    # P6  batch 32: one weight read, 32 tokens
    # =================================================================
    def p6_batch(self):
        m, rf = self.m, self.rf
        tk8 = token_stack(m, 8)
        req = chip("32 requests", BLUE, 20).next_to(tk8, UP, buff=0.12)
        self.play(FadeOut(self.f2), FadeOut(self.gap), FadeOut(self.gl), FadeOut(self.dl),
                  FadeOut(self.step5), *[FadeOut(c) for c in self.outs5],
                  ReplacementTransform(self.tk, tk8), FadeIn(req), *m.light(4), run_time=1.0)
        self.req = req
        self.tk = tk8
        self.put(tk8, req)
        self.say("One weight read serves 32 requests.", "32 requests")

        self.at(5, 5.0)
        self.burst(m)
        p32 = rf.pt(32, rf.perf(32))
        dl2 = label("32 ops/byte", 18, ORANGE).move_to(p32 + UP * 0.4 + RIGHT * 0.2)
        gap2 = dashed_arrow(rf.pt(48, rf.perf(32)), rf.pt(250, rf.perf(32)), color=YEL, sw=1.8)
        self.play(self.dot.animate.move_to(p32), FadeIn(dl2), Create(gap2), run_time=1.4)
        self.put(dl2, gap2)
        self.dl2, self.gap2 = dl2, gap2

        self.at(5, 14.0)
        tc, tm = ValueTracker(0), ValueTracker(0)
        bar_c, lab_c = meter(tc, -4.0, -2.2, 3.0, BLUE, "Tensor Cores")
        bar_m, lab_m = meter(tm, -4.0, -2.7, 3.0, ORANGE, "Memory")
        ill = label("illustrative", 16).move_to([-4.0, -1.85, 0])
        self.add(bar_c, bar_m)
        self.put(bar_c, bar_m, lab_c, lab_m, ill)
        self.play(FadeIn(lab_c), FadeIn(lab_m), FadeIn(ill), tm.animate.set_value(1.0),
                  tc.animate.set_value(0.11), run_time=2.0)

        self.at(5, 23.0)
        tags = VGroup(*[VGroup(dashed_rect(label(t, 18).width + 0.5, 0.5, DIM, sw=1.4),
                               label(t, 18)) for t in
                        ("model size", "precision", "context length", "KV-cache traffic")]
                      ).arrange(RIGHT, buff=0.35).move_to([0, -2.5, 0])
        self.freeze(bar_c, bar_m)
        self.play(FadeOut(bar_c), FadeOut(bar_m), FadeOut(lab_c), FadeOut(lab_m), FadeOut(ill),
                  FadeIn(tags, lag_ratio=0.25), run_time=1.4)
        self.put(tags)
        self.sync(5)

    # =================================================================
    # P7  the obvious fix, and the catch (open loop)
    # =================================================================
    def p7_fix(self):
        m, rf = self.m, self.rf
        tk12 = token_stack(m, 12)
        self.play(FadeOut(self.dl2), FadeOut(self.gap2), self.req.animate.shift(UP * 0.45),
                  ReplacementTransform(self.tk, tk12), *m.light(10),
                  self.dot.animate.move_to(rf.pt(120, rf.perf(120))), run_time=2.0)
        self.tk = tk12
        self.put(tk12)
        self.say("Batch more users. Share more reads.", "more users")

        self.at(6, 10.0)
        self.warn = chip("but: whole-request batching", ORANGE, 20).move_to([-3.6, 3.5, 0])
        self.add(self.warn)
        self.play(FadeIn(self.warn, shift=DOWN * 0.2), run_time=0.8)
        self.play(pulse(self.warn), run_time=0.6)
        self.sync(6)

    # =================================================================
    # P8  static batch: 31 finish at 15, one runs 2,000
    # =================================================================
    def p8_static(self):
        b = Board()
        self.b = b
        qbox = surface_box(1.8, 2.8, color=DIM, hatched=False, inset=0.08, sw=1.2).move_to([5.35, 0.9, 0])
        qlab = label("waiting", 18).move_to([5.35, 2.05, 0])
        qblocks = VGroup(*[blk(1.2, 0.4, GRN, 0.2, 1.2) for _ in range(3)]
                         ).arrange(DOWN, buff=0.2).move_to([5.35, 0.8, 0])
        ax = label("iterations →   (not to scale)", 18).move_to([-0.8, -2.2, 0])
        self.n_act = ValueTracker(32)
        cnt = counter(self.n_act, lambda v: f"active: {int(round(v))}", [-4.8, -2.2, 0], YEL, 28)
        self.swap(qbox, qlab, qblocks, ax, keep=(self.warn,))
        self.add(cnt)
        self.put(cnt)
        self.qblocks = qblocks

        self.at(7, 1.5)
        lanes = [b.piece(i, 0, b.short) for i in range(31)]
        long_a, long_b = b.piece(31, 0, b.short, ORANGE), b.piece(31, b.short, b.w, ORANGE)
        c1 = chip("31 quick questions · 15 tokens", BLUE, 18).move_to([-2.2, 2.9, 0])
        self.play(*[GrowFromEdge(p, LEFT) for p in lanes], GrowFromEdge(long_a, LEFT),
                  FadeIn(c1), run_time=1.4)
        self.put(*lanes, long_a, c1)
        self.lanes = lanes

        self.at(7, 5.0)
        c2 = chip("1 essay · 2,000 tokens", ORANGE, 18).move_to([3.4, -2.2, 0])
        ph = Line([b.x0 + b.short, 2.55, 0], [b.x0 + b.short, -2.0, 0], stroke_color=YEL, stroke_width=2)
        self.play(*[p.animate.set_fill(DIM, opacity=0.35).set_stroke(DIM, 1.0) for p in lanes],
                  self.n_act.animate.set_value(1), FadeIn(c2), FadeIn(ph), run_time=1.0)
        self.put(c2, ph, long_b)
        self.play(GrowFromEdge(long_b, LEFT), ph.animate.shift(RIGHT * (b.w - b.short)),
                  run_time=5.0, rate_func=linear)

        self.at(7, 16.0)
        tied = chip("the group is tied to its slowest member", ORANGE, 20).move_to([-0.5, 1.2, 0])
        self.play(FadeIn(tied, shift=UP * 0.15), run_time=0.8)
        self.put(tied)

        self.at(7, 20.0)
        self.say("The slowest request sets the pace.", "slowest")
        self.sync(7)

    # =================================================================
    # P9  1,985 steps, one active request, everyone else waits
    # =================================================================
    def p9_blocked(self):
        b = self.b
        idle = b.idle_box()
        cx = b.x0 + b.short + (b.w - b.short) / 2
        i1 = chip("idle or padding", DIM, 22).move_to([cx, 1.6, 0])
        steps = chip("1,985 more steps · 1 active request", ORANGE, 22).move_to([cx, 0.5, 0])
        i2 = chip("KV-cache memory stays reserved", ORANGE, 20).move_to([cx, -0.6, 0])
        self.play(FadeOut(self.stage[-2]), FadeOut(self.stage[-1]), FadeIn(idle), run_time=0.8)
        self.play(FadeIn(i1, shift=UP * 0.1), FadeIn(steps, shift=UP * 0.1), run_time=0.9)
        self.put(idle, i1, steps)

        self.at(8, 8.0)
        self.play(FadeIn(i2, shift=UP * 0.1), run_time=0.8)
        self.put(i2)

        self.at(8, 13.0)
        ring = hold_ring([5.35, -1.0, 0], 0.3, AMBER, 12)
        ring.add_updater(lambda mo, dt: mo.rotate(1.4 * dt))
        nw = label("new users wait", 18, AMBER).move_to([5.35, -1.55, 0])
        self.add(ring)
        self.put(ring, nw)
        self.play(FadeIn(nw), *[pulse(q, 1.12, 0.7) for q in self.qblocks], run_time=0.8)

        self.at(8, 19.0)
        hol = chip("head-of-line blocking", ORANGE, 28).move_to([cx, 2.9, 0])
        self.play(FadeIn(hol, scale=1.1), run_time=0.8)
        self.put(hol)

        self.at(8, 23.0)
        self.say("One slow request blocks the queue.", "blocks")
        self.sync(8)

    # =================================================================
    # P10  Orca 2022: schedule every iteration
    # =================================================================
    def p10_iteration(self):
        b = self.b
        self.freeze(*self.stage)
        self.play(*[FadeOut(m) for m in self.stage[-6:]], run_time=0.6)   # idle labels, ring, queue note
        ybot = b.ytop - b.height()
        cols = VGroup(*[Line([b.x0 + k * 0.78, b.ytop + 0.05, 0], [b.x0 + k * 0.78, ybot - 0.05, 0],
                             stroke_color=DIM, stroke_width=1, stroke_opacity=0.3) for k in range(13)])
        hi = Rectangle(width=0.78, height=b.height() + 0.12, stroke_color=YEL, stroke_width=2.4
                       ).move_to([b.x0 + 0.78 * 2.5 + b.short, (b.ytop + ybot) / 2, 0])
        it = label("one iteration", 18, YEL).next_to(hi, UP, buff=0.12)
        self.play(Create(cols, lag_ratio=0.05), run_time=1.2)
        self.play(Create(hi), FadeIn(it), run_time=0.8)

        self.at(9, 7.0)
        old = chip("whole requests", ORANGE, 22)
        new = chip("every iteration", GRN, 22)
        row = VGroup(old, new).arrange(RIGHT, buff=1.6).move_to([-1.5, -2.55, 0])
        arr = dashed_arrow(old.get_right(), new.get_left(), color=DIM, sw=1.8)
        strike = Line(old.get_left() + RIGHT * 0.15, old.get_right() + LEFT * 0.15, stroke_color=ORANGE, stroke_width=3)
        self.play(FadeIn(row, lag_ratio=0.3), Create(arr), run_time=1.0)
        self.play(Create(strike), run_time=0.5)
        tag = chip("Orca · 2022", YEL, 18).move_to([4.6, -2.55, 0])
        self.play(FadeIn(tag), run_time=0.6)
        self.put(cols, hi, it, row, arr, strike, tag)

        self.at(9, 13.0)
        self.say("Schedule every iteration.", "every iteration")
        self.sync(9)

    # =================================================================
    # P11  rebuild the batch each step
    # =================================================================
    def p11_refill(self):
        b = self.b
        eos = chip("end-of-sequence: leaves the batch", GRN, 18).move_to([-0.2, 2.9, 0])
        arr = dashed_arrow(eos.get_left(), [b.x0 + b.short + 0.05, b.y(6), 0], color=GRN, sw=2)
        first = b.piece(6, b.short + 0.02, b.short + 1.6, GRN, 0.4)
        self.play(FadeIn(eos), Create(arr), run_time=0.8)
        self.play(GrowFromEdge(first, LEFT), run_time=0.8)
        self.put(eos, arr, first)

        self.at(10, 6.0)
        rng = np.random.default_rng(11)
        waves = [[], [], [], []]
        for i in range(31):
            x = b.short + 0.02
            while x < b.w - 0.05:
                end = min(x + float(rng.uniform(0.9, 2.4)), b.w)
                if not (i == 6 and x < b.short + 1.7):
                    waves[min(3, int((x - b.short) / 2.0))].append(b.piece(i, x, end, GRN, 0.3))
                x = end + 0.02
        idle_old = [m for m in self.stage if m not in self.stage[-10:]]
        self.play(FadeOut(self.stage[-10]) if False else Wait(0.01), run_time=0.01)
        for w in waves:
            self.play(LaggedStart(*[GrowFromEdge(p, LEFT) for p in w], lag_ratio=0.02),
                      self.n_act.animate.set_value(min(32, self.n_act.get_value() + 10)), run_time=1.5)
            self.put(*w)
        self.play(FadeOut(self.qblocks, shift=LEFT * 1.0), run_time=0.8)

        self.at(10, 22.0)
        ask = chip("but sequences have very different lengths", ORANGE, 22).move_to([0, -2.55, 0])
        self.play(FadeIn(ask, shift=UP * 0.15), run_time=0.8)

        self.at(10, 25.5)
        self.say("Simple idea. Until the lengths differ.", "lengths differ")
        self.sync(10)


# ------------------------------------------------------------------ thumbnail
class CBPart1Thumb(CBScene):
    def construct(self):
        b = Board(w=8.4, x0=-6.4, ytop=1.55, short=1.3)
        self.add(b.idle_box())
        for i in range(31):
            self.add(b.piece(i, 0, b.short, DIM, 0.3))
        self.add(b.piece(31, 0, b.w, ORANGE, 0.4))
        head = VGroup(T("YOUR GPU IS ", 66, TEXT, MONO, W_BOLD, hero=True),
                      T("WAITING", 66, ORANGE, MONO, W_BOLD, hero=True)
                      ).arrange(RIGHT, buff=0.15, aligned_edge=DOWN).to_edge(UP, buff=0.5)
        sub = T("one slow request holds 31 others", 30, TEXT_DIM, MONO, W_REG).to_edge(DOWN, buff=0.6)
        queue = VGroup(*[blk(1.4, 0.45, GRN, 0.25, 1.4) for _ in range(3)]).arrange(DOWN, buff=0.2
                                                                                     ).move_to([5.6, 0.1, 0])
        self.add(head, sub, queue, label("waiting", 22, GRN).next_to(queue, UP, buff=0.25))