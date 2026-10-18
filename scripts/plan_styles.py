# -*- coding: utf-8 -*-
"""Plan the animal band's performance style(s) for a project.

    python plan_styles.py <project> [--style ID|auto|mixed]

Writes style_plan.json, consumed by build_frame.py / frame_template.html:

  mode=fixed     one style for the whole track
  mode=sections  different styles per phrase section (mixed mode)

Style choice precedence (highest first):
  1. --style on the command line (manual choice always wins)
  2. "style" in project.json (set at project creation with new_project.py --style)
  3. auto — recommended from the audio map (energy, tempo, rolls, hard stops)

Everything is deterministic: the seed is crc32(artist|title|plan-mode), so the
same project re-planned twice produces byte-identical style_plan.json.

The plan also carries the pre-scheduled performance events (accent spawns,
freeze frames / holds) so the browser runtime never needs randomness — the
same parameters always render the same choreography.
"""
import argparse
import json
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motion import Rng  # noqa: E402  (mulberry32, same as the glass body seed)

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STYLES_PATH = os.path.join(SKILL, "config", "styles.json")
CHARS_PATH = os.path.join(SKILL, "config", "characters.json")

# mixed-mode guardrails: at most this many distinct sheet pairs load per song
MAX_STYLES = 3
MIN_SEGMENT = 5.0          # sections shorter than this are merged away
FUNNY_SEG_MIN = 1.4        # one-off interaction length (s)
FUNNY_SEG_MAX = 2.0


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def weighted_pick(rng, weights):
    """weights: {key: w} -> key, deterministic."""
    total = float(sum(weights.values()))
    if total <= 0:
        return next(iter(weights))
    r = rng.next() * total
    for k, w in weights.items():
        r -= w
        if r <= 0:
            return k
    return next(reversed(list(weights)))


def audio_features(am, dur):
    """Summarise the beat grid into style-recommendation features."""
    phases = [(float(p["start"]), float(p["end"]), float(p["energy"]))
              for p in am.get("energy_phases", [])]
    if not phases:
        phases = [(0.0, dur, 0.3)]

    def wmed(values_and_weights):
        pairs = sorted(values_and_weights)
        total = sum(w for _, w in pairs)
        acc, cut = 0.0, total / 2.0
        for v, w in pairs:
            acc += w
            if acc >= cut:
                return v
        return pairs[-1][0]

    ew = [(e, max(0.0, b - a)) for a, b, e in phases]
    ew = [(e, w) for e, w in ew if w > 0]
    med = wmed(ew) if ew else 0.3
    mean = sum(e * w for e, w in ew) / max(1e-6, sum(w for _, w in ew))
    es = sorted(e for e, _ in ew)
    p25 = es[int(0.25 * (len(es) - 1))] if es else 0.3
    p75 = es[int(0.75 * (len(es) - 1))] if es else 0.3

    span = sum(b - a for a, b, e in phases if e > 0.55)
    low_span = sum(b - a for a, b, e in phases if e < 0.28)
    events = am.get("events", [])
    beats = (am.get("grid") or {}).get("beats_sec", [])
    bpm = float((am.get("tempo") or {}).get("bpm") or 0.0)
    return {
        "energy_median": round(med, 3),
        "energy_mean": round(mean, 3),
        "energy_p25": round(p25, 3),
        "energy_p75": round(p75, 3),
        "high_energy_frac": round(span / max(1e-6, dur), 3),
        "low_energy_frac": round(low_span / max(1e-6, dur), 3),
        "bpm": round(bpm, 1),
        "onset_rate": round(len(events) / max(1e-6, dur), 2),
        "rolls": len(am.get("rolls", [])),
        "hard_stops": len(am.get("hard_stops", [])),
        "surges": len([k for k in am.get("key_moments", []) if k.get("kind") == "SURGE"]),
        "drops": len([k for k in am.get("key_moments", []) if k.get("kind") == "DROP"]),
        "n_beats": len(beats),
    }


def recommend_style(f):
    """Deterministic mood -> style rules. Order matters; first hit wins."""
    if f["bpm"] >= 105 and f["energy_median"] >= 0.5:
        return "energetic_performance", (
            "bpm %.0f + 能量中位数 %.2f，强节奏高能量" % (f["bpm"], f["energy_median"]))
    if f["energy_median"] <= 0.30 and (f["bpm"] <= 95 or f["low_energy_frac"] >= 0.45):
        return "emotional_listening", (
            "能量中位数 %.2f、低能量占比 %.0f%%，慢歌/安静段落" %
            (f["energy_median"], f["low_energy_frac"] * 100))
    if (f["high_energy_frac"] >= 0.15 and f["low_energy_frac"] >= 0.12
            and f["rolls"] + f["hard_stops"] >= 3 and f["bpm"] >= 95):
        return "funny_interaction", (
            "能量起伏大（高 %.0f%% / 低 %.0f%%）+ %d 个过门或硬停，适合插入互动" %
            (f["high_energy_frac"] * 100, f["low_energy_frac"] * 100,
             f["rolls"] + f["hard_stops"]))
    return "cozy_ensemble", (
        "能量中位数 %.2f、起伏平稳，中速温暖曲风" % f["energy_median"])


