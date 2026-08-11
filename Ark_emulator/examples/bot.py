"""Route-aware auto-deploy bot (reference for AI map analysis).

Strategy:
  - read snapshot.routes (enemy paths) + map tiles;
  - deploy melee blockers on route cells near the blue box (exit);
  - deploy ranged operators next to the route so they cover blockers;
  - auto-cast skills when SP is ready; retreat low-hp operators.

Usage::
    python examples/bot.py --level level_main_01-01 --squad examples/squad_demo.json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ark_emulator import Simulator


def route_cells(routes, battle=None):
    """Collect passable cells covered by routes, expanding between
    consecutive waypoints with BFS (start/end/checkpoints)."""
    cells = set()
    for rt in routes or []:
        pts = []
        if rt.get("startPosition"):
            pts.append(rt["startPosition"])
        for cp in rt.get("checkpoints") or []:
            if cp.get("position"):
                pts.append(cp["position"])
        if rt.get("endPosition"):
            pts.append(rt["endPosition"])
        for p in pts:
            cells.add((p.get("row"), p.get("col")))
        # expand gaps between consecutive waypoints
        for a, b in zip(pts, pts[1:]):
            for cell in _bfs_path(battle, (a.get("row"), a.get("col")),
                                  (b.get("row"), b.get("col"))):
                cells.add(cell)
    return cells


def _bfs_path(battle, start, end):
    """Shortest passable path between two cells (empty = direct line)."""
    if battle is None or start == end:
        return []
    rows, cols = battle.map.rows, battle.map.cols
    from collections import deque
    q = deque([start])
    prev = {start: None}
    while q:
        r, c = q.popleft()
        if (r, c) == end:
            break
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            rr, cc = r + dr, c + dc
            if not (0 <= rr < rows and 0 <= cc < cols):
                continue
            t = battle.map.tile(rr, cc)
            if t is not None and not t.passable(0):
                continue
            if (rr, cc) in prev:
                continue
            prev[(rr, cc)] = (r, c)
            q.append((rr, cc))
    if end not in prev:
        return []
    out = []
    cur = end
    while cur is not None:
        out.append(cur)
        cur = prev[cur]
    return out


class Bot:
    def __init__(self, sim, squad):
        self.sim = sim
        self.squad = squad or []
        self.deployed = set()
        self.retreated = set()

    def tick(self):
        b = self.sim.battle
        snap = self.sim.snapshot()
        # 1. deploy new operators
        routes = snap.get("routes") or []
        cells = route_cells(routes, b)
        if not cells:
            cells = {(3, c) for c in range(4, 7)}
        # order squad: melee first (vanguard/guard/defender), ranged last
        ordered = sorted(self.squad,
                         key=lambda m: 1 if self._is_ranged(m["charId"])
                         else 0)
        for mem in ordered:
            cid = mem["charId"]
            if cid in self.deployed:
                continue
            data = b._char_base(cid)
            attrs = b._squad_attrs(cid, data)
            if b.cost < attrs.get("cost", 10):
                continue
            ranged = self._is_ranged(cid)
            if self._is_medic(cid):
                pos = self._pick_healer_cell(b)
            else:
                pos = self._pick_cell(cells, ranged, b)
            if pos is None:
                continue
            if ranged:
                direction = self._best_direction(b, cid, pos[0], pos[1],
                                                 cells)
            else:
                direction = 1
            ok, _ = b.deploy(cid, pos[0], pos[1], direction=direction)
            if ok:
                self.deployed.add(cid)
        # 2. auto-cast skills
        for op in list(b.operators):
            sc = getattr(op, "skill_controller", None)
            if sc and sc.active is None:
                for si, sk in enumerate(sc.skills):
                    if not sk.on_cooldown and op.sp >= sk.sp_cost:
                        sc.activate(si)
                        break
        # 3. retreat low-hp operators (melee only)
        for op in list(b.operators):
            if op.hp / op.max_hp < 0.3 and op.char_id not in self.retreated \
                    and op.char_id in self.deployed:
                ok, _ = b.withdraw(op.inst_id)
                if ok:
                    self.retreated.add(op.char_id)
                    self.deployed.discard(op.char_id)

    def _best_direction(self, b, cid, row, col, route_cells):
        """Facing that makes the operator's range cover the most route
        cells (range-gated targeting needs actual coverage)."""
        data = b._char_base(cid)
        if not data:
            return 1
        phases = data.get("phases") or []
        range_id = None
        for ph in phases:
            rid = ph.get("rangeId")
            if rid:
                range_id = rid
                break
        if not range_id:
            return 1
        try:
            from ark_emulator.battle import range_offsets_rotated
            best_dir, best_cnt = 1, -1
            for d in range(4):
                shape = range_offsets_rotated(range_id, d)
                cnt = sum(1 for (dr, dc) in shape
                          if (row + dr, col + dc) in route_cells)
                if cnt > best_cnt:
                    best_cnt, best_dir = cnt, d
            return best_dir
        except Exception:
            return 1

    def _is_ranged(self, cid):
        data = self.sim.battle._char_base(cid)
        if not data:
            return False
        return int(data.get("position") or 0) == 2   # 1=melee 2=ranged

    def _is_medic(self, cid):
        data = self.sim.battle._char_base(cid)
        if not data:
            return False
        return int(data.get("profession") or 0) == 8  # MEDIC

    def _pick_healer_cell(self, b):
        """Behind the blocker: an adjacent buildable cell off the route."""
        routes = self.sim.snapshot().get("routes") or []
        cells = route_cells(routes, b)
        if not cells:
            return None
        for p in cells:
            r, c = p
            for dr, dc in ((0, 1), (1, 0), (-1, 0), (0, -1)):
                rr, cc = r + dr, c + dc
                if self._buildable(b, rr, cc, ranged=False):
                    return (rr, cc)
        return None

    def _pick_cell(self, cells, ranged, b):
        """Blocker: route cell near the exit (endPosition). Ranged:
        adjacent to a route cell."""
        if not ranged:
            # blockers near the exit: route cells closest to any endPosition
            exits = []
            for rt in self.sim.snapshot().get("routes") or []:
                ep = rt.get("endPosition")
                if ep:
                    exits.append((ep.get("row"), ep.get("col")))
            def _exit_dist(p):
                if not exits:
                    return 0
                return min((p[0]-e[0])**2 + (p[1]-e[1])**2 for e in exits)
            end_cells = sorted(cells, key=_exit_dist)
            # but prefer cells with buildable ground nearby; fall back to
            # any buildable cell if the exit ring is walled off
            for p in end_cells:
                r, c = p
                for dr, dc in ((0, 0), (0, 1), (0, -1), (1, 0), (-1, 0)):
                    rr, cc = r + dr, c + dc
                    if self._buildable(b, rr, cc, ranged=False):
                        return (rr, cc)
            for r in range(b.map.rows):
                for c in range(b.map.cols):
                    if self._buildable(b, r, c, ranged=False):
                        return (r, c)
        else:
            for p in cells:
                r, c = p
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        rr, cc = r + dr, c + dc
                        if self._buildable(b, rr, cc, ranged=True):
                            return (rr, cc)
        return None

    @staticmethod
    def _buildable(b, r, c, ranged=False):
        """Melee needs buildableType&1 (ground), ranged needs &2 (highland)."""
        t = b.map.tile(r, c)
        if t is None or not t.buildable_type:
            return False
        mask = 2 if ranged else 1
        if not (int(t.buildable_type or 0) & mask):
            return False
        if any(o.row == r and o.col == c for o in b.operators):
            return False
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="level_main_01-01")
    ap.add_argument("--squad", default=None)
    ap.add_argument("--seconds", type=float, default=120.0)
    args = ap.parse_args()
    squad = []
    if args.squad:
        with open(args.squad, encoding="utf-8") as f:
            squad = json.load(f)
    if not squad:
        squad = [
            {"charId": "char_149_scave", "level": 50, "phase": 2},
            {"charId": "char_002_amiya", "level": 50, "phase": 2},
            {"charId": "char_102_texas", "level": 50, "phase": 2},
            {"charId": "char_172_svrash", "level": 50, "phase": 2},
        ]
    sim = Simulator(level_id=args.level, squad=squad)
    bot = Bot(sim, squad)
    ticks = int(args.seconds * 30)
    for _ in range(ticks):
        if sim.battle.finished:
            break
        bot.tick()
        sim.battle.tick_once()
    snap = sim.snapshot()
    print(f"{args.level}: result={snap['result']} t={snap['t']:.1f}s "
          f"life={snap['lifePoint']} deployed={len(sim.battle.operators)} "
          f"kills={len([e for e in snap['events'] if e['type']=='enemy_dead'])}")


if __name__ == "__main__":
    main()
