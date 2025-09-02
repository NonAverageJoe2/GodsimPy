from __future__ import annotations
from typing import List, Tuple, Dict, Optional
import heapq
from hexgrid import distance

Coord = Tuple[int, int]


def terrain_cost(world, q: int, r: int) -> int:
    t = world.get_tile(q, r)
    if t.biome == "ocean":
        return 50
    if t.biome == "mountain":
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
