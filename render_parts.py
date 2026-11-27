"""Render numbered Manim parts and mux them with their WAVs, synced by forced alignment.

Per part N you need: partN.wav, partN.ssml, and a scene file partN.py (or cpu_partN.py)
with one top-level scene class declaring AUDIO, CUES, or TIMELINE. The class name
is discovered automatically. The generated wrapper adds TimelineSync.
partN_timeline.json is generated automatically (and regenerated if the WAV/SSML change).

    python render_parts.py --parts 4 --quality 480p --debug     # quick sync check
    python render_parts.py --quality 480p --fps 15             # low-cost preview
    python render_parts.py --theme planetscale --parts 4 --quality 480p --fps 15
    python render_parts.py --parts 4 --quality 4k               # final
    python render_parts.py --quality 4k                         # all parts + merge
    python render_parts.py --align-only --parts 4               # just (re)build timeline
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from kv_video_themes import available_themes

QUALITY_FLAGS = {"480p": "-ql", "1080p": "-qh", "4k": "-qk"}
BACKGROUND_MUSIC = ROOT / "assets" / "music" / "ambient_loop.flac"
DEFAULT_VOICE_GAIN_DB = 19.0
DEFAULT_MUSIC_GAIN_DB = -15.94
MUSIC_FADE_IN_SECONDS = 2.0
MUSIC_FADE_OUT_SECONDS = 5.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--quality", choices=QUALITY_FLAGS, default="4k")
    p.add_argument("--fps", type=int, choices=(15, 30, 60),
                   help="default: 30 for 4k/480p, 60 for 1080p")
    p.add_argument("--renderer", choices=("cairo", "opengl"), default="cairo")
    p.add_argument("--theme", choices=available_themes(), default="purple",
                   help="visual theme (default: purple)")
    p.add_argument("--parts", nargs="+", type=int,
                   help="part numbers to render (default: discover all partN.wav files)")
    p.add_argument("--workers", type=int, choices=range(1, 7), default=3)
    p.add_argument("--output-dir", type=Path, default=ROOT / "rendered_parts")
    p.add_argument("--music-gain-db", type=float, default=DEFAULT_MUSIC_GAIN_DB,
                   help="background music gain relative to its source (default: -15.94 dB)")
    p.add_argument("--no-music", action="store_true",
                   help="render without the background music bed")
    p.add_argument("--mix-only", action="store_true",
                   help="add narration/music to existing no-music renders without rerendering")
    p.add_argument("--model", default="medium", help="Whisper model for alignment")
    p.add_argument("--realign", action="store_true", help="force re-running alignment")
    p.add_argument("--align-only", action="store_true", help="only build timelines")
    p.add_argument("--debug", action="store_true",
                   help="burn current time + spoken sentence into the video")
    p.add_argument("--merge-only", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def scene_file(part: int) -> Path:
    names = [f"part{part}.py", f"cpu_part{part}.py"] + (["uber.py"] if part == 1 else [])
    for name in names:
        if (ROOT / name).is_file():
            return ROOT / name
    return ROOT / names[0]


def available_parts() -> list[int]:
    parts = []
    for audio in ROOT.glob("part*.wav"):
        match = re.fullmatch(r"part([1-9]\d*)", audio.stem)
        if match:
            parts.append(int(match.group(1)))
    return sorted(parts)


def audio_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        if audio.getframerate() <= 0:
            raise ValueError(f"{path.name} has an invalid sample rate")
        return audio.getnframes() / audio.getframerate()


def scene_class_name(source: Path) -> str:
    text = source.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"{source.name} is empty")
    tree = ast.parse(text, filename=str(source))
    markers = {"AUDIO", "CUES", "TIMELINE"}
    candidates = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        attributes = set()
        for statement in node.body:
            if isinstance(statement, ast.Assign):
                targets = statement.targets
            elif isinstance(statement, ast.AnnAssign):
                targets = [statement.target]
            else:
                continue
            attributes.update(
                target.id for target in targets if isinstance(target, ast.Name)
            )
        if attributes & markers:
            candidates.append(node.name)

    if len(candidates) == 1:
        return candidates[0]
    found = ", ".join(candidates) if candidates else "none"
    raise ValueError(
        f"{source.name} must define exactly one top-level scene class with "
        f"class-level AUDIO, CUES, or TIMELINE metadata; found: {found}"
    )


def ensure_timeline(part: int, audio: Path, args: argparse.Namespace) -> Path:
    ssml = ROOT / f"part{part}.ssml"
    timeline = ROOT / f"part{part}_timeline.json"
    if not ssml.is_file():
        if timeline.is_file():
            return timeline
        raise FileNotFoundError(f"Missing {ssml.name} (needed to build the timeline)")
    stale = (not timeline.is_file()
             or timeline.stat().st_mtime < max(ssml.stat().st_mtime, audio.stat().st_mtime))
    if args.realign or stale:
        if args.dry_run:
            print(f"[Part {part}] would align {ssml.name} + {audio.name}")
        else:
            print(f"[Part {part}] aligning {ssml.name} to {audio.name} ...", flush=True)
            from align_script import align_part
            align_part(ssml, audio, timeline, args.model)
    return timeline


def validate_inputs(args: argparse.Namespace, parts: list[int]):
    items, missing = [], []
    for part in parts:
        source, audio = scene_file(part), ROOT / f"part{part}.wav"
        if not source.is_file():
            missing.append(str(source))
        if not audio.is_file():
            missing.append(str(audio))
        if not source.is_file() or not audio.is_file():
            continue
        duration = audio_duration(audio)
        if duration <= 0:
            raise ValueError(f"{audio.name} is empty")
        timeline = ensure_timeline(part, audio, args)
        items.append((part, source, audio, duration,
                      scene_class_name(source), timeline))
    if missing:
        raise FileNotFoundError("Missing required input files:\n  " + "\n  ".join(missing))
    return items


def wrapper_source(part, source, audio, duration, base_class, timeline) -> str:
    return f'''\
import importlib.util
import sys
from pathlib import Path

_source = Path({str(source.resolve())!r})
sys.path.insert(0, str(_source.parent))
_spec = importlib.util.spec_from_file_location("_batch_part_{part}", _source)
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)
from sync_timeline import TimelineSync
_Base = _module.{base_class}
_audio_duration = {duration!r}


class Part{part}(TimelineSync, _Base):
    AUDIO = {str(audio.resolve())!r}
    TIMELINE = {str(timeline.resolve())!r}

    def start_audio(self):
        pass                      # audio is muxed by ffmpeg afterwards

    def say(self, *args, **kwargs):
        scene_say = getattr(_Base, "say", None)
        if scene_say is not None:
            return scene_say(self, *args, **kwargs)
        return TimelineSync.say(self, *args, **kwargs)

    def construct(self):
        super().construct()
        remaining = _audio_duration - self.renderer.time
        if remaining > 0.02:
            self.wait(remaining)  # video exactly as long as the audio
        elif remaining < -0.5:
            print(f"[batch] warning: Part{part} runs {{-remaining:.2f}}s past its WAV")
'''


def ffmpeg_executable() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
    except ImportError as error:
        raise RuntimeError("FFmpeg not found. Install it or `pip install imageio-ffmpeg`.") from error
    return imageio_ffmpeg.get_ffmpeg_exe()


def validate_runtime_dependencies() -> None:
    if importlib.util.find_spec("manim") is None:
        raise RuntimeError(f'manim is missing for {sys.executable}: "{sys.executable}" -m pip install manim')


def mix_audio_video(video, narration, output, ffmpeg, duration, music_gain_db,
                    no_music, voice_gain_db=DEFAULT_VOICE_GAIN_DB) -> None:
    if duration <= 0:
        raise ValueError("Audio duration must be positive")

    cmd = [ffmpeg, "-y", "-i", str(video), "-i", str(narration)]
    if no_music:
        graph = (f"[1:a]volume={voice_gain_db}dB,"
                 "alimiter=limit=0.95[aout]")
    else:
        if not BACKGROUND_MUSIC.is_file():
            raise FileNotFoundError(f"Missing background music: {BACKGROUND_MUSIC}")
        fade_in = min(MUSIC_FADE_IN_SECONDS, duration / 2)
        fade_out = min(MUSIC_FADE_OUT_SECONDS, duration / 2)
        fade_out_start = max(0.0, duration - fade_out)
        cmd.extend(["-stream_loop", "-1", "-i", str(BACKGROUND_MUSIC)])
        graph = (
            f"[1:a]volume={voice_gain_db}dB,asplit=2[voice][sidechain];"
            f"[2:a]volume={music_gain_db}dB,"
            f"afade=t=in:st=0:d={fade_in:.3f},"
            f"afade=t=out:st={fade_out_start:.3f}:d={fade_out:.3f}[music];"
            "[music][sidechain]sidechaincompress=threshold=0.056:ratio=2:"
            "attack=150:release=1000[ducked];"
            "[voice][ducked]amix=inputs=2:duration=first:dropout_transition=0:"
            "normalize=0,alimiter=limit=0.95[aout]"
        )
    cmd.extend([
        "-filter_complex", graph, "-map", "0:v:0", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-ac", "2", "-shortest", "-movflags", "+faststart", str(output),
    ])
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        tail = "\n".join(result.stderr.splitlines()[-30:])
        raise RuntimeError(f"Audio mix for {output.name} failed:\n{tail}")


def render_part(item, work_dir, output_dir, ffmpeg, quality_flag, fps, renderer,
                label, theme, debug, music_gain_db, no_music):
    part, source, audio, duration, base_class, timeline = item
    pdir = work_dir / f"part{part}"
    pdir.mkdir()
    media = pdir / "manim_media"
    wrapper = pdir / f"part{part}_batch.py"
    wrapper.write_text(wrapper_source(part, source, audio, duration, base_class, timeline),
                       encoding="utf-8")
    stem = f"part{part}_{label}"
    log_path = pdir / "manim.log"
    cmd = [sys.executable, "-m", "manim", "render", quality_flag, "--fps", str(fps),
           "--renderer", renderer, "--media_dir", str(media), "--output_file", stem,
           str(wrapper), f"Part{part}"]
    env = {**os.environ, "KV_VIDEO_THEME": theme,
           **({"SYNC_DEBUG": "1"} if debug else {})}
    print(f"[Part {part}] Rendering...", flush=True)
    try:
        with log_path.open("w", encoding="utf-8") as log:
            subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                           check=True, env=env)
    except subprocess.CalledProcessError as error:
        tail = "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:])
        raise RuntimeError(f"Part {part} Manim render failed. Last log lines:\n{tail}") from error

    rendered = list(media.rglob(f"{stem}.mp4"))
    if len(rendered) != 1:
        raise FileNotFoundError(f"Expected one rendered video for Part {part}, found {len(rendered)}")

    final = output_dir / f"{stem}{'_debug' if debug else ''}.mp4"
    mix_audio_video(rendered[0], audio, final, ffmpeg, duration,
                    music_gain_db, no_music)
    print(f"[Part {part}] Finished: {final}", flush=True)
    return final


def concatenate_wavs(audio_files, output) -> None:
    if not audio_files:
        raise ValueError("At least one narration WAV is required")
    with wave.open(str(audio_files[0]), "rb") as first:
        expected = (first.getnchannels(), first.getsampwidth(), first.getframerate(),
                    first.getcomptype(), first.getcompname())
    with wave.open(str(output), "wb") as target:
        target.setnchannels(expected[0])
        target.setsampwidth(expected[1])
        target.setframerate(expected[2])
        for path in audio_files:
            with wave.open(str(path), "rb") as source:
                actual = (source.getnchannels(), source.getsampwidth(),
                          source.getframerate(), source.getcomptype(),
                          source.getcompname())
                if actual != expected:
                    raise ValueError(f"{path.name} has an incompatible WAV format")
                while True:
                    frames = source.readframes(65536)
                    if not frames:
                        break
                    target.writeframes(frames)


def merge_videos(videos, audio_files, merged, ffmpeg, work_dir, music_gain_db,
                 no_music) -> None:
    if len(videos) != len(audio_files):
        raise ValueError("Each video part must have a matching narration WAV")
    video_list = work_dir / "video_concat.txt"
    video_list.write_text(
        "".join(f"file '{v.resolve().as_posix()}'\n" for v in videos),
        encoding="utf-8",
    )
    joined_video = work_dir / "joined_video.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(video_list),
         "-map", "0:v:0", "-an", "-c:v", "copy", "-movflags", "+faststart",
         str(joined_video)],
        cwd=ROOT, check=True,
    )
    narration = work_dir / "joined_narration.wav"
    concatenate_wavs(audio_files, narration)
    duration = sum(audio_duration(path) for path in audio_files)
    mix_audio_video(joined_video, narration, merged, ffmpeg, duration,
                    music_gain_db, no_music)


def run() -> int:
    args = parse_args()
    if args.merge_only and args.mix_only:
        raise ValueError("--merge-only and --mix-only cannot be used together")
    if args.mix_only and args.no_music:
        raise ValueError("--mix-only always adds the background music")
    if not -60 <= args.music_gain_db <= 0:
        raise ValueError("--music-gain-db must be between -60 and 0")
    parts = list(dict.fromkeys(args.parts)) if args.parts else available_parts()
    if not parts:
        raise FileNotFoundError(
            "No partN.wav files found. Add an audio part or pass --parts explicitly."
        )
    if any(part < 1 for part in parts):
        raise ValueError("--parts values must be positive integers")
    qflag = QUALITY_FLAGS[args.quality]
    fps = args.fps or (30 if args.quality in ("4k", "480p") else 60)
    theme_suffix = f"_{args.theme}" if args.theme != "purple" else ""
    base_label = (f"{args.quality}{fps}{theme_suffix}"
                  + ("_opengl" if args.renderer == "opengl" else ""))
    audio_suffix = "_no_music" if args.no_music else "_music"
    label = f"{base_label}{audio_suffix}"
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    merged = out / f"all_parts_{label}.mp4"
    print(f"Quality: {args.quality} at {fps} FPS ({qflag}), "
          f"renderer: {args.renderer}, theme: {args.theme}")
    if not args.no_music and not BACKGROUND_MUSIC.is_file():
        raise FileNotFoundError(f"Missing background music: {BACKGROUND_MUSIC}")

    audio_files = [ROOT / f"part{part}.wav" for part in parts]

    if args.merge_only:
        videos = [out / f"part{p}_{label}.mp4" for p in parts]
        missing = [str(path) for path in videos + audio_files if not path.is_file()]
        if missing:
            raise FileNotFoundError("Cannot merge; missing:\n  " + "\n  ".join(missing))
        if args.dry_run:
            return 0
        with tempfile.TemporaryDirectory(prefix="manim_merge_", dir=str(out)) as tmp:
            merge_videos(videos, audio_files, merged, ffmpeg_executable(),
                         Path(tmp), args.music_gain_db, args.no_music)
        print(f"Finished: {merged}")
        return 0

    if args.mix_only:
        debug_suffix = "_debug" if args.debug else ""
        source_videos = []
        missing = []
        for part in parts:
            candidates = (
                out / f"part{part}_{base_label}_no_music{debug_suffix}.mp4",
                out / f"part{part}_{base_label}{debug_suffix}.mp4",
            )
            source = next((path for path in candidates if path.is_file()), None)
            if source is None:
                missing.append(" or ".join(str(path) for path in candidates))
            source_videos.append(source)
        missing.extend(str(path) for path in audio_files if not path.is_file())
        if missing:
            raise FileNotFoundError("Cannot mix; missing:\n  " + "\n  ".join(missing))
        if args.dry_run:
            for part, source, audio in zip(parts, source_videos, audio_files):
                print(f"Part {part}: would mix {source.name} + {audio.name}")
            return 0

        ffmpeg = ffmpeg_executable()
        for part, source, audio in zip(parts, source_videos, audio_files):
            final = out / f"part{part}_{label}{debug_suffix}.mp4"
            mix_audio_video(source, audio, final, ffmpeg, audio_duration(audio),
                            args.music_gain_db, no_music=False)
            print(f"[Part {part}] Mixed: {final}", flush=True)
        if len(parts) > 1 and not args.debug:
            with tempfile.TemporaryDirectory(prefix="manim_mix_", dir=str(out)) as tmp:
                merge_videos(source_videos, audio_files, merged, ffmpeg, Path(tmp),
                             args.music_gain_db, no_music=False)
            print(f"Finished: {merged}")
        return 0

    inputs = validate_inputs(args, parts)
    if args.align_only or args.dry_run:
        for part, source, audio, duration, cls, tl in inputs:
            print(f"Part {part}: {source.name}::{cls} + {audio.name} ({duration:.2f}s), timeline {tl.name}")
        return 0

    validate_runtime_dependencies()
    ffmpeg = ffmpeg_executable()
    workers = min(args.workers, len(inputs))
    print(f"Rendering {workers} parts concurrently")
    with tempfile.TemporaryDirectory(prefix="manim_batch_", dir=str(out)) as tmp:
        work = Path(tmp)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            videos = list(ex.map(lambda it: render_part(it, work, out, ffmpeg, qflag, fps,
                                                        args.renderer, label, args.theme,
                                                        args.debug, args.music_gain_db,
                                                        args.no_music), inputs))
        if len(videos) > 1 and not args.debug:
            merge_videos(videos, [item[2] for item in inputs], merged, ffmpeg, work,
                         args.music_gain_db, args.no_music)
            print(f"Finished: {merged}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (FileNotFoundError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error