def merge_tiny(segments, styles_cfg):
    """Drop sections shorter than MIN_SEGMENT by folding them into a neighbour.

    funny_interaction one-offs are never folded away — they are the scripted
    gags of mixed mode, not regular sections.
    """
    out = [dict(s) for s in segments]
    changed = True
    while changed and len(out) > 1:
        changed = False
        for i, seg in enumerate(out):
            if seg["t1"] - seg["t0"] >= MIN_SEGMENT or seg["style"] == "funny_interaction":
                continue
            prev = out[i - 1] if i > 0 else None
            nxt = out[i + 1] if i + 1 < len(out) else None
            if prev and (not nxt or prev["t1"] - prev["t0"] >= nxt["t1"] - nxt["t0"]):
                prev["t1"] = seg["t1"]
            elif nxt:
                nxt["t0"] = seg["t0"]
            else:
                continue
            out.pop(i)
            changed = True
            break
    return out


def cap_styles(segments, styles_cfg):
    """Bound the number of distinct sprite-sheet pairs a song loads.

    The cap counts sheet SETS, not styles: while every style shares the classic
    sheets nothing is demoted; once per-style variant sheets exist, a 4th sheet
    set demotes the least-used style that would introduce it. funny_interaction
    one-offs are protected — losing the gags defeats mixed mode.
    """
    def sheet_key(sid):
        cfg = styles_cfg.get(sid) or styles_cfg["classic"]
        return tuple(cfg.get("sheets") or styles_cfg["classic"]["sheets"])

    while True:
        counts = {}
        for s in segments:
            counts[s["style"]] = counts.get(s["style"], 0.0) + (s["t1"] - s["t0"])
        sets = {}
        for sid in counts:
            sets.setdefault(sheet_key(sid), []).append(sid)
        if len(sets) <= MAX_STYLES:
            return segments
        # least-used style inside the largest sheet set gets folded away
        big_key = max(sets, key=lambda k: sum(counts[s] for s in sets[k]))
        demotable = [s for s in sets[big_key] if s != "funny_interaction"]
        if not demotable:
            return segments
        weakest = min(demotable, key=lambda k: counts[k])
        target = max(counts, key=lambda k: counts[k])
        for s in segments:
            if s["style"] == weakest:
                s["style"] = target
        merged = []
        for s in segments:
            if merged and merged[-1]["style"] == s["style"]:
                merged[-1]["t1"] = s["t1"]
            else:
                merged.append(dict(s))
        segments = merged


def plan_sections(am, dur, rng, styles_cfg):
    """Split the track into phrase sections and pick a style per section."""
    phrases = sorted(am.get("phrases", []), key=lambda p: p["start"])
    if not phrases:
        phrases = [{"start": 0.0, "end": dur}]
    phases = [(float(p["start"]), float(p["end"]), float(p["energy"]))
              for p in am.get("energy_phases", [])]

    def energy_between(a, b):
        acc, w = 0.0, 0.0
        for s, e, en in phases:
            lo, hi = max(s, a), min(e, b)
            if hi > lo:
                acc += en * (hi - lo)
                w += hi - lo
        return acc / w if w > 0 else 0.3

    segs = []
    for ph in phrases:
        t0, t1 = max(0.0, float(ph["start"])), min(dur, float(ph["end"]))
        if t1 - t0 < 0.5:
            continue
        e = energy_between(t0, t1)
        if e < 0.30:
            style = "emotional_listening"
        elif e > 0.55:
            style = "energetic_performance"
        else:
            style = "cozy_ensemble"
        if segs and segs[-1]["style"] == style:
            segs[-1]["t1"] = t1
        else:
            segs.append({"t0": round(t0, 3), "t1": round(t1, 3), "style": style})
    if not segs:
        segs = [{"t0": 0.0, "t1": round(dur, 3), "style": "cozy_ensemble"}]
    segs = merge_tiny(segs, styles_cfg)
    segs = cap_styles(segs, styles_cfg)

    # one-off funny interactions anchored on musical corners: a hard stop, a
    # drum roll's end, or a SURGE/DROP key moment. The gag plays over whatever
    # section contains the anchor, so it reads as "the band reacts to the turn".
    funny_cfg = styles_cfg["funny_interaction"]
    hcfg = funny_cfg.get("holds", {})
    if hcfg.get("enabled"):
        cands = []   # (anchor_time, probability)
        for st in am.get("hard_stops", []):
            cands.append((float(st["t"]), 0.85))
        for r in am.get("rolls", []):
            cands.append((float(r["end"]), 0.5))
        for k in am.get("key_moments", []):
            if k.get("kind") in ("SURGE", "DROP"):
                cands.append((float(k["t"]), 0.45))
        picked = []
        count = int(hcfg.get("max_count", 3))
        gap = float(hcfg.get("min_gap", 18.0))
        # deterministic: scan in time order, let the seeded rng gate each corner
        for anchor, p in sorted(cands):
            if len(picked) >= count:
                break
            if any(abs(anchor - q) < gap for q in picked):
                continue
            # the section hosting the gag decides how likely it is
            host = next((s for s in segs if s["t0"] <= anchor < s["t1"]), None)
            if not host:
                continue
            if anchor + FUNNY_SEG_MAX > host["t1"] + 0.01:
                continue
            if rng.next() < p:
                picked.append(anchor)
        for anchor in reversed(picked):
            d = FUNNY_SEG_MIN + rng.next() * (FUNNY_SEG_MAX - FUNNY_SEG_MIN)
            for i, seg in enumerate(segs):
                if seg["t0"] <= anchor < seg["t1"]:
                    end = min(anchor + d, seg["t1"])
                    segs[i:i + 1] = [
                        {"t0": seg["t0"], "t1": round(anchor, 3), "style": seg["style"]},
                        {"t0": round(anchor, 3), "t1": round(end, 3),
                         "style": "funny_interaction"},
                        {"t0": round(end, 3), "t1": seg["t1"], "style": seg["style"]},
                    ]
                    break
        segs = merge_tiny(segs, styles_cfg)
        segs = cap_styles(segs, styles_cfg)
    return segs


