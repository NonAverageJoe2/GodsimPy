#!/usr/bin/env python3
from __future__ import annotations

"""Simple text-based world simulation CLI.

This utility can generate or load a world, step the simulation a chosen
number of turns and optionally enter a tiny REPL for further control.
"""

import argparse
import os
import sys
from typing import Iterable

import numpy as np

# Ensure repository root is importable even if PYTHONPATH includes the
# ``worldgen`` directory before ``.``. This avoids accidentally importing the
# ``worldgen/worldgen.py`` module as the ``worldgen`` package.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from worldgen import build_world, OCEAN, MOUNTAIN
from sim.state import WorldState, from_worldgen, save_npz, load_npz
from sim.loop import advance_turn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def initialize_civs(ws: WorldState, count: int, seed: int) -> None:
    """Place ``count`` civilizations on random non-ocean tiles."""

    land = np.argwhere((ws.biome_map != OCEAN) & (ws.biome_map != MOUNTAIN))
    if land.size == 0:
        return
    rng = np.random.default_rng(seed)
    rng.shuffle(land)
    count = int(max(0, min(count, len(land))))
    for civ_id in range(count):
        y, x = map(int, land[civ_id])
        ws.owner_map[y, x] = civ_id
        ws.pop_map[y, x] = np.float32(100.0)


def summary(ws: WorldState) -> str:
    m, d, y = ws.get_date_tuple()
    pop = float(ws.pop_map.sum())
    owned = int((ws.owner_map >= 0).sum())
    return f"turn={ws.turn} date={m}/{d}/{y} pop={pop:.1f} owned={owned}"


def run_repl(ws: WorldState, default_out: str) -> None:
    """Interactive command loop."""

    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            print()
            break
        if not line:
            continue
        parts = line.split()
        cmd = parts[0].lower()

        if cmd in {"quit", "exit"}:
            break

        if cmd == "scale":
            if len(parts) == 2 and parts[1] in {"week", "month", "year"}:
                ws.time_scale = parts[1]
                print(f"time_scale={ws.time_scale}")
            else:
                print("usage: scale week|month|year")
            continue

        if cmd == "step":
            if len(parts) != 2:
                print("usage: step N")
                continue
            try:
                n = int(parts[1])
            except ValueError:
                print("invalid step count")
                continue
            advance_turn(ws, steps=n)
            print(summary(ws))
            continue

        if cmd == "pause":
            ws.paused = True
            print("paused")
            continue

        if cmd == "resume":
            ws.paused = False
            print("resumed")
            continue

        if cmd == "date":
            m, d, y = ws.get_date_tuple()
            print(f"{m}/{d}/{y} (scale={ws.time_scale}, paused={ws.paused})")
            continue

        if cmd == "save":
            path = parts[1] if len(parts) > 1 else default_out
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            save_npz(ws, path)
            print(f"saved {path} | {summary(ws)}")
            continue

        print("commands: scale step pause resume date save quit")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run or simulate worlds")
    p.add_argument("--world", type=str, help="Load world from NPZ")
    p.add_argument(
        "--generate",
        nargs=2,
        type=int,
        metavar=("W", "H"),
        help="Generate new world of size WxH",
    )
    p.add_argument("--seed", type=int, help="RNG seed for generation")
    p.add_argument("--civs", type=int, default=3, help="Civilizations to init")
    p.add_argument("--steps", type=int, default=0, help="Steps to run on start")
    p.add_argument(
        "--time-scale",
        choices=["week", "month", "year"],
        help="Override time scale",
    )
    p.add_argument("--out", type=str, default="out/world.npz", help="NPZ save path")
    p.add_argument("--interactive", action="store_true", help="Enter REPL")
    return p.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)

    if args.generate:
        if args.seed is None:
            print("--seed is required when generating", file=sys.stderr)
            return 2
        w, h = args.generate
        height, biomes, sea, _ = build_world(
            w, h, args.seed, 12, 12.0, use_advanced_biomes=True
        )
        ws = from_worldgen(height, biomes, sea, w, h, 12.0, args.seed)
        initialize_civs(ws, args.civs, args.seed)
    else:
        if not args.world:
            print("--world path required", file=sys.stderr)
            return 2
        ws = load_npz(args.world)

    if args.time_scale:
        ws.time_scale = args.time_scale

    if args.steps > 0:
        advance_turn(ws, steps=args.steps)
        print(summary(ws))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    save_npz(ws, args.out)
    print(f"saved {args.out} | {summary(ws)}")

    if args.interactive:
        run_repl(ws, args.out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
