"""Render timeline-selected RoPE or MoE clips as portrait-native Shorts."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from render_parts import (
    BACKGROUND_MUSIC,
    DEFAULT_MUSIC_GAIN_DB,
    DEFAULT_VOICE_GAIN_DB,
    audio_duration,
    ffmpeg_executable,
)

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "rendered_rope_shorts_9x16"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--series", choices=("rope", "moe"), default="rope",
                        help="video series to render (default: rope)")
    parser.add_argument("--shorts", nargs="+",
                        help="short slugs to render (default: all three)")
    parser.add_argument("--output-dir", type=Path,
                        help="output directory (defaults by series)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="overwrite outputs for the selected shorts")
    return parser.parse_args()


def source_timeline(spec) -> list[dict]:
    path = ROOT / f"part{spec.part}_timeline.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing aligned source timeline: {path.name}")
    timeline = json.loads(path.read_text(encoding="utf-8"))
    selected = [
        sentence for sentence in timeline
        if sentence["end"] > spec.start and sentence["start"] < spec.end
    ]
    if not selected:
        raise ValueError(f"{spec.slug} does not overlap any aligned sentences")
    if (abs(selected[0]["start"] - spec.start) > 0.03
            or abs(selected[-1]["end"] - spec.end) > 0.03):
        raise ValueError(
            f"{spec.slug} must start and end on sentence boundaries; "
            f"timeline range is {selected[0]['start']:.2f}-{selected[-1]['end']:.2f}s"
        )
    return selected


def validate_spec(spec, shorts_module) -> list[dict]:
    if not 30.0 <= spec.duration <= 45.0:
        raise ValueError(f"{spec.slug} duration {spec.duration:.2f}s is outside 30-45s")
    audio = ROOT / f"part{spec.part}.wav"
    if not audio.is_file():
        raise FileNotFoundError(f"Missing source narration: {audio.name}")
    duration = audio_duration(audio)
    if spec.start < 0 or spec.end > duration:
        raise ValueError(f"{spec.slug} range exceeds {audio.name} ({duration:.2f}s)")
    scene = getattr(shorts_module, spec.scene, None)
    if scene is None or abs(scene.DURATION - spec.duration) > 0.01:
        raise ValueError(f"{spec.scene} duration does not match {spec.slug}")
    return source_timeline(spec)


def ass_timestamp(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    whole_seconds, fraction = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{fraction:02d}"


def write_ass(spec, sentences: list[dict], path: Path) -> None:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,JetBrains Mono,46,&H00FFFFFF,&H0000FFFF,&HAA000000,&H99000000,-1,0,0,0,100,100,0,0,3,2,0,2,90,90,320,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for sentence in sentences:
        start = max(sentence["start"], spec.start) - spec.start
        end = min(sentence["end"], spec.end) - spec.start
        text = textwrap.fill(sentence["text"], width=38)
        text = (text.replace("\\", r"\\").replace("{", r"\{")
                .replace("}", r"\}").replace("\n", r"\N"))
        events.append(
            f"Dialogue: 0,{ass_timestamp(start)},{ass_timestamp(end)},"
            f"Default,,0,0,0,,{text}"
        )
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def manim_video(spec, output_dir: Path, scene_source: Path) -> Path:
    with tempfile.TemporaryDirectory(prefix=f"manim_{spec.slug}_", dir=output_dir) as tmp:
        work = Path(tmp)
        media = work / "media"
        media.mkdir()
        command = [
            sys.executable, "-m", "manim", "render", "-qh",
            "--fps", "30", "--renderer", "cairo", "--disable_caching",
            "--media_dir", str(media), "--output_file", spec.slug,
            str(scene_source), spec.scene,
        ]
        subprocess.run(
            command, cwd=ROOT, check=True,
            env={**os.environ, "KV_VIDEO_THEME": "planetscale"},
        )
        matches = list(media.rglob(f"{spec.slug}.mp4"))
        if len(matches) != 1:
            raise FileNotFoundError(
                f"Expected one Manim video for {spec.scene}, found {len(matches)}"
            )
        staged = output_dir / f".{spec.slug}_portrait.mp4"
        staged.write_bytes(matches[0].read_bytes())
    return staged


def mix_caption_and_audio(spec, video: Path, output: Path,
                          subtitles: Path, ffmpeg: str) -> None:
    duration = spec.duration
    fade_out = min(1.2, duration / 2)
    fade_out_start = max(0.0, duration - fade_out)
    graph = (
        f"[1:a]atrim=start={spec.start:.3f}:end={spec.end:.3f},"
        f"asetpts=PTS-STARTPTS,volume={DEFAULT_VOICE_GAIN_DB:.2f}dB,"
        "asplit=2[voice][sidechain];"
        f"[2:a]volume={DEFAULT_MUSIC_GAIN_DB:.2f}dB,"
        f"atrim=duration={duration:.3f},afade=t=in:st=0:d=0.7,"
        f"afade=t=out:st={fade_out_start:.3f}:d={fade_out:.3f}[music];"
        "[music][sidechain]sidechaincompress=threshold=0.056:ratio=2:"
        "attack=150:release=1000[ducked];"
        "[voice][ducked]amix=inputs=2:duration=first:dropout_transition=0:"
        "normalize=0,alimiter=limit=0.95[aout]"
    )
    ass_path = subtitles.resolve().as_posix().replace(":", r"\:")
    command = [
        ffmpeg, "-y", "-i", str(video), "-i", str(ROOT / f"part{spec.part}.wav"),
        "-stream_loop", "-1", "-i", str(BACKGROUND_MUSIC),
        "-filter_complex", graph, "-vf", f"ass=filename='{ass_path}'",
        "-map", "0:v:0", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-t", f"{duration:.3f}", "-shortest", "-movflags", "+faststart",
        str(output),
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        tail = "\n".join(result.stderr.splitlines()[-35:])
        raise RuntimeError(f"Short mix for {spec.slug} failed:\n{tail}")
    video.unlink()


def verify_output(path: Path, ffmpeg: str, expected_duration: float) -> None:
    probe = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        capture_output=True, text=True, check=False,
    )
    details = probe.stderr
    if ("1080x1920" not in details or "30 fps" not in details
            or "Audio: aac" not in details):
        raise RuntimeError(f"{path.name} is not a 1080x1920/30fps AAC Short")
    duration_match = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", details
    )
    if not duration_match:
        raise RuntimeError(f"Could not read the encoded duration of {path.name}")
    hours, minutes, seconds = duration_match.groups()
    actual_duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if (not 30.0 <= actual_duration <= 45.0
            or abs(actual_duration - expected_duration) > 0.1):
        raise RuntimeError(
            f"{path.name} duration {actual_duration:.2f}s does not match "
            f"the {expected_duration:.2f}s clip"
        )
    decoded = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-f", "null", "NUL"],
        capture_output=True, text=True, check=False,
    )
    if decoded.returncode:
        raise RuntimeError(f"{path.name} failed full decode:\n{decoded.stderr}")


def run() -> int:
    args = parse_args()
    if args.series == "rope":
        import rope_shorts
        shorts_module = rope_shorts
        scene_source = ROOT / "rope_shorts.py"
        default_output_dir = OUTPUT_DIR
    else:
        import moe_shorts
        shorts_module = moe_shorts
        scene_source = ROOT / "moe_shorts.py"
        default_output_dir = ROOT / "rendered_moe_shorts_9x16"

    all_specs = list(shorts_module.SHORTS)
    available = {spec.slug for spec in all_specs}
    selected = set(args.shorts or available)
    unknown = selected - available
    if unknown:
        raise ValueError(f"Unknown {args.series} short(s): {', '.join(sorted(unknown))}")
    specs = [spec for spec in all_specs if spec.slug in selected]
    output_dir = (args.output_dir or default_output_dir).resolve()
    ffmpeg = ffmpeg_executable()

    print("Format: 1080x1920, 30 fps, PlanetScale theme")
    for spec in specs:
        sentences = validate_spec(spec, shorts_module)
        output = output_dir / f"{spec.slug}.mp4"
        subtitle_file = output_dir / f"{spec.slug}.ass"
        print(
            f"{spec.slug} ({spec.title}): Part {spec.part}, "
            f"{spec.start:.2f}-{spec.end:.2f}s, "
            f"{spec.duration:.2f}s, {len(sentences)} caption cues"
        )
        if not args.dry_run and output.exists() and not args.force:
            raise FileExistsError(
                f"{output} already exists; use --force to replace it"
            )
    if args.dry_run:
        return 0
    if not BACKGROUND_MUSIC.is_file():
        raise FileNotFoundError(f"Missing background music: {BACKGROUND_MUSIC}")
    output_dir.mkdir(parents=True, exist_ok=True)

    for spec in specs:
        sentences = validate_spec(spec, shorts_module)
        output = output_dir / f"{spec.slug}.mp4"
        subtitle_file = output_dir / f"{spec.slug}.ass"
        write_ass(spec, sentences, subtitle_file)
        staged = manim_video(spec, output_dir, scene_source)
        mix_caption_and_audio(spec, staged, output, subtitle_file, ffmpeg)
        verify_output(output, ffmpeg, spec.duration)
        print(f"Finished: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
