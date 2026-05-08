#!/usr/bin/env python3
"""Sample01 用の n8n ワークフロー JSON を生成する。

Usage:
    cd samples/sample01
    python3 scripts/build_n8n_workflow.py

出力:
    samples/sample01/n8n/sample01_workflow.json
"""
from __future__ import annotations

import json
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parents[1] / "n8n" / "sample01_workflow.json"

MODEL = "claude-haiku-4-5-20251001"

# === Prompts (test_classify.py / test_draft.py と同期) ===

SYSTEM_CLASSIFY = """あなたは BtoB 企業の顧客対応窓口で、受信した問い合わせメールを分類するアシスタントです。

入力された問い合わせを以下の 4 軸で分類し、必ず JSON のみを出力してください。説明文や前置きは一切不要です。

<分類軸>
- category: 問い合わせの種類。次のいずれか。
  - "質問"
  - "苦情"
  - "見積もり依頼"
  - "予約・問い合わせ"
  - "その他"
- urgency: 緊急度。次のいずれか。
  - "高": 即時対応が必要(怒り・トラブル・損失発生・期限切迫)
  - "中": 1 営業日以内に返信すべき(通常の見積依頼・予約・質問)
  - "低": 数日以内で問題ない(情報提供依頼・カタログ請求等)
- sentiment: 送信者の感情。次のいずれか。
  - "ポジティブ": 感謝・賞賛・好意的な感想を**明示的に**含む(例:「いつもありがとうございます」「とても助かっています」)。単なる丁寧な敬語はポジティブに含めない
  - "ニュートラル": 事実・要望・依頼ベースで、感情表現が乏しい。ビジネスの定型文や敬語のみの文面はここに分類
  - "ネガティブ": 不満・批判・苦情・要求の強さが明示されている(例:「困っています」「分かりづらい」「対応が遅い」「改善してほしい」)。穏やかな口調でも批判的内容ならネガティブ
- recommended_response_deadline: 推奨対応期限。次のいずれか。
  - "2時間以内"
  - "24時間以内"
  - "3営業日以内"
</分類軸>

<出力形式>
{
  "category": "...",
  "urgency": "...",
  "sentiment": "...",
  "recommended_response_deadline": "..."
}
</出力形式>

<判定の指針>
- urgency と recommended_response_deadline は対応関係を持たせる:
  - 高 → 2時間以内
  - 中 → 24時間以内
  - 低 → 3営業日以内
- 苦情・トラブル系は sentiment がネガティブで urgency が高くなる傾向
- 見積もり依頼は通常 urgency 中、ただし「至急」「本日中」等の文言があれば高
- 判断に迷ったら 1 段階上の緊急度を採用(false negative を避ける)
</判定の指針>"""

COMMON_FORMAT = """
<書式制約(厳守)>
- Markdown 記号(**太字**、## 見出し、- 箇条書き等)は一切使用しない。プレーンテキストのみで出力する
- 改行は段落区切りにのみ使用(2〜3 段落程度)
- 署名は「〇〇株式会社 カスタマーサポート」で締める
</書式制約(厳守)>

<出力>
返信本文のみ。前置きや補足説明は不要。
</出力>"""

SYSTEM_URGENT = """あなたは BtoB 企業のカスタマーサポート担当者です。緊急度の高い問い合わせに対する返信ドラフトを作成します。

<トーン>
- 冒頭で「ご不便をおかけし申し訳ございません」と謝意を示す(ただし過剰に謝らない)
- 即時対応の姿勢を明示する(例:「直ちに調査いたします」「本日中に折り返しご連絡します」)
- 具体的な次のアクションと時間軸を示す
</トーン>

<必須要素>
1. 状況把握のための具体的な質問を 1 つ(例:「対象の注文番号をお知らせください」「いつから発生していますか」)
2. 折り返し連絡の目安時間(2 時間以内、本日 17 時まで等)
</必須要素>

<文字数(厳守)>
200〜300 字。300 字を超えてはならない。簡潔さと迅速性を最優先。
</文字数(厳守)>""" + COMMON_FORMAT

