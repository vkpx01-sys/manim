"""Mixin that makes a Manim scene follow real audio timings.

    class CpuPart4(TimelineSync, ReducibleScene):
        TIMELINE = "part4_timeline.json"
        CUES = [38, 81, 157, 218]     # old estimates, only used to map old dt values

Old calls keep working:   self.at(0, 12.0)   -> mapped onto the real paragraph,
                                                 snapped to the nearest sentence start
                          self.sync(0)       -> waits until real end of paragraph 0
New exact anchors:        self.say("eighty nanoseconds")      wait for that phrase
                          self.t_start("..."), self.t_end("...")
                          self.run_time_to("...")  run_time that ends when phrase starts
Set SYNC_DEBUG=1 (or render_parts.py --debug) for a time + current sentence overlay.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from manim import DL, YELLOW, Text, always_redraw
from reducible_style import DISPLAY


def _norm(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", word.lower())


class TimelineSync:
    TIMELINE = "part4_timeline.json"
    LEAD = 0.35      # give each visual beat time to land before the word
    SNAP = 2.5       # old-style at() snaps to a sentence start within this many seconds

    # ------------------------------------------------------------ loading
    def _now(self) -> float:
        try:
            return self.renderer.time
        except AttributeError:
            return self.time

    def _timeline_path(self) -> Path:
        name = Path(self.TIMELINE)
        if name.is_absolute() and name.is_file():
            return name
        candidates = [Path.cwd() / name]
        for klass in type(self).__mro__:
            module = sys.modules.get(klass.__module__)
            file = getattr(module, "__file__", None)
            if file:
                candidates.append(Path(file).resolve().parent / name)
        for path in candidates:
            if path.is_file():
                return path
        raise FileNotFoundError(
            f"{name} not found. Run align_script.py first. Looked in:\n  "
            + "\n  ".join(map(str, candidates)))

    def _load(self) -> None:
        if getattr(self, "_sents", None) is not None:
            return
        self._sents = json.loads(self._timeline_path().read_text(encoding="utf-8"))
        self._words = []
        for s in self._sents:
            for w in s["words"]:
                self._words.append((_norm(w["w"]), w["start"], w["end"]))
        paras = {}
        for s in self._sents:
            p = paras.setdefault(s["para"], {"start": s["start"], "end": s["end"]})
            p["start"] = min(p["start"], s["start"])
            p["end"] = max(p["end"], s["end"])
        self._paras = [paras[k] for k in sorted(paras)]
        cues = getattr(self, "CUES", None)
        if cues and len(cues) != len(self._paras):
            print(f"[sync] warning: CUES has {len(cues)} entries but the timeline has "
                  f"{len(self._paras)} paragraphs")

    # ------------------------------------------------------------ helpers
    def _debug(self) -> None:
        if not os.environ.get("SYNC_DEBUG"):
            return
        if getattr(self, "_dbg", None) is None:
            def make():
                t = self._now()
                cur = next((s["text"] for s in self._sents
                            if s["start"] <= t <= s["end"]), "")
                return (Text(f"{t:6.2f}s  {cur[:60]}", font=DISPLAY,
                             font_size=16, color=YELLOW)
                        .to_corner(DL, buff=0.1).set_z_index(100))
            self._dbg = always_redraw(make)
        if self._dbg not in self.mobjects:
            self.add(self._dbg)

    def _wait_until(self, t: float) -> None:
        gap = (t - self.LEAD) - self._now()
        if gap > 0.02:
            self.wait(gap)

    def _find(self, phrase: str, nth: int = 0) -> tuple[int, int]:
        self._load()
        toks = [_norm(w) for w in phrase.split() if _norm(w)]
        words = [w[0] for w in self._words]
        hits = [i for i in range(len(words) - len(toks) + 1)
                if words[i:i + len(toks)] == toks]
        if len(hits) <= nth:
            raise ValueError(
                f"phrase not found in timeline: {phrase!r}. Write it the way it is "
                "SPOKEN (numbers as words), see the table printed by align_script.py")
        return hits[nth], hits[nth] + len(toks) - 1

    # ------------------------------------------------------------ public API
    def t_start(self, phrase: str, nth: int = 0) -> float:
        return self._words[self._find(phrase, nth)[0]][1]

    def t_end(self, phrase: str, nth: int = 0) -> float:
        return self._words[self._find(phrase, nth)[1]][2]

    def say(self, phrase: str, nth: int = 0) -> None:
        """Wait until the narrator reaches `phrase`."""
        self._debug()
        self._wait_until(self.t_start(phrase, nth))

    def run_time_to(self, phrase: str, nth: int = 0, minimum: float = 0.4) -> float:
        """run_time for an animation that should finish when `phrase` starts."""
        return max(minimum, self.t_start(phrase, nth) - self._now())

    def at(self, i: int, dt: float = 0.0) -> None:
        """Old API: dt seconds into estimated paragraph i -> real time, sentence-snapped."""
        self._load()
        self._debug()
        para = self._paras[min(i, len(self._paras) - 1)]
        cues = getattr(self, "CUES", None)
        if cues and i < len(cues):
            est_start = cues[i - 1] if i > 0 else 0.0
            est_len = max(cues[i] - est_start, 1e-6)
            frac = min(max(dt / est_len, 0.0), 1.0)
            t = para["start"] + frac * (para["end"] - para["start"])
        else:
            t = min(para["start"] + dt, para["end"])
        starts = [s["start"] for s in self._sents
                  if para["start"] - 0.01 <= s["start"] <= para["end"]]
        nearest = min(starts, key=lambda x: abs(x - t))
        if abs(nearest - t) <= self.SNAP:
            t = nearest
        self._wait_until(t)

    def sync(self, i: int, *args, **kwargs) -> None:
        """Wait until the real end of paragraph i."""
        self._load()
        self._debug()
        para = self._paras[min(i, len(self._paras) - 1)]
        gap = para["end"] - self._now()
        if gap > 0.02:
            self.wait(gap)