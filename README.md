# HMAS


# 🤖 HMAS — Heterogeneous Multi-Agent System

**Claude × Gemini × GitHub Copilot による異種混合マルチエージェント開発支援システム**

各AIエージェントの得意分野を活かして役割分担し、要件定義から実装・レビューまでを自律的に進める開発チームを構築します。エージェントの状態はローカルの Markdown ファイルで管理し、Git によるロールバックにも対応しています。

---

## 📋 目次

- [システム概要](#システム概要)
- [アーキテクチャ](#アーキテクチャ)
- [必要環境](#必要環境)
- [インストール](#インストール)
- [API キー設定](#api-キー設定)
- [使い方](#使い方)
- [シミュレーションモード](#シミュレーションモード)
- [実行モード（実 API）](#実行モード実-api)
- [ファイル構成](#ファイル構成)
- [Markdown 状態管理](#markdown-状態管理)
- [トークンアービトラージ](#トークンアービトラージ)
- [フォロワーシップ設計](#フォロワーシップ設計)
- [Tick-Tock オーケストレーション](#tick-tock-オーケストレーション)
- [トラブルシューティング](#トラブルシューティング)

---

## システム概要

```
┌─────────────────────────────────────────────────┐
│         Heterogeneous Agent Team                 │
│                                                  │
│  🎼 Claude (Lead)   ←→  🔭 Gemini (Context)    │
│       │                                          │
│       └──────────→  🛠️  Copilot (Code)          │
└─────────────────────────────────────────────────┘
              ↕ Read/Write
┌─────────────────────────────────────────────────┐
│           Local Memory (Markdown + Git)          │
│  AGENTS.md  /  TASKS.md  /  MEMORY.md           │
└─────────────────────────────────────────────────┘
```

| エージェント | 役割 | 得意分野 | モデル |
|---|---|---|---|
| 🎼 Claude | Lead / Orchestrator | 設計・統合・指揮 | claude-opus-4-6 |
| 🔭 Gemini | Context Specialist | 大規模テキスト処理（2M token） | gemini-1.5-pro |
| 🛠️ Copilot | Code Specialist | コード生成・セキュリティレビュー | gpt-5.2-codex |

---

## アーキテクチャ

```
hmas/
├── agents/
│   ├── base.py              # BaseAgent / TaskItem / AgentMessage 基底クラス
│   └── implementations.py  # ClaudeLeadAgent / GeminiContextAgent / CopilotCodexAgent
├── mcp/
│   └── proxy.py             # GeminiMCPServer / CopilotProxy / MCPRouter
├── cli/
│   ├── orchestrator.py      # メインオーケストレーター（エントリーポイント）
│   └── state_manager.py     # Markdown 状態管理 + Git スナップショット
└── memory/
    ├── AGENTS.md            # エージェント憲法・ロール定義（読み取り専用）
    ├── TASKS.md             # タスク・進捗管理（リードエージェントのみ書き込み）
    └── MEMORY.md            # 長期記憶・ADR・教訓ナレッジベース
```

---

## 必要環境

- **Python 3.11 以上**
- **pip**（パッケージ管理）
- **Git**（状態のスナップショット・ロールバック用。なくても動作します）

各エージェントを実際の API で使用する場合は、それぞれの API キーが必要です（後述）。

---

## インストール

### 1. リポジトリのクローン（または zip 展開）

```bash
git clone https://github.com/yourname/hmas.git
cd hmas
```

zip を展開した場合:

```bash
unzip hmas_system.zip
cd hmas
```

### 2. 依存パッケージのインストール

```bash
pip install anthropic openai google-generativeai
```

シミュレーションモードのみ使用する場合は追加パッケージは不要です。

---

## API キー設定

HMAS は環境変数で各エージェントの API キーを管理します。キーが設定されていないエージェントは自動的にシミュレーションモードで動作するため、**すべてのキーが揃っていなくても動作します**。

### 環境変数一覧

| 環境変数 | 対応エージェント | 用途 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 🎼 Claude | Anthropic API 認証 |
| `GOOGLE_API_KEY` | 🔭 Gemini | Google AI Studio / Vertex AI 認証 |
| `GITHUB_TOKEN` | 🛠️ Copilot | GitHub Copilot API 認証 |

---

### 🎼 Claude — Anthropic API キーの取得・設定

**取得手順:**

1. [console.anthropic.com](https://console.anthropic.com) にアクセスしてアカウントを作成・ログイン
2. 左メニューの「API Keys」を選択
3. 「Create Key」をクリックしてキーを生成
4. 生成された `sk-ant-...` から始まるキーをコピー

**設定:**

```bash
# macOS / Linux（一時設定）
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxxxxxxxx"

# macOS / Linux（永続設定 — ~/.zshrc または ~/.bashrc に追記）
echo 'export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxxxxxxxx"' >> ~/.zshrc
source ~/.zshrc

# Windows（PowerShell）
$env:ANTHROPIC_API_KEY = "sk-ant-xxxxxxxxxxxxxxxxxx"

# Windows（永続設定）
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-xxxxxxxxxxxxxxxxxx", "User")
```

---

### 🔭 Gemini — Google API キーの取得・設定

**取得手順:**

1. [aistudio.google.com](https://aistudio.google.com) にアクセス
2. 右上の「Get API key」をクリック
3. 「Create API key」でプロジェクトを選択してキーを生成
4. 生成された `AIzaSy...` から始まるキーをコピー

**設定:**

```bash
# macOS / Linux
export GOOGLE_API_KEY="AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# ~/.zshrc に永続追記
echo 'export GOOGLE_API_KEY="AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"' >> ~/.zshrc
source ~/.zshrc

# Windows（PowerShell）
$env:GOOGLE_API_KEY = "AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

> **注意:** Google Cloud プロジェクトで Generative Language API を有効化する必要がある場合があります。[console.cloud.google.com](https://console.cloud.google.com) から確認してください。

---

### 🛠️ GitHub Copilot — GitHub Token の取得・設定

GitHub Copilot API は OpenAI の互換エンドポイント（`https://api.githubcopilot.com`）を使用し、`GITHUB_TOKEN` を Bearer トークンとして認証します。

**取得手順:**

1. GitHub にログインし、右上のアバターから「Settings」を選択
2. 左メニュー最下部「Developer settings」をクリック
3. 「Personal access tokens」→「Tokens (classic)」を選択
4. 「Generate new token (classic)」をクリック
5. スコープとして **`copilot`** にチェックを入れる
6. 「Generate token」をクリックし、`ghp_...` から始まるトークンをコピー

> **前提条件:** GitHub Copilot Individual または Business プランへの加入が必要です。

**設定:**

```bash
# macOS / Linux
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# ~/.zshrc に永続追記
echo 'export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"' >> ~/.zshrc
source ~/.zshrc

# Windows（PowerShell）
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

**通信の仕組み（実装詳細）:**

HMAS は `openai` ライブラリの `base_url` を差し替えて Copilot エンドポイントを利用します。

```python
from openai import OpenAI

client = OpenAI(
    api_key=github_token,                      # GITHUB_TOKEN を Bearer として送信
    base_url="https://api.githubcopilot.com",
    default_headers={
        "Copilot-Integration-Id": "vscode-chat",
        "Editor-Version": "vscode/1.90.0",
    },
)
response = client.chat.completions.create(model="gpt-5.2-codex", ...)
```

---

### `.env` ファイルによる一括管理（推奨）

プロジェクトルートに `.env` ファイルを作成してまとめて管理できます。

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxx
GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

```bash
# .env を読み込んで実行
set -a && source .env && set +a
python cli/orchestrator.py --mode real --request "APIを設計してください"
```

> ⚠️ `.env` ファイルは **絶対に Git にコミットしないでください。** `.gitignore` に追加してください。
>
> ```bash
> echo ".env" >> .gitignore
> ```

---

## 使い方

すべてのコマンドは `hmas/` ディレクトリ内から実行します。

```bash
cd hmas
```

---

## シミュレーションモード

API キーなしで全機能を試せます。開発・デモ・動作確認に使用してください。

### 全フェーズ実行（基本）

```bash
python cli/orchestrator.py --request "ECサイトのバックエンド API を設計してください"
```

### リクエストを省略した場合のデフォルト動作

```bash
python cli/orchestrator.py
# → "ECサイトのバックエンドを設計してください" で実行
```

### 単一フェーズのみ実行

```bash
# 要件定義フェーズのみ
python cli/orchestrator.py --phase REQUIREMENTS --request "ユーザー認証システムを作りたい"

# 設計フェーズのみ
python cli/orchestrator.py --phase DESIGN --request "マイクロサービス構成を検討してください"

# コードレビューフェーズのみ
python cli/orchestrator.py --phase REVIEW --request "決済モジュールをレビューしてください"
```

**指定できるフェーズ一覧:**

| フェーズ | 担当エージェント | 内容 |
|---|---|---|
| `REQUIREMENTS` | Claude + Gemini | 要件定義・コードベース解析 |
| `DESIGN` | Claude + Copilot | アーキテクチャ設計・セキュリティレビュー |
| `IMPLEMENTATION` | Claude | 実装 |
| `REVIEW` | Copilot + Gemini | コード検証・ドキュメント生成 |

### 出力例

```
════════════════════════════════════════════════════════════
  🤖 HMAS — Heterogeneous Multi-Agent System
  異種混合マルチエージェントシステム
════════════════════════════════════════════════════════════
  📋 リクエスト: 決済システムのコードレビューをしてください
  🕐 開始: 09:44:22
  🔧 モード: シミュレーション
════════════════════════════════════════════════════════════

──────────────────────────────────────────────────
  📝 フェーズ: REQUIREMENTS
──────────────────────────────────────────────────
  🔭 Gemini: コンテキスト解析中...
  🎼 Claude: 要件定義中...

  💬 フォロワーシップ フィードバック:
    → [Gemini] ドキュメント観点: APIのレスポンス仕様が未定義です。
    → [Copilot] コード観点: この設計にはSPOFが存在します。

  ✅ REQUIREMENTS フェーズ完了
...
```

---

## 実行モード（実 API）

環境変数に API キーを設定したうえで `--mode real` を指定します。

```bash
# 全エージェント実 API で全フェーズ実行
python cli/orchestrator.py \
  --mode real \
  --request "在庫管理システムのバックエンドを設計・実装してください"

# 単一フェーズを実 API で実行
python cli/orchestrator.py \
  --mode real \
  --phase REVIEW \
  --request "このAPIのコードをレビューしてください"

# memory ディレクトリを指定（デフォルトは ./memory）
python cli/orchestrator.py \
  --mode real \
  --memory-dir /path/to/your/project/memory \
  --request "要件定義をしてください"
```

**キーが一部だけ設定されている場合の動作:**

設定されていないエージェントは自動的にシミュレーションモードで動作します。たとえば `ANTHROPIC_API_KEY` だけ設定した場合、Claude のみが実際の API を呼び出し、Gemini と Copilot はシミュレーションになります。

---

## コマンドライン引数一覧

```
python cli/orchestrator.py [OPTIONS]

オプション:
  --request, -r TEXT      タスクのリクエスト内容（日本語可）
                          デフォルト: "ECサイトのバックエンドを設計してください"

  --mode, -m {simulate|real}
                          実行モード
                          simulate : API キーなしでシミュレーション（デフォルト）
                          real     : 環境変数のAPIキーを使用して実際に呼び出す

  --phase, -p {REQUIREMENTS|DESIGN|IMPLEMENTATION|REVIEW}
                          単一フェーズのみ実行する場合に指定
                          省略時は全フェーズを順番に実行

  --memory-dir TEXT       memory/ ディレクトリのパスを指定
                          デフォルト: スクリプトと同階層の memory/
```

---

## ファイル構成

### memory/AGENTS.md — エージェント憲法

全エージェントがセッション開始時に読み込む「憲法」ファイルです。ロール定義・行動規範・通信プロトコルが記載されています。

このファイルを編集することで、各エージェントの振る舞いや役割をカスタマイズできます。

```markdown
## 共通憲法
- シンプルに考え、シンプルに実装すること
- フォロワーシップ・オーナーシップを持ち建設的な議論を行う

## Copilot ロール定義
- 役割: コード生成・セキュリティレビュー・論理検証
- 制約: 問題指摘は必ず修正コード例とセットで提示する
```

### memory/TASKS.md — タスク・進捗管理

リードエージェント（Claude）のみが書き込みます。タスクの状態・担当・依存関係を管理します。

```markdown
| ID   | タスク名         | 担当       | ステータス      | 優先度 |
|------|-----------------|------------|----------------|--------|
| T001 | 要件定義         | Claude     | ✅ DONE        | HIGH   |
| T002 | コードベース解析  | Gemini     | ✅ DONE        | HIGH   |
| T003 | アーキテクチャ設計| Claude     | 🟡 IN_PROGRESS | HIGH   |
```

### memory/MEMORY.md — 長期記憶・ナレッジベース

タスク完了時に教訓・設計決定（ADR）が自動で追記されます。次回セッションでの再発防止・知識継承に利用します。

---

## Markdown 状態管理

HMAS はデータベースを使わず、ローカルの Markdown ファイルで状態を管理します。

### 特徴

- **透明性（White-box AI）:** VS Code などで直接閲覧・手動修正が可能
- **バージョン管理:** Git で管理されるため `git revert` で任意のタイミングにロールバック可能
- **トークン効率:** Markdown はLLMが読みやすく、コンテキスト注入に最適

### Git スナップショット

各フェーズ完了時に自動で Git コミットが作成されます。

```bash
# スナップショット確認
cd memory
git log --oneline

# 例:
# a3f9c12 [HMAS] REVIEW フェーズ完了
# b7d2e01 [HMAS] IMPLEMENTATION フェーズ完了
# c8a4f33 [HMAS] DESIGN フェーズ完了
# d1e5b99 [HMAS] REQUIREMENTS フェーズ完了

# 特定フェーズの状態に戻す
git checkout a3f9c12 -- TASKS.md
```

### 手動でタスク状態を変更する

`memory/TASKS.md` を直接編集することで、タスクのステータスを手動で変更できます。

```markdown
| T003 | アーキテクチャ設計 | Claude | ❌ BLOCKED | T001, T002 | HIGH |
```

ステータスの凡例:

| 記号 | ステータス | 意味 |
|---|---|---|
| ⬜ | PENDING | 未着手 |
| 🟡 | IN_PROGRESS | 実行中 |
| ✅ | DONE | 完了 |
| ❌ | BLOCKED | ブロック中 |
| 🔄 | REVIEW | レビュー待ち |

---

## トークンアービトラージ

`MCPRouter` がタスクの種類に応じて最適なモデルに自動ルーティングし、コストを最適化します。

| タスク種別 | ルーティング先 | 理由 |
|---|---|---|
| `document_analysis` / `codebase_scan` / `log_analysis` | Gemini Flash | 大量テキスト処理を低単価モデルへオフロード |
| `security_review` / `code_review` / `refactoring` | Copilot gpt-5.2-codex | コード特化モデルへ最適割り当て |
| `architecture` / `orchestration` / `integration` | Claude | 高度な推論・統合はリードへ集中 |

**参考コスト（USD/1Kトークン）:**

| モデル | Input | Output |
|---|---|---|
| claude-opus-4-6 | $0.015 | $0.075 |
| gemini-1.5-flash | $0.00035 | $0.00105 |
| gemini-1.5-pro | $0.0035 | $0.0105 |
| gpt-5.2-codex（参考値） | $0.004 | $0.016 |

### Python から MCPRouter を直接使う

```python
from mcp.proxy import GeminiMCPServer, CopilotProxy, MCPRouter

gemini = GeminiMCPServer()
copilot = CopilotProxy()
router = MCPRouter(gemini, copilot)

# タスク種別を指定してルーティング
response, routed_to = router.route(
    task_type="code_review",
    content="def process_payment(amount): ...",
)
print(f"ルーティング先: {routed_to}")
print(response.content)

# コスト推定
cost = router.estimate_cost("gpt-5.2-codex", input_tokens=1000, output_tokens=500)
print(f"推定コスト: ${cost:.4f}")
```

---

## フォロワーシップ設計

各エージェントは単なる命令実行者ではなく、プロジェクトの共同オーナーとして設計されています。各フェーズ完了後に、サブエージェントがリードエージェントへ建設的なフィードバックを自発的に発信します。

```
[Gemini] ドキュメント観点: APIのレスポンス仕様が未定義です。
         OpenAPI仕様の追加を推奨します。

[Copilot] コード観点: この設計にはSPOFが存在します。
          フェイルオーバー用コードを生成しました。
```

フィードバックには**必ず代替案・改善コードをセット**で提示するよう `AGENTS.md` の憲法で定義されています。

---

## Tick-Tock オーケストレーション

複数エージェントの同時書き込みによるデータ競合（Race Condition）を防ぐための排他制御機構です。

```
[TICK フェーズ]  → Claude のみが TASKS.md に書き込む
                   タスク割り当て・フェーズ更新

[TOCK フェーズ]  → Gemini / Copilot は読み取り専用で作業
                   結果はメッセージとしてリードに返す

[CONSOLIDATION] → Claude が報告を集約し、TASKS.md を更新
                   Git スナップショットを作成
```

Python API から直接制御する場合:

```python
from cli.state_manager import MarkdownStateManager
from agents.base import Phase

state = MarkdownStateManager("./memory")

state.tick()                                      # 書き込みロック取得
state.update_phase(Phase.DESIGN)                  # フェーズを更新
state.update_task_status("T003", "IN_PROGRESS")   # タスクステータスを更新
state.tock()                                      # ロック解放

state.git_snapshot("設計フェーズ開始")            # Git にコミット
```

---

## トラブルシューティング

### API キーが認識されない

環境変数が正しく設定されているか確認します。

```bash
# 確認コマンド
echo $ANTHROPIC_API_KEY
echo $GOOGLE_API_KEY
echo $GITHUB_TOKEN

# 空白の場合は再設定
export ANTHROPIC_API_KEY="sk-ant-..."
```

### GitHub Token で Copilot API に接続できない

GitHub Copilot Individual または Business プランへの加入が必要です。また、Personal Access Token のスコープに `copilot` が含まれているか確認してください。

```bash
# トークンのスコープ確認（curl）
curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/user | jq .login
```

### Gemini API で `403 API_KEY_INVALID` エラーが出る

Google Cloud コンソールで **Generative Language API** が有効になっているか確認します。

1. [console.cloud.google.com/apis/library](https://console.cloud.google.com/apis/library) を開く
2. 「Generative Language API」を検索して「有効にする」をクリック

### ImportError: No module named 'anthropic'

依存パッケージが未インストールです。

```bash
pip install anthropic openai google-generativeai
```

### `memory/` ディレクトリが見つからないエラー

`cli/orchestrator.py` はデフォルトで自身と同階層の `memory/` ディレクトリを参照します。`hmas/` ディレクトリ内から実行しているか確認してください。

```bash
cd /path/to/hmas
python cli/orchestrator.py --request "テスト"
```

別のディレクトリを指定する場合は `--memory-dir` を使用します。

```bash
python cli/orchestrator.py --memory-dir /path/to/memory --request "テスト"
```

---

## ライセンス

MIT License
