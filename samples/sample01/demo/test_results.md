# Sample01 動作確認結果(2026-05-08)

## 1. 分類精度テスト(`test_classify.py`、API 直叩き 10 件)

| 指標 | 結果 |
|---|---|
| All-fields match | **10/10(100%)** |
| category | 10/10(100%) |
| urgency | 10/10(100%) |
| sentiment | 10/10(100%) |
| recommended_response_deadline | 10/10(100%) |
| 入力トークン合計 | 9,995 |
| 出力トークン合計 | 541 |
| 推定コスト(Haiku 4.5) | **$0.0127(約 2 円)** |

### 通過した境界ケース

- `07_catalog_request`(資料請求 → 「その他」分類が安定するか懸念)→ 通過
- `08_short_ambiguous`(短文・情報不足の問い合わせ)→ 「中」緊急度で正しく拾う
- `09_mixed_intent`(苦情+見積依頼の混在)→ 「迷ったら 1 段階上」ルール通り「高」に倒れる
- `10_mild_dissatisfaction`(批判含むが結論は問い合わせ)→ category=質問 / sentiment=ネガで正しく切り分け

→ プロンプト改善は不要と判断。

## 2. n8n エンドツーエンドテスト(production webhook 経由 4 件)

| ID | カテゴリ/緊急度 | 想定ルート | 結果 | Slack 表示 |
|---|---|---|---|---|
| 01_urgent_trouble | 苦情 / 高 | Draft Urgent | ✓ | :red_circle: 崩れなし |
| 02_normal_quote | 見積もり依頼 / 中 | Draft Normal | ✓ | :large_yellow_circle: 崩れなし |
| 05_positive_feedback_question | 質問 / 低 | Draft Simple | ✓ | :large_green_circle: 崩れなし |
| 09_mixed_intent | 苦情 / 高(混在) | Draft Urgent | ✓ | :red_circle: 崩れなし |

3 分岐(高/中/低)+ 混在ケース全部期待通り。Slack の整形(mrkdwn + 絵文字)も問題なし。

## 3. ローカル環境前提

- n8n: Docker Compose、`http://localhost:5678`、ワークフロー active(Publish 済み)
- Slack: Workspace `aiflowlab` / channel `#sample01-inquiries` / Incoming Webhook
- Anthropic API: Haiku 4.5、`.env` の `ANTHROPIC_API_KEY` 経由
- Slack Webhook URL: `.env` の `SLACK_WEBHOOK_URL_SAMPLE01`、ワークフロー JSON は `$env` 参照のみで露出なし
