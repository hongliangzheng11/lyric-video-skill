# -*- coding: utf-8 -*-
"""Word-level Whisper pass over the project's 16 kHz mono WAV.

    python transcribe.py <project> [--model medium.en] [--lang en]

Writes whisper_raw.json (segments + word timings). The model can be a name
("medium.en") or a directory containing a converted faster-whisper model.
A CPU int8 run of medium.en over a 3.5-minute track takes a few minutes.
"""
import argparse
import json
import os
import sys

import soundfile as sf
from faster_whisper import WhisperModel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--model", default="medium.en")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--out", default="whisper_raw.json")
    args = ap.parse_args()

    wav = os.path.join(args.project, "assets", "vocals16k.wav")
    if not os.path.isfile(wav):
        sys.exit("missing %s — run new_project.py first" % wav)

    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    data, sr = sf.read(wav, dtype="float32")
    segments, info = model.transcribe(
        data,
        language=args.lang,
        word_timestamps=True,
        beam_size=5,
        vad_filter=False,
        condition_on_previous_text=False,
        temperature=[0.0, 0.2, 0.4],
    )

    out = {"language": info.language, "duration": info.duration,
           "model": args.model, "segments": []}
    for s in segments:
        out["segments"].append({
            "id": len(out["segments"]),
            "start": round(s.start, 3),
            "end": round(s.end, 3),
            "text": s.text.strip(),
            "words": [{"w": w.word, "s": round(w.start, 3), "e": round(w.end, 3)}
                      for w in (s.words or [])],
        })

    path = os.path.join(args.project, args.out)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("model:", args.model, "segments:", len(out["segments"]),
          "duration:", info.duration, "->", path)


if __name__ == "__main__":
    main()
