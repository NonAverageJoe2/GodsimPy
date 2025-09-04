import heapq
from typing import Dict, List, Tuple

from worldgen.biomes import Biome
from worldgen.hexgrid import distance

Coord = Tuple[int, int]


def _biome_name(tile) -> str:
    """Return biome name as lowercase string for tiles that may store
    either the Biome enum or raw strings."""
    b = tile.biome
    if isinstance(b, Biome):
        return b.name.lower()
    return str(b).lower()


def terrain_cost(world, q: int, r: int) -> int:
    t = world.get_tile(q, r)
    biome = _biome_name(t)
    if biome == "ocean":
        return 50
    if biome == "mountain":
        return 5
    return 1


def reconstruct(came_from: Dict[Coord, Coord], current: Coord) -> List[Coord]:
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def astar(world, start: Coord, goal: Coord) -> List[Coord]:
    if start == goal:
        return []
    open_heap: List[Tuple[float, Coord]] = []
    heapq.heappush(open_heap, (0.0, start))
    came_from: Dict[Coord, Coord] = {}
    g_score: Dict[Coord, float] = {start: 0.0}
    closed: set[Coord] = set()
    while open_heap:
        _, current = heapq.heappop(open_heap)
        if current == goal:
            full_path = reconstruct(came_from, current)
            return full_path[1:]
        if current in closed:
            continue
        closed.add(current)
        for neighbor in world.neighbors6(*current):
            tentative = g_score[current] + terrain_cost(world, *neighbor)
            if tentative < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative
                f = tentative + distance(neighbor[0], neighbor[1], goal[0], goal[1])
                heapq.heappush(open_heap, (f, neighbor))
    return []
