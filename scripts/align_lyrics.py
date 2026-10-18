# -*- coding: utf-8 -*-
"""Align curated lyric lines to Whisper word timestamps.

    python align_lyrics.py <project> [--source lyrics_source.json]

Reads:
  lyrics_source.json  {"audio": ..., "models": [...],
                       "lines": [{"en": ..., "zh": ..., "start"?: ..., "end"?: ...}]}
  whisper_raw.json    output of transcribe.py

Writes lyrics_final.json (per-line start/end/en/zh) and transcript.json
(the deliverable transcript). Prints a review list of lines that need a manual
`start`/`end` override — the caller is expected to fix and re-run.

Never invents timings: every line either comes from matched Whisper words or
from an explicit override written by a human/agent after listening.
"""
import argparse
import bisect
import difflib
import json
import os
import re
import sys

WORD_RE = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?", re.UNICODE)
VOCALISE = {"ooh", "oh", "o", "ah", "uh", "mm", "hmm", "la", "na", "yeah", "hey"}


def norm(w):
    return w.lower().replace("\u2019", "'").strip().strip(".,!?;:\"\u201c\u201d")


def toks(text):
    return WORD_RE.findall(text.lower().replace("\u2019", "'"))


def load(project, source):
    with open(os.path.join(project, source), encoding="utf-8") as f:
        src = json.load(f)
    with open(os.path.join(project, "whisper_raw.json"), encoding="utf-8") as f:
        raw = json.load(f)
    return src, raw


