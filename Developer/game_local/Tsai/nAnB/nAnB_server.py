import socket
import threading
import json
import argparse
from typing import Dict, Any, Optional, Tuple, List


def send_json(conn: socket.socket, obj: Dict[str, Any]) -> None:
    """Send a JSON object over a socket, terminated by a newline."""
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        conn.sendall(data)
    except Exception:
        # If sending fails, ignore. The connection may already be closed.
        pass


def recv_json(conn: socket.socket) -> Optional[Dict[str, Any]]:
    """Receive a single JSON object delimited by a newline. If the connection
    is closed before a complete line is received, return None."""
    buf = b""
    while True:
        try:
            chunk = conn.recv(4096)
        except Exception:
            return None
        if not chunk:
            return None
        buf += chunk
        if b"\n" in buf:
            line, _rest = buf.split(b"\n", 1)
            try:
                return json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                return None


def count_ab(secret: str, guess: str) -> Tuple[int, int]:
    """Compute the nAnB result (A = correct digit and position, B = correct digit
    but wrong position) between a secret and a guess. Both inputs should be
    equal-length strings of digits."""
    A = sum(1 for s, g in zip(secret, guess) if s == g)
    # Count digits that are in both secret and guess, then subtract the As
    B = sum(min(secret.count(d), guess.count(d)) for d in set(guess)) - A
    return A, B


class GameRoom:
    """Maintain state for a three-player nAnB game."""

    def __init__(self, p1: socket.socket, p2: socket.socket, p3: socket.socket):
        self.players: Dict[int, socket.socket] = {1: p1, 2: p2, 3: p3}
        self.lock = threading.Lock()
        # Secrets chosen by each player; None until submitted
        self.secrets: Dict[int, Optional[str]] = {1: None, 2: None, 3: None}
        # Guesses submitted by each player; None until submitted
        self.guesses: Dict[int, Optional[str]] = {1: None, 2: None, 3: None}
        # Track if a player has disconnected
        self.disconnected: Dict[int, bool] = {1: False, 2: False, 3: False}

    def set_secret(self, player_id: int, secret: str) -> None:
        with self.lock:
            self.secrets[player_id] = secret

    def set_guess(self, player_id: int, guess: str) -> None:
        with self.lock:
            self.guesses[player_id] = guess

    def set_disconnected(self, player_id: int) -> None:
        with self.lock:
            self.disconnected[player_id] = True

    def get_state(self) -> Tuple[Dict[int, Optional[str]], Dict[int, Optional[str]], Dict[int, bool]]:
        """Return copies of the current secrets, guesses and disconnection status."""
        with self.lock:
            return dict(self.secrets), dict(self.guesses), dict(self.disconnected)

    def close(self) -> None:
        """Shut down all sockets associated with this game."""
        for c in self.players.values():
            try:
                c.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                c.close()
            except Exception:
                pass


def player_thread(room: GameRoom, conn: socket.socket, player_id: int) -> None:
    """Handle incoming messages from a single player. This thread runs for
    the lifetime of the player's connection and updates the GameRoom state.
    It does not send game-phase prompts; those are handled by run_room."""
    try:
        send_json(conn, {"type": "welcome", "player_id": player_id, "msg": "Connected. Waiting for game start..."})
        while True:
            msg = recv_json(conn)
            if msg is None:
                # Client disconnected
                room.set_disconnected(player_id)
                break

            mtype = msg.get("type")
            if mtype == "secret":
                secret = str(msg.get("secret", "")).strip()
                # Basic validation: must be 4 digits and all digits
                if not (secret.isdigit() and len(secret) == 4 and len(set(secret)) == 4):
                    send_json(conn, {"type": "error", "msg": "Invalid secret. Provide a 4-digit number with no repeated digits."})
                    continue
                room.set_secret(player_id, secret)
                send_json(conn, {"type": "ack", "msg": f"Secret received."})

            elif mtype == "guess":
                guess = str(msg.get("guess", "")).strip()
                if not (guess.isdigit() and len(guess) == 4 and len(set(guess)) == 4):
                    send_json(conn, {"type": "error", "msg": "Invalid guess. Provide a 4-digit number with no repeated digits."})
                    continue
                room.set_guess(player_id, guess)
                send_json(conn, {"type": "ack", "msg": f"Guess received."})

            elif mtype == "quit":
                room.set_disconnected(player_id)
                break
            else:
                send_json(conn, {"type": "error", "msg": f"Unknown message type: {mtype}"})
    except Exception:
        # Any exception implies disconnection or invalid state
        room.set_disconnected(player_id)


