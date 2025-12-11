from ..config import DEV_HOST, DEV_PORT
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
BASE_DIR_LOCAL = Path(__file__).resolve().parent / "game_local"
BASE_DIR_STORE = Path(__file__).resolve().parent / "game_store"
# for Enum
class STATUS():
    INIT = 0
    LOBBY = 1
    
class DEVELOPER():
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
            self.sock.connect((DEV_HOST, DEV_PORT))
            self.main_route()
        except Exception as e:
            print("error_d")
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
        while self.status == STATUS.INIT:
            os.system('clear')
            self.print_and_reset_last_msg()
            print("----- init page (Developer mode) -----")
            print("Welcome to Online Game Shop System")
            print("1. Register")
            print("2. Login")
            print("3. Switch to player mode")
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
                        self.token = resp_data["token"]
                        self.status = STATUS.LOBBY
                        ensure_user_local_dir(self.username)
                        # ensure_user_store_dir(self.username)

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
        while self.status == STATUS.LOBBY:
            # os.system('clear')
            self.print_and_reset_last_msg()
            print("----- Lobby page (Developer)-----")
            print("1. Manage your game on game store")
            print("2. Upload your game to game store")
            print("3. Fast start to cteate game")
            print("4. logout")
            op = nb_input("Enter >> ", self.sock)
            match op:
                case "1":
                    # TODO send request to developer server and show the gamelist of him.
                    resquest_data = {"username": self.username}
                    send_json(self.sock, format(status=self.status, action="manage_game", data=resquest_data, token=self.token))
                    recv_data = recv_json(self.sock)
                    act, result, resp_data, self.last_msg = breakdown(recv_data)
                    # server will return the game list of this developer
                    game_on_store = resp_data.get("game_list", [])
                    if game_on_store:
                        print("=========================")
                        print("Your games on game store:")
                        print("=========================")
                        for i, game in enumerate(game_on_store, start=1):
                            print(f"{i}. {game}")
                        print("=========================")
                        while True:
                            choice = nb_input("Enter the number of the game to view details (or 'q' to abort): ")
                            if choice.lower() == 'q':
                                print("Aborted.")
                                time.sleep(0.5)
                                break
                            if choice.isdigit() and 1 <= int(choice) <= len(game_on_store):
                                selected_game = game_on_store[int(choice) - 1]
                                while True:
                                    print("=========================")
                                    print(f"{selected_game} Options:")
                                    print("1. View Details")
                                    print("2. Update Game on Store")
                                    print("3. Delete Game from Store")
                                    print("4. Back to Previous Menu")
                                    sub_choice = nb_input("Enter >> ")
                                    match sub_choice:
                                        case "1":
                                            # View Details
                                            send_json(self.sock, format(status=self.status, action="view_game_details", data={"gamename": selected_game}, token=self.token))
                                            details_resp = recv_json(self.sock)
                                            act_d, result_d, resp_data_d, self.last_msg = breakdown(details_resp)
                                            if act_d == "view_game_details" and result_d == "ok":
                                                game_details = resp_data_d.get("game_details", {})
                                                print(f"--- Details of {selected_game} ---")
                                                for key, value in game_details.items():
                                                    print(f"{key}: {value}")
                                                print("-------------------------------")
                                                nb_input("Press Enter to continue...")
                                            else:
                                                self.last_msg = f"Failed to get game details: {self.last_msg}"
                                        case "2":
                                            # Update Game on Store
                                            print("Feature not implemented yet.")
                                        case "3":
                                            # Delete Game from Store
                                            print("Feature not implemented yet.")
                                        case "4":
                                            break
                                        case _:
                                            print("Please enter a valid option (1-4).")
                                break
                            else:
                                print("Invalid choice. Please enter a valid number or 'q' to abort.")
                    else:
                        self.last_msg = "You have no game on the game store."
                case "2":
                    print("=== Upload your game to game store ===")
                    # look local game dir
                    user_local_dir = ensure_user_local_dir(self.username)
                    games = [d for d in user_local_dir.iterdir() if d.is_dir()]
                    if not games:
                        self.last_msg = "You have no game in your local directory. Please create a game first."
                        continue
                    print("Your local games:")
                    for i, game_dir in enumerate(games, start=1):
                        print(f"{i}. {game_dir.name}")
                    try:
                        print("Enter the number of the game you want to upload (or 'q' to abort):")
                        while True:
                            choice = nb_input(">> ")
                            if choice.lower() == 'q':
                                print("Upload aborted.")
                                time.sleep(0.5)
                                break
                            if choice.isdigit() and 1 <= int(choice) <= len(games):
                                selected_game_dir = games[int(choice) - 1]
                                # read game files and config
                                try:
                                    gamename = selected_game_dir.name
                                    # create config ask developer to fill in
                                    config_path = selected_game_dir / "config.json"
                                    # TODO check valid config
                                    if not config_path.exists():
                                        self.last_msg = f"Config file not found in {selected_game_dir}. Please create a config.json file."
                                        break
                                    print("Please fill in the game config info:")
                                    # max_players
                                    while True:
                                        max_players = nb_input("Enter max players: ")
                                        if max_players.isdigit() and int(max_players) >= 2:
                                            break
                                        else:
                                            print("Please enter a valid number (>=2).")
                                    # version
                                    while True:
                                        version = nb_input("Enter game version (e.g., 1.0.0): ")
                                        if version:
                                            break
                                        else:
                                            print("Please enter a valid version string.")
                                    # game_type
                                    while True:
                                        game_type = nb_input("Enter game type (CUI/GUI): ")
                                        if game_type in {"CUI", "GUI"}:
                                            break
                                        else:
                                            print("Please enter either 'CUI' or 'GUI'.")

                                    # last_update
                                    last_update = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

                                    with open(config_path, "w", encoding="utf-8") as cf:
                                        config_data = {
                                            "gamename": gamename,
                                            "author": self.username,
                                            "max_players": int(max_players),
                                            "version": version,
                                            "game_type": game_type,
                                            "last_update": last_update
                                        }
                                        json.dump(config_data, cf, indent=4, ensure_ascii=False)
                                        time.sleep(0.1)
                                    # read game files
                                    game_files = {}
                                    for file in selected_game_dir.iterdir():
                                        if file.is_file() and file.suffix in {".py", ".txt", ".md"}:
                                            with open(file, "r", encoding="utf-8") as gf:
                                                game_files[file.name] = gf.read()
                                    # prepare upload data
                                    upload_data = {
                                        "username": self.username,
                                        "gamename": gamename,
                                        "config": config_data,
                                        "files": game_files
                                    }
                                    send_json(self.sock, format(status=self.status, action="upload_game", data=upload_data, token=self.token))
                                    recv_data = recv_json(self.sock)
                                    act, result, resp_data, self.last_msg = breakdown(recv_data)
                                    if act == "upload_game" and result == "ok":
                                        self.last_msg = f"Game '{upload_data.get('gamename', 'unknown')}' uploaded successfully!"
                                    else:
                                        self.last_msg = f"Failed to upload game: {self.last_msg}"
                                    
                                except Exception as e:
                                    self.last_msg = f"Error reading game files: {e}"
                                break
                            else:
                                print("Invalid choice. Please enter a valid number or 'q' to abort.")
                    except KeyboardInterrupt:
                        print("\nUpload aborted.")
                        time.sleep(0.5)
                case "3":
                    # use template to generate {gamename}_client.py, {gamename}_server.py
                    # Ask some info from developer
                    os.system('clear')
                    print("=== Fast create game ===")
                    print("Please enter the following info to create your game template:")
                    print("This is a CUI version game template.")
                    print("Note: You need to modify the game logic for your game later!")
                    print("-----------------------------------")
                    print("Use cntrl+c to abort anytime.")
                    try:
                        gamename = nb_input("Enter your game name: ")
                        # cp whole template folder to working directory
                        template_dir = BASE_DIR_LOCAL / "template"
                        # os.mkdir(f"./game_local/{self.username}", exist_ok=True)
                        os.system(f"cp -r {template_dir} {BASE_DIR_LOCAL}/{self.username}")
                        # rename files
                        os.system(f"mv {BASE_DIR_LOCAL}/{self.username}/template {BASE_DIR_LOCAL}/{self.username}/{gamename}")
                        os.system(f"mv {BASE_DIR_LOCAL}/{self.username}/{gamename}/template_client.py {BASE_DIR_LOCAL}/{self.username}/{gamename}/{gamename}_client.py")
                        os.system(f"mv {BASE_DIR_LOCAL}/{self.username}/{gamename}/template_server.py {BASE_DIR_LOCAL}/{self.username}/{gamename}/{gamename}_server.py")

                        # overwrite config
                        with open(f"{BASE_DIR_LOCAL}/{self.username}/{gamename}/config.json", "w", encoding="utf-8") as f:
                            print("config ok")
                            config_data = {
                                "gamename": gamename,
                                "author": self.username,
                                "version": "1.0.0",
                                "max_players": 2,
                                "game_type": "CUI",
                                "last_update": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                            }
                            json.dump(config_data, f, indent=4, ensure_ascii=False)
                        time.sleep(0.5)
                        self.last_msg = f"Game template '{gamename}' created successfully! Please check your working directory."
                    except OSError as e:
                        self.last_msg = f"File operation error: {e}"
                    except KeyboardInterrupt:
                        print("\nAborted!")
                        time.sleep(0.5)
                # === logout === #
                case "4":
                    send_json(self.sock, format(status=self.status, action="logout", data={"username": self.username}, token=self.token))
                    recv_data = recv_json(self.sock)
                    act, result, resp_data, self.last_msg = breakdown(recv_data)
                    if result == "token miss" or result == "ok":
                        self.logout()
                    else:
                        pass
                case _:
                    self.last_msg = "Please Enter a number bewtween 1 to 4!"

    def print_and_reset_last_msg(self):
        if self.last_msg and self.last_msg != "":
            print("======================")
            print(f"{self.last_msg}")
            print("======================")
            self.last_msg = None

    def logout(self):
        self.username = None
        self.token = None
        self.status = STATUS.INIT

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

def ensure_user_local_dir(username: str) -> Path:
    user_dir = BASE_DIR_LOCAL / str(username)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

def ensure_user_store_dir(username: str) -> Path:
    user_dir = BASE_DIR_STORE / str(username)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir
# def save_download_file(user_id: str, file_name: str, content: bytes) -> Path:
#     user_dir = ensure_user_download_dir(user_id)
#     file_path = user_dir / file_name
#     with open(file_path, "wb") as f:
#         f.write(content)
#     return file_path