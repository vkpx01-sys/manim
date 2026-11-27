"""Portrait-native Shorts for the Mixture-of-Experts series."""
from __future__ import annotations

from dataclasses import dataclass

from manim import config

from part3 import dominated, switch_loss
from reducible_style import *

config.pixel_width = 1080
config.pixel_height = 1920
config.frame_width = 9
config.frame_height = 16
config.frame_rate = 30


@dataclass(frozen=True)
class ShortSpec:
    slug: str
    title: str
    scene: str
    part: int
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


SHORTS = (
    ShortSpec("short01_sparse_isnt_fast", "Sparse compute is not a speed guarantee",
              "MoESparseSpeedShort", 1, 34.08, 69.82),
    ShortSpec("short02_top_two_routing", "How top-two routing works",
              "MoETopTwoShort", 2, 46.36, 83.98),
    ShortSpec("short03_balancing_loss", "Why routers need balancing",
              "MoEBalancingShort", 3, 149.52, 184.40),
)


class VerticalShort(ReducibleScene):
    DURATION = 0.0

    def at(self, seconds: float) -> None:
        gap = seconds - self.renderer.time
        if gap > 0.02:
            self.wait(gap)

    def finish(self) -> None:
        remaining = self.DURATION - self.renderer.time
        if remaining > 0.02:
            self.wait(remaining)
        elif remaining < -0.25:
            raise RuntimeError(
                f"{type(self).__name__} ran {-remaining:.2f}s past its audio clip"
            )

    def headline(self, text: str, size: int = 42):
        return (T(text, size, TEXT, MONO, W_SEMI)
                .to_edge(UP, buff=0.72)
                .to_edge(LEFT, buff=0.55)
                .set_z_index(50))


def expert_card(index: int, center, selected=False) -> VGroup:
    color = GOLD if selected else TEXT_DIM
    card = RoundedRectangle(
        corner_radius=0.12, width=1.45, height=0.92,
        stroke_color=color, stroke_width=2.2,
        fill_color=CARD, fill_opacity=0.95,
    ).move_to(center)
    name = T(f"E{index}", 24, color, MONO, W_MED).move_to(card)
    status = T("ACTIVE" if selected else "SKIPPED", 18, color, MONO, W_REG
               ).next_to(card, DOWN, buff=0.12)
    return VGroup(card, name, status).set_z_index(8)


