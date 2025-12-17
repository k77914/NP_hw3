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


def prompt_secret() -> str:
    while True:
        secret = input("Your secret number (4 digits, no repeats): ").strip()
        if secret.isdigit() and len(secret) == 4 and len(set(secret)) == 4:
            return secret
        print("Invalid secret. Please enter a 4-digit number with no repeated digits.")


def prompt_guess() -> str:
    while True:
        guess = input("Your guess (4 digits, no repeats): ").strip()
        if guess.isdigit() and len(guess) == 4 and len(set(guess)) == 4:
            return guess
        print("Invalid guess. Please enter a 4-digit number with no repeated digits.")


def main() -> None:
    # Expect script name followed by server host and port
    if len(sys.argv) < 3:
        print("Usage: python3 nanb_client.py <server_ip> <server_port>")
        sys.exit(1)
    host = sys.argv[2]
    try:
        port = int(sys.argv[4])
    except (IndexError, ValueError):
        print("Invalid port. Please provide an integer port number.")
        sys.exit(1)

    # Attempt to connect to server with retries
    import time
    max_retries = 10
    retry_delay = 0.5  # seconds
    c: Optional[socket.socket] = None
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
    if c is None:
        # Should not happen
        print("[client] Could not establish connection.")
        sys.exit(1)

    with c:
        player_id: Optional[int] = None
        while True:
            msg = recv_json(c)
            if msg is None:
                print("[client] Server closed connection.")
                break
            mtype = msg.get("type")
            if mtype == "welcome":
                player_id = msg.get("player_id")
                print(f"[client] You are Player {player_id}. {msg.get('msg', '')}")
            elif mtype == "secret_phase":
                print(msg.get("msg", "Please send your secret."))
                secret = prompt_secret()
                send_json(c, {"type": "secret", "secret": secret})
            elif mtype == "guess_phase":
                print(msg.get("msg", "Please send your guess."))
                guess = prompt_guess()
                send_json(c, {"type": "guess", "guess": guess})
            elif mtype == "ack":
                # Acknowledge messages silently
                pass
            elif mtype == "result":
                your_guess = msg.get("your_guess")
                results = msg.get("results", [])
                print(f"\nYour guess: {your_guess}")
                for res in results:
                    opp_id = res.get("opponent_id")
                    result_str = res.get("result")
                    print(f" vs Player {opp_id}: {result_str}")
                print()
            elif mtype == "end":
                print(f"[client] {msg.get('msg', 'Game over.')}")
                break
            elif mtype == "error":
                print(f"[error] {msg.get('msg', 'Unknown error')}")
            else:
                print(f"[client] Unknown message: {msg}")


if __name__ == "__main__":
    main()