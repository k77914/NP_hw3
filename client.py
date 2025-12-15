from NP_hw3.Player.player import PLAYER
from NP_hw3.Developer.developer import DEVELOPER

def main():
    while True:
        try:
            client = PLAYER()
            client.start()
            if not client.change_mode and client.exit:
                break
            client = DEVELOPER()
            client.start()
            if not client.change_mode and client.exit:
                break
        except KeyboardInterrupt:
            print("\nExiting the client. Goodbye!")
            break
if __name__ == '__main__':
    main()