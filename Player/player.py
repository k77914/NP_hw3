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
    ROOM = 2
    INGAME = 3
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
        self.room_id = None

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
                case STATUS.ROOM:
                    self.room_page()
    
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
        while self.status == STATUS.LOBBY:
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
                case "1":# open game store
                    while True:
                        send_json(self.sock, format(status=self.status, action="open_shop", data={}, token=self.token))
                        recv_data = recv_json(self.sock)
                        act, result, resp_data, self.last_msg = breakdown(recv_data)
                        
                        # list all games on the store, and ask user to choose one.
                        if act == "open_shop" and result == "ok":
                            games = resp_data["games"]
                            if games == {}:
                                self.last_msg = "No games available in the store."
                                break
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

                case "2":# play
                    GAME_FOLDER_PATH = DOWNLOAD_ROOT / self.username
                    available_games = [d for d in GAME_FOLDER_PATH.iterdir() if d.is_dir()]
                    if not available_games:
                        self.last_msg = "No downloaded games found. Please download a game first."
                        continue
                    print("=== Available Games ===")
                    for idx, game_dir in enumerate(available_games, start=1):
                        game, author = game_dir.name.rsplit("_", 1)
                        print(f"{idx}. {game}, by {author}")
                    op = nb_input("Choose a game number to play, or '0' to go back:")
                    if op == "0":
                        continue
                    if not op.isdigit() or int(op) < 1 or int(op) > len(available_games):
                        print("Invalid input, please try again.")
                        continue
                    game_idx = int(op) - 1
                    selected_game_dir = available_games[game_idx]
                    # check version from config.json
                    config_path = selected_game_dir / "config.json"
                    if not config_path.exists():
                        print("config.json not found for the selected game. Cannot verify version.")
                        continue
                    with open(config_path, "r") as f:
                        config = json.load(f)
                    local_version = config.get("version")
                    # inform server to check version
                    send_json(self.sock, format(status=self.status, action="check_version", data={"gamename": selected_game_dir.name, "version": local_version}, token=self.token))
                    recv_data = recv_json(self.sock)
                    act, result, resp_data, self.last_msg = breakdown(recv_data)
                    if act != "check_version" or result != "ok":
                        while True:
                            print("Version check failed or game is outdated. Please download the latest version.")
                            print("--------------------------")
                            print("1. Auto-download latest version")
                            print("2. Back to Lobby")
                            op = nb_input(">> ")
                            if op == "1":
                                send_json(self.sock, format(status=self.status, action="download_game", data={"gamename": selected_game_dir.name}, token=self.token))
                                recv_data = recv_json(self.sock)
                                act, result, resp_data, self.last_msg = breakdown(recv_data)
                                if act == "download_game" and result == "ok":
                                    # overwrite existing files
                                    with open(config_path, "w") as f:
                                        json.dump(resp_data["config"], f, indent=4)
                                    
                                    for filename, filecontent in resp_data["files"].items():
                                        file_path = selected_game_dir / filename
                                        with open(file_path, "wb") as f:
                                            f.write(filecontent.encode('latin1'))
                                    
                                    print(f"Game {selected_game_dir.name} updated successfully!")
                                    break
                                else:
                                    print("Failed to download the latest version.")
                            elif op == "2":
                                break
                            else:
                                print("Invalid input, please try again.")
                    while True:
                        print("--------------------------")
                        print("Game: ", selected_game_dir.name.rsplit("_", 1)[0])
                        print("1. Create Room")
                        print("2. Join Room")
                        print(f"3. Learn More about {selected_game_dir.name.rsplit('_', 1)[0]}")
                        print("4. Back to Lobby")
                        op = nb_input(">> ")
                        os.system('clear')
                        match op:
                            case "1": # create room
                                room_password = nb_input("Set room password (or leave empty for no password): ", default="")
                                send_json(self.sock, format(status=self.status, action="create_room", data={"gamename": selected_game_dir.name, "room_password": room_password}, token=self.token))
                                recv_data = recv_json(self.sock)
                                act, result, resp_data, self.last_msg = breakdown(recv_data)
                                if act == "create_room" and result == "ok":
                                    room_id = resp_data.get("room_id")
                                    print(f"Room {room_id} created successfully! Waiting for players to join...")
                                    self.game = selected_game_dir.name
                                    self.status = STATUS.ROOM
                                    self.room_id = room_id
                                    break
                                else:
                                    print("Failed to create room. Try again.")
                            case "2": # Join room
                                # List all rooms.
                                send_json(self.sock, format(status=self.status, action="list_rooms", data={"gamename": selected_game_dir.name}, token=self.token))
                                recv_data = recv_json(self.sock)
                                act, result, resp_data, self.last_msg = breakdown(recv_data)
                                if act == "list_rooms" and result == "ok":
                                    rooms = resp_data.get("rooms", [])
                                    if not rooms:
                                        print("No available rooms to join. Try creating one.")
                                        continue
                                    print("=== Available Rooms ===")
                                    for idx, room in enumerate(rooms, start=1):
                                        print(f"{idx}. Room ID: {room['room_id']}, Players: {room['current_players']}/{room['max_players']}, Password Protected: {'Yes' if room['has_password'] else 'No'}")
                                    op = nb_input("Choose a room number to join, or '0' to go back:")
                                    if op == "0":
                                        continue
                                    if not op.isdigit() or int(op) < 1 or int(op) > len(rooms):
                                        print("Invalid input, please try again.")
                                        continue
                                    room_idx = int(op) - 1
                                    selected_room = rooms[room_idx]
                                    room_id = selected_room['room_id']
                                    room_password = ""
                                    if selected_room['has_password']:
                                        room_password = nb_input("Enter room password: ")
                                    send_json(self.sock, format(status=self.status, action="join_room", data={"room_id": room_id, "room_password": room_password}, token=self.token))
                                    recv_data = recv_json(self.sock)
                                    act, result, resp_data, self.last_msg = breakdown(recv_data)
                                    if act == "join_room" and result == "ok":
                                        print(f"Joined Room {room_id} successfully! Waiting for game to start...")
                                        self.status = STATUS.ROOM
                                        self.room_id = room_id
                                        break
                                    else:
                                        print("Failed to join room. Check password or try another room.")
                                else:
                                    print("Failed to retrieve room list. Try again.")
                            case "3": # learn more
                                print(f"=== About {selected_game_dir.name.rsplit('_', 1)[0]} ===")
                                readme_path = selected_game_dir / "README.txt"
                                if readme_path.exists():
                                    with open(readme_path, "r") as f:
                                        print(f.read())
                                else:
                                    print("No additional information available for this game.")
                            case "4": # back to lobby
                                break
                            case _:
                                print("Invalid input, please try again.")

                    # print(f"Launching game: {selected_game_dir.name} ...")
                    # send_json(self.sock, format(status=self.status, action="play_game", data={"gamename" : selected_game_dir.name}, token=self.token))
                    # # 目前應該卡在這裡
                    # recv_data = recv_json(self.sock)
                    # act, result, resp_data, self.last_msg = breakdown(recv_data)
                    # if act == "play_game" and result == "ok":
                    #     print(f"Game {selected_game_dir.name} started successfully!")
                    # else:
                    #     print("Failed to start the game.")
                    #     continue

                case "3": # logout
                    send_json(self.sock, format(status=self.status, action="logout", data={}, token=self.token))
                    recv_data = recv_json(self.sock)
                    act, result, resp_data, self.last_msg = breakdown(recv_data)
                    if act == "logout" and result == "ok":
                        self.username = None
                        self.token = None
                        self.status = STATUS.INIT
                        break

    def room_page(self):
        self.host = True if self.username == self.room_id else False
        while True:
            os.system('clear')
            self.print_and_reset_last_msg()
            print(f"----- Room: {self.room_id} -----")
            print(f"game: {self.game.rsplit('_', 1)[0]}")
            print("players in room:")
            send_json(self.sock, format(status=self.status, action="list_players_in_room", data={"gamename": self.game, "room_id": self.room_id}, token=self.token))
            recv_data = recv_json(self.sock)
            act, result, resp_data, self.last_msg = breakdown(recv_data)
            if act == "list_players_in_room" and result == "ok":
                players = resp_data.get("players", [])
                for p in players:
                    print(f"- {p}")
            else:
                print("Failed to retrieve player list.")
            print("----------------------")
            print("1. Start Game" if self.host else "1. Ready Up")
            print("2. Leave Room")
            op = nb_input(">> ")
            match op:
                case "1":
                    if self.host:
                        send_json(self.sock, format(status=self.status, action="start_game", data={"room_id": self.room_id}, token=self.token))
                        recv_data = recv_json(self.sock)
                        act, result, resp_data, self.last_msg = breakdown(recv_data)
                        if act == "start_game" and result == "ok":
                            print("Game started successfully!")
                            self.status = STATUS.INGAME
                            break
                        else:
                            print("Failed to start the game. Make sure enough players have joined.")
                    else:
                        send_json(self.sock, format(status=self.status, action="ready_up", data={"room_id": self.room_id}, token=self.token))
                        recv_data = recv_json(self.sock)
                        act, result, resp_data, self.last_msg = breakdown(recv_data)
                        if act == "ready_up" and result == "ok":
                            print("You are now marked as ready.")
                        else:
                            print("Failed to mark as ready. Try again.")
                case "2":
                    send_json(self.sock, format(status=self.status, action="leave_room", data={"room_id": self.room_id}, token=self.token))
                    recv_data = recv_json(self.sock)
                    act, result, resp_data, self.last_msg = breakdown(recv_data)
                    if act == "leave_room" and result == "ok":
                        print("Left the room successfully.")
                        self.status = STATUS.LOBBY
                        self.room_id = None
                        break
                case _:
                    print("Invalid input, please try again.")

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

def nb_input(prompt=">> ", conn=None, default=""):
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