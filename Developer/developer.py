from sympy import re
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
            # os.system('clear')
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
                    # block "_" in username
                    while True:
                        username = nb_input("Account: ")
                        if "_" in username:
                            print("Username cannot contain '_'. Please enter again.")
                        else:
                            break
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
            os.system('clear')
            self.print_and_reset_last_msg()
            print("developer: ", self.username)
            print("----- Lobby page (Developer)-----")
            print("1. Manage your game on game store")
            print("2. Upload your game to game store")
            print("3. Fast start to cteate game")
            print("4. logout")
            op = nb_input("Enter >> ")
            match op:
                case "1":
                    # TODO send request to developer server and show the gamelist of him.
                    while True:
                        os.system('clear')
                        request_data = {"username": self.username}
                        send_json(self.sock, format(status=self.status, action="manage_game", data=request_data, token=self.token))
                        recv_data = recv_json(self.sock)
                        act, result, resp_data, self.last_msg = breakdown(recv_data)
                        # server will return the game list of this developer
                        game_on_store_dict = resp_data.get("game_list", {})
                        if game_on_store_dict:
                            print("=========================")
                            print("Your games on game store:")
                            print("=========================")
                            # gamename is str like "gamename_author"
                            game_on_store_list = []
                            # print(game_on_store_dict)
                            for i, game in enumerate(game_on_store_dict, start=1):
                                print(f"{i}. {ori_gamename(game)}")
                                game_on_store_list.append(game)
                            print("=========================")
                            print("0 for go back")
                            print("Enter one number of game or 0: ")
                            choice = nb_input(">> ")
                            os.system("clear")
                            if choice.lower() == '0':
                                self.last_msg = "go back"
                                break
                            if choice.isdigit() and 1 <= int(choice) <= len(game_on_store_list):
                                selected_game = game_on_store_list[int(choice) - 1]
                                gamename = game_on_store_dict[selected_game].get("gamename", "unknown")
                                while True:
                                    
                                    print("=========================")
                                    print(f"\"{gamename}\" Options:")
                                    print("1. View Details")
                                    print("2. Update Game on Store")
                                    print("3. Delete Game from Store")
                                    print("4. Back to Previous Menu")
                                    print("-------------------------")
                                    print("Select one number.")
                                    sub_choice = nb_input(">> ")
                                    match sub_choice:
                                        case "1":
                                            # View Details
                                            os.system('clear')
                                            print(f"--- Details of {gamename} ---")
                                            for key, value in game_on_store_dict[selected_game].items():
                                                print(f"{key}: {value}")
                                            print("-------------------------------")
                                        case "2":
                                            # Update Game on Store
                                            # 1. check the config is valid first.
                                            # 2. ask developer to fill in the new config info. (version must be higher than before)
                                            # 3. send update request to server.
                                            ori_config = game_on_store_dict[selected_game]
                                            print("Current config:")
                                            for key, value in ori_config.items():
                                                print(f"{key}: {value}")
                                            print("---------------------------------")
                                            print(" =========== updating =========== ")
                                            print("Please fill in the new config info:")
                                            # version
                                            while True:
                                                version = nb_input("new version[x.y.z]: ")
                                                if is_valid_version(version):
                                                    # check version higher than before
                                                    ori_version = ori_config.get("version", "0.0.0")
                                                    if tuple(map(int, version.split('.'))) > tuple(map(int, ori_version.split('.'))):
                                                        break
                                                    else:
                                                        print(f"New version must be higher than the current version ({ori_version}).")
                                                else:
                                                    print("Please enter a valid version string.")
                                            new_config = {
                                                "gamename": gamename,
                                                "author": self.username,
                                                "max_players": ori_config.get("max_players", 2),
                                                "version": version,
                                                "game_type": ori_config.get("game_type", "CUI"),
                                                "last_update": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                                            }
                                            # overwrite the origin cofig in local folder
                                            user_local_dir = ensure_user_local_dir(self.username)
                                            game_dir = user_local_dir / gamename
                                            config_path = game_dir / "config.json"
                                            try:
                                                with open(config_path, "w", encoding="utf-8") as cf:
                                                    json.dump(new_config, cf, indent=4, ensure_ascii=False)
                                                    time.sleep(0.1)
                                                print("Local config updated successfully.")
                                            except Exception as e:
                                                print(f"Failed to update local config: {e}")
                                            # 4. send update request to server (also the files)
                                            game_files = {}
                                            for file in game_dir.iterdir():
                                                if file.is_file() and file.suffix in {".py", ".txt", ".md"}:
                                                    try:
                                                        with open(file, "r", encoding="utf-8") as gf:
                                                            game_files[file.name] = gf.read()
                                                    except Exception as e:
                                                        print(f"Failed to read file {file.name}: {e}")
                                            # ensure developer upload
                                            upload_data = {
                                                "username": self.username,
                                                "gamename": gamename,
                                                "files": game_files,
                                                "config": new_config
                                            }
                                            send_json(self.sock, format(status=self.status, action="update_game", data=upload_data, token=self.token))
                                            recv_data = recv_json(self.sock)
                                            act, result, resp_data, self.last_msg = breakdown(recv_data)
                                            if act == "update_game" and result == "ok":
                                                self.last_msg = f"Game '{gamename}' updated successfully!"
                                                break
                                            else:
                                                self.last_msg = f"Failed to update game: {self.last_msg}"
                                        case "3":
                                            # Delete Game from Store
                                            # TODO: print the warning msg that ask developer to text the game name again.
                                            # ok remove from Game Store.
                                            # can use ctrl+c to cancel.
                                            confirm_name = nb_input(f"Type the game name '{gamename}' again to confirm deletion: ")
                                            if confirm_name == gamename:
                                                delete_data = {
                                                    "username": self.username,
                                                    "gamename": gamename
                                                }
                                                send_json(self.sock, format(status=self.status, action="delete_game", data=delete_data, token=self.token))
                                                recv_data = recv_json(self.sock)
                                                print(recv_data)
                                                act, result, resp_data, self.last_msg = breakdown(recv_data)
                                                if act == "delete_game" and result == "ok":
                                                    print(f"Game '{gamename}' deleted successfully from game store!")
                                                    time.sleep(2)
                                                    break
                                                else:
                                                    os.system('clear')
                                                    print(f"Failed to delete game: {gamename}.")
                                                    time.sleep(0.5)
                                            else:
                                                os.system('clear')
                                                print("Game name mismatch. Deletion aborted.")
                                                time.sleep(0.5)

                                        case "4":
                                            self.last_msg = "Back to previous menu"
                                            break
                                        case _:
                                            print("Please enter a valid option (1-4).")
                            else:
                                print("Invalid choice. Please enter a valid number or 'q' to abort.")
                        else:
                            self.last_msg = "You have no game on the game store."
                            break
                # === upload game === #
                case "2":
                    os.system('clear')
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

                        print("Enter the number of the game you want to upload:")
                        print("Enter 0 to go back!")
                        while True:
                            choice = nb_input(">> ")
                            if choice.lower() == '0':
                                self.last_msg = "No upload, back!"
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
                                    # fill config
                                    config_data = fill_config(gamename, self.username)
                                    # write
                                    with open(config_path, "w", encoding="utf-8") as cf:
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
                # === fast create game === #
                case "3":
                    # use template to generate {gamename}_client.py, {gamename}_server.py
                    # Ask some info from developer
                    os.system('clear')
                    print("=== Fast create game ===")
                    print("Please enter the following info to create your game template:")
                    print("This is a CUI version game template.")
                    print("Note: You need to modify the game logic for your game later!")
                    print("Use cntrl+c to abort anytime.")
                    print("-----------------------------------")
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
                        os.system(f"mv {BASE_DIR_LOCAL}/{self.username}/{gamename}/template_readme.txt {BASE_DIR_LOCAL}/{self.username}/{gamename}/{gamename}_readme.txt")
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

