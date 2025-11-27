import subprocess

# 啟動多個腳本
processes = []
scripts = ["Lobby_server.py", "DB_server.py", "Developer_server.py"]

for s in scripts:
    p = subprocess.Popen(["python", s])
    processes.append(p)

# 等待所有腳本結束
for p in processes:
    p.wait()
