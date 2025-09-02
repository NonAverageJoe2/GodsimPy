import argparse

from engine import SimulationEngine
import render

def cmd_new(args):
    eng = SimulationEngine(width=args.width, height=args.height, seed=args.seed)
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
    if args.topdown:
        render.render_topdown(eng.world, args.topdown)
        print(f"Saved {args.topdown}")
    if args.isometric:
        render.render_isometric(eng.world, args.isometric)
        print(f"Saved {args.isometric}")

def main():
    ap = argparse.ArgumentParser(description="Headless CLI for simulation")
    sub = ap.add_subparsers()

    ap_new = sub.add_parser("new", help="Create a new world")
    ap_new.add_argument("--width", type=int, default=48)
    ap_new.add_argument("--height", type=int, default=32)
    ap_new.add_argument("--seed", type=int, default=12345)
    ap_new.add_argument("--min-pop", type=int, default=3)
    ap_new.add_argument("--max-pop", type=int, default=30)
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
    ap_exp.add_argument("world", nargs="?", default="world.json")
    ap_exp.add_argument("--topdown", dest="topdown", default=None)
    ap_exp.add_argument("--isometric", dest="isometric", default=None)
    ap_exp.set_defaults(func=cmd_export)

    args = ap.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        ap.print_help()

if __name__ == "__main__":
    main()
