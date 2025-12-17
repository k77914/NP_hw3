import socket, threading, uuid
from loguru import logger
from NP_hw3.config import LOBBY_HOST, LOBBY_PORT, DB_HOST, DB_PORT
from NP_hw3.TCP_tool import send_json, recv_json, set_keepalive
import pathlib

GAME_STORE_DIR = pathlib.Path(__file__).resolve().parent / "GameStore"

class STATUS():
    INIT = 0
    LOBBY = 1
    ROOM = 2
    INGAME = 3
class STATUS_DB():
    INIT = "offline"
    LOBBY = "lobby"
    ROOM = "room"
    INGAME = "ingame"
class DB_type():
    PLAYER = "player_db"
    DEVELOPER = "developer_db"
    ROOM = "room_db"
    GAME_STORE = "game_store_db"

# Socket dict for players
# player_sockets = {
#     addr: socket.socket()
# }
player_sockets = {}


# Room dict
# structure:
# rooms: {
#  gamename:{
#     room_id : game_info
#     room_id2: game_info ...
#  }
#}
rooms = {}


# === helper === #
def breakdown_request(request: dict):
    return request["status"], request["action"], request["data"], request["token"]
def response_format(action, result, data:dict, msg):
    return {"action": action, "result": result, "data": data, "msg": msg}

def DB_request(DB_type, action, data):
    with socket.create_connection((DB_HOST, DB_PORT)) as db:
        db.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        #  Send to DB for different db_type, action, data.
        match action:
            case 'create':
                send_json(db, {"type": DB_type, "action": "create", "data": data})
            case 'read':
                send_json(db, {"type": DB_type, "action": "read", "data": data})
            case 'update':
                send_json(db, {"type": DB_type, "action": "update", "data": data})
            case 'delete':
                send_json(db, {"type": DB_type, "action": "delete", "data": data})
            case 'query':
                send_json(db, {"type": DB_type, "action": "query", "data": data})
            case _:
                logger.info(f"{DB_type} DB_request: unknown action {action}")
        
        #  Receive the response
        resp = recv_json(db)
        db.close()
    return resp
# ============= #

