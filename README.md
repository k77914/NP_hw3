# NP_hw3 線上遊戲商店
本次作業實作一個簡易的線上遊戲商店系統，涵蓋伺服端、開發者端與玩家端的完整流程。開發者可以在本地建立遊戲、上傳到商店並進行版本管理；玩家可以瀏覽商店、下載遊戲並透過建立/加入房間與其他人遊玩。伺服端負責保存帳號與遊戲資料、管理房間並動態啟動遊戲伺服程式。

蔡烝旭 (Student ID: 112550099)

## 環境需求
Python：建議使用 Python 3.9 以上版本。
==第三方套件==
pygame – 遊戲開發可用之圖形庫，部分範本使用；

## 專案結構說明

專案根目錄下的 NP_hw3/ 為 Python 套件，其內重要目錄/檔案如下：
**路徑與說明**
* Server/DB_server.py	資料庫伺服端：以 JSON 檔案保存玩家、開發者、房間與遊戲商店資訊，支援建立/查詢/更新/刪除請求，並以後台執行緒定期寫入檔案。
* Server/Developer_server.py	開發者伺服端：處理開發者註冊、登入、遊戲上傳/更新/刪除等請求，並將遊戲檔案寫入 Server/GameStore 目錄。
* Server/Lobby_server.py	大廳伺服端：處理玩家註冊、登入、瀏覽商店、下載遊戲、建立/加入房間及留言等功能，必要時啟動遊戲伺服端。
* Server/GameStore/	存放已上架遊戲及其伺服程式、配置檔與說明文件，資料夾名稱格式為 <遊戲名稱>_<作者>。
* Server/Storage_json/	儲存 player.json、developer.json、room.json、game_store.json 等資料庫檔案。
---
* Developer/developer.py	開發者端命令列介面；提供註冊/登入、管理上架遊戲、上傳遊戲與快速建立遊戲模板等功能。
* Developer/game_local/	開發者本地工作區，包含三種遊戲範本 (template_CUI、template_GUI、template_CUI_3)；快速建立遊戲模板時會複製此目錄。
---
* Player/player.py	玩家端命令列介面；提供註冊/登入、瀏覽商店、下載遊戲、查看/撰寫留言、建立/加入房間及啟動遊戲等功能。
* Player/download/	玩家下載遊戲後的存放目錄，依遊戲名稱與作者建立子資料夾。
---
* client.py	整合開發者與玩家介面的程式，執行後會先進入玩家模式並可在兩種模式間切換。
* script.py	一鍵啟動三個伺服端的腳本。
* clear_storage.py	清空暫存資料與 JSON DB 的工具，方便重新測試。

## 快速開始
以下步驟假定已安裝 Python 並已進入含有 NP_hw3 套件的資料夾。

3.1 安裝依賴
```bash
pip install pygame pysym?
```
3.2 清理舊有資料（可選）

若要從乾淨環境開始，可執行下列指令清除開發者工作區、玩家下載目錄、伺服端遊戲資料與資料庫：
``` bash
python -m NP_hw3.clear_storage
```
此指令僅會刪除 Developer/game_local、Player/download、Server/GameStore 及 Server/Storage_json 中的檔案，模板目錄會被保留。

### 啟動伺服端

在專案根目錄執行以下指令啟動所有伺服端：
``` bash
python -m NP_hw3.script
```
此腳本會分別啟動資料庫伺服端 (DB_server.py)、開發者伺服端 (Developer_server.py) 與大廳伺服端 (Lobby_server.py)，並輸出日誌。如果需要單獨啟動，可分別執行下列指令（須開三個終端）：
``` bash
python -m NP_hw3.Server.DB_server
python -m NP_hw3.Server.Developer_server
python -m NP_hw3.Server.Lobby_server
```
### 啟動客戶端

另開一個終端，於專案根目錄執行：
``` bash
python -m NP_hw3.client
```
程式會先進入玩家模式；若想切換至開發者模式，可在主選單選擇對應選項。按 Ctrl+C 可中斷目前操作。

