"""Copy this file to partN.py to start an audio-synced episode segment.

Keep the SSML paragraph count aligned with the three self.sync() calls below.
render_parts.py replaces the estimated CUES with word-aligned WAV timings.
"""
from reducible_style import *


class EpisodeTemplate(ReducibleScene):
    CUES = [6.0, 12.0, 18.0]  # cumulative estimates until a WAV is aligned
    AUDIO = None

    def construct(self):
        self.start_audio()

        title = display_title("One signal, many frequencies", size=34)
        question = chip("WHAT'S INSIDE THIS WAVE?", color=GOLD, size=17)
        question.next_to(title, DOWN, buff=0.35)
        self.play(FadeIn(title, shift=DOWN * 0.15), FadeIn(question, shift=UP * 0.1))

        x_values = np.linspace(-4.5, 4.5, 100)
        wave_points = [
            (x, 0.45 + 0.55 * np.sin(1.3 * x) + 0.18 * np.sin(3.9 * x), 0)
            for x in x_values
        ]
        wave = signal_trace(wave_points, color=RIDER, width=3.0)
        wave_label = T("ONE COMPOSITE SIGNAL", 17, TEXT_DIM, SANS, W_MED)
        wave_label.move_to([0, 1.55, 0])
        self.play(Write(wave_label), Create(wave), run_time=2.4)
        self.sync(0)

        spectrum = spectrum_bars(
            [0.08, 0.16, 0.28, 0.7, 0.42, 0.2, 0.12, 0.06, 0.03],
            center=[0, -1.95, 0],
            width=8.2,
            height=1.5,
            color=GOLD,
        )
        spectrum_label = T("THE FREQUENCIES INSIDE IT", 17, TEXT_DIM, SANS, W_MED)
        spectrum_label.move_to([0, -0.82, 0])
        self.play(FadeIn(spectrum_label, shift=DOWN * 0.1),
                  LaggedStart(*[GrowFromEdge(bar, DOWN) for bar in spectrum[2]],
                              lag_ratio=0.06, run_time=1.8))
        self.add(spectrum[0], spectrum[1])
        self.sync(1)

        takeaway = T("ONE SHAPE  ->  MANY PARTS", 23, DRIVER, SANS, W_SEMI)
        takeaway.to_edge(DOWN, buff=0.55)
        self.play(FadeIn(takeaway, shift=UP * 0.1))
        self.sync(2)
