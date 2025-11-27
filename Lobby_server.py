import socket, threading, uuid
from loguru import logger
import config, TCP_tool

def handle_client(conn: socket.socket, addr):
    TCP_tool.set_keepalive(conn)
    logger.info(f"[*] connected from {addr}")
    try:
        print("ok")
    except (ConnectionError, OSError) as e:
            logger.info(f"[!] {addr} disconnected: {e}")
    finally:
        conn.close()
        logger.info(f"[*] closed {addr}")

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((config.LOBBY_HOST, config.LOBBY_PORT))
        srv.listen(128)
        logger.info(f"[*] Listening on {config.LOBBY_HOST}:{config.LOBBY_HOST}")
        while True:
            conn, addr = srv.accept()
            th = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            th.start()


if __name__ == "__main__":
    main()