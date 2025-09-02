# main.py - CLI to generate PNGs + NPZ data; renders top-down and isometric
from __future__ import annotations
import argparse, os, numpy as np
from biomes import build_biomes
from engine import SimulationEngine
from render import render_topdown, render_isometric
from worldgen import build_world

def run(args):
    w, h = args.width, args.height
    height, plate_map, sea, _ = build_world(
        w, h, args.seed, args.plates, args.hex_radius, args.sea_level, args.mountain_h
    )
    biomes = build_biomes(height, sea, args.mountain_h)

    eng = SimulationEngine(width=w, height=h, seed=args.seed, hex_size=int(args.hex_radius))
    idx = 0
    for r in range(h):
        for q in range(w):
            t = eng.world.tiles[idx]
            t.height = float(height[r, q])
            t.biome = str(biomes[r, q])
            idx += 1

    os.makedirs(args.out, exist_ok=True)
    np.savez_compressed(
        os.path.join(args.out, "world_data.npz"),
        height=height,
        biome=biomes,
        plate_map=plate_map,
        sea_level=np.array([sea], dtype=np.float32),
        width=np.array([w], dtype=np.int32),
        height_cells=np.array([h], dtype=np.int32),
    )

    render_topdown(eng.world, os.path.join(args.out, "topdown.png"))
    render_isometric(
        eng.world,
        os.path.join(args.out, "iso_corner.png"),
        height_pixels=args.height_pixels,
        yaw_deg=args.yaw,
        tilt_deg=args.tilt,
        supersample=args.ss,
    )

    print("Saved:", os.path.join(args.out, "world_data.npz"))
    print("Saved:", os.path.join(args.out, "topdown.png"))
    print("Saved:", os.path.join(args.out, "iso_corner.png"))
    print(f"Sea level ~ {sea:.3f}")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Hex worldgen (Python-only)")
    p.add_argument("--width", type=int, default=128)
    p.add_argument("--height", type=int, default=96)
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--plates", type=int, default=12)
    p.add_argument("--hex-radius", type=float, default=12.0)
    p.add_argument("--sea-level", type=float, default=0.50)
    p.add_argument("--mountain-h", type=float, default=0.80)
    p.add_argument("--height-pixels", type=float, default=36.0)
    p.add_argument("--yaw", type=float, default=45.0)
    p.add_argument("--tilt", type=float, default=35.264)
    p.add_argument("--ss", type=int, default=1, help="supersample factor (1/2/3)")
    p.add_argument("--out", type=str, default="out")
    run(p.parse_args())
