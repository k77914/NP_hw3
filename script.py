import subprocess
# # 指定 conda 環境名稱
# env_name = "myenv"
# scripts = ["script1.py", "script2.py"]

# processes = []
# for s in scripts:
#     # 用 conda run 啟動指定環境
#     p = subprocess.Popen(["conda", "run", "-n", env_name, "python", s])
#     processes.append(p)

# for p in processes:
#     p.wait()

# 啟動多個腳本
env_name = "NP_hw3"
processes = []
scripts = ["Lobby_server.py", "DB_server.py", "Developer_server.py"]

for s in scripts:
    p = subprocess.Popen(["conda", "run", "-n", env_name, "python", s])
    processes.append(p)

# 等待所有腳本結束
for p in processes:
    p.wait()
