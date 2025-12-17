import socket
import threading
import json
import argparse
import random
import time
from typing import Dict, Any, Optional, Tuple, List

# ---------- JSON helpers (same style as your templates) ----------
def send_json(conn: socket.socket, obj: Dict[str, Any]) -> None:
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
    conn.sendall(data)

def recv_json(conn: socket.socket) -> Optional[Dict[str, Any]]:
    buf = b""
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            return None
        buf += chunk
        if b"\n" in buf:
            line, _rest = buf.split(b"\n", 1)
            try:
                return json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                return None


# ---------- Game logic ----------
DIRS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}

def add(p: Tuple[int, int], d: Tuple[int, int]) -> Tuple[int, int]:
    return (p[0] + d[0], p[1] + d[1])

class GameRoom:
    def __init__(self, p1: socket.socket, p2: socket.socket, w: int, h: int, tick_hz: int):
        self.p1 = p1
        self.p2 = p2
        self.w = w
        self.h = h
        self.tick_hz = tick_hz

        self.lock = threading.Lock()
        self.running = True

        # snake bodies: head at index 0
        self.snakes: Dict[int, List[Tuple[int, int]]] = {
            1: [(w // 4, h // 2), (w // 4 - 1, h // 2), (w // 4 - 2, h // 2)],
            2: [(w * 3 // 4, h // 2), (w * 3 // 4 + 1, h // 2), (w * 3 // 4 + 2, h // 2)],
        }
        self.dir_now: Dict[int, str] = {1: "right", 2: "left"}
        self.dir_want: Dict[int, str] = {1: "right", 2: "left"}

        self.alive: Dict[int, bool] = {1: True, 2: True}
        self.scores: Dict[int, int] = {1: 0, 2: 0}

        self.food: Tuple[int, int] = self._spawn_food()
        self.tick = 0

    def close(self):
        self.running = False
        for c in (self.p1, self.p2):
            try:
                c.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                c.close()
            except Exception:
                pass

    def _occupied(self) -> set:
        occ = set()
        for pid in (1, 2):
            for cell in self.snakes[pid]:
                occ.add(cell)
        return occ

    def _spawn_food(self) -> Tuple[int, int]:
        occ = self._occupied()
        empty = [(x, y) for x in range(self.w) for y in range(self.h) if (x, y) not in occ]
        return random.choice(empty) if empty else (0, 0)

    def set_dir(self, pid: int, d: str):
        if d not in DIRS:
            return
        with self.lock:
            # disallow instant reverse
            if OPPOSITE.get(d) == self.dir_now.get(pid):
                return
            self.dir_want[pid] = d

    def get_state_payload(self, extra_type: str = "state", **kw) -> Dict[str, Any]:
        with self.lock:
            payload = {
                "type": extra_type,
                "tick": self.tick,
                "w": self.w,
                "h": self.h,
                "food": [self.food[0], self.food[1]],
                "snakes": {
                    "1": [[x, y] for (x, y) in self.snakes[1]],
                    "2": [[x, y] for (x, y) in self.snakes[2]],
                },
                "scores": {"1": self.scores[1], "2": self.scores[2]},
                "alive": {"1": self.alive[1], "2": self.alive[2]},
            }
            payload.update(kw)
            return payload

    def step(self) -> Optional[Dict[str, Any]]:
        """Advance one tick. Return game_over payload if ended, else None."""
        with self.lock:
            self.tick += 1

            # commit wanted directions (with reverse already blocked)
            for pid in (1, 2):
                self.dir_now[pid] = self.dir_want[pid]

            # compute next heads
            next_head: Dict[int, Tuple[int, int]] = {}
            for pid in (1, 2):
                if not self.alive[pid]:
                    continue
                d = DIRS[self.dir_now[pid]]
                next_head[pid] = add(self.snakes[pid][0], d)

            # collision checks
            died = {1: False, 2: False}

            # walls
            for pid, nh in next_head.items():
                if nh[0] < 0 or nh[0] >= self.w or nh[1] < 0 or nh[1] >= self.h:
                    died[pid] = True

            # bodies (note: moving tail rule: if not eating, tail will pop)
            # We'll check against current bodies; allow moving into own tail only if tail is moving away (not eating).
            occ1 = set(self.snakes[1])
            occ2 = set(self.snakes[2])

            for pid, nh in next_head.items():
                if died[pid]:
                    continue

                other = 2 if pid == 1 else 1

                # will eat?
                will_eat = (nh == self.food)

                # own collision
                body = self.snakes[pid]
                own_occ = set(body)
                if not will_eat:
                    # tail will move away, so stepping into current tail is allowed
                    own_occ.discard(body[-1])
                if nh in own_occ:
                    died[pid] = True

                # other collision (other tail also may move away, but keep it simple: collide with any other cell)
                if nh in (occ2 if pid == 1 else occ1):
                    died[pid] = True

            # head-on swap / head-on same cell
            if 1 in next_head and 2 in next_head:
                if next_head[1] == next_head[2]:
                    died[1] = True
                    died[2] = True
                elif next_head[1] == self.snakes[2][0] and next_head[2] == self.snakes[1][0]:
                    died[1] = True
                    died[2] = True

            # apply moves
            for pid in (1, 2):
                if not self.alive[pid]:
                    continue
                if died[pid]:
                    self.alive[pid] = False
                    continue

                nh = next_head[pid]
                self.snakes[pid].insert(0, nh)

                if nh == self.food:
                    self.scores[pid] += 1
                    self.food = self._spawn_food()
                else:
                    self.snakes[pid].pop()

            # end condition: if either dead, game ends (winner = remaining alive else draw)
            if not self.alive[1] or not self.alive[2]:
                if self.alive[1] and not self.alive[2]:
                    winner = 1
                    reason = "player2_dead"
                elif self.alive[2] and not self.alive[1]:
                    winner = 2
                    reason = "player1_dead"
                else:
                    winner = 0
                    reason = "both_dead"

                return self.get_state_payload(
                    extra_type="game_over",
                    winner=winner,
                    reason=reason,
                    msg=("Draw!" if winner == 0 else f"Player {winner} wins!"),
                )

            return None


# ---------- Threads (same pattern as your templates) ----------
def player_thread(room: GameRoom, conn: socket.socket, player_id: int):
    try:
        send_json(conn, {"type": "welcome", "player_id": player_id, "msg": "Connected. Waiting for game start..."})
        while room.running:
            msg = recv_json(conn)
            if msg is None:
                break

            mtype = msg.get("type")
            if mtype == "dir":
                d = str(msg.get("dir", "")).lower().strip()
                room.set_dir(player_id, d)
            elif mtype == "quit":
                break
            else:
                send_json(conn, {"type": "error", "msg": f"Unknown message type: {mtype}"})
    except Exception:
        pass
    finally:
        # if a player disconnects, end game
        room.running = False


def run_room(room: GameRoom):
    p1, p2 = room.p1, room.p2
    try:
        send_json(p1, {"type": "start", "msg": "Game started! Use arrow keys / WASD."})
        send_json(p2, {"type": "start", "msg": "Game started! Use arrow keys / WASD."})

        dt = 1.0 / max(1, room.tick_hz)
        while room.running:
            t0 = time.time()
            over = room.step()

            # broadcast state
            state = room.get_state_payload(extra_type="state")
            try:
                send_json(p1, state)
                send_json(p2, state)
            except Exception:
                room.running = False
                break

            if over is not None:
                try:
                    send_json(p1, over)
                    send_json(p2, over)
                except Exception:
                    pass
                break

            # tick pacing
            spent = time.time() - t0
            if spent < dt:
                time.sleep(dt - spent)
    finally:
        room.close()


def parse_args():
    ap = argparse.ArgumentParser(description="Two-Player Snake GUI Game Server (JSON over TCP)")
    ap.add_argument("-m")  # keep compatible with `python -m ...` calls if you use that pattern
    ap.add_argument("--host", default="0.0.0.0", help="Bind host/IP (default: 0.0.0.0)")
    ap.add_argument("--port", type=int, default=5050, help="Bind port (use 0 for auto-assign)")
    ap.add_argument("--backlog", type=int, default=5, help="Listen backlog")
    ap.add_argument("--w", type=int, default=20, help="Grid width (cells)")
    ap.add_argument("--h", type=int, default=20, help="Grid height (cells)")
    ap.add_argument("--tick", type=int, default=10, help="Ticks per second")
    return ap.parse_args()


def main():
    args = parse_args()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((args.host, args.port))
        bind_host, bind_port = s.getsockname()
        print(f"[server] Listening on {bind_host}:{bind_port}")
        s.listen(args.backlog)

        print("[server] Waiting for Player 1...")
        p1, addr1 = s.accept()
        print(f"[server] Player 1 connected from {addr1}")

        print("[server] Waiting for Player 2...")
        p2, addr2 = s.accept()
        print(f"[server] Player 2 connected from {addr2}")

        room = GameRoom(p1, p2, w=args.w, h=args.h, tick_hz=args.tick)
        threading.Thread(target=player_thread, args=(room, p1, 1), daemon=True).start()
        threading.Thread(target=player_thread, args=(room, p2, 2), daemon=True).start()

        run_room(room)
        print("[server] Room finished. Bye.")


if __name__ == "__main__":
    main()
