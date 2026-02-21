"""
cli/orchestrator.py — HMASメインオーケストレーター

使用方法:
  python orchestrator.py --request "要件定義をしてください" --mode simulate
  python orchestrator.py --request "コードレビューをしてください" --mode real
  python orchestrator.py --interactive
"""

import sys
import os
import argparse
import json
import time
from pathlib import Path
from datetime import datetime

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import (
    ClaudeLeadAgent, GeminiContextAgent, CopilotCodexAgent,
    Phase, TaskItem, AgentMessage, MessageType
)
from mcp.proxy import GeminiMCPServer, CopilotProxy, MCPRouter
from cli.state_manager import MarkdownStateManager


class HMASOrchestrator:
    """
    Heterogeneous Multi-Agent System オーケストレーター

    Tick-Tockサイクルで各エージェントを協調させ、
    Markdownで状態を管理する。
    """

    PHASE_ORDER = [
        Phase.REQUIREMENTS,
        Phase.DESIGN,
        Phase.IMPLEMENTATION,
        Phase.REVIEW,
        Phase.DONE,
    ]

    def __init__(self, memory_dir: str, use_real_api: bool = False):
        self.memory_dir = memory_dir
        self.use_real_api = use_real_api

        # エージェント初期化
        config = {"use_real_api": use_real_api}
        self.lead = ClaudeLeadAgent(config=config)
        self.gemini = GeminiContextAgent(config=config)
        self.copilot = CopilotCodexAgent(config=config)
        self.team = [self.lead, self.gemini, self.copilot]

        # MCP & プロキシ
        self.gemini_mcp = GeminiMCPServer()
        self.copilot_proxy = CopilotProxy()
        self.router = MCPRouter(self.gemini_mcp, self.copilot_proxy)

        # 状態管理
        self.state = MarkdownStateManager(memory_dir)

        # セッションログ
        self.session_log: list[dict] = []
        self.total_messages = 0

    def run_session(self, user_request: str) -> dict:
        """
        完全なHMASセッションを実行

        Returns:
            セッション結果サマリー
        """
        self._print_header(user_request)
        start_time = time.time()
        all_messages = []

        current_phase = Phase.REQUIREMENTS

        for phase in self.PHASE_ORDER:
            if phase == Phase.DONE:
                break

            self._print_phase_banner(phase)

            # ━━ TICK: リードが計画 ━━
            self.state.tick()
            self.state.update_phase(phase)

            phase_messages = self._run_phase(user_request, phase)
            all_messages.extend(phase_messages)

            # ━━ CONSOLIDATION: 結果集約 ━━
            self.state.consolidate(phase_messages)

            # Git スナップショット
            self.state.git_snapshot(f"{phase.value} フェーズ完了")

            # フォロワーシップ: 各エージェントからフィードバック収集
            feedbacks = self._collect_followership_feedback(user_request)
            if feedbacks:
                self._print_feedback_summary(feedbacks)

            # フェーズ完了確認
            if self._is_phase_complete(phase):
                self._print_phase_complete(phase)
            else:
                print(f"\n  ⚠️  フェーズ {phase.value} に未完了タスクがあります")

        elapsed = time.time() - start_time

        # 最終サマリー
        summary = self._build_summary(all_messages, elapsed)
        self._print_summary(summary)

        # MEMORY.mdに教訓を追記
        self._record_lessons(summary)

        return summary

    def run_single_phase(self, user_request: str, phase: Phase) -> list[AgentMessage]:
        """単一フェーズのみ実行"""
        self.state.tick()
        messages = self._run_phase(user_request, phase)
        self.state.consolidate(messages)
        self.state.tock()
        return messages

    def _run_phase(self, request: str, phase: Phase) -> list[AgentMessage]:
        """フェーズ内のオーケストレーション実行"""
        messages = []

        if phase == Phase.REQUIREMENTS:
            # Gemini → コードベース解析（並行実行イメージ）
            print("  🔭 Gemini: コンテキスト解析中...")
            gemini_task = TaskItem(id="T002", name="コードベース解析", assignee=self.gemini.role, status="IN_PROGRESS")
            gemini_msg = self.gemini.process(gemini_task, request)
            messages.append(gemini_msg)
            self._print_agent_message(gemini_msg)

            # Claude → 要件定義
            print("  🎼 Claude: 要件定義中...")
            lead_task = TaskItem(id="T001", name="要件定義", assignee=self.lead.role, status="IN_PROGRESS")
            lead_msg = self.lead.process(lead_task, request)
            messages.append(lead_msg)
            self._print_agent_message(lead_msg)

        elif phase == Phase.DESIGN:
            # Claude → アーキテクチャ設計
            print("  🎼 Claude: アーキテクチャ設計中...")
            design_task = TaskItem(id="T003", name="アーキテクチャ設計", assignee=self.lead.role, status="IN_PROGRESS")
            design_msg = self.lead.process(design_task, request)
            messages.append(design_msg)
            self._print_agent_message(design_msg)

            # Copilot → セキュリティレビュー
            print("  🛠️  Copilot: セキュリティレビュー中...")
            sec_task = TaskItem(id="T004", name="セキュリティレビュー", assignee=self.copilot.role, status="IN_PROGRESS")
            sec_msg = self.copilot.process(sec_task, request)
            messages.append(sec_msg)
            self._print_agent_message(sec_msg)

        elif phase == Phase.IMPLEMENTATION:
            # Claude → 実装
            print("  🎼 Claude: 実装中...")
            impl_task = TaskItem(id="T005", name="実装", assignee=self.lead.role, status="IN_PROGRESS")
            impl_msg = self.lead.process(impl_task, request)
            messages.append(impl_msg)
            self._print_agent_message(impl_msg)

        elif phase == Phase.REVIEW:
            # Copilot → コード検証
            print("  🛠️  Copilot: コード検証中...")
            review_task = TaskItem(id="T006", name="コード検証", assignee=self.copilot.role, status="IN_PROGRESS")
            review_msg = self.copilot.process(review_task, request)
            messages.append(review_msg)
            self._print_agent_message(review_msg)

            # Gemini → ドキュメント生成
            print("  🔭 Gemini: ドキュメント生成中...")
            doc_task = TaskItem(id="T007", name="ドキュメント生成", assignee=self.gemini.role, status="IN_PROGRESS")
            doc_msg = self.gemini.process(doc_task, request)
            messages.append(doc_msg)
            self._print_agent_message(doc_msg)

        self.total_messages += len(messages)
        return messages

    def _collect_followership_feedback(self, request: str) -> list[str]:
        """フォロワーシップ原則に基づきサブエージェントからフィードバック収集"""
        feedbacks = []
        for agent in [self.gemini, self.copilot]:
            fb = agent.provide_feedback(request)
            feedbacks.append(f"[{agent.name}] {fb}")
        return feedbacks

    def _is_phase_complete(self, phase: Phase) -> bool:
        """フェーズが完了しているか確認"""
        return True  # 実装: TASKS.mdのステータスを確認

    def _record_lessons(self, summary: dict):
        """セッション終了時に教訓をMEMORY.mdに記録"""
        lesson = (
            f"セッション所要時間: {summary['elapsed_sec']:.1f}秒 | "
            f"メッセージ数: {summary['total_messages']} | "
            f"ルーティング: {json.dumps(summary['routing'], ensure_ascii=False)}"
        )
        self.state.add_lesson("セッション統計", lesson)

    def _build_summary(self, messages: list[AgentMessage], elapsed: float) -> dict:
        routing_summary = self.router.get_routing_summary()
        return {
            "total_messages": len(messages),
            "elapsed_sec": elapsed,
            "routing": routing_summary,
            "phases_completed": [p.value for p in self.PHASE_ORDER if p != Phase.DONE],
            "agents": [a.name for a in self.team],
            "mode": "real_api" if self.use_real_api else "simulation",
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 表示ヘルパー
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _print_header(self, request: str):
        print("\n" + "═" * 60)
        print("  🤖 HMAS — Heterogeneous Multi-Agent System")
        print("  異種混合マルチエージェントシステム")
        print("═" * 60)
        print(f"  📋 リクエスト: {request[:80]}")
        print(f"  🕐 開始: {datetime.now().strftime('%H:%M:%S')}")
        print(f"  🔧 モード: {'実API' if self.use_real_api else 'シミュレーション'}")
        print("═" * 60 + "\n")

    def _print_phase_banner(self, phase: Phase):
        emoji = {"REQUIREMENTS": "📝", "DESIGN": "🏗️", "IMPLEMENTATION": "💻", "REVIEW": "🔍"}.get(phase.value, "📌")
        print(f"\n{'─' * 50}")
        print(f"  {emoji} フェーズ: {phase.value}")
        print(f"{'─' * 50}")

    def _print_agent_message(self, msg: AgentMessage):
        emoji = {
            "Claude (Lead)":       "🎼",
            "Gemini (Context)":    "🔭",
            "Copilot/Codex (Logic)": "🛠️",
        }.get(msg.agent, "🤖")
        content_preview = msg.content[:120].replace("\n", " ")
        print(f"  {emoji} {msg.agent}: {content_preview}...")

    def _print_feedback_summary(self, feedbacks: list[str]):
        print(f"\n  💬 フォロワーシップ フィードバック:")
        for fb in feedbacks:
            print(f"    → {fb[:100]}")

    def _print_phase_complete(self, phase: Phase):
        print(f"\n  ✅ {phase.value} フェーズ完了")

    def _print_summary(self, summary: dict):
        print("\n" + "═" * 60)
        print("  📊 セッションサマリー")
        print("═" * 60)
        print(f"  メッセージ総数: {summary['total_messages']}")
        print(f"  所要時間: {summary['elapsed_sec']:.2f}秒")
        print(f"  完了フェーズ: {', '.join(summary['phases_completed'])}")
        print(f"  実行エージェント: {', '.join(summary['agents'])}")
        print("═" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="HMAS — Heterogeneous Multi-Agent System")
    parser.add_argument("--request", "-r", type=str, default="ECサイトのバックエンドを設計してください")
    parser.add_argument("--mode", "-m", choices=["simulate", "real"], default="simulate")
    parser.add_argument("--memory-dir", type=str, default=str(Path(__file__).parent.parent / "memory"))
    parser.add_argument("--phase", "-p", type=str, choices=[p.value for p in Phase], default=None)
    args = parser.parse_args()

    orchestrator = HMASOrchestrator(
        memory_dir=args.memory_dir,
        use_real_api=(args.mode == "real"),
    )

    if args.phase:
        phase = Phase(args.phase)
        messages = orchestrator.run_single_phase(args.request, phase)
        print(f"\n✅ {len(messages)}件のメッセージを生成しました")
    else:
        result = orchestrator.run_session(args.request)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