SYSTEM_NORMAL = """あなたは BtoB 企業のカスタマーサポート担当者です。通常の問い合わせに対する返信ドラフトを作成します。

<トーン>
- 丁寧かつビジネスライクに受け取り確認をする
- 問い合わせ内容を要約して理解を示す(「〜のご相談ですね」「〜の件、承知しました」)
- 必要な追加情報を整理して質問する
</トーン>

<必須要素>
1. 問い合わせ内容の要約・受け取り確認
2. 回答に必要な追加情報を整理した質問を 1 つ(例:希望納期、想定予算、利用人数 等)
3. 回答提供までの目安時間(1 営業日以内、24 時間以内 等)
</必須要素>

<文字数(厳守)>
300〜400 字。400 字を超えてはならない。情報を整理して論点を明確に。
</文字数(厳守)>""" + COMMON_FORMAT

SYSTEM_SIMPLE = """あなたは BtoB 企業のカスタマーサポート担当者です。緊急度の低い問い合わせに対する返信ドラフトを作成します。

<トーン>
- 簡潔かつ温かみのある受け答え
- 過度に時間を割かず、要点を絞る
- 関心度合いを把握する軽い質問で会話を継続させる
</トーン>

<必須要素>
1. 問い合わせへの簡潔な感謝・受け取り確認
2. 関心度合いを把握する確認質問を 1 つ(例:「導入時期のご希望はございますか」「特にご関心のある機能はありますか」)
3. 過度に長い説明は避け、必要なら別途資料送付を提案
</必須要素>

<文字数(厳守)>
150〜250 字。250 字を超えてはならない。簡潔に。
</文字数(厳守)>""" + COMMON_FORMAT

# === User prompt templates (n8n expression を埋め込む) ===
# Webhook 入力は { "body": {sender_name, sender_email, subject, body} }

USER_CLASSIFY = """以下の問い合わせメールを分類してください。

<inquiry>
<sender_name>{{ $json.body.sender_name }}</sender_name>
<sender_email>{{ $json.body.sender_email }}</sender_email>
<subject>{{ $json.body.subject }}</subject>
<body>
{{ $json.body.body }}
</body>
</inquiry>"""

# ドラフト生成時は Parse Classification の出力を使う
# $('Parse Classification').first().json = { classification: {...}, original: {...} }
USER_DRAFT = """以下の問い合わせメールに対する返信ドラフトを作成してください。

<inquiry>
<sender_name>{{ $('Parse Classification').first().json.original.sender_name }}</sender_name>
<subject>{{ $('Parse Classification').first().json.original.subject }}</subject>
<body>
{{ $('Parse Classification').first().json.original.body }}
</body>
</inquiry>

<classification>
<category>{{ $('Parse Classification').first().json.classification.category }}</category>
<urgency>{{ $('Parse Classification').first().json.classification.urgency }}</urgency>
<sentiment>{{ $('Parse Classification').first().json.classification.sentiment }}</sentiment>
</classification>"""