def schedule_events(segments, am, dur, rng, styles_cfg, chars_cfg):
    """Pre-schedule accent spawns (and funny reaction pairs) on real beats."""
    beats = sorted(float(b) for b in (am.get("grid") or {}).get("beats_sec", []))
    events, holds = [], []
    last_t = -1e9
    MIN_GAP = 0.32

    for seg in segments:
        sid = seg["style"]
        cfg = styles_cfg[sid]
        acc = cfg.get("accents", {})
        rate = float(acc.get("rate_per_min", 0))
        if rate <= 0 or not beats:
            continue
        bpm = float((am.get("tempo") or {}).get("bpm") or 120.0)
        p_beat = min(0.9, rate / max(30.0, bpm))
        lo, hi = seg["t0"] + 0.3, seg["t1"] - 0.8
        # brag/cheer bursts right at surges inside this segment
        for km in am.get("key_moments", []):
            if km.get("kind") != "SURGE" or not (lo <= float(km["t"]) <= hi):
                continue
            if sid not in ("energetic_performance", "cozy_ensemble"):
                continue
            if rng.next() < 0.6:
                for _ in range(3):
                    events.append({"t": round(float(km["t"]) + rng.next() * 0.5, 3),
                                   "kind": "spark", "char": weighted_pick(
                                       rng, chars_cfg["__weights__"][sid])})
        for b in beats:
            t = b
            if not (lo <= t <= hi):
                continue
            if rng.next() >= p_beat:
                continue
            if t - last_t < MIN_GAP:
                continue
            kind = weighted_pick(rng, acc.get("kinds", {"note": 1.0}))
            char = weighted_pick(rng, chars_cfg["__weights__"][sid])
            t = t + (0.0 if kind in ("bang", "quest") else -0.04 + rng.next() * 0.1)
            events.append({"t": round(t, 3), "kind": kind, "char": char})
            last_t = t
            if len(events) > rate * dur / 60.0 * 2.0 + 40:
                break

        # funny segments get reaction pairs (bang + quest) + freeze frames.
        # one-off mixed-mode gags fire at the segment start; a fixed funny song
        # spreads its gags across rolls / hard stops instead.
        hcfg = cfg.get("holds", {})
        if hcfg.get("enabled") and sid == "funny_interaction":
            w = chars_cfg["__weights__"][sid]
            ranked = sorted(w, key=lambda k: -w[k])
            a, b2 = ranked[0], ranked[1 % len(ranked)]
            gag_times = []
            if seg["t0"] > 2.0:                      # mixed-mode one-off
                gag_times.append(seg["t0"])
            else:                                     # fixed funny: spread gags
                cands = []
                for st in am.get("hard_stops", []):
                    if seg["t0"] + 1.0 <= float(st["t"]) <= seg["t1"] - 2.0:
                        cands.append(float(st["t"]))
                for r in am.get("rolls", []):
                    rt = float(r["end"])
                    if seg["t0"] + 1.0 <= rt <= seg["t1"] - 2.0:
                        cands.append(rt)
                cands.sort()
                count = int(hcfg.get("max_count", 3))
                gap = float(hcfg.get("min_gap", 18.0))
                for c in cands:
                    if len(gag_times) >= count:
                        break
                    if all(abs(c - g) >= gap for g in gag_times):
                        gag_times.append(c)
            for gt in gag_times:
                events.append({"t": round(gt + 0.06, 3), "kind": "bang", "char": a})
                events.append({"t": round(gt + 0.12, 3), "kind": "quest", "char": b2})
                holds.append({"t": round(gt + 0.18, 3),
                              "dur": round(hcfg.get("dur_min", 0.24)
                                           + rng.next() * (hcfg.get("dur_max", 0.4)
                                                           - hcfg.get("dur_min", 0.24)), 3)})
    events.sort(key=lambda e: e["t"])
    holds.sort(key=lambda h: h["t"])
    return events, holds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--style", default=None,
                    help="classic | emotional_listening | energetic_performance | "
                         "funny_interaction | cozy_ensemble | auto | mixed")
    args = ap.parse_args()
    p = args.project

    with open(os.path.join(p, "project.json"), encoding="utf-8") as f:
        meta = json.load(f)
    dur = float(meta["duration"])
    styles_cfg = load(STYLES_PATH)["styles"]
    chars_cfg = load(CHARS_PATH)["characters"]
    am = {}
    am_path = os.path.join(p, "audiomap.json")
    if os.path.isfile(am_path):
        am = load(am_path)

    requested = args.style or (meta.get("style") or "auto")
    valid = set(styles_cfg) | {"auto", "mixed"}
    if requested not in valid:
        sys.exit("unknown style %r — pick one of: %s"
                 % (requested, ", ".join(sorted(valid))))

    seed = zlib.crc32(("%s|%s|%s" % (meta.get("artist", ""), meta.get("title", ""),
                                    requested)).encode())
    rng = Rng(seed)

    feats = None
    if requested in ("auto", "mixed"):
        feats = audio_features(am, dur) if am else None
        if requested == "auto":
            style, reason = recommend_style(feats) if feats else ("classic", "no audio map — classic")
            mode = "fixed"
            segments = [{"t0": 0.0, "t1": round(dur, 3), "style": style}]
        else:
            mode = "sections"
            segments = plan_sections(am, dur, rng, styles_cfg)
            counts = {}
            for s in segments:
                counts[s["style"]] = counts.get(s["style"], 0.0) + (s["t1"] - s["t0"])
            top = max(counts, key=lambda k: counts[k])
            reason = "混合模式：按乐句能量分段（%s）" % "、".join(
                "%s %.0fs" % (k, v) for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
            style = top
    else:
        mode = "fixed"
        style = requested
        reason = "user-specified style"
        segments = [{"t0": 0.0, "t1": round(dur, 3), "style": style}]

    # per-style character weights for accent placement
    weights = {}
    for sid in set(s["style"] for s in segments):
        cfg_w = styles_cfg[sid].get("accents", {}).get(
            "char_weights", {k: 1 for k in chars_cfg})
        weights[sid] = {k: float(cfg_w.get(k, 1.0)) * float(chars_cfg[k]["accent_weight"])
                        for k in chars_cfg}
    work = dict(chars_cfg)
    work["__weights__"] = weights

    events, holds = schedule_events(segments, am, dur, rng, styles_cfg, work)

    downbeats = [round(float(d), 3) for d in (am.get("grid") or {}).get("downbeats_sec", [])]
    beats = [round(float(b), 3) for b in (am.get("grid") or {}).get("beats_sec", [])]
    surges = [round(float(k["t"]), 3) for k in am.get("key_moments", [])
              if k.get("kind") == "SURGE"]
    drops = [round(float(k["t"]), 3) for k in am.get("key_moments", [])
             if k.get("kind") == "DROP"]

    plan = {
        "version": 1,
        "mode": mode,
        "style": style,
        "reason": reason,
        "segments": segments,
        "used_styles": sorted(set(s["style"] for s in segments)),
        "seed": seed,
        "events": events,
        "holds": holds,
        "music": {
            "bpm": round(float((am.get("tempo") or {}).get("bpm") or 0.0), 1),
            "beats": beats,
            "downbeats": downbeats,
            "surges": surges,
            "drops": drops,
        },
    }
    out = os.path.join(p, "style_plan.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)

    print("mode=%s  style=%s  seed=%d" % (mode, style, seed))
    print("reason: %s" % reason)
    if feats is not None and requested == "auto":
        print("features: %s" % json.dumps(feats, ensure_ascii=False))
    for s in segments:
        print("  %7.2f - %7.2f  %s" % (s["t0"], s["t1"], s["style"]))
    print("events %d  holds %d  downbeats %d -> %s"
          % (len(events), len(holds), len(downbeats), out))


if __name__ == "__main__":
    main()