## 玩家模式操作說明
玩家模式的狀態機分為 INIT、LOBBY、ROOM 與 INGAME 四個階段，介面皆以命令列呈現。

### 帳號註冊與登入

註冊：選擇選項 Register 後輸入帳號及密碼；若帳號不存在，資料庫會建立新玩家並回傳成功訊息。

登入：選擇 Login 後輸入帳號及密碼；若密碼正確且帳號未登入，伺服端會回傳 token 並切換至 LOBBY 狀態。

### 遊戲商店

在 LOBBY 狀態選擇 Open Game Store 可查看所有上架的遊戲。選擇某一遊戲後可：

查看詳細資料 – 顯示名稱、作者、版本號、最大玩家數、類型及最後更新時間。

下載遊戲 – 將選定遊戲的程式及 config.json 下載至 Player/download/<遊戲名稱_作者>/；下載後便可以遊玩。

查看留言 – 列出其他玩家的留言與發表者及時間戳；若尚無留言會提示。

撰寫留言 – 僅限曾遊玩過此遊戲的玩家；留言內容會在商店中公開。

### 遊玩遊戲

在 LOBBY 狀態選擇 Play Game 可啟動遊戲。步驟如下：

選擇已下載的遊戲。

客戶端向大廳伺服端比對版本；若有新版本可選擇自動更新或返回。

選擇建立房間或加入房間：

建立房間 – 可設定密碼；伺服端會產生房號、儲存房間資訊並動態啟動遊戲伺服端 <gamename>_server.py，玩家進入 ROOM 狀態等待其他玩家。

加入房間 – 列出目前可加入的房間（顯示房號、目前人數及是否有密碼）；輸入房號（及密碼）後加入房間。

當人數達到 config.json 中的 max_players 且房主啟動遊戲後，客戶端會執行 <gamename>_client.py 與遊戲伺服端互動，進入 INGAME 狀態。遊戲結束後自動返回 LOBBY。遊戲的具體規則與互動流程可參考下載資料夾中的 <gamename>_readme.txt。

## 開發者模式操作說明

開發者模式包含兩個狀態：INIT 與 LOBBY。

### 帳號註冊與登入

操作流程與玩家模式類似，登入後伺服端會回傳 token 以識別會話。

### 管理已上架遊戲

在 LOBBY 狀態選擇 Manage your game on game store，伺服端會回傳該開發者上架的所有遊戲清單。選擇某遊戲後可：

檢視詳細資訊 – 列出伺服端儲存的配置。

更新遊戲 – 修改版本號（須大於舊版本）與其他欄位，並重新讀取本地檔案上傳；伺服端會覆寫舊資料。

刪除遊戲 – 自遊戲商店刪除指定遊戲並移除伺服端存放的檔案。

### 上傳遊戲至商店

選擇 Upload your game to game store 會要求選擇一個位於 Developer/game_local/<username> 的遊戲資料夾。程式將讀取其中的 config.json 及所有 .py/.txt/.md 檔案並透過開發者伺服端上傳。首次上傳時伺服端在 GameStore/<遊戲名稱_作者>/ 建立資料夾並加入 config.json 欄位 comments。更新遊戲時僅更新配置與檔案內容。

### 快速建立遊戲模板

選擇 Fast start to create game 可以快速建立一個遊戲範本並填寫簡易資料：

選擇範本類型：CUI (2人)、GUI (2人) 或 CUI (3人)。

輸入遊戲名稱。

程式會將對應模板目錄 (template_CUI、template_GUI 或 template_CUI_3) 複製至 Developer/game_local/<username>/<gamename>，並將模板檔案改名為 <gamename>_client.py、<gamename>_server.py、<gamename>_readme.txt，同時產生初始 config.json。

開發者可以修改產生的程式以實作遊戲邏輯，完成後再透過「上傳遊戲」功能將遊戲發布到商店。