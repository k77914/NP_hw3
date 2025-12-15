from pathlib import Path
import shutil
import sys

# 你要清空的資料夾（相對於 NP_hw3 專案根目錄）
TARGET_DIRS = [
    Path("Developer/game_local"),
    Path("Player/download"),
    Path("Server/GameStore"),
    Path("Server/Storage_json"),
]

def clear_dir(dir_path: Path, project_root: Path, dry_run: bool = False) -> None:
    # 安全檢查：避免意外刪到專案外
    resolved_dir = (project_root / dir_path).resolve()
    if project_root not in resolved_dir.parents and resolved_dir != project_root:
        raise RuntimeError(f"安全檢查失敗：{resolved_dir} 不在專案目錄內，停止執行。")

    if not resolved_dir.exists():
        print(f"[SKIP] 不存在：{dir_path}")
        return
    if not resolved_dir.is_dir():
        print(f"[SKIP] 不是資料夾：{dir_path}")
        return

    items = list(resolved_dir.iterdir())
    if not items:
        print(f"[OK] 已是空的：{dir_path}")
        return

    for item in items:
        # 可選：保留 .gitkeep（如果你有用）
        if item.name == ".gitkeep" or item.name == "template":
            continue

        if dry_run:
            print(f"[DRY] 會刪除：{item}")
            continue

        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    print(f"[OK] 已清空：{dir_path}")

def main():
    project_root = Path(__file__).resolve().parent  # clear_storage.py 所在的 NP_hw3

    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY RUN：只顯示將刪除的項目，不會真的刪 ===")

    for d in TARGET_DIRS:
        clear_dir(d, project_root, dry_run=dry_run)

if __name__ == "__main__":
    main()
