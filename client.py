import config
from Player.player import PLAYER
from Developer.developer import DEVELOPER

def main():
    while True:
        client = PLAYER(config.LOBBY_HOST, config.LOBBY_PORT)
        if not client.change_mode and client.exit:
            break
        client = DEVELOPER(config.DEV_HOST, config.DEV_PROT)
        if not client.change_mode and client.exit:
            break
if __name__ == '__main__':
    main()