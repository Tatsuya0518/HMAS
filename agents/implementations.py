"""
agents/implementations.py — Claude/Gemini/OpenAI エージェント実装

実際の環境では各APIを呼び出しますが、本実装はシミュレーションモードと
実APIモードの両方をサポートします。
"""

import os
import re
import json
import time
import random
from typing import Optional
from .base import BaseAgent, AgentRole, AgentMessage, MessageType, Phase, TaskItem


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎼 Claude Lead Agent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ClaudeLeadAgent(BaseAgent):
    """
    オーケストレーター。
    タスク分解・割り振り・コード統合・人間とのIF。
    実環境では Anthropic API を使用。
    """

    def __init__(self, config: dict = None):
        super().__init__("Claude (Lead)", AgentRole.LEAD, config)
        self._api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self._use_real_api = bool(self._api_key) and config.get("use_real_api", False)

    def process(self, task: TaskItem, context: str = "") -> AgentMessage:
        if self._use_real_api:
            return self._call_anthropic_api(task, context)
        return self._simulate(task, context)

    def orchestrate(
        self,
        user_request: str,
        team: list[BaseAgent],
        phase: Phase,
    ) -> list[AgentMessage]:
        """
        Tick-Tockオーケストレーション実行。
        1. TICK: タスク分解・割り当て
        2. TOCK: サブエージェント実行
        3. CONSOLIDATION: 結果集約
        """
        messages = []

        # TICK: 計画フェーズ
        plan_msg = self._create_message(
            phase=phase,
            msg_type=MessageType.REPORT,
            content=f"[TICK] タスク分解開始。リクエスト: {user_request[:100]}...\n各サブエージェントへ割り振りを行います。",
            next_action="DISPATCH_TO_SUBAGENTS",
        )
        messages.append(plan_msg)

        # TOCK: サブエージェント実行
        sub_results = []
        for agent in team:
            if agent.role == AgentRole.LEAD:
                continue
            dummy_task = TaskItem(
                id=f"T_{agent.role.value}",
                name=f"{agent.name} への委譲タスク",
                assignee=agent.role,
                status="IN_PROGRESS",
            )
            result = agent.process(dummy_task, context=user_request)
            sub_results.append(result)
            messages.append(result)

        # CONSOLIDATION: 集約
        consolidated = "\n".join([f"• [{r.agent}]: {r.content[:200]}" for r in sub_results])
        final_msg = self._create_message(
            phase=phase,
            msg_type=MessageType.DONE,
            content=f"[CONSOLIDATION] サブエージェント結果を集約:\n{consolidated}",
            next_action="UPDATE_TASKS_MD",
        )
        messages.append(final_msg)
        return messages

    def _simulate(self, task: TaskItem, context: str) -> AgentMessage:
        """APIキーなし時のシミュレーションモード"""
        responses = {
            "REQUIREMENTS": "要件を分析しました。主要機能として①認証②データ管理③API連携が必要です。シンプルな実装から始めることを推奨します。",
            "DESIGN": "MVC構成を採用します。過剰な抽象化を避け、まず動くものを作ります。Geminiにコードベース解析を依頼し、OpenAIにセキュリティレビューを依頼します。",
            "IMPLEMENTATION": "実装を開始します。TDD方式で進め、各モジュールを独立してテスト可能な形にします。",
            "REVIEW": "コードレビュー完了。OpenAIの検証結果を統合し、修正点を適用しました。",
        }
        content = responses.get(task.status, f"タスク '{task.name}' を処理中です。")
        time.sleep(0.3)  # API呼び出し擬似遅延
        return self._create_message(
            phase=Phase.REQUIREMENTS,
            msg_type=MessageType.REPORT,
            content=content,
            next_action="WAIT_FOR_SUBAGENTS",
        )

    def _call_anthropic_api(self, task: TaskItem, context: str) -> AgentMessage:
        """実際のAnthropic API呼び出し"""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self._api_key)
            system = """あなたはHeterogeneousマルチエージェントシステムのリードエージェントです。
シンプルに考え、シンプルに実装することを第一原則とします。
フォロワーシップを持ち、建設的なフィードバックを行います。"""
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": f"タスク: {task.name}\nコンテキスト: {context}"}],
            )
            return self._create_message(
                phase=Phase.REQUIREMENTS,
                msg_type=MessageType.REPORT,
                content=response.content[0].text,
                next_action="CONTINUE",
            )
        except Exception as e:
            return self._create_message(
                phase=Phase.REQUIREMENTS,
                msg_type=MessageType.ERROR,
                content=f"API呼び出しエラー: {str(e)}",
            )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔭 Gemini Context Agent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GeminiContextAgent(BaseAgent):
    """
    コンテキスト考古学者。
    大規模テキスト処理・ドキュメント解析専門。
    実環境では Google Gemini API または MCP サーバー経由。
    """

    def __init__(self, config: dict = None):
        super().__init__("Gemini (Context)", AgentRole.CONTEXT, config)
        self._api_key = os.environ.get("GOOGLE_API_KEY", "")
        self._use_real_api = bool(self._api_key) and (config or {}).get("use_real_api", False)
        self._mcp_endpoint = (config or {}).get("mcp_endpoint", "gemini-cli-mcp-server")

    def process(self, task: TaskItem, context: str = "") -> AgentMessage:
        if self._use_real_api:
            return self._call_gemini_api(task, context)
        return self._simulate(task, context)

    def analyze_codebase(self, file_paths: list[str]) -> str:
        """コードベース解析（最大2Mトークン対応）"""
        summary_parts = []
        for path in file_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    summary_parts.append(f"## {path}\n行数: {len(content.splitlines())}")
            except Exception:
                summary_parts.append(f"## {path}\n読み込みエラー")
        return "\n".join(summary_parts)

    def provide_feedback(self, proposal: str) -> str:
        """フォロワーシップ: ドキュメント観点のフィードバック"""
        if self._use_real_api:
            return self._feedback_via_api(proposal)
        feedbacks = [
            "ドキュメント観点: APIのレスポンス仕様が未定義です。OpenAPI仕様の追加を推奨します。",
            "ドキュメント観点: エラーハンドリングのパターンが明記されていません。",
            "ドキュメント観点: 現在の設計は妥当です。追加のドキュメント不要と判断します。",
        ]
        return random.choice(feedbacks)

    def _simulate(self, task: TaskItem, context: str) -> AgentMessage:
        time.sleep(0.5)
        content = (
            "【コードベース解析完了】\n"
            "- 総ファイル数: 42\n"
            "- 主要言語: Python (68%), TypeScript (24%), Other (8%)\n"
            "- 循環的複雑度: 平均 3.2（良好）\n"
            "- 未使用インポート: 7件検出\n"
            "- 重複コード候補: 3箇所\n"
            "※ 挨拶省略。結論を直接返します（Geminiプロトコル準拠）"
        )
        return self._create_message(
            phase=Phase.REQUIREMENTS,
            msg_type=MessageType.REPORT,
            content=content,
            next_action="REPORT_TO_LEAD",
        )

    def _call_gemini_api(self, task: TaskItem, context: str) -> AgentMessage:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            model = genai.GenerativeModel("gemini-1.5-pro")
            prompt = f"""あなたはコンテキスト解析専門エージェントです。
挨拶は省略し、結論と箇条書きで回答してください。
タスク: {task.name}
コンテキスト: {context[:50000]}"""
            response = model.generate_content(prompt)
            return self._create_message(
                phase=Phase.REQUIREMENTS,
                msg_type=MessageType.REPORT,
                content=response.text,
                next_action="REPORT_TO_LEAD",
            )
        except Exception as e:
            return self._simulate(task, context)

    def _feedback_via_api(self, proposal: str) -> str:
        return f"[Gemini API] フィードバック生成中... (proposal長さ: {len(proposal)}文字)"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🛠️ GitHub Copilot / gpt-5.2-codex Agent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CopilotCodexAgent(BaseAgent):
    """
    コードスペシャリスト。
    コード生成・リファクタリング・セキュリティレビュー・論理検証専門。
    GitHub Copilot API (gpt-5.2-codex) を使用。

    認証方式:
      - GITHUB_TOKEN 環境変数 (GitHub Copilot Individual / Business)
      - エンドポイント: https://api.githubcopilot.com
    """

    # GitHub Copilot API エンドポイント
    COPILOT_API_BASE = "https://api.githubcopilot.com"
    MODEL = "gpt-5.2-codex"

    def __init__(self, config: dict = None):
        super().__init__("Copilot/Codex (Logic)", AgentRole.LOGIC, config)
        # GitHub Copilot は GITHUB_TOKEN で認証
        self._github_token = os.environ.get("GITHUB_TOKEN", "")
        self._use_real_api = bool(self._github_token) and (config or {}).get("use_real_api", False)

    def process(self, task: TaskItem, context: str = "") -> AgentMessage:
        if self._use_real_api:
            return self._call_copilot_api(task, context)
        return self._simulate(task, context)

    def red_team(self, architecture: str) -> list[dict]:
        """レッドチーム分析（コード品質 + セキュリティ観点）"""
        if self._use_real_api:
            return self._red_team_via_api(architecture)
        return [
            {
                "severity": "HIGH",
                "issue": "認証トークンの有効期限が設定されていない",
                "recommendation": "JWTに exp クレームを追加し、最大24時間に制限する",
            },
            {
                "severity": "MEDIUM",
                "issue": "SQLクエリのパラメータ化が一部未実施",
                "recommendation": "ORM使用箇所を確認し、生SQLは全てパラメータバインディングに変換",
            },
            {
                "severity": "LOW",
                "issue": "エラーレスポンスにスタックトレースが含まれる可能性",
                "recommendation": "本番環境では詳細エラーをログに隔離し、クライアントには汎用メッセージを返す",
            },
        ]

    def provide_feedback(self, proposal: str) -> str:
        """フォロワーシップ: コード品質・論理・セキュリティ観点のフィードバック"""
        feedbacks = [
            "コード観点: この設計にはSPOF（単一障害点）が存在します。代替案: リードエージェントにフェイルオーバー機構を追加してください。",
            "コード観点: タスクの依存関係グラフに循環依存の可能性があります。T003→T004→T005の順序を明確化してください。",
            "コード観点: 現在の設計は論理的に整合しています。追加の懸念事項はありません。",
        ]
        return random.choice(feedbacks)

    def _simulate(self, task: TaskItem, context: str) -> AgentMessage:
        time.sleep(0.4)
        issues = self.red_team("")
        issue_text = "\n".join(
            [f"[{i['severity']}] {i['issue']}\n  → {i['recommendation']}" for i in issues]
        )
        content = (
            f"【コードレビュー & セキュリティ検証完了】 (GitHub Copilot / {self.MODEL})\n\n"
            f"{issue_text}\n\n"
            "※ 問題点と代替案をセットで提示（Copilotプロトコル準拠）"
        )
        return self._create_message(
            phase=Phase.REVIEW,
            msg_type=MessageType.FEEDBACK,
            content=content,
            next_action="REPORT_TO_LEAD",
        )

    def _call_copilot_api(self, task: TaskItem, context: str) -> AgentMessage:
        """
        GitHub Copilot API 呼び出し。
        openai ライブラリの base_url を差し替えることで Copilot エンドポイントを利用。
        """
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=self._github_token,          # GITHUB_TOKEN を Bearer として送信
                base_url=self.COPILOT_API_BASE,
                default_headers={
                    "Copilot-Integration-Id": "vscode-chat",   # Copilot required header
                    "Editor-Version": "vscode/1.90.0",
                },
            )

            response = client.chat.completions.create(
                model=self.MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "あなたはGitHub Copilot上で動作するコードスペシャリストです。"
                            "コードレビュー・セキュリティ検証・論理検証を担当します。"
                            "問題点を指摘する際は必ず改善案とコード例をセットで提示してください。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"タスク: {task.name}\nコンテキスト: {context}",
                    },
                ],
                max_tokens=2048,
            )

            return self._create_message(
                phase=Phase.REVIEW,
                msg_type=MessageType.FEEDBACK,
                content=response.choices[0].message.content,
                next_action="REPORT_TO_LEAD",
            )

        except Exception as e:
            # API失敗時はシミュレーションにフォールバック
            fallback = self._simulate(task, context)
            fallback.content = f"[Copilot API エラー: {e}]\n\n{fallback.content}"
            return fallback

    def _red_team_via_api(self, architecture: str) -> list[dict]:
        """API経由でのレッドチーム分析（簡易版）"""
        return [{"severity": "UNKNOWN", "issue": "Copilot API で分析中", "recommendation": "後ほど確認"}]
