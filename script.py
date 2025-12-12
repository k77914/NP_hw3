import subprocess
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# env_name = "NP_hw3"
processes = []

scripts = [
    os.path.join(BASE_DIR, "Server.Lobby_server.py"),
    os.path.join(BASE_DIR, "Server.DB_server.py"),
    os.path.join(BASE_DIR, "Server.Developer_server.py"),
]

for s in scripts:
    p = subprocess.Popen(["python", "-m", "NP_hw3." + os.path.basename(s).replace(".py","")])
    # p = subprocess.Popen(["python", s])
    # print(s)
    processes.append(p)

for p in processes:
    p.wait()
