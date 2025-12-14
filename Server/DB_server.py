import uuid ,socket, threading, queue, copy, os, json, tempfile, time  #  For random user IDs and room IDs
from loguru import logger
from NP_hw3.config import DB_HOST, DB_PORT, LOBBY_HOST, DEV_HOST # addr
from NP_hw3.config import PLAYER_JSON, DEVELOPER_JSON, ROOM_JSON, GAME_STORE_JSON
from NP_hw3.TCP_tool import set_keepalive, send_json, recv_json
class DB:
    def __init__(self, path: str, commit_interval: float = 0.5, max_batch: int = 64):
        self.path = path
        self.commit_interval = commit_interval
        self.max_batch = max_batch

        self._lock = threading.RLock()
        self._q = queue.Queue()
        self._state = self._load_file() 

        self._stop_evt = threading.Event()
        self._writer = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer.start()
        # print(f"[*] DB initialized from {self.path}")

    #===================== Socket API ==============================#
    def create(self, new_data: dict):
        self._q.put(("create", new_data))

    def read(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._state)

    def update(self, new_data: dict):
        self._q.put(("update", new_data))
    
    def delete(self, remove_data: dict):
        self._q.put(("delete", remove_data))

    def query(self) -> dict:
        #  Do nothing in parent but children class.
        return
    def shutdown(self):
        self._q.put(("__stop__", None))
        self._stop_evt.wait(timeout=3.0)
    
    #==================== Inner declaration for function ===========#
    def _load_file(self) -> dict:
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({}, f)
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {}
                return data
        except (json.JSONDecodeError, OSError):
            return {}
    def _writer_loop(self):
        #  Do nothing in parent but children class.
        return
    def _atomic_write(self, data: dict):
        """write into tempfile → flush+fsync → os.replace (atomic)"""
        dir_ = os.path.dirname(self.path) or "."
        fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=dir_, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        finally:
            try:
                os.remove(tmp)
            except FileNotFoundError:
                pass
#==================== Inner logic for different DB==============================#
class UDB(DB):
    def query(self, data):
        with self._lock:
            userlist = self._state  # 直接使用 _state 而非 read()
            if data["username"] in userlist:
                return copy.deepcopy(userlist[data["username"]])
            return {}

    def _writer_loop(self):
        dirty = False
        batch = 0
        last_flush = time.time()
        while True:
            timeout = max(0.0, self.commit_interval - (time.time() - last_flush))
            try:
                op, args = self._q.get(timeout=timeout)
            except queue.Empty:
                op = None
            if op == "__stop__":
                if dirty:
                    with self._lock:
                        self._atomic_write(self._state)
                self._stop_evt.set()
                return

            if op == "create":
                with self._lock:
                    new_account = {
                        "password": args["password"],
                        "status": "offline",
                        "token": ""
                    }
                    self._state[args["username"]] = new_account
                    dirty = True
                    batch += 1

            if op == "update":
                with self._lock:
                    if args["username"] in self._state:
                        self._state[args["username"]]["status"] = args.get("status", self._state[args["username"]]["status"])
                        self._state[args["username"]]["token"] = args.get("token", self._state[args["username"]]["token"])
                        dirty = True
                        batch += 1

            if op == "delete":
                with self._lock:
                    if args["username"] in self._state:
                        del self._state[args["username"]]
                        dirty = True
                        batch += 1

            if op is None:
                # no request -> if dirty -> update
                if dirty:
                    with self._lock:
                        self._atomic_write(self._state)
                    dirty = False
                    batch = 0
                    last_flush = time.time()
                continue

            if batch >= self.max_batch:
                with self._lock:
                    self._atomic_write(self._state)
                dirty = False
                batch = 0
                last_flush = time.time()

class DDB(DB):
    def query(self, data):
        with self._lock:
            userlist = self._state  # 直接使用 _state 而非 read()
            if data["username"] in userlist:
                return copy.deepcopy(userlist[data["username"]])
            return {}

    def _writer_loop(self):
        dirty = False
        batch = 0
        last_flush = time.time()
        while True:
            timeout = max(0.0, self.commit_interval - (time.time() - last_flush))
            try:
                op, args = self._q.get(timeout=timeout)
            except queue.Empty:
                op = None
            if op == "__stop__":
                if dirty:
                    with self._lock:
                        self._atomic_write(self._state)
                self._stop_evt.set()
                return

            if op == "create":
                with self._lock:
                    new_account = {
                        "password": args["password"],
                        "status": "offline",
                        "token": "",
                        "download": {},
                        "mailbox": []
                    }
                    self._state[args["username"]] = new_account
                    dirty = True
                    batch += 1

            if op == "update":
                # TODO for download
                with self._lock:
                    if args["username"] in self._state:
                        self._state[args["username"]]["status"] = args.get("status", self._state[args["username"]]["status"])
                        self._state[args["username"]]["token"] = args.get("token", self._state[args["username"]]["token"])
                        if args.get("inv_msg", []) != "clear" and args.get("inv_msg", []) != []: # get inv msg
                                self._state[args["username"]]["mailbox"].extend([args.get("inv_msg", [])])
                        elif args.get("inv_msg", []) == "clear":
                            self._state[args["username"]]["mailbox"] = []
                        dirty = True
                        batch += 1

            if op == "delete":
                with self._lock:
                    if args["username"] in self._state:
                        del self._state[args["username"]]
                        dirty = True
                        batch += 1

            if op is None:
                # no request -> if dirty -> update
                if dirty:
                    with self._lock:
                        self._atomic_write(self._state)
                    dirty = False
                    batch = 0
                    last_flush = time.time()
                continue

            if batch >= self.max_batch:
                with self._lock:
                    self._atomic_write(self._state)
                dirty = False
                batch = 0
                last_flush = time.time()

