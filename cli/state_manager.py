"""
cli/state_manager.py — Markdown状態管理エンジン

Tick-Tockオーケストレーション & Git連携
"""

import os
import re
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.base import TaskItem, AgentMessage, Phase, AgentRole


class MarkdownStateManager:
    """
    TASKS.md / MEMORY.md をリードエージェントが排他的に管理するクラス。
    Tick-Tockオーケストレーション対応。
    """

    def __init__(self, memory_dir: str):
        self.memory_dir = Path(memory_dir)
        self.tasks_path = self.memory_dir / "TASKS.md"
        self.memory_path = self.memory_dir / "MEMORY.md"
        self.agents_path = self.memory_dir / "AGENTS.md"
        self._write_lock = False  # Tick-Tockロック

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Tick-Tock 排他制御
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def tick(self):
        """TICK: 計画フェーズ。書き込みロック取得"""
        self._write_lock = True

    def tock(self):
        """TOCK: 実行フェーズ。書き込みロック解放（サブエージェントは読み取り専用）"""
        self._write_lock = False

    def consolidate(self, messages: list[AgentMessage]):
        """CONSOLIDATION: リードエージェントが結果を集約してTASKS.mdに書き込む"""
        self.tick()
        try:
            self._append_discussion_log(messages)
        finally:
            self.tock()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # タスク管理
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def update_task_status(self, task_id: str, status: str, result: Optional[str] = None):
        """タスクのステータスを更新（リードエージェントのみ）"""
        if not self._write_lock:
            raise PermissionError("Write lock not held. Call tick() first.")

        content = self._read(self.tasks_path)
        status_emoji = {
            "PENDING": "⬜",
            "IN_PROGRESS": "🟡",
            "DONE": "✅",
            "BLOCKED": "❌",
            "REVIEW": "🔄",
        }.get(status, "❓")

        # テーブル行のステータスを更新
        updated = re.sub(
            rf"(\| {task_id} \|.*?\| )([^|]+)(\|)",
            lambda m: m.group(1) + f"{status_emoji} {status}" + m.group(3),
            content,
        )

        # 進捗サマリーを更新
        done_count = updated.count("✅")
        total = len(re.findall(r"\| T\d+", updated))
        inprogress = updated.count("🟡")
        blocked = updated.count("❌")

        updated = re.sub(
            r"(- 完了: )\d+ / \d+",
            f"\\g<1>{done_count} / {total}",
            updated,
        )
        updated = re.sub(r"(- 進行中: )\d+", f"\\g<1>{inprogress}", updated)
        updated = re.sub(r"(- ブロック中: )\d+", f"\\g<1>{blocked}", updated)

        self._write(self.tasks_path, updated)

    def update_phase(self, phase: Phase):
        """現在フェーズを更新"""
        if not self._write_lock:
            raise PermissionError("Write lock not held.")
        content = self._read(self.tasks_path)
        updated = re.sub(
            r"(current_phase: )\w+",
            f"\\g<1>{phase.value}",
            content,
        )
        self._write(self.tasks_path, updated)

    def get_tasks(self) -> list[dict]:
        """TASKS.mdからタスク一覧を解析して返す"""
        content = self._read(self.tasks_path)
        tasks = []
        for line in content.splitlines():
            if line.startswith("| T") and "|" in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 6:
                    tasks.append({
                        "id": parts[0],
                        "name": parts[1],
                        "assignee": parts[2],
                        "status": parts[3],
                        "depends_on": parts[4],
                        "priority": parts[5],
                    })
        return tasks

    def get_current_phase(self) -> str:
        """現在フェーズを取得"""
        content = self._read(self.tasks_path)
        m = re.search(r"current_phase: (\w+)", content)
        return m.group(1) if m else "UNKNOWN"

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 長期記憶管理
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def add_adr(self, title: str, decision: str, rationale: str, tradeoffs: str):
        """Architecture Decision Record を追加"""
        self.tick()
        try:
            content = self._read(self.memory_path)
            adr_count = len(re.findall(r"### ADR-\d+", content))
            new_adr = f"""
### ADR-{adr_count + 1:03d}: {title}
- **日付:** {datetime.now().strftime('%Y-%m-%d')}
- **ステータス:** Accepted
- **決定:** {decision}
- **理由:** {rationale}
- **トレードオフ:** {tradeoffs}
"""
            updated = content.replace(
                "## ⚠️ 技術的ハマりポイント",
                new_adr + "\n## ⚠️ 技術的ハマりポイント",
            )
            self._write(self.memory_path, updated)
        finally:
            self.tock()

    def add_lesson(self, category: str, lesson: str):
        """教訓・ベストプラクティスを追記"""
        self.tick()
        try:
            content = self._read(self.memory_path)
            new_lesson = f"\n### {category}\n{lesson}\n"
            updated = content.replace(
                "## 📚 参考リンク",
                new_lesson + "## 📚 参考リンク",
            )
            self._write(self.memory_path, updated)
        finally:
            self.tock()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Git連携
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def git_snapshot(self, message: str) -> bool:
        """現在の状態をGitにコミット（ロールバック可能）"""
        try:
            subprocess.run(["git", "init"], cwd=self.memory_dir, capture_output=True)
            subprocess.run(["git", "add", "."], cwd=self.memory_dir, capture_output=True)
            result = subprocess.run(
                ["git", "commit", "-m", f"[HMAS] {message}"],
                cwd=self.memory_dir,
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False  # gitが未インストール

    def git_rollback(self, steps: int = 1) -> bool:
        """指定ステップ数前の状態にロールバック"""
        try:
            result = subprocess.run(
                ["git", "revert", f"HEAD~{steps}..HEAD", "--no-edit"],
                cwd=self.memory_dir,
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 内部ユーティリティ
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _read(self, path: Path) -> str:
        if not path.exists():
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _write(self, path: Path, content: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _append_discussion_log(self, messages: list[AgentMessage]):
        """エージェント間ディスカッションログをTASKS.mdに追記"""
        content = self._read(self.tasks_path)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"\n### [{timestamp}] セッション更新\n"
        for msg in messages:
            log_entry += msg.to_markdown() + "\n\n"

        # ディスカッションセクションに追記
        if "## 💬 エージェント間ディスカッションログ" in content:
            updated = content.replace(
                "## ✅ 完了タスク",
                log_entry + "## ✅ 完了タスク",
            )
            self._write(self.tasks_path, updated)
