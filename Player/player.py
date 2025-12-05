from ..config import LOBBY_HOST, LOBBY_PORT
from ..TCP_tool import set_keepalive, recv_json, send_json
import threading
import select
import sys
import time
import queue
import socket
import os

from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_ROOT = BASE_DIR / "download"
# for Enum
class STATUS():
    INIT = 0
    LOBBY = 1
    
class PLAYER():
    # ======= setting ======= #
    def __init__(self):
        self.sock = None # connect with client server
        self.status = STATUS.INIT
        self.change_mode = False
        self.exit = False
        self.last_msg = None
        # === after login === #
        self.username = None
        self.token = False
        self.filepath = None

    # connect to Client Server
    def start(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((LOBBY_HOST, LOBBY_PORT))
            self.main_route()
        except Exception as e:
            print(f"[!] {(LOBBY_HOST, LOBBY_PORT)} disconnected: {e}")
        finally:
            if self.sock is not None:
                try:
                    self.sock.close()
                except Exception:
                    pass
    
    # === main loop === #
    def main_route(self):
        # exit or change mode will leave the while loop
        while not self.exit and not self.change_mode:
            match self.status:
                case STATUS.INIT:
                    self.init_page()
                case STATUS.LOBBY:
                    self.lobby_page()
    
    def init_page(self):
        while True:
            os.system('clear')
            self.print_and_reset_last_msg()
            print("----- init page (Player mode) -----")
            print("Welcome to Online Game Shop System")
            print("1. Register")
            print("2. Login")
            print("3. Switch to developer mode")
            print("4. Exit")

            op = nb_input(prompt=">> ")
            match op:
                # === register === #
                case "1":
                    os.system('clear')
                    print("\n=== Register ===")
                    username = nb_input("Account: ")
                    password = nb_input("Password: ")

                    request_data = {"username": username, "password": password}
                    send_json(self.sock, format(status=self.status, action="register", data=request_data, token=None))

                    recv_data = recv_json(self.sock)
                    act, result, resp_data, self.last_msg = breakdown(recv_data)

                # === login === #
                case "2":
                    os. system('clear')
                    print("=== Login ===")
                    username = nb_input("Account: ")
                    password = nb_input("Password: ")

                    request_data = {"username": username, "password": password}
                    send_json(self.sock, format(status=self.status, action="login", data=request_data, token=None))
                    recv_data = recv_json(self.sock)
                    act, result, resp_data, self.last_msg = breakdown(recv_data)
                    
                    if act == "login" and result == "ok":
                        self.username = username
                        print("ok there")
                        self.token = resp_data["token"]
                        self.status = STATUS.LOBBY
                        # TODO establish own download folder

                        break

                # === change mode === #
                case "3":
                    print("Switch to developer mode.")
                    self.change_mode = True
                    break

                # === exit === #
                case "4":
                    print("Exit!")
                    self.exit = True
                    break

                # === illegal === #
                case _:
                    self.last_msg = "Please Enter a number bewtween 1 to 4!"

    def lobby_page(self):
        while True:
            os.system('clear')
            self.print_and_reset_last_msg()
            print("----- Lobby page -----")
            print("1. Open Game Store")
            print("2. Play Game")
            print("3. Open mailbox")
            time.sleep(5.0)

    
    def print_and_reset_last_msg(self):
        if self.last_msg and self.last_msg != "":
            print("======================")
            print(f"{self.last_msg}")
            print("======================")
            self.last_msg = None

# === helper === #
def format(status, action, data:dict={}, token=None):
    return {"status": status, "action": action, "data": data, "token": token}

def breakdown(resp: dict):
    action = resp["action"]
    result = resp["result"]
    data   = resp["data"]
    msg    = resp["msg"]
    return action, result, data, msg

def nb_input(prompt=">> ", conn=None):
    print(prompt, end="", flush=True)
    while True:
        # check server socket first
        if conn:
            r, _, _ = select.select([conn], [], [], 0)
            if r:
                try:
                    resp = recv_json(conn)
                    act, result, resp_data, last_msg = breakdown(resp)
                except Exception:
                    resp = None
                if resp:
                    # TODO non blocking
                    pass
        # check stdin
        r, _, _ = select.select([sys.stdin], [], [], 0.05)
        if r:
            s = sys.stdin.readline()
            if s:
                s = s.strip()
                if s:
                    return s
        # small sleep to avoid busy loop
        time.sleep(0.01)

def ensure_user_download_dir(username: str) -> Path:
    user_dir = DOWNLOAD_ROOT / str(username)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

def save_download_file(user_id: str, file_name: str, content: bytes) -> Path:
    user_dir = ensure_user_download_dir(user_id)
    file_path = user_dir / file_name
    with open(file_path, "wb") as f:
        f.write(content)
    return file_path