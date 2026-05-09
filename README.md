# n8n × Claude API Samples

[n8n](https://n8n.io/) と [Claude API](https://docs.anthropic.com/) を組み合わせた業務自動化サンプル集。各サンプルはそのまま動かせる構成で、ワークフロー定義 / プロンプト / テストスクリプト / 検証結果を一式公開しています。

## サンプル一覧

| サンプル | 概要 | 状態 |
|---|---|---|
| [Sample01: Inquiry Auto-Router](./samples/sample01/) | 問い合わせメール自動分類 + 緊急度別 返信ドラフト + Slack 通知 | ✓ 完成(2026-05-08) |

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

### 3. ワークフローをインポート

n8n UI から `samples/sample01/n8n/sample01_workflow.json` をインポート。インポート後は **Unpublish → Publish** で Active 化(import 直後は Draft 状態)。

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

## ディレクトリ構成

```
n8n-claude-samples/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
└── samples/
    └── sample01/
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
```

## ライセンス

MIT License — 商用利用・改変・再配布自由。詳しくは [LICENSE](./LICENSE)。

## 連絡先

業務自動化(n8n × Claude API)のご相談・見積依頼・カスタマイズ依頼はこちらまで:

- Email: aiflowlab.jp@gmail.com
- X (Twitter): [@aiflowlab](https://x.com/aiflowlab)(DM 開放中)

## 関連記事

- note: [Claude Haiku 4.5 + n8n で問い合わせ対応ワークフローを作った](https://note.com/aiflowlab/n/n510b10be496c)
- Zenn: [Claude Haiku 4.5 + n8n で問い合わせ対応ワークフローを作ったら、100% 精度・1 件 0.5 円で運用できた](https://zenn.dev/aiflowlab/articles/n8n-claude-haiku-inquiry-workflow)
