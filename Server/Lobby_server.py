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
                        if config["version"] == user_version:
                            send_json(conn, response_format(action=action, result="ok", data={}, msg="You have the latest version"))
                        else:
                            send_json(conn, response_format(action=action, result="error"), data={}, msg="New version released!")
                    elif action == "create_room":
                        # use dict
                        room_info = {
                            "host": username,
                            "players": [(username, addr)],
                            "room_password": request_data.get("room_password", "")
                        }
                        gamename = request_data["gamename"]
                        if gamename not in rooms:
                            rooms[gamename] = {}
                        rooms[gamename][username] = room_info
                        # update player status
                        DB_request(DB_type.PLAYER, "update", {"username": username, "status": STATUS_DB.ROOM})
                        send_json(conn, response_format(action=action, result="ok", data={"room_id": username}, msg="Room created successfully"))

                    elif action == "list_rooms":
                        gamename = request_data["gamename"]
                        if gamename not in rooms:
                            rooms[gamename] = {}
                        room_list = []
                        with open(GAME_STORE_DIR / gamename / "config.json", "r") as f:
                            config = f.read()
                        max_players = config.get("max_players", 2)
                        for room_id, info in rooms[gamename].items():
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
                        if room_info["room_password"] != room_password:
                            send_json(conn, response_format(action=action, result="error", data={}, msg="Wrong room password"))
                            continue
                        room_info["players"].append((username, addr))
                        # update player status
                        DB_request(DB_type.PLAYER, "update", {"username": username, "status": STATUS_DB.ROOM})
                        send_json(conn, response_format(action=action, result="ok", data={}, msg="Joined room successfully"))
                    elif action == "logout":
                        username = None
                        token_srv = None
                        DB_request(DB_type.PLAYER, "update", {"username": username, "status": STATUS_DB.INIT, "token": None})
                        send_json(conn, response_format(action=action, result="ok", data={}, msg="Logout successfully!"))
                    else:
                        send_json(conn, response_format(action=action, result="error", data={}, msg="Unknown operation"))

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
            conn, addr = srv.accept()
            player_sockets[addr] = {"conn":conn, "username": None}
            th = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            th.start()

if __name__ == "__main__":
    main()