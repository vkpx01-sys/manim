# Audio-first Manim Video Studio

A reusable production setup for original, polished technical explainers. The
workflow starts with narration: write SSML in short parts, generate each part's
WAV with your chosen TTS provider, align the spoken words, then render the
Manim scenes against those timings.

The project already includes a five-part example, selectable visual themes,
custom geometry helpers, forced alignment, and batch rendering. The
reference videos are for studying broad craft choices such as visual clarity
and pacing; build an original channel identity and do not copy their scenes,
assets, characters, or code.

The default visual system uses a dark purple gradient. The optional
PlanetScale-inspired theme uses a black background, JetBrains Mono, square
cards, dashed connectors, and restrained orange, blue, green, and yellow
accents.

## Project map

- `kv_video_themes/` — selectable palettes, including `planetscale`.
- `reducible_style.py` — shared palette, background, scene base, and
  reusable visual components, including waveform and spectrum helpers.
- `hexkit.py` — reusable hexagonal and polyhedral geometry.
- `episode_template.py` — copyable, audio-timed Manim scene starter.
- `partN.ssml`, `partN.wav`, `partN.py` — narration, generated audio, and scene
  code for one numbered segment.
- `align_script.py` — aligns the SSML text to the WAV and writes
  `partN_timeline.json`.
- `sync_timeline.py` — timing helpers used by rendered scenes.
- `render_parts.py` — discovers parts, aligns stale timelines, renders, muxes
  audio, and merges segments.

## Start a new segment

1. Copy `episode_template.py` to the next numbered scene, for example
   `part7.py`. Replace the template animation and update its `CUES` estimates.
2. Save matching narration in `part7.ssml`. Use three `<p>...</p>` blocks for
   the template's three `self.sync()` calls, or change both together.
3. Generate `part7.wav` from that SSML with your TTS provider. Keep provider
   credentials outside the repository.
4. Preview the complete pipeline at low quality:

   ```powershell
   .\.venv\Scripts\python.exe render_parts.py --parts 7 --quality 480p --debug
   ```

   Alignment runs automatically when the WAV or SSML is newer than its
   timeline. To align without rendering:

   ```powershell
   .\.venv\Scripts\python.exe render_parts.py --parts 7 --align-only
   ```

5. Render a final segment:

   ```powershell
   .\.venv\Scripts\python.exe render_parts.py --parts 7 --quality 1080p --fps 30 --theme planetscale
   ```

   Render all discovered `partN.wav` segments and merge them with:

   ```powershell
   .\.venv\Scripts\python.exe render_parts.py --quality 1080p --fps 30 --theme planetscale
   ```

The output is written to `rendered_parts\`. Use `--realign` to force a fresh
alignment, `--merge-only` to reassemble already-rendered parts, and `--dry-run`
to inspect which inputs would be used.

## Keep the series coherent

- Use the shared helpers in `reducible_style.py` and `hexkit.py`; do not
  redefine the palette, gradient, typography, or recurring components inside
  each scene.
- Keep each segment focused on one question and one memorable visual. Reveal
  diagrams in steps and let the narration lead the timing.
- Prefer original, concept-specific shapes built from Manim geometry. Use
  `signal_trace()` and `spectrum_bars()` as starting points for signal topics.
- Keep SSML wording faithful to the WAV; alignment errors are surfaced rather
  than silently papered over.

The TTS provider is intentionally pluggable: the current pipeline begins once
the provider has produced a WAV. A provider-specific synthesis command can be
added later without changing the visual or timing workflow.
