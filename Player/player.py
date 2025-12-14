from ..config import LOBBY_HOST, LOBBY_PORT
from ..TCP_tool import set_keepalive, recv_json, send_json
import threading
import select
import sys
import time
import queue
import socket
import os
import json

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
            # os.system('clear')
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
            print("3. Logout")
            op = nb_input(prompt=">> ")
            if op not in ["1", "2", "3", "4"]:
                self.last_msg = "Please Enter a number bewtween 1 to 4!"
                continue
            match op:
                case "1":
                    # TODO open game store
                    while True:
                        send_json(self.sock, format(status=self.status, action="open_shop", data={}, token=self.token))
                        recv_data = recv_json(self.sock)
                        act, result, resp_data, self.last_msg = breakdown(recv_data)
                        
                        # list all games on the store, and ask user to choose one.
                        if act == "open_shop" and result == "ok":
                            games = resp_data["games"]
                            print("=== Game Store ===")
                            # enumerate games
                            for idx, (game_name, game_info) in enumerate(games.items(), start=1):
                                print(f"{idx}. {game_info["gamename"]} - Author: {game_info['author']} - version: {game_info["version"]}")
                            op = nb_input("Choose a game number to take the action, or '0' to go back:")
                            if op == "0":
                                break

                            if not op.isdigit() or int(op) < 1 or int(op) > len(games):
                                print("Invalid input, please try again.")
                                continue
                            game_idx = int(op) - 1
                            game_name = list(games.keys())[game_idx]
                            game_info = games[game_name]
                            os.system('clear')
                            while True:
                                
                                print(f"Selected Game: {game_info['gamename']} by {game_info['author']}")
                                print("1. See Details")
                                print("2. Download Game")
                                print("3. Back to Game List")
                                op = nb_input(">> ")
                                os.system('clear')
                                match op:
                                    case "1": # see details
                                        print(f"=== Details of {game_info['gamename']} ===")
                                        print(f"Name: {game_info['gamename']}")
                                        print(f"Author: {game_info['author']}")
                                        print(f"Version: {game_info['version']}")
                                        print(f"Max Players: {game_info['max_players']}")
                                        print(f"game type: {game_info['game_type']}")
                                        print(f"Last Update: {game_info['last_update']}")
                                        print("----------------------------------------")
                                    case "2": # download game
                                        print(f"Downloading {game_info['gamename']}...")
                                        send_json(self.sock, format(status=self.status, action="download_game", data={"gamename": game_name}, token=self.token))
                                        recv_data = recv_json(self.sock)
                                        act, result, resp_data, self.last_msg = breakdown(recv_data)
                                        if act == "download_game" and result == "ok":
                                            # at DOWNLOAD PATH
                                            # resp_data expected to contain files mapping and optional config
                                            files = resp_data.get("files", {}) if isinstance(resp_data, dict) else {}
                                            config = resp_data.get("config") if isinstance(resp_data, dict) else None
                                            # use game_info gamename for folder name if available

                                            target_dir = ensure_user_download_dir(self.username) / game_name
                                            os.makedirs(target_dir, exist_ok=True)
                                            with open(target_dir / "config.json", "w") as f:
                                                json.dump(config, f, indent=4)
                                            
                                            for filename, filecontent in resp_data['files'].items():
                                                file_path = target_dir / filename
                                                with open(file_path, "wb") as f:
                                                    f.write(filecontent.encode('latin1'))
                                            
                                            print(f"Game {game_info['gamename']} downloaded successfully to {target_dir}!")
                                            break
                                        else:
                                            print("Failed to download the game.")
                                    case "3": # go back game list
                                        os.system('clear')
                                        break
                                    case _:
                                        os.system("clear")
                                        print("Invalid input, please try again.")
                                        print("----------------------")

                case "2":
                    # TODO play game
                    self.last_msg = "Not implemented yet!"
                case "3":
                    send_json(self.sock, format(status=self.status, action="logout", data={}, token=self.token))
                    recv_data = recv_json(self.sock)
                    act, result, resp_data, self.last_msg = breakdown(recv_data)
                    if act == "logout" and result == "ok":
                        self.username = None
                        self.token = None
                        self.status = STATUS.INIT
                        break

    
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