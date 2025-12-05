import subprocess
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# env_name = "NP_hw3"
processes = []

scripts = [
    os.path.join(BASE_DIR, "Lobby_server.py"),
    os.path.join(BASE_DIR, "DB_server.py"),
    os.path.join(BASE_DIR, "Developer_server.py"),
]

for s in scripts:
    # p = subprocess.Popen(["conda", "run", "-n", env_name, "python", s])
    p = subprocess.Popen(["python", s])
    # print(s)
    processes.append(p)

for p in processes:
    p.wait()
