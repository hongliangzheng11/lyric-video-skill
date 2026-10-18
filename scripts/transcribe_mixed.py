# -*- coding: utf-8 -*-
"""Window-wise transcription for songs that switch language mid-track.

    python transcribe_mixed.py <project> [--model large-v3-turbo] [--window 14] [--hop 10]

`transcribe.py --lang xx` locks one language for the whole file. A song that
mixes English and Japanese (or Korean, Spanish, ...) then gets its second
language force-transcribed into the first one — the words come out fluent but
wrong, which is worse than an obvious failure.

This script decodes overlapping windows and lets the model pick a language per
window, so each section is transcribed in the language actually being sung.
Words in the overlap region are dropped (only the window core is kept), so the
output stitches together without duplicates.

Writes whisper_mixed.json:
  [{"a": 0.0, "lang": "ja", "p": 0.98, "text": "...", "words": [[s, e, w], ...]}, ...]

It also prints the language map — check it before writing lyrics; a window that
flips language usually marks a section boundary.
"""
import argparse
import json
import os

import soundfile as sf
from faster_whisper import WhisperModel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--model", default="large-v3-turbo",
                    help="must be a multilingual model; *.en models cannot switch")
    ap.add_argument("--window", type=float, default=14.0)
    ap.add_argument("--hop", type=float, default=10.0)
    ap.add_argument("--out", default="whisper_mixed.json")
    args = ap.parse_args()

    wav = os.path.join(args.project, "assets", "vocals16k.wav")
    if not os.path.isfile(wav):
        raise SystemExit("missing %s — run new_project.py first" % wav)

    data, sr = sf.read(wav, dtype="float32")
    dur = len(data) / sr
    model = WhisperModel(args.model, device="cpu", compute_type="int8")

    out, a = [], 0.0
    while a < dur:
        b = min(dur, a + args.window)
        segs, info = model.transcribe(
            data[int(a * sr):int(b * sr)], language=None, word_timestamps=True,
            beam_size=5, vad_filter=False, condition_on_previous_text=False,
            temperature=[0.0, 0.2])
        # keep only the window core (one hop wide) so neighbouring windows do not
        # repeat words: window 14 / hop 10 keeps [a+2, a+12)
        pad = (args.window - args.hop) / 2.0
        lo = a + (pad if a > 0 else 0.0)
        hi = a + (args.window - pad if b < dur else args.window)
        words = []
        for s in segs:
            for w in (s.words or []):
                ws = round(w.start + a, 2)
                if lo <= ws < hi:
                    words.append([ws, round(w.end + a, 2), w.word.strip()])
        out.append({"a": round(a, 1), "lang": info.language,
                    "p": round(info.language_probability, 2),
                    "text": " ".join(w[2] for w in words), "words": words})
        print("[%6.1f-%6.1f] %-2s %.2f  %s"
              % (a, b, info.language, info.language_probability, out[-1]["text"]))
        a += args.hop

    path = os.path.join(args.project, args.out)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    langs = {}
    for w in out:
        langs[w["lang"]] = langs.get(w["lang"], 0) + 1
    print("\nlanguage map: " + "  ".join("%s=%d windows" % kv for kv in sorted(langs.items())))
    print("->", path)


if __name__ == "__main__":
    main()
