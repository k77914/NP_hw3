#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import threading
import json
import argparse
from typing import Dict, Any, Optional, Tuple

MOVES = {"rock", "paper", "scissors"}
WIN_TABLE = {
    ("rock", "scissors"): 1,
    ("scissors", "paper"): 1,
    ("paper", "rock"): 1,
}

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

def judge(a: str, b: str) -> int:
    if a == b:
        return 0
    return 1 if (a, b) in WIN_TABLE else -1

class GameRoom:
    def __init__(self, p1: socket.socket, p2: socket.socket):
        self.p1 = p1
        self.p2 = p2
        self.lock = threading.Lock()
        self.moves: Dict[int, Optional[str]] = {1: None, 2: None}
        self.play_again: Dict[int, Optional[bool]] = {1: None, 2: None}

    def close(self):
        for c in (self.p1, self.p2):
            try:
                c.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                c.close()
            except Exception:
                pass

    def reset_round(self):
        with self.lock:
            self.moves = {1: None, 2: None}
            self.play_again = {1: None, 2: None}

    def set_move(self, player_id: int, move: str) -> None:
        with self.lock:
            self.moves[player_id] = move

    def set_play_again(self, player_id: int, again: bool) -> None:
        with self.lock:
            self.play_again[player_id] = again

    def get_state(self) -> Tuple[Optional[str], Optional[str], Optional[bool], Optional[bool]]:
        with self.lock:
            return self.moves[1], self.moves[2], self.play_again[1], self.play_again[2]

def player_thread(room: GameRoom, conn: socket.socket, player_id: int):
    try:
        send_json(conn, {"type": "welcome", "player_id": player_id, "msg": "Connected. Waiting for game start..."})
        while True:
            msg = recv_json(conn)
            if msg is None:
                break

            mtype = msg.get("type")
            if mtype == "move":
                move = str(msg.get("move", "")).lower().strip()
                if move not in MOVES:
                    send_json(conn, {"type": "error", "msg": f"Invalid move: {move}. Use rock/paper/scissors."})
                    continue
                room.set_move(player_id, move)
                send_json(conn, {"type": "ack", "msg": f"Move received: {move}"})

            elif mtype == "play_again":
                again = bool(msg.get("again", False))
                room.set_play_again(player_id, again)
                send_json(conn, {"type": "ack", "msg": f"Play again = {again}"})

            elif mtype == "quit":
                break
            else:
                send_json(conn, {"type": "error", "msg": f"Unknown message type: {mtype}"})
    except Exception:
        pass

def run_room(room: GameRoom):
    p1, p2 = room.p1, room.p2
    try:
        send_json(p1, {"type": "start", "msg": "Game started! Send your move: rock/paper/scissors"})
        send_json(p2, {"type": "start", "msg": "Game started! Send your move: rock/paper/scissors"})

        round_no = 1
        while True:
            while True:
                m1, m2, a1, a2 = room.get_state()
                if m1 is not None and m2 is not None:
                    break
                threading.Event().wait(0.05)

            m1, m2, _, _ = room.get_state()
            res = judge(m1, m2)

            if res == 0:
                r1, r2 = "draw", "draw"
            elif res == 1:
                r1, r2 = "win", "lose"
            else:
                r1, r2 = "lose", "win"

            send_json(p1, {"type": "result", "round": round_no, "you": m1, "opponent": m2, "outcome": r1})
            send_json(p2, {"type": "result", "round": round_no, "you": m2, "opponent": m1, "outcome": r2})

            send_json(p1, {"type": "ask_play_again", "msg": "Play again? (yes/no)"})
            send_json(p2, {"type": "ask_play_again", "msg": "Play again? (yes/no)"})

            while True:
                _m1, _m2, a1, a2 = room.get_state()
                if a1 is not None and a2 is not None:
                    break
                threading.Event().wait(0.05)

            _, _, a1, a2 = room.get_state()
            if a1 and a2:
                room.reset_round()
                round_no += 1
                send_json(p1, {"type": "info", "msg": "New round!"})
                send_json(p2, {"type": "info", "msg": "New round!"})
            else:
                send_json(p1, {"type": "end", "msg": "Game over."})
                send_json(p2, {"type": "end", "msg": "Game over."})
                break
    finally:
        room.close()

def parse_args():
    ap = argparse.ArgumentParser(description="Rock-Paper-Scissors Game Server")
    ap.add_argument("--host", default="0.0.0.0", help="Bind host/IP (default: 0.0.0.0)")
    ap.add_argument("--port", type=int, default=5050, help="Bind port (use 0 for auto-assign)")
    ap.add_argument("--backlog", type=int, default=5, help="Listen backlog")
    return ap.parse_args()

def main():
    args = parse_args()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((args.host, args.port))

        # 若 port=0，OS 會分配；用 getsockname() 拿到真實 port
        bind_host, bind_port = s.getsockname()
        print(f"[server] Listening on {bind_host}:{bind_port}")

        s.listen(args.backlog)

        print("[server] Waiting for Player 1...")
        p1, addr1 = s.accept()
        print(f"[server] Player 1 connected from {addr1}")

        print("[server] Waiting for Player 2...")
        p2, addr2 = s.accept()
        print(f"[server] Player 2 connected from {addr2}")

        room = GameRoom(p1, p2)
        threading.Thread(target=player_thread, args=(room, p1, 1), daemon=True).start()
        threading.Thread(target=player_thread, args=(room, p2, 2), daemon=True).start()

        run_room(room)
        print("[server] Room finished. Bye.")

if __name__ == "__main__":
    main()
