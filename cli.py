import argparse
import shlex

from engine import SimulationEngine
import render
import numpy as np
from time_model import DAYS_PER_MONTH


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))

def cmd_new(args):
    eng = SimulationEngine(width=args.width, height=args.height, seed=args.seed,
                           hex_size=args.hex_size)
    eng.init_worldgen(sea_percentile=args.sea_percentile,
                      mountain_thresh=args.mountain_thresh)
    eng.seed_population_everywhere(min_pop=args.min_pop, max_pop=args.max_pop)
    if args.civ:
        for spec in args.civ:
            name, rest = spec.split(":")
            x, y = map(int, rest.split(","))
            eng.add_civ(name=name, at=(x, y))
    eng.save_json(args.out)
    print(f"World created and saved to {args.out}")

def cmd_step(args):
    eng = SimulationEngine()
    eng.load_json(args.world)
    for _ in range(args.weeks):
        eng.advance_turn()
    if args.save:
        eng.save_json(args.save)
        print(f"Saved to {args.save}")
    print(eng.summary())

def cmd_summary(args):
    eng = SimulationEngine()
    eng.load_json(args.world)
    print(eng.summary())

def cmd_autoplay(args):
    eng = SimulationEngine()
    eng.load_json(args.world)
    for _ in range(args.weeks):
        eng.advance_turn()
    if args.save:
        eng.save_json(args.save)
        print(f"Saved to {args.save}")
    print("Auto-play complete.", eng.summary())


def cmd_export(args):
    eng = SimulationEngine()
    eng.load_json(args.world)
    if args.topdown or args.isometric:
        w = eng.world
        H, W = w.height_hex, w.width_hex
        height = np.zeros((H, W), dtype=np.float32)
        biome = np.zeros((H, W), dtype=np.int32)
        for t in w.tiles:
            height[t.r, t.q] = float(t.height)
            try:
                biome[t.r, t.q] = int(t.biome)
            except Exception:
                biome[t.r, t.q] = 0
    if args.topdown:
        img = render.render_topdown(biome, w.hex_size)
        img.save(args.topdown)
        print(f"Saved {args.topdown}")
    if args.isometric:
        img = render.render_iso(height, biome, w.hex_size, sea_level=w.sea_level)
        img.save(args.isometric)
        print(f"Saved {args.isometric}")


def cmd_set_timescale(args):
    eng = SimulationEngine()
    eng.load_json(args.world)
    eng.world.time_scale = args.scale
    eng.save_json(args.world)
    print(f"Time scale set to {args.scale} in {args.world}")


def cmd_set_date(args):
    eng = SimulationEngine()
    eng.load_json(args.world)
    year = max(0, args.year)
    month = clamp(args.month, 1, 12)
    day = clamp(args.day, 1, DAYS_PER_MONTH[month - 1])
    w = eng.world.calendar
    w.year, w.month, w.day = year, month, day
    eng.save_json(args.world)
    print(f"Date set to {year}-{month}-{day} in {args.world}")


def cmd_repl(args):
    eng = SimulationEngine()
    eng.load_json(args.world)
    print("Enter commands: step N | spawn_army CIV Q R [--strength S] |"
          " target ARMY Q R | summary | exit")
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            break
        if not line:
            continue
        parts = shlex.split(line)
        cmd = parts[0]
        if cmd == "step" and len(parts) >= 2:
            n = int(parts[1])
            for _ in range(n):
                eng.advance_turn()
            eng.save_json(args.world)
            print(f"Advanced {n} steps")
        elif cmd == "spawn_army" and len(parts) >= 4:
            civ, q, r = map(int, parts[1:4])
            strength = 10
            if len(parts) >= 6 and parts[4] == "--strength":
                strength = int(parts[5])
            eng.add_army(civ, (q, r), strength=strength)
            eng.save_json(args.world)
            print("Army spawned")
        elif cmd == "target" and len(parts) >= 4:
            idx, q, r = map(int, parts[1:4])
            try:
                army = eng.world.armies[idx]
            except IndexError:
                print("No such army")
                continue
            eng.set_army_target(army, (q, r))
            eng.save_json(args.world)
            print("Target set")
        elif cmd == "summary":
            print(eng.summary())
        elif cmd in {"exit", "quit"}:
            break
        else:
            print("Unknown command")

def main():
    ap = argparse.ArgumentParser(description="Headless CLI for simulation")
    sub = ap.add_subparsers()

    ap_new = sub.add_parser("new", help="Create a new world")
    ap_new.add_argument("--width", type=int, default=48)
    ap_new.add_argument("--height", type=int, default=32)
    ap_new.add_argument("--seed", type=int, default=12345)
    ap_new.add_argument("--min-pop", type=int, default=3)
    ap_new.add_argument("--max-pop", type=int, default=30)
    ap_new.add_argument("--hex-size", type=int, default=1, help="Hex size in px")
    ap_new.add_argument("--sea-percentile", type=float, default=0.35,
                        help="Percentile of tiles considered sea")
    ap_new.add_argument("--mountain-thresh", type=float, default=0.8,
                        help="Height threshold for mountains")
    ap_new.add_argument("--civ", action="append", help="e.g. 'Rome:10,10' (can repeat)")
    ap_new.add_argument("--out", default="world.json")
    ap_new.set_defaults(func=cmd_new)

    ap_step = sub.add_parser("step", help="Advance turns and print summary")
    ap_step.add_argument("world")
    ap_step.add_argument("--weeks", type=int, default=1)
    ap_step.add_argument("--save", default=None)
    ap_step.set_defaults(func=cmd_step)

    ap_sum = sub.add_parser("summary", help="Print summary")
    ap_sum.add_argument("world")
    ap_sum.set_defaults(func=cmd_summary)

    ap_auto = sub.add_parser("autoplay", help="Run a bot for N turns")
    ap_auto.add_argument("world")
    ap_auto.add_argument("--weeks", type=int, default=52)
    ap_auto.add_argument("--save", default=None)
    ap_auto.set_defaults(func=cmd_autoplay)

    ap_exp = sub.add_parser("export", help="Render world to PNG images")
    ap_exp.add_argument("--world", required=True, help="World JSON file")
    ap_exp.add_argument("--topdown", required=True, help="Topdown PNG path")
    ap_exp.add_argument("--isometric", default=None, help="Isometric PNG path")
    ap_exp.set_defaults(func=cmd_export)

    ap_ts = sub.add_parser("set-timescale", help="Set simulation time scale")
    ap_ts.add_argument("world")
    ap_ts.add_argument("scale", choices=["week", "month", "year"])
    ap_ts.set_defaults(func=cmd_set_timescale)

    ap_date = sub.add_parser("set-date", help="Set calendar date")
    ap_date.add_argument("world")
    ap_date.add_argument("--year", type=int, required=True)
    ap_date.add_argument("--month", type=int, required=True)
    ap_date.add_argument("--day", type=int, required=True)
    ap_date.set_defaults(func=cmd_set_date)

    ap_repl = sub.add_parser("repl", help="Interactive REPL")
    ap_repl.add_argument("world")
    ap_repl.set_defaults(func=cmd_repl)

    args = ap.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        ap.print_help()

if __name__ == "__main__":
    main()