def handle_client(conn: socket.socket, addr):
    set_keepalive(conn)
    logger.info(f"[*] connected from {addr}")
    # === some variables === #
    username = None
    token_srv = None
    # ====================== #
    try:
        while True:
            request = recv_json(conn)
            status, action, request_data, token = breakdown_request(request)
            match status:
                case STATUS.INIT:
                    if action == "register":
                        regi_name = request_data["username"]
                        resp_db_query = DB_request(DB_type.PLAYER, "query", {"username" : regi_name})
                        if resp_db_query == {}:
                            DB_request(DB_type.PLAYER, "create", request_data)
                            send_json(conn, response_format(action=action, result="ok", data={}, msg="Register succuessfully"))
                        else:
                            send_json(conn, response_format(action, "error", {}, msg="Fail, change another username"))
                    elif action == "login":
                        login_name = request_data["username"]
                        resp_db_query = DB_request(DB_type.PLAYER, "query", {"username" : login_name})
                        # Not find
                        if resp_db_query == {}:
                            send_json(conn, response_format(action=action, result="error", data={}, msg="Account doesn't exist!"))
                        elif resp_db_query["password"] != request_data["password"]:
                            send_json(conn, response_format(action=action, result="error", data={}, msg="Wrong password!"))
                        else:
                            if resp_db_query["status"] != STATUS_DB.INIT:
                                send_json(conn, response_format(action=action, result="error", data={}, msg="User already logged in!"))
                                continue
                            username = login_name
                            player_sockets[addr]["username"] = username
                            token_srv = uuid.uuid4().hex
                            DB_request(DB_type.PLAYER, "update", {"username": username, "status": STATUS_DB.LOBBY, "token": token_srv})
                            send_json(conn, response_format(action=action, result="ok", data={"token": token_srv}, msg="Login successfully!"))
                    else:
                        send_json(conn, response_format(action=action, result="error", data={}, msg=""))
                case STATUS.LOBBY:
                    if token != token_srv:
                        # Not matching token, logout!
                        username = None
                        token_srv = None
                        DB_request(DB_type.PLAYER, "update", {"username": username, "status": STATUS_DB.INIT, "token": None})
                        send_json(conn, response_format(action=action, result="token miss", data={"status_change": STATUS.INIT}, msg="Miss matching token, logout"))
                        
                    elif action == "open_shop":
                        resp_db_query = DB_request(DB_type.GAME_STORE, "read", {})
                        send_json(conn, response_format(action=action, result="ok", data={"games": resp_db_query}, msg=""))
                    elif action == "download_game":
                        gamename = request_data["gamename"]
                        # directly read from GameStore
                        gamedir = GAME_STORE_DIR / gamename
                        if not gamedir.exists():
                            send_json(conn, response_format(action=action, result="error", data={}, msg="Game not found"))
                            continue
                        # read config.json
                        with open(gamedir / "config.json", "r") as f:
                            config = f.read()
                            # turn string into dict
                            import json
                            config = json.loads(config)
                        # read all files instead of server
                        files_data = {}
                        for file in gamedir.iterdir():
                            if file.name == "config.json" or "server.py" in file.name:
                                continue
                            with open(file, "rb") as f:
                                files_data[file.name] = f.read().decode('latin1')
                        send_json(conn, response_format(action=action, result="ok", data={"config": config, "files": files_data}, msg="Download success"))
                    elif action == "check_version":
                        gamename = request_data["gamename"]
                        user_version = request_data["version"]
                        # directly read from GameStore
                        gamedir = GAME_STORE_DIR / gamename
                        if not gamedir.exists():
                            send_json(conn, response_format(action=action, result="error", data={}, msg="Game not found"))
                            continue
                        # read config.json
                        with open(gamedir / "config.json", "r") as f:
                            config = f.read()
                            # turn string into dict
                            import json
                            config = json.loads(config)

                        if config["version"] == user_version:
                            send_json(conn, response_format(action=action, result="ok", data={}, msg="You have the latest version"))
                        else:
                            send_json(conn, response_format(action=action, result="error", data={}, msg="New version released!"))
                    elif action == "create_room":
                        # use dict

                        gamename = request_data["gamename"]
                        gamedir = GAME_STORE_DIR / gamename
                        if not gamedir.exists():
                            send_json(conn, response_format(action=action, result="error", data={}, msg="Game not found"))
                            continue
                        # read config.json
                        with open(gamedir / "config.json", "r") as f:
                            config = f.read()
                            # turn string into dict
                            import json
                            config = json.loads(config)

                        room_info = {
                            "host": username,
                            "players": [[username, addr, 1]],
                            "max_players": config["max_players"],
                            "room_password": request_data.get("room_password", ""),
                            "gaming": False,
                            "version" : config["version"]
                        }

                        if gamename not in rooms:
                            rooms[gamename] = {}
                        rooms[gamename][username] = room_info
                        # update player status
                        DB_request(DB_type.PLAYER, "update", {"username": username, "status": STATUS_DB.ROOM})
                        send_json(conn, response_format(action=action, result="ok", data={"room_id": username}, msg="Room created successfully"))
                        logger.info(f"Current rooms dict: {rooms}")
                    elif action == "list_rooms":
                        gamename = request_data["gamename"]
                        if gamename not in rooms:
                            rooms[gamename] = {}
                        room_list = []
                        with open(GAME_STORE_DIR / gamename / "config.json", "r") as f:
                            config = f.read()
                            import json
                            config = json.loads(config)
                        max_players = config.get("max_players", 2)
                        for room_id, info in rooms[gamename].items():
                            if info["gaming"]:
                                continue
                            room_list.append({
                                "room_id": room_id,
                                "host": info["host"],
                                "current_players": len(info["players"]),
                                "max_players" : max_players,
                                "has_password": info["room_password"] != ""
                            })
                        send_json(conn, response_format(action=action, result="ok", data={"rooms": room_list}, msg=""))
                    elif action == "join_room":
                        gamename = request_data["gamename"]
                        room_id = request_data["room_id"]
                        room_password = request_data.get("room_password", "")
                        if gamename not in rooms or room_id not in rooms[gamename]:
                            send_json(conn, response_format(action=action, result="error", data={}, msg="Room not found"))
                            continue
                        
                        room_info = rooms[gamename][room_id]
                        if len(room_info["players"]) >= room_info["max_players"]:
                            send_json(conn, response_format(action=action, result="error", data={}, msg="Full room"))
                            continue                            
                        if room_info["room_password"] != room_password:
                            send_json(conn, response_format(action=action, result="error", data={}, msg="Wrong room password"))
                            continue
                        room_info["players"].append([username, addr, 0])
                        # update player status
                        DB_request(DB_type.PLAYER, "update", {"username": username, "status": STATUS_DB.ROOM})
                        send_json(conn, response_format(action=action, result="ok", data={}, msg="Joined room successfully"))
                        # notify other players about new player
                        for player, player_addr, _ in room_info["players"]:
                            if player == username:
                                continue
                            player_conn = player_sockets[player_addr]["conn"]
                            send_json(player_conn, response_format(action="room_update", result="ok", data={"players": room_info["players"]}, msg=f"Player {username} joined the room"))
                    elif action == "logout":
                        DB_request(DB_type.PLAYER, "update", {"username": username, "status": STATUS_DB.INIT, "token": None})
                        username = None
                        token_srv = None
                        send_json(conn, response_format(action=action, result="ok", data={}, msg="Logout successfully!"))
                    else:
                        send_json(conn, response_format(action=action, result="error", data={}, msg="Unknown operation"))

                case STATUS.ROOM:
                    player_room = None
                    game = request_data.get("gamename", None)
                    room_id = request_data.get("room_id", None)
                    game_rooms = rooms.get(game, {})
                    player_room = game_rooms.get(room_id, None)

                    if token != token_srv:
                        # Not matching token, logout!
                        username = None
                        token_srv = None
                        DB_request(DB_type.PLAYER, "update", {"username": username, "status": STATUS_DB.INIT, "token": None})
                        send_json(conn, response_format(action=action, result="token miss", data={"status_change": STATUS.INIT}, msg="Miss matching token, logout"))
                    elif action == "list_players_in_room":
                        if player_room is None:
                            send_json(conn, response_format(action=action, result="error", data={}, msg="You are not in any room"))
                            continue
                        player_list = [[player, _ , ready] for player, _ , ready in player_room["players"]]
                        send_json(conn, response_format(action=action, result="ok", data={"players": player_list, "host": player_room["host"], "room_password": player_room["room_password"]}, msg=""))
                    elif action == "leave_room":
                        if player_room is None:
                            send_json(conn, response_format(action=action, result="error", data={}, msg="You are not in any room"))
                            continue
                        # remove player from room
                        player_room["players"] = [[player, addr, ready] for player, addr, ready in player_room["players"] if player != username]
                        # host leave
                        if player_room["host"] == username:
                            for player, player_addr, ready in player_room["players"]:
                                player_conn = player_sockets[player_addr]["conn"]
                                send_json(player_conn, response_format(action="room_closed", result="ok", data={}, msg="Host closed the room!"))
                                DB_request(DB_type.PLAYER, "update", {"username": player, "status": STATUS_DB.LOBBY})
                            player_room["players"] = []

                        # update player status
                        DB_request(DB_type.PLAYER, "update", {"username": username, "status": STATUS_DB.LOBBY})
                        send_json(conn, response_format(action=action, result="ok", data={}, msg="Left room successfully"))
                        # notify other players about player leaving
                        for player, player_addr, _ in player_room["players"]:
                            player_conn = player_sockets[player_addr]["conn"]
                            send_json(player_conn, response_format(action="room_update", result="ok", data={"players": player_room["players"]}, msg=f"Player {username} left the room"))

                        if player_room["players"] == []:
                            # close room
                            del rooms[gamename][room_id]
                    elif action == "ready_up":
                        idx = 0
                        for player, playeraddr, ready in player_room["players"]:
                            if player == username:
                                player_room["players"][idx][2] = True if not player_room["players"][idx][2] else False
                                break
                            idx += 1
                        send_json(conn, response_format(action=action, result="ok", data={}, msg="Ready" if ready else "Cancel ready"))
                        

                        host_addr = player_room["players"][0][1]
                        host_sock = player_sockets[host_addr]["conn"]
                        send_json(host_sock, response_format(action="player_ready", result="ok", data={}, msg=f"player {username}" + (" ready" if ready else " unready")))
                    elif action == "start_game":
                        # TODO check the player in the room is all ready.
                        cnt = 0
                        for player, playeraddr, ready in player_room["players"]:
                            if ready:
                                cnt += 1
                            else:
                                break
                        if cnt != player_room["max_players"]:
                            send_json(conn, response_format(action=action, result="error", data={"type": "wait"}, msg="Not everyone is ready!"))
                        # check game version
                        gamedir = GAME_STORE_DIR / game
                        if not gamedir.exists():
                            for player, player_addr, ready in player_room["players"]:
                                player_conn = player_sockets[player_addr]["conn"]
                                send_json(player_conn, response_format(action="room_closed", result="ok", data={}, msg="Game have been removed."))
                                DB_request(DB_type.PLAYER, "update", {"username": player, "status": STATUS_DB.LOBBY})
                            del rooms[gamename][room_id]
                            continue
                        # read config.json
                        with open(gamedir / "config.json", "r") as f:
                            config = f.read()
                            # turn string into dict
                            import json
                            config = json.loads(config)
                       
                        # if not same version, notify all player to update game, and leave room
                        if player_room["version"] != config["version"]:
                            for player, player_addr, ready in player_room["players"]:
                                player_conn = player_sockets[player_addr]["conn"]
                                send_json(player_conn, response_format(action="room_closed", result="ok", data={}, msg="Please update the game version!"))
                                DB_request(DB_type.PLAYER, "update", {"username": player, "status": STATUS_DB.LOBBY})
                            del rooms[gamename][room_id]
                        # if ok -> play game
                        # fork a thread to run game server at given addr, port
                        # sent the port information to all player in room

                        # wait for game end.
                        # return to the room ...
    except (ConnectionError, OSError) as e:
        logger.info(f"[!] {addr} disconnected: {e}")
    finally:
        conn.close()
        player_sockets.pop(addr)
        logger.info(f"[*] closed {addr}")
        if username != None:
            # set to logout
            DB_request(DB_type.PLAYER, "update", {"username": username, "status":STATUS_DB.INIT, "token":None})

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((LOBBY_HOST, LOBBY_PORT))
        srv.listen(128)
        logger.info(f"[*] Player server Listening on {LOBBY_HOST}:{LOBBY_PORT}")
        while True:
            try:
                conn, addr = srv.accept()
            except KeyboardInterrupt:
                logger.info("[*] Shutting down Lobby server...")
                break
            player_sockets[addr] = {"conn":conn, "username": None}
            th = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            th.start()

if __name__ == "__main__":
    main()