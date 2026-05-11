# n8n × Claude API Samples

[n8n](https://n8n.io/) と [Claude API](https://docs.anthropic.com/) を組み合わせた業務自動化サンプル集。各サンプルはそのまま動かせる構成で、ワークフロー定義 / プロンプト / テストスクリプト / 検証結果を一式公開しています。

## サンプル一覧

| サンプル | 概要 | 状態 |
|---|---|---|
| [Sample01: Inquiry Auto-Router](./samples/sample01/) | 問い合わせメール自動分類 + 緊急度別 返信ドラフト + Slack 通知 | ✓ 完成(2026-05-08) |
| [Sample02: Expense Auto-Detector](./samples/sample02/) | クレカ明細メール自動検知 + AI 経費判定 + 帳簿追記 + Slack 通知 | ✓ 完成(2026-05-13) |

## Sample01 — Inquiry Auto-Router

問い合わせメールを Webhook で受け取り、Claude Haiku 4.5 で 4 軸(カテゴリ / 緊急度 / 感情 / 推奨対応期限)に分類し、緊急度別に異なるトーンの返信ドラフトを生成、Slack の専用チャンネルに整形通知します。

### こんな方におすすめ

- 顧客窓口・カスタマーサポートで定型対応に時間を取られている
- LLM × ワークフロー自動化の実装パターンが知りたい
- n8n と Claude API の組み合わせ事例を探している

### 構成

10 ノードの n8n ワークフロー:

```
Webhook → Classify (Claude) → Parse → Switch by Urgency → Draft (Urgent/Normal/Simple) → Format → Post to Slack → Respond
```

詳細は [samples/sample01/demo/flow.md](./samples/sample01/demo/flow.md) を参照。

### 検証結果

- **分類精度**: 10/10 全件で 4 軸完全一致(2026-05-08 実測)
- **コスト**: 1 件あたり約 0.5 円(Claude Haiku 4.5)
- **対応分岐**: 高(謝罪先行)/ 中(確認 + 概算)/ 低(感謝 + 簡潔)の 3 ルート

詳細は [samples/sample01/demo/test_results.md](./samples/sample01/demo/test_results.md) を参照。

### スクリーンショット

- [ワークフロー全体](./samples/sample01/demo/screenshots/workflow_canvas.png)
- [Slack 投稿(3 分岐動作)](./samples/sample01/demo/screenshots/slack_three_colors.png)
- [混在ケース(苦情 + 見積)の処理例](./samples/sample01/demo/screenshots/slack_mixed_intent_detail.png)
- [テスト結果ターミナル](./samples/sample01/demo/screenshots/terminal_test_result.png)

## 動かし方(Sample01)

### 前提

- Docker(n8n 用)
- Python 3.10+
- Anthropic API キー
- Slack Workspace + Incoming Webhook(専用チャンネル推奨)

### 1. 環境変数を準備

```bash
cp .env.example .env
# エディタで .env を開き、各値を埋める
```

### 2. n8n を起動(Docker Compose)

```bash
# docker-compose.yml は別途用意してください(リポジトリには含めていません)
docker compose up -d
# http://localhost:5678 にアクセスして初期セットアップ
```

### 3. ワークフローをビルド・インポート

```bash
cd samples/sample01
python3 scripts/build_n8n_workflow.py
```

生成された `n8n/sample01_workflow.json` を n8n UI からインポート。インポート後は **Unpublish → Publish** で Active 化(import 直後は Draft 状態)。

### 4. 分類精度をローカル検証

```bash
cd samples/sample01
python3 scripts/test_classify.py
```

10 件のテストケースを Anthropic API に直接投げて、分類結果と期待値の一致率を表示します(コスト約 2 円)。

### 5. n8n エンドツーエンド検証

```bash
curl -X POST http://localhost:5678/webhook/sample01 \
  -H "Content-Type: application/json" \
  -d '{
    "sender_name": "田中健一",
    "sender_email": "tanaka@example.com",
    "subject": "【至急】商品が届かない",
    "body": "本文..."
  }'
```

→ Slack の指定チャンネルに緊急度絵文字付きの通知が届きます。

## Sample02 — Expense Auto-Detector

業務用 Gmail に届くクレカ明細メールを自動で検知し、Claude Haiku 4.5 で取引情報を抽出・分類、経費帳簿(CSV)に追記 + Slack 通知します。既知の取引先はルールで即処理、未知の取引先は AI が業務コンテキストを参照して判定するハイブリッド設計。

### こんな方におすすめ

- 個人事業主・フリーランスで経費の手入力・記録漏れに悩んでいる
- ルール + AI ハイブリッドの判定設計パターンが知りたい
- 設定ファイルを書き換えるだけで自分の業種に合わせたい

### 構成

13 ノードの n8n ワークフロー:

```
Gmail Trigger → Load Configs → Determine Bank → Bank Found? → Extract (Claude)
→ Parse + Rule Match → Rule Hit? → Apply Rule / Classify (Claude) → Format From AI
→ Merge Paths → Append Ledger → Post to Slack
```

詳細は [samples/sample02/demo/flow.md](./samples/sample02/demo/flow.md) を参照。

### 検証結果

- **テスト全件 PASS**: 7/7(3 銀行 / カード会社・複数経費パターン)
- **コスト**: 1 件あたり約 1 円(Claude Haiku 4.5)
- **対応経路**: ルール一致(自動記録)/ AI 要レビュー / AI スキップ / Bank not found の 4 経路

詳細は [samples/sample02/demo/test_results.md](./samples/sample02/demo/test_results.md) を参照。

### スクリーンショット

- [ワークフロー全体](./samples/sample02/demo/screenshots/workflow_canvas.png)
- [Slack 完了通知](./samples/sample02/demo/screenshots/slack_complete.png)
- [Slack 要レビュー通知(AI 判定理由付き)](./samples/sample02/demo/screenshots/slack_review.png)

## 動かし方(Sample02)

### 前提

- Docker(n8n 用)
- Python 3.10+
- Anthropic API キー
- Gmail アカウント(業務専用推奨)+ GCP プロジェクト(Gmail API 有効化済み)
- Slack Workspace + Incoming Webhook(専用チャンネル推奨)

### 1. 設定ファイルを準備

```bash
cd samples/sample02/config

# .example をコピーして編集
cp bank_senders.example.json bank_senders.json
cp vendor_rules.example.json vendor_rules.json
cp business_context.example.md business_context.md
```

- `bank_senders.json`: 使用している銀行/カード会社の送信元メールアドレスを確認・追記
- `vendor_rules.json`: 毎月固定で来る取引先(SaaS 等)をルールとして登録
- `business_context.md`: 自分の事業内容を自由文で記述(AI 判定の基準になります)

### 2. n8n を起動(Docker Compose)

```bash
# docker-compose.yml は別途用意してください
docker compose up -d
# http://localhost:5678 にアクセスして初期セットアップ
```

### 3. Gmail OAuth を設定

1. [GCP Console](https://console.cloud.google.com/) でプロジェクトを作成し Gmail API を有効化
2. OAuth 同意画面を設定(External / Test mode)
3. OAuth クライアント ID を作成(Web アプリ、リダイレクト URI: `http://localhost:5678/rest/oauth2-credential/callback`)
4. n8n の Credentials に Gmail OAuth2 API を追加し、スコープは `gmail.modify` + `gmail.labels` を選択

### 4. ワークフローをビルド・インポート

```bash
cd samples/sample02
python3 scripts/build_n8n_workflow.py
```

生成された `n8n/sample02_workflow.json` を n8n UI からインポート。インポート後は **Unpublish → Publish** で Active 化。

### 5. 抽出精度をローカル検証

```bash
cd samples/sample02
python3 scripts/test_extract.py
```

7 件のテストケースを Anthropic API に直接投げて、抽出精度と AI 判定結果を確認します(コスト約 6 円)。

### 6. 実メールで動作確認

n8n を Active 化した状態で、登録済みの銀行/カード会社からのメールを Gmail で受信すると自動的にワークフローが動きます。Slack の指定チャンネルに通知が届けば成功です。

## ディレクトリ構成

```
n8n-claude-samples/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
└── samples/
    ├── sample01/
        ├── n8n/
        │   └── sample01_workflow.json    # n8n ワークフロー定義(import 用)
        ├── prompts/
        │   ├── classify.md               # 分類プロンプト解説
        │   └── draft.md                  # ドラフト生成プロンプト解説
        ├── scripts/
        │   ├── test_classify.py          # 分類精度ローカル検証
        │   ├── test_draft.py             # ドラフト品質ローカル検証
        │   └── build_n8n_workflow.py     # ワークフロー JSON ビルダー
        ├── testcases/
        │   └── inquiries.jsonl           # 10 件のテストケース
        └── demo/
            ├── flow.md                   # アーキテクチャ図と設計ポイント
            ├── test_results.md           # 検証結果サマリ
            ├── examples.md               # 代表 4 ケースの入出力対比
            └── screenshots/              # 各種スクリーンショット
    └── sample02/
        ├── n8n/
        │   ├── sample02_workflow.json    # n8n ワークフロー定義(import 用)
        │   └── code/
        │       └── determine_bank.js     # 銀行ホワイトリスト照合コード
        ├── prompts/
        │   ├── extract.md                # 取引情報抽出プロンプト(Tool Use)
        │   └── classify.md               # 業務関連性判定プロンプト
        ├── config/
        │   ├── bank_senders.example.json # 銀行/カード会社 送信元ホワイトリスト
        │   ├── vendor_rules.example.json # 取引先ルール定義
        │   └── business_context.example.md # 業務コンテキスト(AI 判定の基準)
        ├── scripts/
        │   ├── test_extract.py           # 抽出・分類精度ローカル検証
        │   └── build_n8n_workflow.py     # ワークフロー JSON ビルダー
        ├── testcases/
        │   └── testcases.jsonl           # 7 件のテストケース
        └── demo/
            ├── flow.md                   # アーキテクチャ図と設計ポイント
            ├── test_results.md           # 検証結果サマリ
            ├── examples.md               # 7 ケースの入出力対比
            └── screenshots/              # 各種スクリーンショット
```

## ライセンス

MIT License — 商用利用・改変・再配布自由。詳しくは [LICENSE](./LICENSE)。

## 連絡先

業務自動化(n8n × Claude API)のご相談・見積依頼・カスタマイズ依頼はこちらまで:

- Email: aiflowlab.jp@gmail.com
- X (Twitter): [@aiflowlab](https://x.com/aiflowlab)(DM 開放中)

## 関連記事

**Sample01**
- note: [問い合わせ対応を AI 化したら、月 1,000 通でも 500 円(精度 100%)になった話【コード公開】](https://note.com/aiflowlab/n/n510b10be496c)
- Zenn: [Claude Haiku 4.5 + n8n で問い合わせ対応ワークフローを作ったら、100% 精度・1 件 0.5 円で運用できた](https://zenn.dev/aiflowlab/articles/n8n-claude-haiku-inquiry-workflow)

**Sample02**
- note: (2026-05-13 公開予定)
- Zenn: (2026-05-13 公開予定)
