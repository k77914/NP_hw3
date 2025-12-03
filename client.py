from Player.player import PLAYER
from Developer.developer import DEVELOPER

def main():
    while True:
        client = PLAYER()
        client.start()
        if not client.change_mode and client.exit:
            break
        client = DEVELOPER()
        client.start()
        if not client.change_mode and client.exit:
            break
if __name__ == '__main__':
    main()