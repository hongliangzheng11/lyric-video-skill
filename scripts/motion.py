# -*- coding: utf-8 -*-
"""Pre-compute the glass body's drift + wall-bounce path.

    python motion.py <project>

Deterministic: the seed comes from the song title, so a given song always gets
the same path (stable across renders and seeks) while different songs differ.
Writes motion.json: legs (linear travel between walls) and bounces (impact time,
outward normal, shape before/after, morph window). The frame only interpolates.
"""
import argparse
import json
import math
import os
import zlib

W, H = 1080, 1920
R = 214
MARGIN = 30
XMIN, XMAX = R + MARGIN, W - R - MARGIN
YMIN, YMAX = R + MARGIN + 40, H - R - MARGIN - 40
N_SHAPES = 8


def imul(a, b):
    return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF


def to_u32(x):
    return x & 0xFFFFFFFF


class Rng:
    """mulberry32 — identical sequence in Python and JS."""

    def __init__(self, seed):
        self.a = seed & 0xFFFFFFFF

    def next(self):
        self.a = to_u32(self.a + 0x6D2B79F5)
        t = imul(self.a ^ (self.a >> 15), 1 | self.a)
        t = to_u32(t + imul(t ^ (t >> 7), 61 | t))
        return to_u32(t ^ (t >> 14)) / 4294967296.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    args = ap.parse_args()

    with open(os.path.join(args.project, "project.json"), encoding="utf-8") as f:
        meta = json.load(f)
    dur = float(meta["duration"])
    seed = zlib.crc32(("%s|%s" % (meta.get("artist", ""), meta.get("title", ""))).encode())

    am_path = os.path.join(args.project, "audiomap.json")
    phases = []
    if os.path.isfile(am_path):
        with open(am_path, encoding="utf-8") as f:
            am = json.load(f)
        phases = [(p["start"], p["end"], float(p["energy"])) for p in am["energy_phases"]]

    def energy_at(t):
        for i, (a, b, e) in enumerate(phases):
            if a <= t < b:
                nxt = phases[i + 1][2] if i + 1 < len(phases) else e
                u = (t - a) / max(0.001, b - a)
                return e + (nxt - e) * min(1.0, u)
        return 0.3

    def speed_at(t):
        # px/s — the drift breathes with the music, never snaps
        return 50.0 + 34.0 * energy_at(t)

    def time_to_wall(x, y, ang):
        vx, vy = math.cos(ang), math.sin(ang)
        tx = (XMAX - x) / vx if vx > 0 else ((XMIN - x) / vx if vx < 0 else math.inf)
        ty = (YMAX - y) / vy if vy > 0 else ((YMIN - y) / vy if vy < 0 else math.inf)
        return min(tx, ty), ("x" if tx < ty else "y")

    rng = Rng(seed)
    legs, bounces = [], []
    t = 0.0
    x = XMIN + (XMAX - XMIN) * (0.25 + 0.5 * rng.next())
    y = YMIN + (YMAX - YMIN) * (0.30 + 0.30 * rng.next())
    ang = -0.62 + (rng.next() - 0.5) * 0.9
    cur = 0
    history = [-1, -1, -1]

    while t < dur:
        best_ang, best_t = ang, -1.0
        for k in range(24):
            cand = ang if k == 0 else ang + (rng.next() - 0.5) * 1.5
            tw, _ = time_to_wall(x, y, cand)
            secs = tw / speed_at(t)
            if secs > best_t:
                best_t, best_ang = secs, cand
            if secs >= 4.6 and k > 0:
                best_ang, best_t = cand, secs
                break
        ang = best_ang
        dist, axis = time_to_wall(x, y, ang)
        end = min(t + dist / speed_at(t), dur)
        ex = min(XMAX, max(XMIN, x + math.cos(ang) * dist))
        ey = min(YMAX, max(YMIN, y + math.sin(ang) * dist))

        legs.append({"t0": round(t, 3), "t1": round(end, 3),
                     "x0": round(x, 2), "y0": round(y, 2),
                     "x1": round(ex, 2), "y1": round(ey, 2)})
        if end >= dur:
            break

        nx = (1 if math.cos(ang) > 0 else -1) if axis == "x" else 0
        ny = (1 if math.sin(ang) > 0 else -1) if axis == "y" else 0

        nxt = cur
        for _ in range(20):
            c = int(rng.next() * N_SHAPES)
            if c not in history and c != cur:
                nxt = c
                break
        if nxt == cur:
            nxt = (cur + 1 + int(rng.next() * (N_SHAPES - 1))) % N_SHAPES

        bounces.append({"t": round(end, 3), "nx": nx, "ny": ny, "from": cur, "to": nxt,
                        "m0": round(end + 0.06, 3), "m1": round(end + 0.94, 3)})

        history = [cur] + history[:2]
        cur = nxt

        vx, vy = math.cos(ang), math.sin(ang)
        if nx != 0:
            vx = -vx
        else:
            vy = -vy
        base = math.atan2(vy, vx)
        ang = base + (rng.next() - 0.5) * 0.26
        if nx != 0 and math.cos(ang) * nx < 0.18:
            ang = base
        if ny != 0 and math.sin(ang) * ny < 0.18:
            ang = base

        x, y = ex, ey
        t = end

    data = {"canvas": [W, H], "radius": R, "legs": legs, "bounces": bounces}
    with open(os.path.join(args.project, "motion.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)

    short = [l for l in legs if l["t1"] - l["t0"] < 2.6]
    print("seed %d  legs %d  bounces %d  last %.2fs  short legs %d"
          % (seed, len(legs), len(bounces), legs[-1]["t1"], len(short)))


if __name__ == "__main__":
    main()
