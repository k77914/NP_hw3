import socket, threading, uuid
from loguru import logger
from config import LOBBY_HOST, LOBBY_PORT, DB_HOST, DB_PORT
from TCP_tool import send_json, recv_json, set_keepalive

class STATUS():
    INIT = 0
    LOBBY = 1

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
                        # TODO send request to DB
                        pass
                    elif action == "login":
                        # TODO send request to DB
                        pass
                    else:
                        send_json(conn, response_format(action=action, result="error", data={}, msg=""))
                case STATUS.LOBBY:
                    pass

    except (ConnectionError, OSError) as e:
            logger.info(f"[!] {addr} disconnected: {e}")
    finally:
        conn.close()
        logger.info(f"[*] closed {addr}")

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((LOBBY_HOST, LOBBY_PORT))
        srv.listen(128)
        logger.info(f"[*] Listening on {LOBBY_HOST}:{LOBBY_HOST}")
        while True:
            conn, addr = srv.accept()
            th = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            th.start()

if __name__ == "__main__":
    main()