def http_body_classify() -> str:
    payload = {
        "model": MODEL,
        "max_tokens": 256,
        "temperature": 0,
        "system": SYSTEM_CLASSIFY,
        "messages": [
            {"role": "user", "content": USER_CLASSIFY},
            {"role": "assistant", "content": "{"},
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def http_body_draft(system: str) -> str:
    payload = {
        "model": MODEL,
        "max_tokens": 800,
        "temperature": 0,
        "system": system,
        "messages": [{"role": "user", "content": USER_DRAFT}],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


CODE_PARSE = """// Claude のレスポンスから分類結果を抽出。
// Prefill で "{" を送ったので、レスポンス本文は "..." 形式の文字列。
// 元のWebhook入力も後段で使うため保持する。
const apiResponse = $input.first().json;
const classifyText = apiResponse.content[0].text;
const classification = JSON.parse('{' + classifyText);
const original = $('Webhook').first().json.body;
return [{ json: { classification, original } }];"""

CODE_FORMAT = r"""// 各ドラフト HTTP Request の output を受け取り、Slack 投稿用メッセージに整形。
const draftResponse = $input.first().json;
const draftText = draftResponse.content[0].text;
const parseResult = $('Parse Classification').first().json;
const c = parseResult.classification;
const o = parseResult.original;

const urgencyIcon = { '高': ':red_circle:', '中': ':large_yellow_circle:', '低': ':large_green_circle:' }[c.urgency] || ':white_circle:';

const slackMessage = `${urgencyIcon} *[緊急度: ${c.urgency}]* ${o.subject || '(件名なし)'}

*--- 元メッセージ ---*
*From:* ${o.sender_name} <${o.sender_email}>
*Subject:* ${o.subject}
\`\`\`
${o.body}
\`\`\`

*--- AI分類 ---*
• カテゴリ: ${c.category}
• 緊急度: ${c.urgency}
• 感情: ${c.sentiment}
• 推奨対応期限: ${c.recommended_response_deadline}

*--- 返信ドラフト ---*
\`\`\`
${draftText}
\`\`\``;

return [{
  json: {
    slack_message: slackMessage,
    classification: c,
    draft: draftText,
    original: o,
  }
}];"""


def http_node(node_id: str, name: str, x: int, y: int, body_json: str) -> dict:
    return {
        "parameters": {
            "method": "POST",
            "url": "https://api.anthropic.com/v1/messages",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpCustomAuth",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "content-type", "value": "application/json"}
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "=" + body_json,
            "options": {},
        },
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [x, y],
        "id": node_id,
        "name": name,
        "credentials": {
            "httpCustomAuth": {
                "name": "Anthropic API"
            }
        },
    }


def build_workflow() -> dict:
    nodes = [
        # 1. Webhook
        {
            "parameters": {
                "httpMethod": "POST",
                "path": "sample01",
                "responseMode": "responseNode",
                "options": {},
            },
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2.1,
            "position": [0, 300],
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Webhook",
            "webhookId": "sample01-webhook-uuid",
        },
        # 2. HTTP Request: Classify
        http_node(
            "22222222-2222-2222-2222-222222222222",
            "Classify",
            220, 300,
            http_body_classify(),
        ),
        # 3. Code: Parse Classification
        {
            "parameters": {
                "language": "javaScript",
                "jsCode": CODE_PARSE,
            },
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [440, 300],
            "id": "33333333-3333-3333-3333-333333333333",
            "name": "Parse Classification",
        },
        # 4. Switch by Urgency
        {
            "parameters": {
                "rules": {
                    "values": [
                        {
                            "conditions": {
                                "options": {
                                    "caseSensitive": True,
                                    "leftValue": "",
                                    "typeValidation": "strict",
                                    "version": 2,
                                },
                                "conditions": [
                                    {
                                        "leftValue": "={{ $json.classification.urgency }}",
                                        "rightValue": "高",
                                        "operator": {
                                            "type": "string",
                                            "operation": "equals",
                                        },
                                    }
                                ],
                                "combinator": "and",
                            },
                            "renameOutput": True,
                            "outputKey": "高",
                        },
                        {
                            "conditions": {
                                "options": {
                                    "caseSensitive": True,
                                    "leftValue": "",
                                    "typeValidation": "strict",
                                    "version": 2,
                                },
                                "conditions": [
                                    {
                                        "leftValue": "={{ $json.classification.urgency }}",
                                        "rightValue": "中",
                                        "operator": {
                                            "type": "string",
                                            "operation": "equals",
                                        },
                                    }
                                ],
                                "combinator": "and",
                            },
                            "renameOutput": True,
                            "outputKey": "中",
                        },
                        {
                            "conditions": {
                                "options": {
                                    "caseSensitive": True,
                                    "leftValue": "",
                                    "typeValidation": "strict",
                                    "version": 2,
                                },
                                "conditions": [
                                    {
                                        "leftValue": "={{ $json.classification.urgency }}",
                                        "rightValue": "低",
                                        "operator": {
                                            "type": "string",
                                            "operation": "equals",
                                        },
                                    }
                                ],
                                "combinator": "and",
                            },
                            "renameOutput": True,
                            "outputKey": "低",
                        },
                    ]
                },
                "options": {},
            },
            "type": "n8n-nodes-base.switch",
            "typeVersion": 3.2,
            "position": [660, 300],
            "id": "44444444-4444-4444-4444-444444444444",
            "name": "Switch by Urgency",
        },
        # 5a. HTTP Request: Draft Urgent
        http_node(
            "55555555-5555-5555-5555-555555555551",
            "Draft Urgent",
            880, 100,
            http_body_draft(SYSTEM_URGENT),
        ),
        # 5b. HTTP Request: Draft Normal
        http_node(
            "55555555-5555-5555-5555-555555555552",
            "Draft Normal",
            880, 300,
            http_body_draft(SYSTEM_NORMAL),
        ),
        # 5c. HTTP Request: Draft Simple
        http_node(
            "55555555-5555-5555-5555-555555555553",
            "Draft Simple",
            880, 500,
            http_body_draft(SYSTEM_SIMPLE),
        ),
        # 6. Code: Format Slack Message
        {
            "parameters": {
                "language": "javaScript",
                "jsCode": CODE_FORMAT,
            },
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [1100, 300],
            "id": "66666666-6666-6666-6666-666666666666",
            "name": "Format Slack Message",
        },
        # 7. HTTP Request: Post to Slack (Incoming Webhook)
        {
            "parameters": {
                "method": "POST",
                "url": "={{ $env.SLACK_WEBHOOK_URL_SAMPLE01 }}",
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [
                        {"name": "content-type", "value": "application/json"}
                    ]
                },
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={\n  \"text\": {{ JSON.stringify($json.slack_message) }}\n}",
                "options": {},
            },
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [1320, 300],
            "id": "77777777-7777-7777-7777-777777777777",
            "name": "Post to Slack",
        },
        # 8. Respond to Webhook
        {
            "parameters": {
                "respondWith": "json",
                "responseBody": "={{ JSON.stringify($('Format Slack Message').first().json) }}",
                "options": {},
            },
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1.5,
            "position": [1540, 300],
            "id": "88888888-8888-8888-8888-888888888888",
            "name": "Respond to Webhook",
        },
    ]

    connections = {
        "Webhook": {
            "main": [[{"node": "Classify", "type": "main", "index": 0}]]
        },
        "Classify": {
            "main": [[{"node": "Parse Classification", "type": "main", "index": 0}]]
        },
        "Parse Classification": {
            "main": [[{"node": "Switch by Urgency", "type": "main", "index": 0}]]
        },
        "Switch by Urgency": {
            "main": [
                [{"node": "Draft Urgent", "type": "main", "index": 0}],
                [{"node": "Draft Normal", "type": "main", "index": 0}],
                [{"node": "Draft Simple", "type": "main", "index": 0}],
            ]
        },
        "Draft Urgent": {
            "main": [[{"node": "Format Slack Message", "type": "main", "index": 0}]]
        },
        "Draft Normal": {
            "main": [[{"node": "Format Slack Message", "type": "main", "index": 0}]]
        },
        "Draft Simple": {
            "main": [[{"node": "Format Slack Message", "type": "main", "index": 0}]]
        },
        "Format Slack Message": {
            "main": [[{"node": "Post to Slack", "type": "main", "index": 0}]]
        },
        "Post to Slack": {
            "main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]
        },
    }

    return {
        "id": "lImKhYUEYT0kv0i4",
        "name": "Sample01 Inquiry Triage",
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {"executionOrder": "v1"},
        "versionId": "1",
        "meta": {},
        "tags": [],
    }


def main():
    workflow = build_workflow()
    OUT_PATH.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"Generated: {OUT_PATH}")
    print(f"Size: {size_kb:.1f} KB")
    print(f"Nodes: {len(workflow['nodes'])}")


if __name__ == "__main__":
    main()