def ori_gamename(gameid: str) -> str:
    # gameid = gamename + _ + developername -> remove all thing that behind the _.
    return gameid.rsplit("_", 1)[0]

def fill_config(gamename: str, username: str) -> dict:
    os.system("clear")
    print("----------------------------------")
    print("Please fill in the game config info:")
    print("press enter to use default value where applicable.")
    print("Use cntrl+c to abort anytime.")
    print("----------------------------------")
    # max_players
    while True:
        max_players = nb_input("Enter max players [default: 2]: ", default="2")
        if max_players.isdigit() and int(max_players) >= 2:
            break
        else:
            print("Please enter a valid number (>=2).")
    # version
    while True:
        version = nb_input("Enter game version [default: 1.0.0]: ", default="1.0.0")
        # check the version format, must be like x.y.z
        if is_valid_version(version):
            break
        else:
            print("Please enter a valid version string.")
    # game_type
    while True:
        game_type = nb_input("Enter game type (CUI/GUI) [default: CUI]: ", default="CUI")
        if game_type in {"CUI", "GUI"}:
            break
        else:
            print("Please enter either 'CUI' or 'GUI'.")

    # last_update
    last_update = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    config_data = {
        "gamename": gamename,
        "author": username,
        "max_players": int(max_players),
        "version": version,
        "game_type": game_type,
        "last_update": last_update
    }
    return config_data

def nb_input(prompt=">> ", default=None, conn=None):
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
            if s is not None:
                s = s.rstrip("\n")
                if s == "":
                    if default is not None:
                        return default
                else:
                    return s

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

def is_valid_version(v):
    parts = v.split('.')
    if len(parts) != 3:
        return False
    return all(p.isdigit() for p in parts)