def expert_grid(active=()) -> VGroup:
    xs = (-3.35, -1.12, 1.12, 3.35)
    ys = (3.45, 1.25)
    return VGroup(*[
        expert_card(k + 1, [xs[k % 4], ys[k // 4], 0], selected=k + 1 in active)
        for k in range(8)
    ])


class MoESparseSpeedShort(VerticalShort):
    DURATION = SHORTS[0].duration

    def construct(self):
        title = self.headline("SPARSE != FASTER", 42)
        token = T("ONE TOKEN", 24, GOLD, MONO, W_MED).move_to([0, 5.2, 0])
        experts = expert_grid(active=(3, 6))
        self.play(FadeIn(title), FadeIn(token), FadeIn(experts, lag_ratio=0.06),
                  run_time=1.4)

        self.at(5.2)
        less = chip("LESS FFN WORK PER TOKEN", DRIVER, 24).move_to([0, -0.7, 0])
        self.play(FadeIn(less), run_time=0.8)

        self.at(9.8)
        caveat = T("SPARSE COMPUTE DOES NOT GUARANTEE LOWER LATENCY",
                   26, BAD, MONO, W_MED).move_to([0, -2.0, 0])
        self.play(FadeOut(less), FadeIn(caveat), run_time=0.8)

        self.at(16.2)
        factors = VGroup(
            T("MEMORY BANDWIDTH", 28, TEXT_DIM, MONO, W_MED),
            T("BATCHING", 28, TEXT_DIM, MONO, W_MED),
            T("GPU COMMUNICATION", 28, TEXT_DIM, MONO, W_MED),
            T("SERVING SOFTWARE", 28, TEXT_DIM, MONO, W_MED),
        ).arrange(DOWN, buff=0.48).move_to([0, 0.5, 0])
        heading = T("LATENCY ALSO DEPENDS ON", 24, GOLD, MONO, W_MED
                    ).next_to(factors, UP, buff=0.55)
        self.play(FadeOut(token, experts, caveat), FadeIn(heading),
                  FadeIn(factors, lag_ratio=0.12), run_time=1.2)

        self.at(23.0)
        total_label = T("TOTAL PARAMETERS", 24, TEXT_DIM, MONO, W_MED
                        ).move_to([0, 3.0, 0])
        total_bar = Rectangle(width=6.8, height=0.48, stroke_width=0,
                              fill_color=TEXT_DIM, fill_opacity=0.75
                              ).move_to([0, 2.2, 0])
        total_note = T("WEIGHTS THE MODEL CONTAINS", 22, TEXT, MONO, W_REG
                       ).move_to([0, 1.45, 0])
        total_group = VGroup(total_label, total_bar, total_note)
        self.play(FadeOut(heading, factors), FadeIn(total_group), run_time=1.0)

        self.at(30.7)
        active_label = T("ACTIVE PARAMETERS", 24, GOLD, MONO, W_MED
                         ).move_to([0, 0.25, 0])
        active_bar = Rectangle(width=2.0, height=0.48, stroke_width=0,
                               fill_color=GOLD, fill_opacity=0.9
                               ).move_to([-2.4, -0.55, 0])
        active_note = T("WEIGHTS USED BY ONE TOKEN", 22, GOLD, MONO, W_REG
                        ).next_to(active_bar, RIGHT, buff=0.28)
        self.play(FadeIn(active_label), FadeIn(active_bar), FadeIn(active_note),
                  run_time=0.9)
        self.finish()


class MoETopTwoShort(VerticalShort):
    DURATION = SHORTS[1].duration

    def construct(self):
        title = self.headline("TOP-TWO ROUTING", 42)
        token = T('TOKEN: "def"', 26, RIDER, MONO, W_MED).move_to([0, 5.5, 0])
        experts = expert_grid(active=(3, 6))
        self.play(FadeIn(title), FadeIn(token), FadeIn(experts, lag_ratio=0.06),
                  run_time=1.4)

        self.at(7.2)
        renorm = VGroup(
            T("48 / 80 = 60%", 30, GOLD, MONO, W_MED),
            T("32 / 80 = 40%", 30, RIDER, MONO, W_MED),
        ).arrange(DOWN, buff=0.55).move_to([0, -1.45, 0])
        self.play(FadeIn(renorm, lag_ratio=0.18), run_time=1.0)

        self.at(16.0)
        combined = chip("TWO EXPERT OUTPUTS COMBINE", GOLD, 22
                        ).move_to([0, -3.3, 0])
        self.play(FadeIn(combined), run_time=0.8)

        self.at(21.5)
        skipped = T("SIX OTHER EXPERTS SKIPPED FOR THIS TOKEN",
                    22, TEXT_DIM, MONO, W_MED).move_to([0, -4.4, 0])
        self.play(FadeIn(skipped), run_time=0.8)

        self.at(28.8)
        routes = VGroup()
        for word, experts_text, color, y in (
            ("def", "E3 + E6", GOLD, 2.1),
            ("42", "E2 + E7", RIDER, 0.6),
            (",", "E1 + E5", DRIVER, -0.9),
        ):
            row = VGroup(
                T(word, 28, TEXT, MONO, W_MED),
                T("->", 26, TEXT_DIM, MONO, W_REG),
                T(experts_text, 28, color, MONO, W_MED),
            ).arrange(RIGHT, buff=0.38)
            row.move_to([0, y, 0])
            routes.add(row)
        route_title = T("EACH TOKEN ROUTES AGAIN", 24, GOLD, MONO, W_MED
                        ).move_to([0, 3.65, 0])
        self.play(FadeOut(token, experts, renorm, combined, skipped),
                  FadeIn(route_title), FadeIn(routes, lag_ratio=0.16),
                  run_time=1.1)
        self.finish()


def distribution_row(values, color, y) -> VGroup:
    bar_width = 0.62
    gap = 0.22
    total_width = 8 * bar_width + 7 * gap
    row = VGroup()
    for index, value in enumerate(values):
        height = 0.16 + 1.18 * float(value)
        x = -total_width / 2 + index * (bar_width + gap) + bar_width / 2
        row.add(Rectangle(
            width=bar_width, height=height, stroke_width=0,
            fill_color=color, fill_opacity=0.9,
        ).move_to([x, y + height / 2, 0]))
    return row.set_z_index(8)


class MoEBalancingShort(VerticalShort):
    DURATION = SHORTS[2].duration

    def construct(self):
        title = self.headline("WHY BALANCE ROUTING?", 40)
        formula_line = formula("L = 8 x sum(", ("f_i", GOLD), " x ",
                               ("P_i", DRIVER), ")", size=28)
        formula_line.move_to([0, 5.75, 0])
        collapse = ValueTracker(0.0)
        f_bars = always_redraw(lambda: distribution_row(
            dominated(collapse.get_value()), GOLD, 3.1
        ))
        p_bars = always_redraw(lambda: distribution_row(
            dominated(collapse.get_value()), DRIVER, 0.15
        ))
        f_label = T("f_i: EXPERT ASSIGNMENT SHARE", 22, GOLD, MONO, W_MED
                    ).move_to([0, 4.65, 0])
        p_label = T("P_i: MEAN ROUTER PROBABILITY", 22, DRIVER, MONO, W_MED
                    ).move_to([0, 1.8, 0])
        loss = always_redraw(lambda: T(
            f"L = {switch_loss(dominated(collapse.get_value()), dominated(collapse.get_value())):.2f}",
            40, TEXT, MONO, W_MED,
        ).move_to([0, -1.75, 0]).set_z_index(12))
        self.play(FadeIn(title), FadeIn(formula_line), FadeIn(f_label),
                  FadeIn(f_bars), FadeIn(p_label), FadeIn(p_bars),
                  FadeIn(loss), run_time=1.6)

        self.at(12.2)
        baseline = chip("BALANCED: L = 1", DRIVER, 24).move_to([0, -3.35, 0])
        self.play(FadeIn(baseline), run_time=0.8)

        self.at(19.8)
        rises = chip("PENALTY RISES", BAD, 24).move_to([0, -3.35, 0])
        self.play(FadeOut(baseline), collapse.animate.set_value(1.0),
                  FadeIn(rises), run_time=2.4)

        self.at(25.0)
        takeaway = T("DISCOURAGE CONCENTRATING TRAFFIC",
                     24, TEXT, MONO, W_MED).move_to([0, -4.0, 0])
        self.play(FadeIn(takeaway), run_time=0.8)
        self.finish()