def run_room(room: GameRoom) -> None:
    """Coordinate the three-player nAnB game. This function runs in the
    main thread of the server after all players are connected. It sends
    phase prompts, waits for player inputs, and computes results or
    aborts the game if any player disconnects."""
    players = room.players
    p1, p2, p3 = players[1], players[2], players[3]

    # Phase 1: request secrets from all players
    for pid in (1, 2, 3):
        try:
            send_json(players[pid], {"type": "secret_phase", "msg": "Game started! Please send your secret (4-digit number)."})
        except Exception:
            room.set_disconnected(pid)

    # Wait for all secrets or a disconnection
    while True:
        secrets, guesses, disc = room.get_state()
        if any(disc.values()):
            break
        if all(secrets[pid] is not None for pid in (1, 2, 3)):
            break
        threading.Event().wait(0.05)

    # If a player disconnected before submitting secrets, abort game
    secrets, guesses, disc = room.get_state()
    if any(disc.values()):
        # Notify remaining connected players that game is aborted
        for pid, disconnected in disc.items():
            if not disconnected:
                try:
                    send_json(players[pid], {"type": "end", "msg": "A player has disconnected. Game aborted."})
                except Exception:
                    pass
        return

    # Phase 2: request guesses from all players
    for pid in (1, 2, 3):
        try:
            send_json(players[pid], {"type": "guess_phase", "msg": "All secrets received. Please send your guess (4-digit number)."})
        except Exception:
            room.set_disconnected(pid)

    # Wait for all guesses or a disconnection
    while True:
        secrets, guesses, disc = room.get_state()
        if any(disc.values()):
            break
        if all(guesses[pid] is not None for pid in (1, 2, 3)):
            break
        threading.Event().wait(0.05)

    secrets, guesses, disc = room.get_state()
    if any(disc.values()):
        # A player disconnected during guess phase, abort and notify others
        for pid, disconnected in disc.items():
            if not disconnected:
                try:
                    send_json(players[pid], {"type": "end", "msg": "A player has disconnected. Game aborted."})
                except Exception:
                    pass
        return

    # Compute results for each player
    # For each guess, compare with every other player's secret
    for pid in (1, 2, 3):
        guess = guesses[pid]
        # Build list of result objects
        result_list: List[Dict[str, Any]] = []
        for opp in (1, 2, 3):
            if opp == pid:
                continue
            A, B = count_ab(secrets[opp], guess)
            result_list.append({"opponent_id": opp, "result": f"{A}A{B}B", "opponent_secret_len": len(secrets[opp])})
        # Send results to player
        try:
            send_json(players[pid], {
                "type": "result",
                "your_guess": guess,
                "results": result_list
            })
        except Exception:
            # Mark as disconnected if cannot send
            room.set_disconnected(pid)

    # Send end-of-game message to all still connected players
    for pid in (1, 2, 3):
        if not disc.get(pid, False):
            try:
                send_json(players[pid], {"type": "end", "msg": "Game over. Thanks for playing!"})
            except Exception:
                pass


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="nAnB (Bulls and Cows) Game Server - 3 players")
    ap.add_argument("--host", default="0.0.0.0", help="Bind host/IP (default: 0.0.0.0)")
    ap.add_argument("--port", type=int, default=5050, help="Bind port (use 0 for auto-assign)")
    ap.add_argument("--backlog", type=int, default=5, help="Listen backlog")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((args.host, args.port))
        bind_host, bind_port = s.getsockname()
        print(f"[server] Listening on {bind_host}:{bind_port}")
        s.listen(args.backlog)

        # Accept three players
        players: List[Tuple[socket.socket, Tuple[str, int]]] = []
        for i in range(1, 4):
            print(f"[server] Waiting for Player {i}...")
            conn, addr = s.accept()
            print(f"[server] Player {i} connected from {addr}")
            players.append((conn, addr))

        # Unpack player connections
        p1, p2, p3 = players[0][0], players[1][0], players[2][0]
        room = GameRoom(p1, p2, p3)
        # Start player threads
        threading.Thread(target=player_thread, args=(room, p1, 1), daemon=True).start()
        threading.Thread(target=player_thread, args=(room, p2, 2), daemon=True).start()
        threading.Thread(target=player_thread, args=(room, p3, 3), daemon=True).start()

        # Run the game loop
        try:
            run_room(room)
        finally:
            room.close()
            print("[server] Room finished. Bye.")


if __name__ == "__main__":
    main()