def word_stream(raw, vocab):
    """Flatten Whisper output to (token, start, end), keeping only lyric words."""
    words = []
    for seg in raw["segments"]:
        for w in seg.get("words", []):
            t = norm(w["w"])
            if not t:
                continue
            if t in vocab:
                words.append((t, w["s"], w["e"]))
            elif t in VOCALISE:
                continue
    return words


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--source", default="lyrics_source.json")
    args = ap.parse_args()

    src, raw = load(args.project, args.source)
    lines_src = src["lines"]
    canon, owner = [], []
    for li, ln in enumerate(lines_src):
        for t in toks(ln["en"]):
            canon.append(t)
            owner.append(li)
    vocab = set(canon)

    words = word_stream(raw, vocab)
    if not words:
        raise SystemExit("no lyric words found in whisper output — check --lang / model")

    flat = [w[0] for w in words]
    sm = difflib.SequenceMatcher(a=canon, b=flat, autojunk=False)
    cmap = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("equal", "replace"):
            for k in range(min(i2 - i1, j2 - j1)):
                cmap[i1 + k] = j1 + k
    keys = sorted(cmap)

    def near(i):
        if i in cmap:
            return cmap[i]
        pos = bisect.bisect_left(keys, i)
        cands = [keys[k] for k in (pos, pos - 1) if 0 <= k < len(keys)]
        if not cands:
            return None
        return cmap[min(cands, key=lambda k: abs(k - i))]

    lines, review = [], []
    for li, ln in enumerate(lines_src):
        idx = [i for i, o in enumerate(owner) if o == li]
        if "start" in ln and "end" in ln:
            s0, e0, src_tag = float(ln["start"]), float(ln["end"]), "manual"
        else:
            # a line is only "matched" when enough of its own tokens landed on
            # whisper words — a stray nearest-neighbour hit would otherwise
            # collapse a whole block onto one timestamp
            hit = sum(1 for i in idx if i in cmap)
            if not idx or hit < max(1, int(0.5 * len(idx))):
                s0 = e0 = None
                src_tag = "unmatched"
            else:
                wi, wj = near(idx[0]), near(idx[-1])
                if wi is None or wj is None or wj <= wi and len(idx) > 2:
                    s0 = e0 = None
                    src_tag = "unmatched"
                else:
                    s0, e0, src_tag = words[wi][1], words[wj][2], "whisper"
        if s0 is None:
            review.append((li, ln["en"], "no matching words in the transcript"))
        lines.append({"en": ln["en"], "zh": ln.get("zh", ""), "start": s0, "end": e0,
                      "src": src_tag})

    # an unmatched run at the head or tail has no anchor: stop instead of guessing
    first_ok = next((i for i, l in enumerate(lines) if l["start"] is not None), None)
    last_ok = next((i for i, l in enumerate(reversed(lines)) if l["start"] is not None), None)
    if first_ok is None:
        raise SystemExit("no line matched the transcript — check --lang and the lyrics text")
    last_ok = len(lines) - 1 - last_ok
    orphans = [l for i, l in enumerate(lines)
               if l["start"] is None and (i < first_ok or i > last_ok)]
    if orphans:
        raise SystemExit(
            "these lines have no transcript anchor and cannot be placed:\n  "
            + "\n  ".join(l["en"] for l in orphans)
            + "\n\nRe-decode that passage with rescan.py and add explicit start/end "
              "overrides in lyrics_source.json.")

    # inner gaps borrow the space between their neighbours
    for i, ln in enumerate(lines):
        if ln["start"] is not None:
            continue
        prev = next((l for l in reversed(lines[:i]) if l["start"] is not None), None)
        nxt = next((l for l in lines[i + 1:] if l["start"] is not None), None)
        ln["start"], ln["end"], ln["src"] = prev["end"] + 0.12, nxt["start"] - 0.12, "gap-filled"

    order = sorted(range(len(lines)), key=lambda i: lines[i]["start"])
    lines = [lines[i] for i in order]

    for i, ln in enumerate(lines):
        nxt = lines[i + 1]["start"] if i + 1 < len(lines) else ln["end"] + 4
        ln["end"] = min(max(ln["end"], ln["start"] + 1.4), nxt - 0.12, ln["start"] + 8.5)
        if ln["end"] > nxt - 0.12:
            ln["end"] = max(ln["start"] + 0.9, nxt - 0.12)

    # post-clamp audit: catches collapsed blocks that "matched" but share a stamp
    for i, ln in enumerate(lines):
        if ln["end"] - ln["start"] < 0.5:
            review.append((i, ln["en"], "collapsed to %.2fs" % (ln["end"] - ln["start"])))
        if i and abs(ln["start"] - lines[i - 1]["start"]) < 0.05:
            review.append((i, ln["en"], "same start as the line before (%.2f)" % ln["start"]))

    out = [{"start": round(l["start"], 2), "end": round(l["end"], 2),
            "en": l["en"], "zh": l["zh"], "align": l["src"]} for l in lines]

    with open(os.path.join(args.project, "lyrics_final.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    transcript = {
        "audio": src.get("audio", ""),
        "duration_sec": round(raw["duration"], 3),
        "source": "whisper",
        "models": src.get("models", [raw.get("model", "")]),
        "segments": [{"start": o["start"], "end": o["end"],
                      "text_en": o["en"], "text_zh": o["zh"]} for o in out],
    }
    with open(os.path.join(args.project, "transcript.json"), "w", encoding="utf-8") as f:
        json.dump(transcript, f, ensure_ascii=False, indent=2)

    for o in out:
        print("%7.2f-%7.2f [%-12s] %s" % (o["start"], o["end"], o["align"], o["en"]))
    print("\nlines: %d  manual: %d  gap-filled: %d" % (
        len(out), sum(1 for o in out if o["align"] == "manual"),
        sum(1 for o in out if o["align"] == "gap-filled")))

    if review:
        print("\nREVIEW — %d line(s) need attention. Re-decode the passage with"
              " rescan.py, then add start/end overrides to %s and re-run:" % (len(review), args.source))
        for i, en, why in review:
            print("  #%-3d %-48s %s" % (i, en[:48], why))
        sys.exit(2)
    print("OK: every line anchored to a real sung timestamp")


if __name__ == "__main__":
    main()
