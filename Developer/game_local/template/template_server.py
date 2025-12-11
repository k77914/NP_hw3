import socket
import json
import sys
import threading
from ....config import LOBBY_HOST, LOBBY_PORT_GAMESERVER
from ....TCP_tool import recv_json, send_json, set_keepalive

PLAYER_NUM = 2

class GAME():
    def __init__(self, player_conns: list):
        self.player_conns = player_conns  # list of (conn, addr)
        self.scores = [0 for _ in range(len(player_conns))]
        self.current_turn = 0  # index of current player's turn

    def start(self):
        # Notify players that the game is starting
        for idx, (conn, addr) in enumerate(self.player_conns):
            send_json(conn, {"action": "start_game", "player_index": idx})
        
        # Main game loop
        while not self.is_game_over():
            current_conn, _ = self.player_conns[self.current_turn]
            send_json(current_conn, {"action": "your_turn"})
            
            # Wait for player's move
            move = recv_json(current_conn)
            self.process_move(self.current_turn, move)
            
            # Notify all players about the move
            for conn, _ in self.player_conns:
                send_json(conn, {"action": "player_move", "player_index": self.current_turn, "move": move})
            
            # Switch to next player's turn
            self.current_turn = (self.current_turn + 1) % len(self.player_conns)
        
        # Notify players that the game is over
        for conn, _ in self.player_conns:
            send_json(conn, {"action": "game_over", "scores": self.scores})

    def process_move(self, player_index, move):
        # Process the player's move and update scores accordingly
        self.scores[player_index] += move.get("points", 0)

    def is_game_over(self):
        # Define game over condition
        return max(self.scores) >= 10  # Example condition: first to reach 10 points
    

def check_connection(srv: socket.socket, results: list):
    """Listen on `srv`, accept one connection and append (conn, addr) to results."""
    try:
        srv.listen(1)
        conn, addr = srv.accept()
        # set TCP keepalive if helper available
        try:
            set_keepalive(conn)
        except Exception:
            pass
        results.append((conn, addr))
    except Exception as e:
        # On error, append the exception so caller can notice
        results.append(e)
    
# Two player, CUI template
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python game_server.py <room_id>")
        sys.exit(1)
        
    room_id = sys.argv[1]
    # host and port are needed to be sent to the client server.
    player_socket_list = []   # list of (host, port) to advertise to lobby
    player_connections = []   # list to collect accepted (conn, addr) tuples
    pthread = []
    for _ in range(PLAYER_NUM):
        psock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # bind to any address, let OS pick port
        psock.bind(("", 0))
        addr = psock.getsockname()

        player_socket_list.append(addr)
        th = threading.Thread(target=check_connection, args=(psock, player_connections))
        th.daemon = True
        th.start()
        pthread.append(th)

    server_information = {"roomid": room_id, "sockets": player_socket_list}

    lobby_sock = None
    try:
        # create socket connecting to lobbyserver.
        lobby_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lobby_sock.connect((LOBBY_HOST, LOBBY_PORT_GAMESERVER))
        send_json(lobby_sock, {"game_server": server_information})       
        # Waiting for all player connect to game.
        for p in pthread:
            p.join()
        
        # start the game
        game = GAME(player_connections)
        game.start()

        
    except Exception as e:
        print(f"{e}")
    finally:
        if lobby_sock is not None:
            try:
                lobby_sock.close()
            except Exception:
                pass