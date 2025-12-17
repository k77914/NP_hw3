import socket, threading, uuid
from loguru import logger
from NP_hw3.config import DEV_HOST, DEV_PORT, DB_HOST, DB_PORT, GAME_STORE_PATH
from NP_hw3.TCP_tool import send_json, recv_json, set_keepalive
import os
import pathlib
class STATUS():
    INIT = 0
    LOBBY = 1
class STATUS_DB():
    INIT = "offline"
    LOBBY = "lobby"
class DB_type():
    PLAYER = "player_db"
    DEVELOPER = "developer_db"
    ROOM = "room_db"
    GAME_STORE = "game_store_db"



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
                        resp_db_query = DB_request(DB_type.DEVELOPER, "query", {"username" : regi_name})
                        if resp_db_query == {}:
                            DB_request(DB_type.DEVELOPER, "create", request_data)
                            send_json(conn, response_format(action=action, result="ok", data={}, msg="Register succuessfully"))
                        else:
                            send_json(conn, response_format(action, "error", {}, msg="Fail, change another username"))
                    elif action == "login":
                        login_name = request_data["username"]
                        resp_db_query = DB_request(DB_type.DEVELOPER, "query", {"username" : login_name})
                        # Not find
                        if resp_db_query == {}:
                            send_json(conn, response_format(action=action, result="error", data={}, msg="Account doesn't exist!"))
                        elif resp_db_query["password"] != request_data["password"]:
                            send_json(conn, response_format(action=action, result="error", data={}, msg="Wrong password!"))
                        elif resp_db_query["status"] != STATUS_DB.INIT:
                            send_json(conn, response_format(action=action, result="error", data={}, msg="Account has logined!"))
                        else:
                            username = login_name
                            token_srv = uuid.uuid4().hex
                            DB_request(DB_type.DEVELOPER, "update", {"username": username, "status": STATUS_DB.LOBBY, "token": token_srv})
                            send_json(conn, response_format(action=action, result="ok", data={"token": token_srv}, msg="Login successfully!"))
                    else:
                        send_json(conn, response_format(action=action, result="error", data={}, msg="Unknown operation"))
                case STATUS.LOBBY:
                    if token != token_srv:
                        # Not matching token, logout!
                        username = None
                        token_srv = None
                        DB_request(DB_type.DEVELOPER, "update", {"username": username, "status": STATUS_DB.INIT, "token": None})
                        send_json(conn, response_format(action=action, result="token miss", data={"status_change": STATUS.INIT}, msg="Miss matching token, logout"))

                    if action == "update_game":
                        # receive game data and update to game store db
                        game_data = request_data
                        # update config data to DB
                        logger.info(f"Updating game '{game_data}' to GAME_STORE DB")
                        DB_request(DB_type.GAME_STORE, "update", game_data)
                        # update files on server side
                        # create path to store game files
                        create_path = pathlib.Path(GAME_STORE_PATH)
                        folder_name = game_data["gamename"] + "_" + username
                        os.makedirs(create_path / folder_name, exist_ok=True)
                        # store config file
                        with open(create_path / folder_name / "config.json", 'w') as f:
                            import json
                            json.dump(game_data['config'], f, indent=4)
                        # store each file
                        for filename, filecontent in game_data['files'].items():
                            with open(create_path / folder_name / filename, 'wb') as f:
                                f.write(filecontent.encode('utf-8'))  # assuming filecontent is str, encode to bytes
                        
                        send_json(conn, response_format(action=action, result="ok", data={}, msg="Update game successfully!"))

                    elif action == "manage_game":
                        # fetch all games from game store db
                        resp_db_query = DB_request(DB_type.GAME_STORE, "query", {"username": username, "gamename": None})
                        send_json(conn, response_format(action=action, result="ok", data={"game_list": resp_db_query}, msg="Fetch game list successfully!"))

                    elif action == "upload_game":
                        # receive game data and store to game store db
                        game_data = request_data
                        # create game folder under GameStore, on server side
                        # create path to store game files
                        create_path = pathlib.Path(GAME_STORE_PATH)
                        folder_name = game_data["gamename"] + "_" + username
                        os.makedirs(create_path / folder_name, exist_ok=True)
                        # store config file
                        # game_data['config']["comments"] = []
                        with open(create_path / folder_name / "config.json", 'w') as f:
                            import json
                            json.dump(game_data['config'], f, indent=4)
                        # store each file
                        for filename, filecontent in game_data['files'].items():
                            with open(create_path / folder_name / filename, 'wb') as f:
                                f.write(filecontent.encode('utf-8'))  # assuming filecontent is str, encode to bytes
                        
                        # only store config data to DB
                        del game_data['files']
                        logger.info(f"Storing game '{game_data}' to GAME_STORE DB")
                        DB_request(DB_type.GAME_STORE, "create", game_data)
                        send_json(conn, response_format(action=action, result="ok", data={}, msg="Upload game successfully!"))

                    elif action == "delete_game":
                        game_data = request_data
                        # delete from DB
                        logger.info(f"Deleting game '{game_data}' from GAME_STORE DB")
                        create_path = pathlib.Path(GAME_STORE_PATH)
                        folder_name = game_data["gamename"] + "_" + username
                        game_data = {"gamename": folder_name}                        
                        DB_request(DB_type.GAME_STORE, "delete", game_data)
                        # delete files on server side
                        # create path to store game files

                        import shutil
                        shutil.rmtree(create_path / folder_name, ignore_errors=True)
                        send_json(conn, response_format(action=action, result="ok", data={}, msg="Delete game successfully!"))

                    elif action == "logout":
                        DB_request(DB_type.DEVELOPER, "update", {"username": username, "status": STATUS_DB.INIT, "token": None})
                        send_json(conn, response_format(action=action, result="ok", data={}, msg="Logout successfully!"))
                        username = None
                        token_srv = None
                    else:
                        logger.info(f"Unknown action {action} from {addr}")
                        send_json(conn, response_format(action=action, result="error", data={}, msg="Unknown operation"))


    except (ConnectionError, OSError) as e:
        logger.info(f"[!] {addr} disconnected: {e}")
    finally:
        conn.close()
        logger.info(f"[*] closed {addr}")
        if username != None:
            # set to logout
            DB_request(DB_type.DEVELOPER, "update", {"username": username, "status":STATUS_DB.INIT, "token":None})

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((DEV_HOST, DEV_PORT))
        srv.listen(128)
        logger.info(f"[*] Developer server Listening on {DEV_HOST}:{DEV_PORT}")
        while True:
            try:
                conn, addr = srv.accept()
            except KeyboardInterrupt:
                logger.info("[*] Shutting down Developer server...")
                break
            th = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            th.start()

if __name__ == "__main__":
    main()