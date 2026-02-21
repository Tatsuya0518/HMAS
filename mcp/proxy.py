"""
mcp/proxy.py — MCPサーバー & プロキシラッパー

実環境では実際のMCPサーバーに接続します。
本実装はHTTP/Stdioプロキシのインターフェースを定義します。
"""

import json
import subprocess
import os
from typing import Optional, Any
from dataclasses import dataclass


@dataclass
class MCPResponse:
    success: bool
    content: str
    model: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    error: Optional[str] = None


class MCPServerBase:
    """MCPサーバー基底クラス"""

    def __init__(self, server_name: str, endpoint: str, transport: str = "stdio"):
        self.server_name = server_name
        self.endpoint = endpoint
        self.transport = transport  # "stdio" | "http"
        self._connected = False

    def connect(self) -> bool:
        """サーバーに接続"""
        try:
            # 実環境: subprocess or HTTP接続
            self._connected = True
            return True
        except Exception as e:
            print(f"[MCP] {self.server_name} 接続失敗: {e}")
            return False

    def call(self, method: str, params: dict) -> MCPResponse:
        raise NotImplementedError

    @property
    def is_connected(self) -> bool:
        return self._connected


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Gemini MCP サーバー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GeminiMCPServer(MCPServerBase):
    """
    gemini-cli-mcp-server ラッパー
    Gemini の 200万トークンコンテキストを外部記憶として利用
    """

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            server_name="gemini-cli-mcp-server",
            endpoint="gemini-mcp://localhost:3100",
            transport="stdio",
        )
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self.max_context_tokens = 2_000_000

    def call(self, method: str, params: dict) -> MCPResponse:
        """MCP プロトコルでGeminiを呼び出す"""
        if not self.api_key:
            return self._simulate(method, params)

        try:
            # 実環境: gemini-cli-mcp-server を subprocess で起動
            # mcp_request = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel("gemini-1.5-pro")
            prompt = params.get("prompt", "")
            response = model.generate_content(prompt)
            return MCPResponse(
                success=True,
                content=response.text,
                model="gemini-1.5-pro",
                tokens_used=len(prompt.split()) * 2,
            )
        except Exception as e:
            return MCPResponse(success=False, content="", model="gemini", error=str(e))

    def analyze_large_context(self, content: str, instruction: str) -> MCPResponse:
        """大規模コンテキスト解析 (最大2Mトークン)"""
        token_estimate = len(content.split()) * 1.3
        if token_estimate > self.max_context_tokens:
            return MCPResponse(
                success=False,
                content="",
                model="gemini-1.5-pro",
                error=f"コンテキスト超過: 推定{token_estimate:.0f} > 最大{self.max_context_tokens}",
            )
        return self.call("generate", {"prompt": f"{instruction}\n\n{content}"})

    def _simulate(self, method: str, params: dict) -> MCPResponse:
        """APIキーなし時のシミュレーション"""
        import time
        import random
        time.sleep(random.uniform(0.3, 0.8))
        return MCPResponse(
            success=True,
            content=f"[Gemini MCP Simulation] {method} 完了。200万トークン処理能力を活用し、コンテキスト解析を実施しました。",
            model="gemini-1.5-pro (simulated)",
            tokens_used=random.randint(1000, 50000),
            latency_ms=random.uniform(300, 800),
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GitHub Copilot プロキシ (gpt-5.2-codex)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CopilotProxy(MCPServerBase):
    """
    GitHub Copilot API プロキシ (gpt-5.2-codex)。
    openai ライブラリの base_url を差し替えて Copilot エンドポイントへルーティング。

    認証: GITHUB_TOKEN (Bearer)
    必須ヘッダー:
      - Copilot-Integration-Id: vscode-chat
      - Editor-Version: vscode/1.90.0
    """

    COPILOT_API_BASE = "https://api.githubcopilot.com"
    DEFAULT_MODEL = "gpt-5.2-codex"

    def __init__(self, github_token: Optional[str] = None, model: str = DEFAULT_MODEL):
        super().__init__(
            server_name="github-copilot-proxy",
            endpoint=f"{CopilotProxy.COPILOT_API_BASE}/chat/completions",
            transport="http",
        )
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN", "")
        self.model = model

    def call(self, method: str, params: dict) -> MCPResponse:
        if not self.github_token:
            return self._simulate(method, params)

        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=self.github_token,
                base_url=self.COPILOT_API_BASE,
                default_headers={
                    "Copilot-Integration-Id": "vscode-chat",
                    "Editor-Version": "vscode/1.90.0",
                },
            )
            messages = params.get(
                "messages",
                [{"role": "user", "content": params.get("prompt", "")}],
            )
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=params.get("max_tokens", 2048),
            )
            return MCPResponse(
                success=True,
                content=response.choices[0].message.content,
                model=self.model,
                tokens_used=response.usage.total_tokens if response.usage else 0,
            )
        except Exception as e:
            return MCPResponse(success=False, content="", model=self.model, error=str(e))

    def verify_architecture(self, architecture_doc: str) -> MCPResponse:
        """アーキテクチャ論理検証（コード観点）"""
        prompt = (
            "以下のアーキテクチャをコードスペシャリストとして検証してください。"
            "問題点は必ず改善案とコード例をセットで提示してください。\n\n"
            f"{architecture_doc}"
        )
        return self.call("chat", {"prompt": prompt})

    def red_team_analysis(self, target: str) -> MCPResponse:
        """セキュリティレッドチーム分析"""
        prompt = (
            "以下のコード/システムのセキュリティ脆弱性を分析し、"
            "各脆弱性に対する具体的な修正コードを提示してください:\n"
            f"{target}"
        )
        return self.call("chat", {"prompt": prompt})

    def _simulate(self, method: str, params: dict) -> MCPResponse:
        import time, random
        time.sleep(random.uniform(0.2, 0.6))
        return MCPResponse(
            success=True,
            content=f"[Copilot/{self.model} Simulation] コードレビュー完了。3件の問題点と改善案を検出しました。",
            model=f"{self.model} (simulated)",
            tokens_used=random.randint(500, 5000),
            latency_ms=random.uniform(200, 600),
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCP ルーター (タスク種別に応じてルーティング)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MCPRouter:
    """
    タスク特性に応じて最適なモデルにルーティング
    トークンアービトラージを実現
    """

    # トークン単価（USD/1Kトークン, 参考値）
    COST_TABLE = {
        "claude-opus-4-6":    {"input": 0.015,   "output": 0.075},
        "gemini-1.5-pro":     {"input": 0.0035,  "output": 0.0105},
        "gemini-1.5-flash":   {"input": 0.00035, "output": 0.00105},
        "gpt-5.2-codex":      {"input": 0.004,   "output": 0.016},   # Copilot参考値
    }

    def __init__(self, gemini_server: GeminiMCPServer, copilot_proxy: CopilotProxy):
        self.gemini = gemini_server
        self.copilot = copilot_proxy
        self.routing_log = []

    def route(self, task_type: str, content: str, token_budget: int = 10000) -> tuple[MCPResponse, str]:
        """
        タスク種別とトークン予算に基づいてルーティング

        Returns:
            (MCPResponse, routed_to: str)
        """
        routed_to = "claude"
        response = None

        if task_type in ("document_analysis", "codebase_scan", "log_analysis"):
            # 大量テキスト → Gemini Flash (低コスト)
            routed_to = "gemini-flash"
            response = self.gemini.call("generate", {"prompt": content})

        elif task_type in ("security_review", "logic_verification", "red_team",
                           "code_review", "refactoring"):
            # コード検証・レビュー → GitHub Copilot gpt-5.2-codex
            routed_to = "copilot-gpt-5.2-codex"
            response = self.copilot.call("chat", {"prompt": content})

        elif task_type in ("architecture", "orchestration", "integration"):
            # オーケストレーション → Claude (デフォルト)
            routed_to = "claude"
            response = MCPResponse(
                success=True,
                content=f"[Claude] {task_type} タスクを処理します。",
                model="claude-opus-4-6",
            )

        else:
            # 不明 → Claude にフォールバック
            routed_to = "claude (fallback)"
            response = MCPResponse(
                success=True,
                content="不明なタスク種別。Claudeがフォールバック処理します。",
                model="claude-opus-4-6",
            )

        self.routing_log.append({
            "task_type": task_type,
            "routed_to": routed_to,
            "content_length": len(content),
        })

        return response, routed_to

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """コスト推定 (USD)"""
        if model not in self.COST_TABLE:
            return 0.0
        rates = self.COST_TABLE[model]
        return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1000

    def get_routing_summary(self) -> dict:
        """ルーティングサマリーを返す"""
        from collections import Counter
        if not self.routing_log:
            return {"total": 0, "by_model": {}}
        by_model = Counter(r["routed_to"] for r in self.routing_log)
        return {
            "total": len(self.routing_log),
            "by_model": dict(by_model),
        }
