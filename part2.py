"""
Continuous batching - Part 2: selective batching, paged KV cache, chunked prefill, limits   (PlanetScale theme)

Keep together:  cb_part2.py + cb_kit.py + reducible_style.py + kv_video_themes/ + cb_part2.wav
Render:
    KV_VIDEO_THEME=planetscale manim -pqh cb_part2.py CBPart2
    KV_VIDEO_THEME=planetscale manim -sqh cb_part2.py CBPart2Thumb

TIMING
CUES = END time (s) of each narration paragraph. ESTIMATES from word counts and the
<prosody> rates (86% ~ 2.15 words/s, 92% ~ 2.3 words/s, plus the <break>s). Replace with the
real ends of cb_part2.wav:
    ffmpeg -i cb_part2.wav -af silencedetect=noise=-35dB:d=0.35 -f null - 2>&1 | grep silence_start
(keep the 15 longest gaps; each marks a paragraph end, the 16th end is the end of the file)
Every in-paragraph beat is `self.at(i, dt)` = "dt seconds after paragraph i starts", so after you
swap in the real CUES the beats stay locked to the narration.

PARAGRAPH MAP
P1   mismatch: 1,400-token request vs a short one, each query reads its own K,V
P2   selective batching 1: Q/K/V + FFN use the same weights per token -> stack tokens into one batch
P3   selective batching 2: split before attention, per-request attention, merge, batch again
P4   Orca 2022 benchmark: 36.9x vs FasterTransformer (GPT-3 175B, 16 A100) - one benchmark, not a promise
P5   fragmentation: max-length contiguous KV slab per request -> holes -> fewer requests fit
P6   PagedAttention: fixed-size blocks + block table (virtual-memory idea)
P7   blocks allocated on growth, returned to the pool; VRAM is still finite
P8   stall: 31 chats decoding, a 10,000-token prefill runs as ONE step
P9   chunked prefill (Sarathi-Serve): 512 budget = 31 decode + 481 prompt tokens, rest later
P10  bounded interruption + prefill (compute) rides on the decode weight read (memory)
P11  trade-off: chunk size vs first-token delay; disaggregated serving + KV transfer
P12  295 ops/byte is an idealised, weights-only ridge; KV reads push you back toward DRAM-bound
P13  diminishing returns: capacity, bandwidth, compute, kernels, latency decide the useful batch
P14  recap: four fixes
P15  closing argument: not peak math - keep useful work in flight (callback to Part 1's meters)
P16  Tetris closing: one more piece

Illustrative on screen (labelled): lit-cell counts, meter values, slider values, curves in P12/P13.
Real numbers on screen: 1,400 / 36.9x / 175B / 16 A100 / 2022 / 31 / 10,000 / 512 / 481 / 295.
"""
from cb_kit import *
from manim import rate_functions


# ------------------------------------------------------------------ small local helpers
def tag(s, size=18, color=DIM):
    """Dashed 'not important / caveat' tag (same look as Part 1's P6 tags)."""
    t = label(s, size, color)
    return VGroup(dashed_rect(t.width + 0.5, 0.5, color, sw=1.4), t)


def tok(w=1.0, h=0.14, color=BLUE, at=None, fill=0.35):
    return blk(w, h, color, fill, 1.0, at)


def strike(mob, color=ORANGE, sw=3):
    return Line(mob.get_left() + RIGHT * 0.15, mob.get_right() + LEFT * 0.15,
                stroke_color=color, stroke_width=sw)


def square(side, color, at):
    return Square(side, stroke_width=0, fill_color=color, fill_opacity=1).move_to(at)


