# -*- coding: utf-8 -*-
"""Re-transcribe a time window with a different model / prompt.

    python rescan.py <project> --from 10 --to 33 [--model small.en] [--prompt "..."]

Use this when a passage came out as a vocalisation ("ooh"), was merged into one
blob, or the alignment looks wrong. It prints word-level timings for the window
and saves rescan_<from>-<to>.json so those numbers can be written into
lyrics_source.json as explicit start/end overrides.

Nothing here is an estimate: it is a second decode of the same audio.
"""
import argparse
import json
import os

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--from", dest="t0", type=float, required=True)
    ap.add_argument("--to", dest="t1", type=float, required=True)
    ap.add_argument("--model", default="small.en")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--prompt", default=None,
                    help="hint text for the decoder, e.g. the lyric lines in that window")
    ap.add_argument("--pad", type=float, default=1.0, help="seconds of context each side")
    args = ap.parse_args()

    wav = os.path.join(args.project, "assets", "vocals16k.wav")
    data, sr = sf.read(wav, dtype="float32")
    a = max(0.0, args.t0 - args.pad)
    b = min(len(data) / sr, args.t1 + args.pad)
    clip = data[int(a * sr):int(b * sr)]

    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        clip, language=args.lang, word_timestamps=True, beam_size=5,
        vad_filter=False, condition_on_previous_text=False,
        initial_prompt=args.prompt, temperature=[0.0, 0.2],
    )

    out = {"model": args.model, "window": [args.t0, args.t1], "pad": a, "segments": []}
    print("model %s  window %.2f-%.2f (pad %.2f)" % (args.model, args.t0, args.t1, a))
    for s in segments:
        seg = {"start": round(s.start + a, 3), "end": round(s.end + a, 3),
               "text": s.text.strip(),
               "words": [{"w": w.word, "s": round(w.start + a, 3), "e": round(w.end + a, 3)}
                         for w in (s.words or [])]}
        out["segments"].append(seg)
        print("%7.2f-%7.2f  %s" % (seg["start"], seg["end"], seg["text"]))
        print("        " + " ".join("%s[%.2f]" % (w["w"].strip(), w["s"]) for w in seg["words"]))

    path = os.path.join(args.project, "rescan_%.1f-%.1f.json" % (args.t0, args.t1))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n->", path)


if __name__ == "__main__":
    main()