class GSDB(DB):
    def query(self, data):
        with self._lock:
            gamelist = self._state  # 直接使用 _state 而非 read()
            logger.info(f"GSDB query with data: {data}")
            if data["gamename"] is None:
                # return all games from a developer
                result = {}
                logger.info(f"{gamelist}")
                for gname, gconfig in gamelist.items():
                    if gconfig["author"] == data["username"]:
                        result[gname] = copy.deepcopy(gconfig)
                logger.info(f"GSDB query result: {result}")
                return result
            
            if data["gamename"]+"_"+data["username"] in gamelist:
                return copy.deepcopy(gamelist[data["gamename"]+"_"+data["username"]])
            return {}

    def _writer_loop(self):
        dirty = False
        batch = 0
        last_flush = time.time()
        while True:
            timeout = max(0.0, self.commit_interval - (time.time() - last_flush))
            try:
                op, args = self._q.get(timeout=timeout)
            except queue.Empty:
                op = None
            if op == "__stop__":
                if dirty:
                    with self._lock:
                        self._atomic_write(self._state)
                self._stop_evt.set()
                return

            if op == "create":
                with self._lock:
                    self._state[args["gamename"]+"_"+args["username"]] = args["config"]
                    dirty = True
                    batch += 1

            if op == "update":
                with self._lock:
                    if args["gamename"]+"_"+args["username"] in self._state:
                        self._state[args["gamename"]+"_"+args["username"]] = args["config"]
                        dirty = True
                        batch += 1

            if op == "delete":
                with self._lock:
                    if args["gamename"] in self._state:
                        del self._state[args["gamename"]]
                        dirty = True
                        batch += 1

            if op is None:
                # no request -> if dirty -> update
                if dirty:
                    with self._lock:
                        self._atomic_write(self._state)
                    dirty = False
                    batch = 0
                    last_flush = time.time()
                continue

            if batch >= self.max_batch:
                with self._lock:
                    self._atomic_write(self._state)
                dirty = False
                batch = 0
                last_flush = time.time()

def DB_handle_requset(conn: socket.socket, addr):
    set_keepalive(conn)
    if addr[0] != LOBBY_HOST and addr[0] != DEV_HOST:
        logger.info("Invalid Accessing from other host : ", addr)
        send_json(conn, {})
        conn.close()
        return
    try:
        #  receive request
        req = recv_json(conn)
        Database = DB_DICT[req["type"]]
        resp = {}
        logger.info(f"Request from {addr}: {req}")
        match req["action"]:
            case "create":
                Database.create(req["data"])
            case "read":
                resp = Database.read()
            case "update":
                Database.update(req["data"])
            case "delete":
                Database.delete(req["data"])
            case "query":
                resp = Database.query(req["data"])
            case _:
                logger.info(f"DB_handle_request: unknown action {req['action']}")
                resp = {} #  design a ERROR response
        send_json(conn, resp)
    except (ConnectionError, OSError) as e:
        logger.info(f"[!] {addr} disconnected: {e}")
    finally:
        try: conn.shutdown(socket.SHUT_RDWR)
        except: pass
        conn.close()
        logger.info(f"[*] closed {addr}")


    conn.close()


def main():
    global player_db, developer_db, game_store_db#, room_db, DB_DICT
    global DB_DICT
    player_db = UDB(PLAYER_JSON)
    developer_db = DDB(DEVELOPER_JSON)
    game_store_db = GSDB(GAME_STORE_JSON)
    # TODO other db    
    
    DB_DICT = {"player_db": player_db, "developer_db": developer_db, "game_store_db": game_store_db} #, "room_db": room_db, "game_store_db": game_store_db}

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as DBsrv:
        DBsrv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        DBsrv.bind((DB_HOST, DB_PORT))
        DBsrv.listen(128)
        logger.info(f"[*] DB server Listening on {DB_HOST}:{DB_PORT}")
        while True:
            conn, addr = DBsrv.accept()
            th = threading.Thread(target=DB_handle_requset, args=(conn, addr), daemon=True)
            th.start()
main()