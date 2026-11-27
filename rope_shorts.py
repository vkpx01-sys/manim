"""Portrait-native Manim scenes and source timing for the RoPE Shorts batch."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from manim import config

from reducible_style import *
from rope.part4 import TH, dial_bank

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
    ShortSpec("short01_word_order", "Same words, different meaning",
              "RoPEOrderShort", 1, 0.58, 38.14),
    ShortSpec("short02_relative_offset", "Why position is relative",
              "RoPERelativeShort", 3, 111.30, 141.34),
    ShortSpec("short03_sixty_four_clocks", "The 64 clocks in RoPE",
              "RoPE64ClocksShort", 4, 0.46, 43.12),
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
        return (T(text, size, TEXT, SANS, W_SEMI)
                .to_edge(UP, buff=0.72)
                .to_edge(LEFT, buff=0.55)
                .set_z_index(50))


def _token_card(word: str, color, point) -> VGroup:
    box = Rectangle(
        width=2.05, height=0.88, stroke_color=color, stroke_width=2.8,
        fill_color=CARD, fill_opacity=1,
    ).move_to(point).set_z_index(8)
    label = T(word, 27, color, MONO, W_SEMI).move_to(point).set_z_index(9)
    return VGroup(box, label)


def _token_row(words: tuple[str, str, str], y: float) -> VGroup:
    colors = {"Dog": RIDER, "Man": DRIVER, "bit": GOLD}
    return VGroup(*[
        _token_card(word, colors[word], [x, y, 0])
        for word, x in zip(words, (-2.45, 0, 2.45))
    ])


class RoPEOrderShort(VerticalShort):
    DURATION = SHORTS[0].duration

    def construct(self):
        title = self.headline("WORD ORDER")
        first = _token_row(("Dog", "bit", "Man"), 4.5)
        first_label = T("ORDINARY EVENT", 25, DRIVER, MONO, W_SEMI
                        ).move_to([0, 3.15, 0])
        self.play(FadeIn(title, shift=DOWN * 0.2),
                  FadeIn(first, lag_ratio=0.12), run_time=1.2)

        self.at(2.12)
        first_arrow = Arrow(
            first[0].get_top() + UP * 0.42,
            first[2].get_top() + UP * 0.42,
            buff=0, color=DRIVER, stroke_width=4.5,
            max_tip_length_to_length_ratio=0.15,
        ).set_z_index(12)
        self.play(Create(first_arrow), FadeIn(first_label), run_time=0.9)

        self.at(4.12)
        second = _token_row(("Man", "bit", "Dog"), 1.15)
        second_label = T("UNUSUAL NEWS STORY", 23, AMBER, MONO, W_SEMI
                         ).move_to([0, -0.2, 0])
        second_arrow = Arrow(
            second[0].get_top() + UP * 0.42,
            second[2].get_top() + UP * 0.42,
            buff=0, color=AMBER, stroke_width=4.5,
            max_tip_length_to_length_ratio=0.15,
        ).set_z_index(12)
        self.play(FadeIn(second, shift=UP * 0.2),
                  Create(second_arrow), run_time=1.0)
        self.at(7.76)
        self.play(FadeIn(second_label), run_time=0.6)

        self.at(12.88)
        same_words = T("SAME THREE WORDS", 26, GOLD, MONO, W_SEMI
                       ).move_to([0, -1.5, 0])
        meaning = T("ORDER CHANGES THE MEANING", 23, TEXT, MONO, W_SEMI
                    ).move_to([0, -2.3, 0])
        self.play(FadeIn(same_words), run_time=0.6)
        self.at(14.02)
        self.play(FadeIn(meaning), run_time=0.6)

        self.at(16.5)
        self.clear_all(0.45)
        attention_title = self.headline("SELF-ATTENTION")
        positions = (-2.45, 0, 2.45)
        inputs = _token_row(("Dog", "bit", "Man"), 4.0)
        outputs = _token_row(("Dog", "bit", "Man"), 0.55)
        input_label = T("INPUT TOKENS", 22, TEXT_DIM, MONO, W_SEMI
                        ).move_to([0, 5.0, 0])
        output_label = T("OUTPUTS", 22, TEXT_DIM, MONO, W_SEMI
                         ).move_to([0, -0.45, 0])
        links = VGroup(*[
            Arrow([x, 3.45, 0], [x, 1.05, 0], buff=0.15,
                  color=TEXT_DIM, stroke_width=2.5,
                  max_tip_length_to_length_ratio=0.12)
            for x in positions
        ]).set_z_index(4)
        no_positions = T("NO POSITION TAGS", 27, BAD, MONO, W_SEMI
                         ).move_to([0, -1.35, 0])
        self.at(18.94)
        self.play(FadeIn(attention_title), FadeIn(input_label),
                  FadeIn(output_label), FadeIn(inputs, lag_ratio=0.1),
                  FadeIn(outputs, lag_ratio=0.1), Create(links, lag_ratio=0.15),
                  run_time=1.4)
        self.play(FadeIn(no_positions), run_time=0.7)

        self.at(25.22)
        self.play(
            inputs[0].animate.move_to([positions[2], 4.0, 0]),
            inputs[2].animate.move_to([positions[0], 4.0, 0]),
            outputs[0].animate.move_to([positions[2], 0.55, 0]),
            outputs[2].animate.move_to([positions[0], 0.55, 0]),
            run_time=1.1,
        )
        shuffled = T("SHUFFLE IN -> SHUFFLE OUT", 22, GOLD, MONO, W_SEMI
                     ).move_to([0, -2.15, 0])
        self.play(FadeIn(shuffled), run_time=0.7)

        self.at(32.78)
        takeaway = T("NO BUILT-IN WORD ORDER", 26, TEXT, MONO, W_SEMI
                     ).move_to([0, -3.2, 0])
        self.play(FadeIn(takeaway), run_time=0.8)
        self.finish()


def _comparison_dial(center, radius: float, rotation: float):
    rim = Circle(radius=radius, stroke_color=TEXT_DIM, stroke_width=3.2,
                 fill_color=BG_HEX, fill_opacity=0).move_to(center)
    ticks = VGroup()
    for i in range(8):
        angle = TAU * i / 8
        direction = np.array([np.cos(angle), np.sin(angle), 0])
        ticks.add(Line(
            center + (radius - 0.16) * direction,
            center + (radius - 0.02) * direction,
            stroke_color=RING_IDLE, stroke_width=2.4,
        ))
    q_angle = rotation + np.deg2rad(28)
    k_angle = rotation - np.deg2rad(28)
    length = radius * 0.68
    q_end = center + length * np.array([np.cos(q_angle), np.sin(q_angle), 0])
    k_end = center + length * np.array([np.cos(k_angle), np.sin(k_angle), 0])
    q_arrow = Arrow(center, q_end, buff=0, color=GOLD, stroke_width=6,
                    max_tip_length_to_length_ratio=0.2)
    k_arrow = Arrow(center, k_end, buff=0, color=DRIVER, stroke_width=6,
                    max_tip_length_to_length_ratio=0.2)
    arc = Arc(radius=0.48, start_angle=k_angle,
              angle=q_angle - k_angle).move_arc_center_to(center)
    arc.set_stroke(color=TEXT, width=4)
    hub = Dot(center, radius=0.07, color=TEXT)
    arrows = VGroup(q_arrow, k_arrow, arc, hub).set_z_index(15)
    return VGroup(rim, ticks), arrows


class RoPERelativeShort(VerticalShort):
    DURATION = SHORTS[1].duration

    def construct(self):
        title = self.headline("SAME OFFSET", 44)
        upper_center = np.array([0, 3.35, 0])
        lower_center = np.array([0, -1.45, 0])
        upper_dial, upper_arrows = _comparison_dial(upper_center, 1.42, 0.0)
        upper_label = T("POSITIONS 1 -> 2", 25, GOLD, MONO, W_SEMI
                        ).move_to([0, 5.18, 0])
        self.play(FadeIn(title), FadeIn(upper_dial), Create(upper_arrows),
                  FadeIn(upper_label), run_time=1.2)

        equation = T("m - n", 44, GOLD, MONO, W_SEMI).move_to([0, 1.0, 0])
        self.at(1.3)
        self.play(FadeIn(equation), run_time=0.6)

        movement_note = T("BOTH TOKENS MOVE FORWARD", 22, TEXT, MONO, W_SEMI
                          ).move_to([0, 0.35, 0])
        self.at(7.96)
        self.play(
            upper_arrows.animate.rotate(PI / 3, about_point=upper_center),
            FadeIn(movement_note), run_time=1.2,
        )

        same_gap = T("SAME ONE-TOKEN GAP", 24, TEXT, MONO, W_SEMI
                     ).move_to([0, 0.35, 0])
        self.at(12.94)
        self.play(Transform(movement_note, same_gap), run_time=0.6)

        self.at(16.76)
        lower_dial, lower_arrows = _comparison_dial(
            lower_center, 1.42, np.deg2rad(95)
        )
        lower_label = T("POSITIONS 51 -> 52", 25, DRIVER, MONO, W_SEMI
                        ).move_to([0, -3.35, 0])
        self.play(FadeIn(lower_dial), Create(lower_arrows),
                  FadeIn(lower_label), run_time=1.2)

        self.at(19.92)
        self.play(
            upper_arrows.animate.rotate(PI / 2, about_point=upper_center),
            lower_arrows.animate.rotate(PI / 2, about_point=lower_center),
            run_time=1.6,
        )
        same_angle = T("RELATIVE ANGLE UNCHANGED", 24, GOLD, MONO, W_SEMI
                       ).move_to([0, 0.35, 0])
        self.at(24.86)
        self.play(Transform(movement_note, same_angle), run_time=0.8)
        self.finish()


class RoPE64ClocksShort(VerticalShort):
    DURATION = SHORTS[2].duration

    def construct(self):
        title = self.headline("128 -> 64 PAIRS", 44)
        coords = VGroup()
        pair_marks = VGroup()
        for row in range(8):
            y = 4.45 - row * 0.58
            for col in range(2):
                x = -0.38 + col * 0.76
                coords.add(Rectangle(
                    width=0.56, height=0.38,
                    stroke_color=RIDER if col == 0 else DRIVER,
                    stroke_width=2.4, fill_color=CARD, fill_opacity=1,
                ).move_to([x, y, 0]))
            pair_marks.add(SurroundingRectangle(
                VGroup(coords[-2], coords[-1]), buff=0.06,
                stroke_color=GOLD, stroke_width=2.2,
            ))
        dimension_label = T("one Query / Key vector", 25, TEXT_DIM, MONO, W_SEMI
                            ).move_to([0, -0.75, 0])
        pair_label = T("each pair is one 2-D plane", 24, GOLD, MONO, W_SEMI
                       ).move_to([0, -2.0, 0])
        self.play(FadeIn(title), FadeIn(coords, lag_ratio=0.03),
                  FadeIn(dimension_label), run_time=1.4)
        self.at(7.68)
        self.play(Create(pair_marks, lag_ratio=0.06),
                  FadeIn(pair_label), run_time=1.4)

        self.at(16.62)
        self.clear_all(0.45)
        clock_title = self.headline("64 CLOCKS", 48)
        faces, hands, centers = dial_bank(
            [0, 0.25, 0], TH, cols=8, r=0.34, spacing=0.82
        )
        dots = VGroup()
        for k, (face, hand) in enumerate(zip(faces, hands)):
            row = k // 8
            ring_color = TEXT if row < 2 else TEXT_DIM if row < 5 else RING_IDLE
            face.set_stroke(
                color=ring_color,
                width=3.0 - 0.15 * row,
                opacity=1.0 - 0.04 * row,
            )
            hand_color = TEXT if row == 0 else GOLD
            hand.set_stroke(color=hand_color, width=4.0)
            dots.add(Dot(centers[k], radius=0.045, color=hand_color))
        self.at(16.62)
        self.play(FadeIn(clock_title), FadeIn(faces, lag_ratio=0.006),
                  FadeIn(hands, lag_ratio=0.006), FadeIn(dots, lag_ratio=0.006),
                  run_time=2.0)

        def spin(group, dt):
            for k, hand in enumerate(group):
                hand.rotate(float(TH[k]) * 2.4 * dt, about_point=centers[k])

        hands.add_updater(spin)
        self.at(21.18)
        fast_box = SurroundingRectangle(
            VGroup(*faces[:8], *hands[:8]), buff=0.08,
            stroke_color=GOLD, stroke_width=3.2,
        ).set_z_index(14)
        fast_label = T("FAST: NEARBY DETAIL", 23, GOLD, MONO, W_SEMI
                       ).move_to([0, 4.0, 0])
        self.at(29.1)
        self.play(Create(fast_box), FadeIn(fast_label), run_time=0.9)

        slow_box = SurroundingRectangle(
            VGroup(*faces[-8:], *hands[-8:]), buff=0.08,
            stroke_color=DRIVER, stroke_width=3.2,
        ).set_z_index(14)
        slow_label = T("SLOW: BROAD PATTERNS", 23, DRIVER, MONO, W_SEMI
                       ).move_to([0, -3.42, 0])
        self.at(35.46)
        self.play(Create(slow_box), FadeIn(slow_label), run_time=0.9)

        combined = T("COMBINED PATTERN", 23, GOLD, MONO, W_SEMI
                     ).move_to([0, -3.42, 0])
        self.at(40.38)
        self.play(Transform(slow_label, combined), run_time=0.8)
        self.finish()
        hands.clear_updaters()