# ------------------------------------------------------------------ the scene
class CBPart2(CBScene):
    AUDIO = "cb_part2.wav"
    N = 16
    CUES = [20, 39, 58, 76, 98, 117, 135, 160, 187, 214, 242, 269, 287, 305, 328, 343]

    def construct(self):
        self.start_audio()
        self.p1_mismatch()
        self.p2_selective_linear()
        self.p3_selective_attention()
        self.p4_orca_number()
        self.p5_fragmentation()
        self.p6_paged()
        self.p7_pool()
        self.p8_stall()
        self.p9_chunked()
        self.p10_bounded_mix()
        self.p11_tradeoff()
        self.p12_ridge_caveat()
        self.p13_diminishing()
        self.p14_recap()
        self.p15_closing_argument()
        self.p16_tetris()

    # one-note-at-a-time helper (used where a single caption chip is replaced by the next)
    def note(self, mob, rt=0.6):
        old = getattr(self, "_note", None)
        anims = [FadeIn(mob, shift=DOWN * 0.1)]
        if old is not None:
            anims.append(FadeOut(old, shift=DOWN * 0.1))
        self.play(*anims, run_time=rt)
        self._note = mob
        self.put(mob)

    # =================================================================
    # P1  same forward pass, very different histories
    # =================================================================
    def p1_mismatch(self):
        x0, ya, yb = -6.0, 1.2, -0.2
        bar_a = blk(5.2, 0.55, BLUE, 0.25, 1.4, [x0 + 2.6, ya, 0])
        txt_a = label("1,400 tokens of history", 18, TEXT, W_MED).move_to(bar_a)
        lab_a = label("request A", 18).move_to([x0 + 0.8, ya + 0.55, 0])
        self.play(FadeIn(lab_a), GrowFromEdge(bar_a, LEFT), FadeIn(txt_a), run_time=1.6)
        self.put(bar_a, txt_a, lab_a)

        self.at(0, 4.5)
        bar_b = blk(0.9, 0.55, BLUE, 0.25, 1.4, [x0 + 0.45, yb, 0])
        lab_b = label("request B", 18).move_to([x0 + 0.8, yb + 0.55, 0])
        short = label("short context", 18, DIM).move_to([x0 + 2.6, yb - 0.42, 0])
        self.play(FadeIn(lab_b), GrowFromEdge(bar_b, LEFT), FadeIn(short), run_time=1.2)
        self.put(bar_b, lab_b, short)

        self.at(0, 8.5)
        diff = chip("different lengths", AMBER, 18).move_to([-2.4, 0.5, 0])
        self.play(FadeIn(diff, scale=1.1), pulse(bar_a, 1.04, 0.6), pulse(bar_b, 1.1, 0.6), run_time=0.8)
        self.put(diff)

        self.at(0, 12.0)
        qa = square(0.34, YEL, [0.6, ya, 0])
        qb = square(0.34, YEL, [0.6, yb, 0])
        ql = label("current token", 16).next_to(qa, UP, buff=0.18)
        ra = dashed_arrow(qa.get_left() + LEFT * 0.08, bar_a.get_right() + RIGHT * 0.08, color=YEL, sw=1.8)
        rb = dashed_arrow(qb.get_left() + LEFT * 0.08, bar_b.get_right() + RIGHT * 0.08, color=YEL, sw=1.8)
        own = chip("each query reads its own K, V", ORANGE, 20).move_to([-2.4, -1.5, 0])
        self.play(FadeIn(qa, scale=2), FadeIn(qb, scale=2), FadeIn(ql), Create(ra), Create(rb),
                  FadeIn(own, shift=UP * 0.15), run_time=1.3)
        self.put(qa, qb, ql, ra, rb, own)

        self.at(0, 16.0)
        box = surface_box(2.6, 3.0, color=GRN, hatched=False, inset=0.1, sw=1.6).move_to([4.0, 0.5, 0])
        bt = VGroup(label("one", 20, TEXT, W_MED), label("forward pass", 20, TEXT, W_MED)
                    ).arrange(DOWN, buff=0.12).move_to(box)
        fa = dashed_arrow(qa.get_right(), [2.7, ya, 0], color=DIM, sw=1.8)
        fb = dashed_arrow(qb.get_right(), [2.7, yb, 0], color=DIM, sw=1.8)
        qc = chip("How do mismatched streams share one pass?", ORANGE, 24).move_to([0, 2.9, 0])
        self.play(FadeIn(box), FadeIn(bt), Create(fa), Create(fb), FadeIn(qc, shift=DOWN * 0.15), run_time=1.2)
        self.put(box, bt, fa, fb, qc)

        self.at(0, 17.4)
        self.say("Same pass. Different histories.", "histories")
        self.sync(0)

    # =================================================================
    # P2  selective batching, part 1: linear layers stack
    # =================================================================
    def p2_selective_linear(self):
        top = chip("Orca: selective batching", GRN, 24).move_to([0, 2.8, 0])
        wbox = blk(2.4, 2.4, ORANGE, 0.22, 1.6, [0.2, 0.15, 0])
        wt = VGroup(label("shared weights", 20, TEXT, W_MED), label("Q  K  V  +  FFN", 18, ORANGE)
                    ).arrange(DOWN, buff=0.15).move_to(wbox)
        self.swap(top, wbox, wt)

        self.at(1, 3.0)
        pos = ["pos 1400", "pos 12", "pos 530", "pos 3"]
        scat = [1.5, 0.55, -0.4, -1.35]
        cards = []
        for p_, y in zip(pos, scat):
            b = tok(1.9, 0.38, BLUE, at=[-4.8, y, 0], fill=0.3)
            t = label(p_, 16, TEXT, W_MED).move_to(b)
            cards.append(VGroup(b, t))
        self.play(LaggedStart(*[FadeIn(c, shift=RIGHT * 0.3) for c in cards], lag_ratio=0.25), run_time=2.0)
        self.put(*cards)
        ind = chip("same weights, each token independent", BLUE, 18).move_to([0.2, -2.0, 0])
        self.play(FadeIn(ind, shift=UP * 0.1), run_time=0.7)
        self.put(ind)

        self.at(1, 11.0)
        ys = [0.15 + 0.57 - k * 0.38 for k in range(4)]
        batch = dashed_rect(2.2, 1.75, GRN, sw=1.8).move_to([-4.8, 0.15, 0])
        bl = chip("one batch", GRN, 18).next_to(batch, UP, buff=0.12)
        self.play(*[c.animate.move_to([-4.8, y, 0]) for c, y in zip(cards, ys)], run_time=1.2)
        self.play(Create(batch), FadeIn(bl), run_time=0.7)
        self.put(batch, bl)

        self.at(1, 13.8)
        a1 = dashed_arrow([-3.65, 0.15, 0], wbox.get_left() + LEFT * 0.05, color=DIM, sw=1.8)
        outs = []
        for p_, y in zip(pos, ys):
            b = tok(1.9, 0.38, BLUE, at=[4.9, y, 0], fill=0.3)
            outs.append(VGroup(b, label(p_, 16, TEXT, W_MED).move_to(b)))
        a2 = dashed_arrow(wbox.get_right() + RIGHT * 0.05, [3.8, 0.15, 0], color=DIM, sw=1.8)
        self.play(Create(a1), pulse(wbox, 1.06, 0.7), run_time=0.9)
        self.play(Create(a2), LaggedStart(*[FadeIn(o, shift=RIGHT * 0.3) for o in outs], lag_ratio=0.15),
                  run_time=1.2)
        self.put(a1, a2, *outs)

        self.at(1, 16.0)
        self.say("Linear layers: stack the tokens.", "stack")
        self.sync(1)

    # =================================================================
    # P3  selective batching, part 2: split, attend, merge
    # =================================================================
    def p3_selective_attention(self):
        ys = [1.45, 0.15, -1.15]
        kvw = [3.4, 1.0, 2.2]
        names = ["req A", "req B", "req C"]
        kvx = -4.2

        stack_l = VGroup(*[tok(0.9, 0.14, BLUE, at=[-5.6, 0.15 + (1 - k) * 0.2, 0]) for k in range(3)])
        stack_r = VGroup(*[tok(0.9, 0.14, BLUE, at=[3.7, 0.15 + (1 - k) * 0.2, 0]) for k in range(3)])
        kv = VGroup(*[tok(w, 0.4, BLUE, at=[kvx + w / 2, y, 0], fill=0.22) for w, y in zip(kvw, ys)])
        kvl = VGroup(*[label(n, 16).move_to([kvx + 0.35, y + 0.42, 0]) for n, y in zip(names, ys)])
        attn = VGroup(*[blk(1.1, 0.5, DIM, 0.3, 1.4, [0.7, y, 0]) for y in ys])
        attn_t = VGroup(*[label("attn", 18, TEXT, W_MED).move_to(a) for a in attn])
        reads = VGroup(*[DashedVMobject(Line([kvx + w + 0.05, y, 0], [0.1, y, 0], stroke_color=ORANGE,
                                             stroke_width=2), num_dashes=10)
                         for w, y in zip(kvw, ys)])
        h1 = chip("batched", GRN, 18).move_to([-5.6, 2.75, 0])
        h2 = chip("separate, per request", ORANGE, 18).move_to([-1.2, 2.75, 0])
        self.swap(stack_l, h1)
        self.put(kv, kvl)
        self.play(FadeIn(kv, lag_ratio=0.2), FadeIn(kvl), run_time=1.2)
        self.play(FadeIn(attn), FadeIn(attn_t), Create(reads), FadeIn(h2), run_time=1.4)
        self.put(attn, attn_t, reads, h2)

        self.at(2, 6.0)
        fan = VGroup(*[Line([-5.1, 0.15 + (1 - k) * 0.2, 0], [kvx - 0.05, ys[k], 0], stroke_color=GRN,
                            stroke_width=2) for k in range(3)])
        splt = chip("split", GRN, 20).move_to([-4.65, -2.1, 0])
        self.play(Create(fan, lag_ratio=0.3), FadeIn(splt), run_time=1.2)
        self.put(fan, splt)

        self.at(2, 7.8)
        for k in range(3):
            self.play(attn[k].animate.set_fill(YEL, opacity=0.9).set_stroke(YEL, 1.6), run_time=0.45)
            self.play(attn[k].animate.set_fill(tint(DIM, 0.3), opacity=1).set_stroke(DIM, 1.4), run_time=0.45)
        self.play(*[a.animate.set_fill(tint(GRN, 0.3), opacity=1).set_stroke(GRN, 1.4) for a in attn], run_time=0.5)

        self.at(2, 12.5)
        merge = VGroup(*[Line([1.3, ys[k], 0], [3.2, 0.15 + (1 - k) * 0.2, 0], stroke_color=GRN,
                              stroke_width=2) for k in range(3)])
        mg = chip("merge", GRN, 20).move_to([2.4, -2.1, 0])
        self.play(Create(merge, lag_ratio=0.3), FadeIn(stack_r, lag_ratio=0.2), FadeIn(mg), run_time=1.3)
        self.put(merge, stack_r, mg)

        self.at(2, 14.6)
        nxt = blk(1.4, 0.9, ORANGE, 0.22, 1.6, [5.6, 0.15, 0])
        nt = label("FFN...", 18, TEXT, W_MED).move_to(nxt)
        h3 = chip("batched again", GRN, 18).move_to([4.2, 2.75, 0])
        ar = dashed_arrow([4.25, 0.15, 0], nxt.get_left() + LEFT * 0.05, color=DIM, sw=1.8)
        self.play(FadeIn(nxt), FadeIn(nt), Create(ar), FadeIn(h3, shift=DOWN * 0.1), run_time=1.0)
        self.put(nxt, nt, ar, h3)

        self.at(2, 15.8)
        self.say("Attention: split, read, merge.", "split")
        self.sync(2)

    # =================================================================
    # P4  Orca's number, with its caveat
    # =================================================================
    def p4_orca_number(self):
        c1 = chip("GPT-3 175B", BLUE, 20).move_to([-1.5, 2.3, 0])
        c2 = chip("16x A100 GPUs", BLUE, 20).move_to([1.5, 2.3, 0])
        ttl = label("serving throughput", 18).move_to([-4.6, 1.5, 0])
        x0, wmax, yb, yo = -2.6, 7.0, 0.7, -0.4
        base = tok(wmax / 36.9, 0.55, DIM, at=[x0 + wmax / 36.9 / 2, yb, 0], fill=0.4)
        nb = label("FasterTransformer", 18, DIM).move_to([x0 - 1.55, yb, 0])
        no = label("Orca", 20, GRN, W_MED).move_to([x0 - 0.9, yo, 0])
        one = label("1x", 24, DIM, W_MED).move_to([5.6, yb, 0])
        self.swap(c1, c2, ttl, base, nb, no, one)

        tr = ValueTracker(0.0)

        def orca_bar():
            v = max(tr.get_value(), 0.004)
            return Rectangle(width=wmax * v, height=0.55, stroke_color=GRN, stroke_width=1.4,
                             fill_color=tint(GRN, 0.5), fill_opacity=1).move_to([x0 + wmax * v / 2, yo, 0])

        bar = always_redraw(orca_bar)
        big = counter(tr, lambda v: f"{36.9 * v:.1f}x", [5.6, yo, 0], YEL, 34)
        self.add(bar, big)
        self.put(bar, big)

        self.at(3, 6.5)
        self.play(tr.animate.set_value(1.0), run_time=2.6, rate_func=smooth)
        lat = tag("at comparable median latency", 18).move_to([1.0, -1.15, 0])
        self.play(FadeIn(lat, shift=UP * 0.1), run_time=0.7)
        self.put(lat)

        self.at(3, 13.0)
        cav = chip("one 2022 benchmark, not a guaranteed multiplier", AMBER, 20).move_to([0, -1.95, 0])
        self.play(FadeIn(cav, shift=UP * 0.15), run_time=0.8)
        self.put(cav)

        self.at(3, 14.6)
        self.say("One benchmark, not a promise.", "benchmark")
        self.sync(3)

    # =================================================================
    # P5  fragmentation: max-length slabs
    # =================================================================
    def p5_fragmentation(self):
        lx, W, hgt = -5.6, 9.0, 0.38
        ys = [1.55 - k * 0.52 for k in range(6)]
        used = [1.2, 3.0, 0.7, 2.1, 0.9, 1.6]
        vr = label("VRAM", 20, DIM).move_to([lx + 0.4, 2.35, 0])
        tops = chip("requests come and go", BLUE, 20).move_to([0.3, 2.85, 0])
        usedb = VGroup(*[tok(u, hgt, BLUE, at=[lx + u / 2, y, 0], fill=0.35) for u, y in zip(used, ys)])
        self.swap(vr, tops)
        self.play(LaggedStart(*[GrowFromEdge(b, LEFT) for b in usedb], lag_ratio=0.15), run_time=1.6)
        self.put(usedb)

        self.at(4, 6.0)
        slabs = VGroup(*[dashed_rect(W, hgt, ORANGE, sw=1.6).move_to([lx + W / 2, y, 0]) for y in ys])
        sc = chip("max-length slab per request", ORANGE, 20).move_to([0.3, 2.85, 0])
        self.play(Create(slabs, lag_ratio=0.15), FadeOut(tops), FadeIn(sc), run_time=1.8)
        self.put(slabs, sc)

        self.at(4, 10.0)
        holes = VGroup(*[hatch(W - u, hgt, DIM, opacity=0.35).move_to([lx + u + (W - u) / 2, y, 0])
                         for u, y in zip(used, ys)])
        hl_ = chip("reserved, mostly unused", DIM, 20).move_to([-1.2, -1.8, 0])
        self.play(FadeIn(holes, lag_ratio=0.15), FadeIn(hl_, shift=UP * 0.1), run_time=1.6)
        self.put(holes, hl_)

        self.at(4, 14.5)
        new = tok(1.6, 0.4, GRN, at=[5.4, 0.6, 0], fill=0.4)
        nl = label("new request", 18, GRN).next_to(new, UP, buff=0.15)
        self.play(FadeIn(new, shift=LEFT * 0.4), FadeIn(nl), run_time=0.8)
        self.play(new.animate.shift(LEFT * 0.35), run_time=0.3)
        self.play(new.animate.shift(RIGHT * 0.35), run_time=0.3)
        no = chip("no free slab", AMBER, 20).move_to([5.2, -0.1, 0])
        self.play(FadeIn(no, shift=UP * 0.1), run_time=0.6)
        self.put(new, nl, no)

        self.at(4, 18.5)
        self.say("Max-length slabs leave holes.", "holes")
        self.sync(4)

    # =================================================================
    # P6  PagedAttention: blocks + block table
    # =================================================================
    def p6_paged(self):
        s, pitch = 0.5, 0.56
        gx, gy = 3.6, 0.0

        def cell_pos(i):
            r, c = divmod(i, 6)
            return [gx + (c - 2.5) * pitch, gy + (1.5 - r) * pitch, 0]

        self.cell_pos = cell_pos
        other = {0, 1, 5, 6, 10, 11, 12, 16, 17, 19, 21, 22, 23}
        self.cells = {}
        for i in range(24):
            if i in other:
                self.cells[i] = blk(s, s, DIM, 0.4, 1.0, cell_pos(i))
            else:
                self.cells[i] = blk(s, s, DIM, 0.06, 1.0, cell_pos(i))
        grid = VGroup(*self.cells.values())
        gl = label("GPU memory: fixed-size blocks", 18, DIM).move_to([gx, 1.45, 0])
        top = chip("a virtual-memory idea, for the KV cache", GRN, 22).move_to([0, 2.8, 0])
        self.top6 = top
        self.swap(grid, gl, top)

        self.at(5, 5.0)
        ys = [1.0, 0.35, -0.3, -0.95]
        self.lblocks = []
        for k, y in enumerate(ys):
            b = blk(1.3, 0.5, BLUE, 0.3, 1.4, [-5.3, y, 0])
            self.lblocks.append(VGroup(b, label(f"block {k}", 18, TEXT, W_MED).move_to(b)))
        ll = label("request A: tokens", 18, DIM).move_to([-5.3, 1.6, 0])
        fx = chip("fixed size", BLUE, 18).move_to([-5.3, -1.75, 0])
        self.play(FadeIn(ll), LaggedStart(*[FadeIn(b, shift=RIGHT * 0.2) for b in self.lblocks], lag_ratio=0.25),
                  FadeIn(fx), run_time=1.8)
        self.put(ll, fx, *self.lblocks)

        self.at(5, 11.5)
        mp = [7, 2, 9, 4]
        self.trows = []
        for k, (y, m_) in enumerate(zip(ys, mp)):
            b = blk(1.6, 0.5, YEL, 0.14, 1.4, [-2.4, y, 0])
            self.trows.append(VGroup(b, label(f"{k} -> {m_}", 20, TEXT, W_MED).move_to(b)))
        th = chip("block table", YEL, 18).move_to([-2.4, 1.6, 0])
        self.play(FadeIn(th), LaggedStart(*[FadeIn(r) for r in self.trows], lag_ratio=0.2), run_time=1.2)
        self.put(th, *self.trows)
        arrows, lit = [], []
        for y, m_ in zip(ys, mp):
            p = cell_pos(m_)
            arrows.append(dashed_arrow([-1.55, y, 0], [p[0] - 0.3, p[1], 0], color=BLUE, sw=1.8))
            lit.append(self.cells[m_].animate.set_fill(tint(BLUE, 0.4), opacity=1).set_stroke(BLUE, 1.6))
        self.play(LaggedStart(*[Create(a) for a in arrows], lag_ratio=0.25), *lit, run_time=1.6)
        self.arrows6 = arrows
        self.put(*arrows)

        self.at(5, 15.0)
        self.say("KV cache in blocks. Table finds them.", "blocks")
        self.sync(5)

    # =================================================================
    # P7  allocate on growth, return to the pool, still finite
    # =================================================================
    def p7_pool(self):
        cp = self.cell_pos
        y4 = -1.6
        lb = VGroup(blk(1.3, 0.5, GRN, 0.3, 1.4, [-5.3, y4, 0]),
                    label("block 4", 18, TEXT, W_MED).move_to([-5.3, y4, 0]))
        tr4 = blk(1.6, 0.5, YEL, 0.14, 1.4, [-2.4, y4, 0])
        tr4 = VGroup(tr4, label("4 -> 13", 20, TEXT, W_MED).move_to(tr4))
        p = cp(13)
        a4 = dashed_arrow([-1.55, y4, 0], [p[0] - 0.3, p[1], 0], color=GRN, sw=1.8)
        gr = chip("allocated as the sequence grows", GRN, 18).move_to([-3.4, 2.7, 0])
        self.play(FadeOut(self.top6), FadeIn(lb, shift=RIGHT * 0.2), FadeIn(tr4), Create(a4),
                  self.cells[13].animate.set_fill(tint(GRN, 0.4), opacity=1).set_stroke(GRN, 1.6),
                  FadeIn(gr, shift=DOWN * 0.1), run_time=1.6)
        self.put(lb, tr4, a4, gr)

        self.at(6, 3.8)
        done = [5, 6]
        pool = chip("returned to the pool", GRN, 18).move_to([3.6, -1.55, 0])
        self.play(*[self.cells[i].animate.set_fill(tint(DIM, 0.06), opacity=1).set_stroke(DIM, 1.0)
                    for i in done], FadeIn(pool, shift=UP * 0.1), run_time=1.0)
        self.put(pool)

        self.at(6, 6.0)
        self.play(*[self.cells[i].animate.set_fill(tint(GRN, 0.4), opacity=1).set_stroke(GRN, 1.6)
                    for i in done], run_time=0.6)
        self.play(pulse(self.cells[5], 1.15, 0.5), pulse(self.cells[6], 1.15, 0.5), run_time=0.5)

        self.at(6, 7.5)
        slab = chip("huge slab per request", ORANGE, 18).move_to([-3.7, -2.35, 0])
        sk = strike(slab, ORANGE)
        self.play(FadeIn(slab), run_time=0.5)
        self.play(Create(sk), run_time=0.5)
        less = chip("less fragmentation", GRN, 18).move_to([-0.2, -2.35, 0])
        self.play(FadeIn(less, shift=UP * 0.1), run_time=0.7)
        self.put(slab, sk, less)

        self.at(6, 13.5)
        fin = chip("VRAM is still finite", AMBER, 18).move_to([3.7, -2.35, 0])
        self.play(FadeIn(fin, shift=UP * 0.1), run_time=0.8)
        self.put(fin)

        self.at(6, 15.0)
        self.say("Allocate on growth. Free on finish.", "Free")
        self.sync(6)

    # =================================================================
    # P8  one monolithic prefill stalls 31 chats
    # =================================================================
    def p8_stall(self):
        self.freeze(*self.stage)
        chats = VGroup(*[square(0.24, BLUE, [-5.6 + (i % 16) * 0.32, 2.0 - (i // 16) * 0.32, 0])
                         for i in range(31)])
        cl = chip("31 chats streaming", BLUE, 18).move_to([3.2, 1.85, 0])
        line = Line([-5.9, 0.3, 0], [5.9, 0.3, 0], stroke_color=RING_IDLE, stroke_width=1.2, stroke_opacity=0.5)
        steps = VGroup(*[tok(0.5, 0.5, BLUE, at=[-5.6 + k * 0.62, 0.3, 0], fill=0.35) for k in range(5)])
        sl = label("decode steps", 18, DIM).move_to([-4.2, -0.35, 0])
        top = chip("one more stall", ORANGE, 22).move_to([0, 2.95, 0])
        self.swap(chats, cl, line, sl, top)
        self.play(LaggedStart(*[GrowFromEdge(s_, LEFT) for s_ in steps], lag_ratio=0.2), run_time=2.0)
        self.put(steps)

        self.at(7, 4.5)
        new = chip("new request: 10,000-token codebase", GRN, 20).move_to([0.6, 1.05, 0])
        self.play(FadeIn(new, shift=DOWN * 0.4), run_time=0.9)
        self.put(new)

        self.at(7, 9.0)
        pre = tok(4.8, 0.5, ORANGE, at=[-0.2, 0.3, 0], fill=0.4)
        pt_ = label("prefill: 10,000 tokens", 18, TEXT, W_MED).move_to(pre)
        one = chip("one monolithic step", ORANGE, 20).move_to([-0.2, -0.95, 0])
        self.play(GrowFromEdge(pre, LEFT), FadeIn(pt_), FadeIn(one, shift=UP * 0.1), run_time=1.6)
        self.put(pre, pt_, one)

        self.at(7, 13.0)
        ph = Line([-2.6, 0.75, 0], [-2.6, -0.15, 0], stroke_color=YEL, stroke_width=2.4)
        self.add(ph)
        self.play(*[c.animate.set_fill(DIM, opacity=0.5) for c in chats],
                  ph.animate(rate_func=linear).shift(RIGHT * 4.8), run_time=4.0)
        self.put(ph)
        wait = chip("all 31 chats wait", AMBER, 20).move_to([-0.2, -1.7, 0])
        self.play(FadeIn(wait, shift=UP * 0.1), run_time=0.7)
        self.put(wait)

        self.at(7, 19.0)
        late = VGroup(*[dashed_rect(0.5, 0.5, DIM, sw=1.4).move_to([2.7 + k * 0.62, 0.3, 0]) for k in range(2)])
        lt = label("next decode step: delayed", 18, AMBER).move_to([3.9, -0.5, 0])
        self.play(Create(late), FadeIn(lt), run_time=1.0)
        self.put(late, lt)

        self.at(7, 21.5)
        self.say("One huge prefill stalls every chat.", "stalls")
        self.sync(7)

    # =================================================================
    # P9  chunked prefill: 512 = 31 + 481
    # =================================================================
    def p9_chunked(self):
        top = chip("Sarathi-Serve: chunked prefill", GRN, 24).move_to([0, 2.95, 0])
        long = tok(10.0, 0.5, ORANGE, at=[0, -0.5, 0], fill=0.4)
        ll = label("10,000-token prompt", 18, TEXT, W_MED).move_to(long)
        self.swap(top, long, ll)

        self.at(8, 5.5)
        n, wc = 21, 10.0 / 21
        chunks = VGroup(*[tok(wc - 0.05, 0.5, ORANGE, at=[-5.0 + wc * (k + 0.5), -0.5, 0], fill=0.25)
                          for k in range(n)])
        cl = label("about 21 chunks", 18, DIM).move_to([0, -1.2, 0])
        self.play(FadeOut(ll), ReplacementTransform(long, chunks), FadeIn(cl), run_time=1.6)
        self.put(chunks, cl)

        self.at(8, 10.5)
        x0, W = -5.0, 9.0
        wdec, wpro = W * 31 / 512, W * 481 / 512
        frame = dashed_rect(W, 0.7, YEL, sw=1.8).move_to([x0 + W / 2, 1.5, 0])
        bud = chip("512-token budget per iteration", YEL, 20).move_to([x0 + W / 2, 2.35, 0])
        self.play(Create(frame), FadeIn(bud, shift=DOWN * 0.1), run_time=1.0)
        self.put(frame, bud)

        self.at(8, 13.8)
        dec = tok(wdec, 0.6, BLUE, at=[x0 + wdec / 2, 1.5, 0], fill=0.45)
        dl = label("31 decode", 18, BLUE).move_to([x0 + 0.6, 0.98, 0])
        self.play(GrowFromEdge(dec, LEFT), FadeIn(dl), run_time=0.9)
        self.put(dec, dl)

        self.at(8, 17.8)
        pro = tok(wpro, 0.6, GRN, at=[x0 + wdec + wpro / 2, 1.5, 0], fill=0.4)
        pl = label("481 prompt tokens", 18, GRN).move_to([x0 + wdec + wpro / 2, 0.98, 0])
        self.play(GrowFromEdge(pro, LEFT), FadeIn(pl), run_time=1.0)
        self.put(pro, pl)

        self.at(8, 22.0)
        it = ValueTracker(1)
        itc = counter(it, lambda v: f"iteration {int(round(v))}", [5.3, 1.5, 0], YEL, 22)
        self.add(itc)
        self.put(itc)
        prev = None
        for k in range(3):
            tx = -5.0 + wc * (k + 0.5)
            ar = dashed_arrow([x0 + wdec + wpro / 2, 0.75, 0], [tx, -0.25, 0], color=GRN, sw=1.6)
            gone = [FadeOut(prev)] if prev is not None else []
            self.play(*gone, Create(ar),
                      chunks[k].animate.set_fill(tint(GRN, 0.4), opacity=1).set_stroke(GRN, 1.4),
                      it.animate.set_value(k + 1), run_time=0.7)
            prev = ar
        self.put(prev)

        self.at(8, 23.8)
        self.say("Chunk the prompt. Decode goes first.", "Decode")
        self.sync(8)

    # =================================================================
    # P10  bounded interruption, and the idle math gets used
    # =================================================================
    def p10_bounded_mix(self):
        pairs = VGroup()
        for k in range(8):
            pairs.add(tok(0.5, 0.4, BLUE, at=[-3.5 + k * 0.89 + 0.25, 2.8, 0], fill=0.35))
            pairs.add(tok(0.34, 0.4, GRN, at=[-3.5 + k * 0.89 + 0.67, 2.8, 0], fill=0.4))
        pl = chip("bounded chunks between decodes", GRN, 18).move_to([0, 2.2, 0])
        self.swap(pairs, pl)

        self.at(9, 6.0)
        m = Machine().move_to([0, -0.2, 0])
        pk = m.start_flow(n=4, speed=0.4)
        tdec = token_stack(m, 2)
        tc, tm = ValueTracker(0.1), ValueTracker(1.0)
        bar_c, lab_c = meter(tc, -1.4, -2.0, 3.0, BLUE, "Tensor Cores")
        bar_m, lab_m = meter(tm, -1.4, -2.45, 3.0, ORANGE, "Memory")
        ill = label("illustrative", 16).move_to([4.6, -2.2, 0])
        d1 = chip("decode only", BLUE, 18).move_to([4.9, 0.9, 0])
        self.add(pk, bar_c, bar_m)
        self.play(FadeIn(m), FadeIn(tdec), FadeIn(lab_c), FadeIn(lab_m), FadeIn(ill), FadeIn(d1), run_time=1.2)
        self.play(*m.light(3), run_time=0.5)
        self.put(m, pk, tdec, bar_c, bar_m, lab_c, lab_m, ill, d1)

        self.at(9, 11.0)
        tpro = VGroup(*[Rectangle(width=m.grid.width, height=0.07, stroke_width=0, fill_color=GRN,
                                  fill_opacity=0.85) for _ in range(6)]).arrange(DOWN, buff=0.04)
        tpro.next_to(tdec, UP, buff=0.05).set_z_index(8)
        d2 = chip("+ prefill chunk", GRN, 18).move_to([4.9, 0.2, 0])
        self.play(FadeIn(tpro, lag_ratio=0.15), FadeIn(d2, shift=LEFT * 0.2), *m.light(26),
                  tc.animate.set_value(0.6), run_time=2.0)
        self.put(tpro, d2)

        self.at(9, 15.0)
        same = chip("same weight read", ORANGE, 18).move_to([4.9, -0.5, 0])
        self.play(FadeIn(same, shift=LEFT * 0.2), run_time=0.7)
        self.put(same)

        self.at(9, 19.5)
        dep = tag("depends on workload", 16).move_to([4.9, -1.2, 0])
        self.play(FadeIn(dep, shift=UP * 0.1), run_time=0.7)
        self.put(dep)

        self.at(9, 22.5)
        self.say("Fill the idle math with prefill.", "idle math")
        self.sync(9)

    # =================================================================
    # P11  chunk size trade-off; disaggregated serving
    # =================================================================
    def p11_tradeoff(self):
        self.freeze(*self.stage)
        sx0, sw_ = -5.2, 4.2
        track = Line([sx0, 1.7, 0], [sx0 + sw_, 1.7, 0], stroke_color=RING_IDLE, stroke_width=2.5)
        e1 = label("small", 18).move_to([sx0, 1.3, 0])
        e2 = label("large", 18).move_to([sx0 + sw_, 1.3, 0])
        hd = chip("chunk size", YEL, 20).move_to([-3.1, 2.4, 0])
        tk_, tt_, st_ = ValueTracker(0.0), ValueTracker(0.95), ValueTracker(0.1)
        knob = always_redraw(lambda: Dot([sx0 + sw_ * tk_.get_value(), 1.7, 0], radius=0.14, color=YEL
                                         ).set_z_index(12))
        bar_t, lab_t = meter(tt_, -3.0, 0.4, 2.2, AMBER, "first token")
        bar_s, lab_s = meter(st_, -3.0, -0.2, 2.2, ORANGE, "decode stalls")
        ill = label("illustrative", 16).move_to([-3.1, -0.85, 0])
        self.swap(track, e1, e2, hd, lab_t, lab_s, ill)
        self.add(knob, bar_t, bar_s)
        self.put(knob, bar_t, bar_s)

        self.at(10, 3.0)
        self.play(tk_.animate.set_value(1.0), tt_.animate.set_value(0.15), st_.animate.set_value(0.9),
                  run_time=3.0)
        first = chip("small chunks delay the first token", AMBER, 18).move_to([-3.1, -1.5, 0])
        self.play(FadeIn(first, shift=UP * 0.1), run_time=0.6)
        self.put(first)

        self.at(10, 8.5)
        self.play(tk_.animate.set_value(0.5), tt_.animate.set_value(0.55), st_.animate.set_value(0.5),
                  run_time=1.8)
        bal = chip("balance latency and smooth streaming", YEL, 18).move_to([-3.1, -2.2, 0])
        self.play(FadeIn(bal, shift=UP * 0.1), FadeOut(first), run_time=0.8)
        self.put(bal)

        self.at(10, 13.5)
        dh = chip("disaggregated serving", DIM, 20).move_to([3.8, 2.4, 0])
        pbox = surface_box(3.0, 0.95, color=BLUE, hatched=False, inset=0.08, sw=1.5).move_to([3.8, 1.3, 0])
        pt_ = label("prefill GPUs", 20, TEXT, W_MED).move_to(pbox)
        dbox = surface_box(3.0, 0.95, color=ORANGE, hatched=False, inset=0.08, sw=1.5).move_to([3.8, -1.1, 0])
        dt_ = label("decode GPUs", 20, TEXT, W_MED).move_to(dbox)
        self.play(FadeIn(dh), FadeIn(pbox), FadeIn(pt_), FadeIn(dbox), FadeIn(dt_), run_time=1.4)
        self.put(dh, pbox, pt_, dbox, dt_)

        self.at(10, 20.0)
        xa = dashed_arrow([3.8, 0.8, 0], [3.8, -0.6, 0], color=ORANGE, sw=2.2)
        xc = chip("KV-cache transfer", ORANGE, 18).move_to([3.8, 0.1, 0]).set_z_index(10)
        self.play(Create(xa), FadeIn(xc), run_time=1.0)
        self.put(xa, xc)

        self.at(10, 24.0)
        self.say("Chunk size trades first token for flow.", "first token")
        self.sync(10)

    # =================================================================
    # P12  the 295 ridge is not a universal limit
    # =================================================================
    def p12_ridge_caveat(self):
        self.freeze(*self.stage)
        rf = Roofline().move_to([3.6, 0.15, 0]).make()
        rg = chip("ridge = 295", YEL, 18).move_to(rf.pt(295, 12))
        self.swap(rf, rf.slope, rf.roof, rf.ridge, rg)

        self.at(11, 6.0)
        c1 = chip("ideal: weight traffic only", YEL, 18).move_to([-3.4, 1.3, 0])
        d_ideal = rf.dot(1, YEL)
        self.play(FadeIn(c1, shift=RIGHT * 0.2), FadeIn(d_ideal, scale=2), run_time=0.8)
        self.play(d_ideal.animate.move_to(rf.pt(295, rf.perf(295))), run_time=2.2, rate_func=smooth)
        self.put(c1, d_ideal)

        self.at(11, 10.5)
        c2 = chip("real: + KV-cache reads", ORANGE, 18).move_to([-3.4, 0.3, 0])
        d_real = rf.dot(1, ORANGE)
        tgt = rf.pt(38, rf.perf(38))
        stall = tag("stalls short (illustrative)", 16, ORANGE).move_to(rf.pt(38, rf.perf(38)) + DOWN * 0.5 + RIGHT * 0.4)
        self.play(FadeIn(c2, shift=RIGHT * 0.2), FadeIn(d_real, scale=2), run_time=0.8)
        self.play(d_real.animate.move_to(tgt), run_time=2.0, rate_func=rate_functions.ease_out_cubic)
        self.play(FadeIn(stall), run_time=0.6)
        self.put(c2, d_real, stall)

        self.at(11, 17.0)
        c3 = chip("attention: DRAM-bound", ORANGE, 18).move_to([-3.4, -0.7, 0])
        self.play(FadeIn(c3, shift=RIGHT * 0.2), pulse(c2, 1.06, 0.5), run_time=0.8)
        self.put(c3)

        self.at(11, 22.0)
        self.say("295 is a ridge, not a batch limit.", "not a batch limit")
        self.sync(11)

    # =================================================================
    # P13  diminishing returns
    # =================================================================
    def p13_diminishing(self):
        self.freeze(*self.stage)
        o = np.array([-5.4, -2.1, 0.0])
        w, h = 5.4, 3.9

        def P(x, y):
            return o + np.array([x * w, y * h, 0.0])

        axes = VGroup(Line(o, o + RIGHT * w, stroke_color=DIM, stroke_width=1.6),
                      Line(o, o + UP * h, stroke_color=DIM, stroke_width=1.6))
        xt = label("batch size", 18).move_to(o + np.array([w - 0.7, -0.4, 0]))
        yt = label("throughput", 18).move_to(o + np.array([0.9, h + 0.25, 0]))
        ideal = DashedVMobject(Line(P(0, 0), P(1, 0.97), stroke_color=DIM, stroke_width=2), num_dashes=22)
        il = label("ideal", 16).move_to(P(0.9, 0.97) + LEFT * 0.35 + UP * 0.25)
        self.swap(axes, xt, yt, ideal, il)

        self.at(12, 1.5)
        xs = np.linspace(0, 1, 60)
        curve = VMobject(stroke_color=YEL, stroke_width=4).set_points_as_corners(
            [P(x, 0.82 * (1 - np.exp(-3.2 * x))) for x in xs])
        self.play(Create(curve), run_time=3.2, rate_func=smooth)
        self.put(curve)

        self.at(12, 5.5)
        names = ["KV-cache capacity", "memory bandwidth", "compute", "kernel efficiency", "latency targets"]
        tags = VGroup(*[tag(n, 18) for n in names]).arrange(DOWN, buff=0.28).move_to([3.5, 0.3, 0])
        self.play(FadeIn(tags, lag_ratio=0.45), run_time=4.0)
        self.put(tags)

        self.at(12, 10.2)
        kx = 0.38
        knee = P(kx, 0.82 * (1 - np.exp(-3.2 * kx)))
        kl = DashedVMobject(Line([knee[0], o[1], 0], knee, stroke_color=YEL, stroke_width=2), num_dashes=10)
        kd = Dot(knee, radius=0.1, color=YEL).set_z_index(12)
        kt = chip("useful batch size", YEL, 18).move_to([knee[0] + 1.5, o[1] + 0.55, 0])
        self.play(Create(kl), FadeIn(kd, scale=2), FadeIn(kt), run_time=1.0)
        self.put(kl, kd, kt)

        self.at(12, 13.2)
        ceil_ = DashedVMobject(Line(P(0, 0.82), P(1, 0.82), stroke_color=ORANGE, stroke_width=2), num_dashes=24)
        cl = chip("hardware limits", ORANGE, 18).move_to(P(0.78, 0.82) + UP * 0.5)
        self.play(Create(ceil_), FadeIn(cl, shift=DOWN * 0.1), run_time=1.0)
        self.put(ceil_, cl)

        self.at(12, 14.8)
        self.say("More requests, diminishing returns.", "diminishing")
        self.sync(12)

    # =================================================================
    # P14  recap: four fixes
    # =================================================================
    def p14_recap(self):
        cy = 0.5
        xs = [-4.65, -1.55, 1.55, 4.65]
        frames = VGroup(*[surface_box(2.9, 3.1, color=RING_IDLE, hatched=False, inset=0.08, sw=1.4
                                      ).move_to([x, cy, 0]) for x in xs])
        top = chip("our opening scene, fixed", GRN, 22).move_to([0, 2.7, 0])
        self.swap(frames, top)

        def titles(x, l1, l2, sub, color):
            return VGroup(label(l1, 20, TEXT, W_MED).move_to([x, cy - 0.35, 0]),
                          label(l2, 20, TEXT, W_MED).move_to([x, cy - 0.72, 0]),
                          label(sub, 16, color).move_to([x, cy - 1.15, 0])).set_z_index(9)

        # 1 continuous batching: ragged lanes, nothing waits
        x = xs[0]
        ic1 = VGroup()
        for k, ws in enumerate([[0.8, 0.9, 0.3], [0.5, 1.1, 0.5], [1.2, 0.7, 0.2]]):
            xx = x - 1.05
            for w_ in ws:
                ic1.add(tok(w_ - 0.04, 0.18, GRN, at=[xx + w_ / 2, cy + 1.2 - k * 0.26, 0], fill=0.35))
                xx += w_
        ic1.set_z_index(8)
        t1 = titles(x, "continuous", "batching", "no barrier", GRN)
        self.at(13, 0.5)
        self.play(FadeIn(ic1, lag_ratio=0.05), FadeIn(t1), run_time=1.2)
        self.put(ic1, t1)

        # 2 selective batching: different lengths share one op
        x = xs[1]
        ic2 = VGroup(*[tok(w_, 0.14, BLUE, at=[x - 1.1 + w_ / 2, cy + 1.35 - k * 0.2, 0])
                       for k, w_ in enumerate([0.9, 0.5, 0.7])]).set_z_index(8)
        ic2.add(blk(0.6, 0.6, ORANGE, 0.22, 1.4, [x + 0.85, cy + 1.15, 0]))
        ic2.add(dashed_arrow([x - 0.1, cy + 1.15, 0], [x + 0.5, cy + 1.15, 0], color=DIM, sw=1.6))
        ic2.set_z_index(8)
        t2 = titles(x, "selective", "batching", "shared ops", BLUE)
        self.at(13, 7.2)
        self.play(FadeIn(ic2, lag_ratio=0.05), FadeIn(t2), run_time=1.2)
        self.put(ic2, t2)

        # 3 PagedAttention: scattered blocks
        x = xs[2]
        lit_ = {1, 4, 6, 9}
        ic3 = VGroup(*[blk(0.3, 0.3, BLUE if i in lit_ else DIM, 0.4 if i in lit_ else 0.15, 1.0,
                           [x - 0.9 + (i % 6) * 0.36, cy + 1.35 - (i // 6) * 0.36, 0])
                       for i in range(12)]).set_z_index(8)
        t3 = titles(x, "Paged", "Attention", "KV in blocks", BLUE)
        self.at(13, 11.6)
        self.play(FadeIn(ic3, lag_ratio=0.05), FadeIn(t3), run_time=1.2)
        self.put(ic3, t3)

        # 4 chunked prefill: a long prompt in bounded pieces
        x = xs[3]
        ic4 = VGroup(tok(0.3, 0.3, BLUE, at=[x - 1.0, cy + 1.2, 0], fill=0.4))
        for i in range(6):
            col = GRN if i < 2 else ORANGE
            ic4.add(blk(0.3, 0.3, col, 0.4 if i < 2 else 0.18, 1.0, [x - 0.55 + i * 0.36, cy + 1.2, 0]))
        ic4.set_z_index(8)
        t4 = titles(x, "chunked", "prefill", "bounded prefill", GRN)
        self.at(13, 14.6)
        self.play(FadeIn(ic4, lag_ratio=0.05), FadeIn(t4), run_time=1.2)
        self.put(ic4, t4)

        self.at(13, 16.2)
        self.say("Four fixes, one scheduler.", "one scheduler")
        self.sync(13)

    # =================================================================
    # P15  the closing argument (callback to Part 1's meters)
    # =================================================================
    def p15_closing_argument(self):
        m = Machine().scale(1.25).move_to([0, 1.0, 0])
        pk = m.start_flow()
        tc, tm = ValueTracker(0.07), ValueTracker(1.0)
        bar_c, lab_c = meter(tc, -2.0, -2.15, 4.2, BLUE, "Tensor Cores")
        bar_m, lab_m = meter(tm, -2.0, -2.65, 4.2, ORANGE, "Memory")
        self.swap(m, lab_c, lab_m)
        self.add(pk, bar_c, bar_m)
        self.put(pk, bar_c, bar_m)
        self.play(*m.light(2), run_time=0.5)

        peak = chip("more peak FLOPS?", DIM, 22).move_to([0, -1.35, 0])
        self.play(FadeIn(peak, shift=UP * 0.1), run_time=0.6)
        sk = strike(peak, ORANGE)
        self.play(Create(sk), run_time=0.5)
        self._note = peak
        self.put(peak, sk)

        self.at(14, 5.5)
        self.play(FadeOut(sk), run_time=0.15)
        self.note(chip("decode: a memory-bandwidth problem", ORANGE, 22).move_to([0, -1.35, 0]), 0.7)

        self.at(14, 10.5)
        tk = token_stack(m, 8)
        self.play(FadeIn(tk, lag_ratio=0.1), *m.light(26), tc.animate.set_value(0.65), run_time=2.0)
        self.put(tk)
        self.note(chip("keep useful work in flight", GRN, 22).move_to([0, -1.35, 0]), 0.7)

        self.at(14, 14.5)
        self.burst(m)
        self.note(chip("reuse each weight read", GRN, 22).move_to([0, -1.35, 0]), 0.7)

        self.at(14, 18.5)
        self.note(chip("no slow prompt stalls the rest", GRN, 22).move_to([0, -1.35, 0]), 0.7)

        self.at(14, 20.2)
        self.say("Keep useful work in flight.", "useful work")
        self.sync(14)

    # =================================================================
    # P16  Tetris
    # =================================================================
    def p16_tetris(self):
        self.freeze(*self.stage)
        bub = surface_box(3.0, 0.9, color=RING_IDLE, hatched=False, inset=0.08, sw=1.4).move_to([-4.4, 0.9, 0])
        dots = VGroup(*[Dot([-4.4 + (k - 1) * 0.4, 0.9, 0], radius=0.09, color=TEXT_DIM) for k in range(3)])
        bl = label("the reply pauses", 18).move_to([-4.4, 0.25, 0])
        self.swap(bub, dots, bl)
        for d in dots:
            self.play(pulse(d, 1.5, 0.45))

        self.at(15, 4.0)
        cols, rows, s = 6, 4, 0.55
        cx, cy = 2.2, 0.3
        c0 = np.array([cx - cols * s / 2, cy - rows * s / 2, 0.0])

        def cp(r, c):
            return c0 + np.array([(c + 0.5) * s, (r + 0.5) * s, 0.0])

        well = surface_box(cols * s + 0.3, rows * s + 0.3, color=RING_IDLE, hatched=False, inset=0.08,
                           sw=1.4).move_to([cx, cy, 0])
        gl = label("the GPU, behind the chat", 18, DIM).move_to([cx, cy + rows * s / 2 + 0.55, 0])
        ar = dashed_arrow([-2.7, 0.9, 0], [cx - cols * s / 2 - 0.3, 0.9, 0], color=DIM, sw=1.8)
        hole = {(0, 2), (0, 3), (1, 3)}
        occ = {}
        for r in range(2):
            for c in range(cols):
                if (r, c) not in hole:
                    occ[(r, c)] = BLUE if (r + c) % 2 == 0 else DIM
        for c in (0, 1, 4):
            occ[(2, c)] = BLUE if c != 1 else DIM
        cells = {k: blk(s - 0.04, s - 0.04, col, 0.4, 1.4, cp(*k)) for k, col in occ.items()}
        self.play(FadeIn(well), FadeIn(gl), Create(ar), LaggedStart(*[FadeIn(c) for c in cells.values()],
                                                                    lag_ratio=0.04), run_time=2.2)
        self.put(well, gl, ar, *cells.values())

        self.at(15, 8.0)
        piece = VGroup(*[blk(s - 0.04, s - 0.04, GRN, 0.45, 1.6, cp(*k)) for k in sorted(hole)])
        pl = chip("one more piece", GRN, 20).move_to([cx, cy - rows * s / 2 - 0.65, 0])
        piece.shift(UP * 3.5)
        self.add(piece)
        self.play(FadeIn(pl, shift=UP * 0.1), piece.animate.shift(DOWN * 3.5), run_time=1.2, rate_func=rush_into)
        self.put(piece, pl)

        self.at(15, 10.6)
        full = [cells[k] for k in cells if k[0] < 2] + list(piece)
        self.play(*[m.animate.set_stroke(YEL, 2.2) for m in full], run_time=0.4)
        self.play(*[FadeOut(m, scale=0.6) for m in full], run_time=0.6)
        rest = [cells[k] for k in cells if k[0] == 2]
        self.play(*[m.animate.shift(DOWN * 2 * s) for m in rest], run_time=0.6)

        self.at(15, 12.6)
        self.say("Fit one more piece.", "one more piece")
        self.sync(15)


# ------------------------------------------------------------------ thumbnail
class CBPart2Thumb(CBScene):
    def construct(self):
        cols, rows, s = 8, 5, 0.62
        cx, cy = 3.6, -0.2
        c0 = np.array([cx - cols * s / 2, cy - rows * s / 2, 0.0])
        well = surface_box(cols * s + 0.3, rows * s + 0.3, color=RING_IDLE, hatched=False, inset=0.08,
                           sw=1.6).move_to([cx, cy, 0])
        self.add(well)
        rng = np.random.default_rng(5)
        hole = {(2, 3), (2, 4), (1, 4)}
        for r in range(3):
            for c in range(cols):
                if (r, c) in hole:
                    continue
                col = BLUE if rng.random() < 0.55 else DIM
                self.add(blk(s - 0.05, s - 0.05, col, 0.4, 1.4,
                             c0 + np.array([(c + 0.5) * s, (r + 0.5) * s, 0.0])))
        self.add(VGroup(*[blk(s - 0.05, s - 0.05, GRN, 0.45, 1.8,
                              c0 + np.array([(k[1] + 0.5) * s, (k[0] + 0.5) * s + 1.5, 0.0]))
                          for k in sorted(hole)]))
        head = VGroup(T("GPU ", 72, TEXT, MONO, W_BOLD, hero=True),
                      T("TETRIS", 72, GRN, MONO, W_BOLD, hero=True)
                      ).arrange(RIGHT, buff=0.15, aligned_edge=DOWN).to_edge(UP, buff=0.5).to_edge(LEFT, buff=0.6)
        sub = T("fit one more request", 30, TEXT_DIM, MONO, W_REG).next_to(head, DOWN, buff=0.35, aligned_edge=LEFT)
        chips = VGroup(chip("paged", BLUE, 24), chip("chunked", GRN, 24), chip("selective", YEL, 24)
                       ).arrange(DOWN, buff=0.3, aligned_edge=LEFT).move_to([-4.6, -1.3, 0])
        self.add(head, sub, chips)