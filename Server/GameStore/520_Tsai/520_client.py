import socket
import json
import sys
from typing import Dict, Any, Optional

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

def prompt_move() -> str:
    while True:
        mv = input("Your move (rock/paper/scissors): ").strip().lower()
        if mv in ("rock", "paper", "scissors"):
            return mv
        print("Invalid. Please type rock, paper, or scissors.")

def prompt_yesno(msg: str) -> bool:
    while True:
        s = input(msg).strip().lower()
        if s in ("y", "yes"):
            return True
        if s in ("n", "no"):
            return False
        print("Please answer yes/no.")

def main():
    # Expect the script name followed by host and port. For example:
    #   python3 game_client.py 127.0.0.1 5050
    # In this case, sys.argv[1] is the host and sys.argv[2] is the port.
    if len(sys.argv) < 3:
        print("Usage: python3 game_client.py <server_ip> <server_port>")
        sys.exit(1)

    host = sys.argv[2]
    try:
        port = int(sys.argv[4])
    except (IndexError, ValueError):
        print("Invalid port. Please provide an integer port number.")
        sys.exit(1)

    # Connection retry logic to handle server startup delay
    import time
    max_retries = 10
    retry_delay = 0.5  # seconds
    c = None
    
    for attempt in range(max_retries):
        try:
            c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c.connect((host, port))
            print(f"[client] Connected to {host}:{port}")
            break
        except ConnectionRefusedError:
            if attempt < max_retries - 1:
                print(f"[client] Connection refused, retrying... ({attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print(f"[client] Failed to connect after {max_retries} attempts")
                sys.exit(1)
        except Exception as e:
            print(f"[client] Connection error: {e}")
            sys.exit(1)
    
    with c:

        player_id = None

        while True:
            msg = recv_json(c)
            if msg is None:
                print("[client] Server closed connection.")
                break

            mtype = msg.get("type")

            if mtype == "welcome":
                player_id = msg.get("player_id")
                print(f"[client] You are Player {player_id}. {msg.get('msg','')}")

            elif mtype == "start":
                print(msg.get("msg", "Game started!"))

                mv = prompt_move()
                send_json(c, {"type": "move", "move": mv})

            elif mtype == "ack":
                # print(f"[client] {msg.get('msg')}")
                pass

            elif mtype == "result":
                rnd = msg.get("round")
                you = msg.get("you")
                opp = msg.get("opponent")
                out = msg.get("outcome")
                print(f"\n[Round {rnd}] You: {you} | Opponent: {opp} => {out.upper()}\n")
                break

            elif mtype == "info":
                print(f"[info] {msg.get('msg','')}")

            elif mtype == "end":
                print(f"[client] {msg.get('msg','Game over.')}")
                break

            elif mtype == "error":
                print(f"[error] {msg.get('msg','Unknown error')}")

            else:
                print(f"[client] Unknown message: {msg}")

if __name__ == "__main__":
    main()
