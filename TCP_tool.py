import socket, json, struct
def set_keepalive(sock):
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    try:
        import platform
        if platform.system() == "Linux":
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 20)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
    except Exception:
        pass

def recvn(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed")
        buf += chunk
    if len(buf) > 65536:
        return {}
    
    return buf

def send_json(sock: socket.socket, obj: dict):
    body = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    hdr = struct.pack("!I", len(body))
    sock.sendall(hdr + body)

def recv_json(sock: socket.socket) -> dict:
    n = struct.unpack("!I", recvn(sock, 4))[0]
    # print server msg
    if n > 65536:
        return {}
    return json.loads(recvn(sock, n).decode("utf-8"))