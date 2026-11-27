"""Forced-align an SSML script to its WAV and write partN_timeline.json.

    pip install stable-ts
    python align_script.py part4.ssml part4.wav [--model medium]

The SSML gives the exact words, so Whisper only has to find WHERE each word is.
Output: <wav stem>_timeline.json = list of sentences, each with paragraph index,
start/end seconds and per-word times.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def ffmpeg_on_path() -> Iterator[None]:
    if shutil.which("ffmpeg"):
        yield
        return

    import imageio_ffmpeg

    with tempfile.TemporaryDirectory(prefix="stable_ts_ffmpeg_") as directory:
        ffmpeg_alias = Path(directory) / "ffmpeg.exe"
        try:
            os.link(imageio_ffmpeg.get_ffmpeg_exe(), ffmpeg_alias)
        except OSError:
            shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), ffmpeg_alias)

        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = directory + os.pathsep + original_path
        try:
            yield
        finally:
            os.environ["PATH"] = original_path


def parse_ssml(path: Path) -> list[tuple[int, str]]:
    raw = path.read_text(encoding="utf-8")
    raw = re.sub(r"<break[^>]*/>", " ", raw)
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", raw, re.S)
    if not paragraphs:
        raise ValueError(f"{path.name}: no <p>...</p> paragraphs found")
    sentences = []
    for index, para in enumerate(paragraphs):
        text = html.unescape(re.sub(r"<[^>]+>", "", para))
        text = " ".join(text.split())
        for sentence in re.split(r"(?<=[.?!])\s+", text):
            if sentence.strip():
                sentences.append((index, sentence.strip()))
    return sentences


def validate_timeline(timeline: list[dict]) -> None:
    for sentence in timeline:
        if not any(word["end"] > word["start"] for word in sentence["words"]):
            raise RuntimeError(
                f"No words aligned for sentence: {sentence['text']!r}. "
                "Check that the SSML matches the WAV and does not continue past it."
            )


def align_part(ssml: Path, wav: Path, out: Path, model_name: str = "medium",
               language: str = "en") -> list[dict]:
    import stable_whisper  # imported lazily so --dry-run needs no ML install

    sentences = parse_ssml(ssml)
    model = stable_whisper.load_model(model_name)
    with ffmpeg_on_path():
        result = model.align(
            str(wav),
            "\n".join(text for _, text in sentences),
            language=language,
            original_split=True,
        )

    # Preferred: one aligned segment per script sentence.
    per_sentence = None
    if len(result.segments) == len(sentences):
        per_sentence = [list(seg.words) for seg in result.segments]
    else:
        # Fallback: slice the flat word list by each sentence's word count.
        words = list(result.all_words())
        expected = sum(len(text.split()) for _, text in sentences)
        if len(words) != expected:
            raise RuntimeError(
                f"Alignment mismatch: {len(result.segments)} segments for "
                f"{len(sentences)} sentences, {len(words)} words for {expected} "
                "script words. Check that the SSML matches the WAV."
            )
        per_sentence, cursor = [], 0
        for _, text in sentences:
            n = len(text.split())
            per_sentence.append(words[cursor:cursor + n])
            cursor += n

    timeline = []
    for (para, text), words in zip(sentences, per_sentence):
        if not words:
            raise RuntimeError(f"No words aligned for: {text[:50]}")
        timeline.append({
            "para": para,
            "text": text,
            "start": round(words[0].start, 3),
            "end": round(words[-1].end, 3),
            "words": [{"w": w.word.strip(), "start": round(w.start, 3),
                       "end": round(w.end, 3)} for w in words],
        })

    validate_timeline(timeline)
    out.write_text(json.dumps(timeline, indent=1), encoding="utf-8")
    report(timeline)
    print(f"wrote {out}")
    return timeline


def report(timeline: list[dict]) -> None:
    print(f"\n{'#':>3} {'P':>2} {'start':>7} {'end':>7}  text")
    for i, s in enumerate(timeline):
        print(f"{i:>3} {s['para']:>2} {s['start']:7.2f} {s['end']:7.2f}  {s['text'][:70]}")
    print()
    for a, b in zip(timeline, timeline[1:]):
        gap = b["start"] - a["end"]
        if not 0.15 < gap < 1.3:
            print(f"[check] gap {gap:.2f}s between sentences: "
                  f"'{a['text'][:30]}...' -> '{b['text'][:30]}...'")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ssml", type=Path)
    ap.add_argument("wav", type=Path)
    ap.add_argument("--model", default="medium")
    ap.add_argument("--language", default="en")
    a = ap.parse_args()
    align_part(a.ssml, a.wav, a.wav.with_name(a.wav.stem + "_timeline.json"),
               a.model, a.language)