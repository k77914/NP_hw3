import socket
import json
import argparse
import threading
import queue
from typing import Dict, Any, Optional, Tuple, List
import sys
import tkinter as tk
from tkinter import messagebox

# ---------- JSON helpers ----------
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


class SnakeGUIClient:
    def __init__(self, host: str, port: int, cell_px: int = 24):
        self.host = host
        self.port = port
        self.cell_px = cell_px

        self.sock: Optional[socket.socket] = None
        self.player_id: Optional[int] = None

        self.state_q: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self.running = True

        # last state
        self.grid_w = 20
        self.grid_h = 20
        self.food = (0, 0)
        self.snakes = {1: [], 2: []}  # type: ignore
        self.scores = {1: 0, 2: 0}
        self.alive = {1: True, 2: True}
        self.started = False
        self.game_over = False

        # Tk
        self.root = tk.Tk()
        self.root.title("Two-Player Snake (Client)")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        top = tk.Frame(self.root)
        top.pack(fill="x")

        self.info_var = tk.StringVar(value="Connecting...")
        self.score_var = tk.StringVar(value="Score P1: 0 | P2: 0")
        tk.Label(top, textvariable=self.info_var, anchor="w").pack(side="left", padx=8, pady=6)
        tk.Label(top, textvariable=self.score_var, anchor="e").pack(side="right", padx=8, pady=6)

        self.canvas = tk.Canvas(
            self.root,
            width=self.grid_w * self.cell_px,
            height=self.grid_h * self.cell_px,
            highlightthickness=0,
        )
        self.canvas.pack(padx=10, pady=10)

        # key binds (arrows + WASD)
        self.root.bind("<Up>", lambda e: self.send_dir("up"))
        self.root.bind("<Down>", lambda e: self.send_dir("down"))
        self.root.bind("<Left>", lambda e: self.send_dir("left"))
        self.root.bind("<Right>", lambda e: self.send_dir("right"))
        self.root.bind("w", lambda e: self.send_dir("up"))
        self.root.bind("s", lambda e: self.send_dir("down"))
        self.root.bind("a", lambda e: self.send_dir("left"))
        self.root.bind("d", lambda e: self.send_dir("right"))

    def connect(self):
        c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        c.connect((self.host, self.port))
        self.sock = c

        t = threading.Thread(target=self.net_loop, daemon=True)
        t.start()

        self.root.after(33, self.ui_loop)
        self.root.mainloop()

    def net_loop(self):
        assert self.sock is not None
        try:
            while self.running:
                msg = recv_json(self.sock)
                if msg is None:
                    self.state_q.put({"type": "disconnect"})
                    break
                self.state_q.put(msg)
        except Exception:
            self.state_q.put({"type": "disconnect"})

    def send_dir(self, d: str):
        if not self.started or self.game_over:
            return
        if not self.sock:
            return
        try:
            send_json(self.sock, {"type": "dir", "dir": d})
        except Exception:
            pass

    def on_close(self):
        self.running = False
        try:
            if self.sock:
                send_json(self.sock, {"type": "quit"})
        except Exception:
            pass
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.root.destroy()

    def apply_state(self, st: Dict[str, Any]):
        # resize if needed
        self.grid_w = int(st.get("w", self.grid_w))
        self.grid_h = int(st.get("h", self.grid_h))
        self.canvas.config(width=self.grid_w * self.cell_px, height=self.grid_h * self.cell_px)

        fx, fy = st.get("food", [0, 0])
        self.food = (int(fx), int(fy))

        snakes = st.get("snakes", {})
        s1 = snakes.get("1", [])
        s2 = snakes.get("2", [])
        self.snakes = {
            1: [(int(x), int(y)) for x, y in s1],
            2: [(int(x), int(y)) for x, y in s2],
        }

        scores = st.get("scores", {})
        self.scores = {1: int(scores.get("1", 0)), 2: int(scores.get("2", 0))}

        alive = st.get("alive", {})
        self.alive = {1: bool(alive.get("1", True)), 2: bool(alive.get("2", True))}

        self.score_var.set(f"Score P1: {self.scores[1]} | P2: {self.scores[2]}")

    def draw(self):
        self.canvas.delete("all")

        # grid lines (light)
        for x in range(self.grid_w + 1):
            px = x * self.cell_px
            self.canvas.create_line(px, 0, px, self.grid_h * self.cell_px)
        for y in range(self.grid_h + 1):
            py = y * self.cell_px
            self.canvas.create_line(0, py, self.grid_w * self.cell_px, py)

        # food
        fx, fy = self.food
        self._rect(fx, fy, fill="orange")

        # snakes
        # P1: green, P2: blue; heads are darker via outline
        for pid, fill in [(1, "green"), (2, "deepskyblue")]:
            body = self.snakes.get(pid, [])
            for i, (x, y) in enumerate(body):
                if i == 0:
                    self._rect(x, y, fill=fill, outline="black", width=2)
                else:
                    self._rect(x, y, fill=fill)

        # status hint
        if not self.started:
            self._center_text("Waiting for game start...")
        elif self.game_over:
            self._center_text("Game Over")

    def _rect(self, x: int, y: int, fill: str, outline: str = "", width: int = 1):
        x0 = x * self.cell_px
        y0 = y * self.cell_px
        x1 = x0 + self.cell_px
        y1 = y0 + self.cell_px
        self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=width)

    def _center_text(self, s: str):
        self.canvas.create_text(
            (self.grid_w * self.cell_px) // 2,
            (self.grid_h * self.cell_px) // 2,
            text=s,
            font=("Arial", 16, "bold"),
        )

    def ui_loop(self):
        # consume messages
        try:
            while True:
                msg = self.state_q.get_nowait()
                mtype = msg.get("type")

                if mtype == "welcome":
                    self.player_id = int(msg.get("player_id"))
                    self.info_var.set(f"Connected as Player {self.player_id}. Waiting for Player 2...")
                elif mtype == "start":
                    self.started = True
                    self.info_var.set(f"Game started! You are Player {self.player_id}. (Arrows / WASD)")
                elif mtype == "state":
                    self.apply_state(msg)
                elif mtype == "game_over":
                    self.apply_state(msg)
                    self.game_over = True
                    winner = int(msg.get("winner", 0))
                    reason = str(msg.get("reason", ""))
                    text = msg.get("msg", "Game Over")
                    self.info_var.set(f"{text} (reason: {reason})")
                    if winner == 0:
                        messagebox.showinfo("Game Over", f"{text}\n{reason}")
                    else:
                        messagebox.showinfo("Game Over", f"{text}\nWinner: Player {winner}\n{reason}")
                elif mtype == "error":
                    self.info_var.set(f"Error: {msg.get('msg','')}")
                elif mtype == "disconnect":
                    self.info_var.set("Disconnected from server.")
                    self.game_over = True
                else:
                    # ignore unknown
                    pass
        except queue.Empty:
            pass

        self.draw()
        if self.running:
            self.root.after(33, self.ui_loop)


def parse_args():
    ap = argparse.ArgumentParser(description="Two-Player Snake GUI Game Client")
    ap.add_argument("--host", help="Server IP/hostname")
    ap.add_argument("--port", type=int, help="Server port")
    ap.add_argument("--cell", type=int, default=24, help="Cell size in pixels")
    return ap.parse_args()


def main():
    args = parse_args()
    host = sys.argv[2]
    port = int(sys.argv[4])
    client = SnakeGUIClient(host, port, cell_px=args.cell)
    client.connect()


if __name__ == "__main__":
    main()
