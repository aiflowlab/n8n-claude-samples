#!/usr/bin/env python3
"""Sample02 用の n8n ワークフロー JSON を生成する。

Usage:
    cd samples/sample02
    python3 scripts/build_n8n_workflow.py

出力:
    samples/sample02/n8n/sample02_workflow.json

ビルド時に config/ と prompts/ の内容を読み込んで Code / HTTP ノードに埋め込む。
Gmail Trigger / Slack Webhook の credential 設定は Step 5 / Step 6 で別途実施。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SAMPLE_DIR = Path(__file__).resolve().parents[1]
OUT_PATH = SAMPLE_DIR / "n8n" / "sample02_workflow.json"
EXTRACT_PROMPT = SAMPLE_DIR / "prompts" / "extract.md"
CLASSIFY_PROMPT = SAMPLE_DIR / "prompts" / "classify.md"
CONFIG_DIR = SAMPLE_DIR / "config"

MODEL = "claude-haiku-4-5-20251001"


def extract_md_block(md_path: Path, header: str) -> str:
    text = md_path.read_text()
    pattern = re.compile(
        rf"^##\s+{re.escape(header)}\s*$.*?```(?:json)?\n(.*?)\n```",
        re.DOTALL | re.MULTILINE,
    )
    m = pattern.search(text)
    if not m:
        sys.exit(f"ERROR: '## {header}' のコードブロックが {md_path} に見つかりません")
    return m.group(1)


def load_config_file(stem: str, ext: str) -> str:
    """`{stem}.{ext}`(本番用)があればそれを、なければ `{stem}.example.{ext}` を読む。"""
    primary = CONFIG_DIR / f"{stem}.{ext}"
    fallback = CONFIG_DIR / f"{stem}.example.{ext}"
    path = primary if primary.exists() else fallback
    if not path.exists():
        sys.exit(f"ERROR: {primary} も {fallback} も見つかりません")
    return path.read_text()


# === Prompts (Markdown から動的に取得) ===

EXTRACT_SYSTEM = extract_md_block(EXTRACT_PROMPT, "System プロンプト")
CLASSIFY_SYSTEM = extract_md_block(CLASSIFY_PROMPT, "System プロンプト")
EXTRACT_TOOL = json.loads(extract_md_block(EXTRACT_PROMPT, "Tool 定義(record_expense)"))


# === Configs (ビルド時に読み込んで JS に埋め込む) ===

BANK_SENDERS_RAW = load_config_file("bank_senders", "json")
VENDOR_RULES_RAW = load_config_file("vendor_rules", "json")
BUSINESS_CONTEXT_RAW = load_config_file("business_context", "md")


# === User プロンプト(n8n expression を埋め込む) ===

# 注意: 改行を含む文字列(text、business_context 等)は n8n expression 内で
# JSON.stringify(...).slice(1, -1) を通して、JSON Body 文法を壊さないようエスケープする
# (両端のダブルクォートは外側の文字列リテラルが供給する)

USER_EXTRACT = """以下のクレカ明細メールから取引情報を抽出してください。

<email_subject>
{{ JSON.stringify($json.subject || '').slice(1, -1) }}
</email_subject>

<email_received_at>
{{ JSON.stringify($json.received_at || '').slice(1, -1) }}
</email_received_at>

<email_body>
{{ JSON.stringify($json.body || '').slice(1, -1) }}
</email_body>"""

USER_CLASSIFY = """以下の取引情報について、ユーザーの業務関連性と按分率を判定してください。

<user_business_context>
{{ JSON.stringify($('Load Configs').first().json.business_context || '').slice(1, -1) }}
</user_business_context>

<transaction>
取引先(原文): {{ JSON.stringify($json.extract.vendor_raw || '').slice(1, -1) }}
金額: {{ $json.extract.amount_jpy }} 円
原通貨: {{ JSON.stringify($json.extract.amount_original || '').slice(1, -1) }}
ご利用区分: {{ JSON.stringify($json.extract.transaction_category || '').slice(1, -1) }}
取引日: {{ $json.extract.transaction_date }}
</transaction>"""


def http_body_extract() -> str:
    payload = {
        "model": MODEL,
        "max_tokens": 512,
        "temperature": 0,
        "system": EXTRACT_SYSTEM,
        "tools": [EXTRACT_TOOL],
        "tool_choice": {"type": "tool", "name": EXTRACT_TOOL["name"]},
        "messages": [{"role": "user", "content": USER_EXTRACT}],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def http_body_classify() -> str:
    payload = {
        "model": MODEL,
        "max_tokens": 512,
        "temperature": 0,
        "system": CLASSIFY_SYSTEM,
        "messages": [
            {"role": "user", "content": USER_CLASSIFY},
            {"role": "assistant", "content": "{"},
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# === Code ノード本体 ===

CODE_LOAD_CONFIGS = f"""// ビルド時に config/ を読み込んで埋め込み。再ビルド(build_n8n_workflow.py 再実行)で更新。
const bankSenders = {BANK_SENDERS_RAW};
const vendorRules = {VENDOR_RULES_RAW};
const businessContext = {json.dumps(BUSINESS_CONTEXT_RAW, ensure_ascii=False)};

return [{{ json: {{ bank_senders: bankSenders, vendor_rules: vendorRules, business_context: businessContext }} }}];
"""

CODE_DETERMINE_BANK = """// Gmail Trigger 出力(Simplify=false、mailparser 整形済み)から送信元アドレスを抽出し、
// Load Configs の bank_senders と照合する。
// Gmail Trigger は 1 poll で複数 item を返しうるため、$('Gmail Trigger').all() を回す。
// 出力構造: { from: { value: [{ address, name }], text, html }, subject, date, text, ... }
const triggerItems = $('Gmail Trigger').all();
const configs = $('Load Configs').first().json;

return triggerItems.map((triggerItem, idx) => {
  const trigger = triggerItem.json;

  let fromAddr = '';
  if (trigger.from && trigger.from.value && trigger.from.value[0]) {
    fromAddr = (trigger.from.value[0].address || '').toLowerCase().trim();
  }

  let matchedKey = null;
  let matchedRule = null;
  for (const [key, rule] of Object.entries(configs.bank_senders)) {
    if (key.startsWith('_')) continue;
    if (rule.from && rule.from.toLowerCase() === fromAddr) {
      matchedKey = key;
      matchedRule = rule;
      break;
    }
  }

  return {
    json: {
      bank_matched: matchedKey !== null,
      bank_key: matchedKey,
      payment_method: matchedRule ? matchedRule.payment_method : null,
      bank_display_name: matchedRule ? matchedRule.display_name : null,
      from_addr: fromAddr,
      subject: trigger.subject || '',
      received_at: trigger.date || '',
      body: trigger.text || '',
    },
    pairedItem: { item: idx },
  };
});
"""

CODE_PARSE_EXTRACT = """// Anthropic Tool Use レスポンスから抽出結果を取り出し、vendor_rules で照合する。
// runOnceForEachItem: 各メールごとに 1 回走る。$('Determine Bank').item で
// 現在処理中の item に対応する bank info を取得(pairedItem 経由)。
const apiResponse = $json;
const bankInfo = $('Determine Bank').item.json;
const configs = $('Load Configs').first().json;

let extracted = null;
for (const block of (apiResponse.content || [])) {
  if (block.type === 'tool_use' && block.name === 'record_expense') {
    extracted = block.input;
    break;
  }
}
if (!extracted) {
  throw new Error('Tool use block not found in extract response: ' + JSON.stringify(apiResponse));
}

// vendor_rules.match_patterns で OR 照合(大文字無視・部分一致)
const vendorRaw = (extracted.vendor_raw || '').toUpperCase();
let ruleKey = null;
let rule = null;
for (const [key, r] of Object.entries(configs.vendor_rules)) {
  if (key.startsWith('_')) continue;
  for (const pat of (r.match_patterns || [])) {
    if (vendorRaw.includes(pat.toUpperCase())) {
      ruleKey = key;
      rule = r;
      break;
    }
  }
  if (ruleKey) break;
}

return {
  json: {
    extract: extracted,
    rule_matched: ruleKey !== null,
    rule_key: ruleKey,
    rule: rule,
    bank: bankInfo,
  }
};
"""

CODE_APPLY_RULE = """// vendor_rules 一致時:rule から ledger 行と Slack payload を組み立て(完了通知)。
// runOnceForEachItem: 各メールごとに 1 回走る。
const data = $json;
const r = data.rule;
const e = data.extract;
const b = data.bank;

const ledgerRow = {
  date: e.transaction_date,
  type: '経費',
  category: r.category,
  vendor: r.vendor,
  description: r.description_template
    ? (e.transaction_category ? `${r.description_template}(${e.transaction_category})` : r.description_template)
    : (e.transaction_category || ''),
  amount_jpy: e.amount_jpy,
  payment_method: b.payment_method,
  apportionment_pct: r.default_apportionment,
  net_amount: Math.round(e.amount_jpy * r.default_apportionment / 100),
  evidence_url: r.evidence_url_template,
  note: `Sample02 自動記録(${e.transaction_date})/ ルール一致(${data.rule_key})`,
};

const amountOriginal = e.amount_original ? ` / ${e.amount_original}` : '';
const slackText = `:white_check_mark: 自動記録しました
─────────
取引先: ${r.vendor}
内容: ${e.transaction_category || ''}${amountOriginal}
金額: ¥${e.amount_jpy.toLocaleString()} (按分 ${r.default_apportionment}% / 計上 ¥${ledgerRow.net_amount.toLocaleString()})
日付: ${e.transaction_date}
支払: ${b.payment_method}
─────────
ledger に追加予定`;

return {
  json: {
    flow: 'auto_record',
    ledger_row: ledgerRow,
    slack_text: slackText,
    extract: e,
    bank: b,
    rule_key: data.rule_key,
  }
};
"""

CODE_FORMAT_FROM_AI = """// Classify レスポンス(prefill="{")を JSON.parse、Slack payload を組み立て。
// Phase 1 仕様: 業務関連 → AI 推奨値で ledger 追記 + 要レビュー通知 / 業務無関係 → 追記スキップ + 通知のみ。
// (Phase 2 で承認ボタン版に切り替え予定。spec.md 9 章参照)
// runOnceForEachItem: 各メールごとに 1 回走る。Parse + Rule Match 出力は pairedItem 経由でアクセス。
const apiResponse = $json;
const data = $('Parse + Rule Match').item.json;
const e = data.extract;
const b = data.bank;

const text = '{' + (apiResponse.content[0].text || '');
let cls;
try {
  cls = JSON.parse(text);
} catch (err) {
  throw new Error('classify JSON parse failed: ' + err.message + ' / raw=' + text);
}

const amountOriginal = e.amount_original ? ` (${e.amount_original})` : '';

if (!cls.is_business_related) {
  // 業務無関係: ledger には追加しない、Slack に通知のみ
  const slackText = `:no_entry_sign: 業務無関係と判定、スキップしました
─────────
取引先: ${cls.vendor} (${e.vendor_raw})
内容: ¥${e.amount_jpy.toLocaleString()} の${e.transaction_category || 'ショッピング'}${amountOriginal}
日付: ${e.transaction_date}
─────────
:robot_face: AI 判定理由: ${cls.reasoning}
─────────
※ ledger には追加していません。業務扱いにしたい場合は手動で追加してください。`;
  return {
    json: {
      flow: 'skipped_not_business',
      ledger_row: null,
      slack_text: slackText,
      classify: cls,
      extract: e,
      bank: b,
    }
  };
}

// 業務関連: AI 推奨値で ledger 追記(備考に要レビューマーカー)+ Slack に要レビュー通知
const netAmount = Math.round(e.amount_jpy * cls.recommended_apportionment / 100);
const reasoningOneLine = (cls.reasoning || '').replace(/\\s+/g, ' ').slice(0, 300);
const ledgerRow = {
  date: e.transaction_date,
  type: '経費',
  category: cls.category,
  vendor: cls.vendor,
  description: e.transaction_category || '',
  amount_jpy: e.amount_jpy,
  payment_method: b.payment_method,
  apportionment_pct: cls.recommended_apportionment,
  net_amount: netAmount,
  evidence_url: '',
  note: `Sample02 AI判定(${e.transaction_date})/ ⚠ 要レビュー(AI 推奨)/ ${reasoningOneLine}`,
};

const slackText = `:warning: AI 推奨で自動追記しました(要レビュー)
─────────
取引先: ${cls.vendor} (${e.vendor_raw})
内容: ¥${e.amount_jpy.toLocaleString()} の${e.transaction_category || 'ショッピング'}${amountOriginal}
日付: ${e.transaction_date}
支払: ${b.payment_method}
カテゴリ: ${cls.category} / 按分 ${cls.recommended_apportionment}% / 計上 ¥${netAmount.toLocaleString()}
─────────
:robot_face: AI 判定理由: ${cls.reasoning}
─────────
ledger に追加予定。按分率に違和感があれば手動で修正してください。`;

return {
  json: {
    flow: 'review_required',
    ledger_row: ledgerRow,
    slack_text: slackText,
    classify: cls,
    extract: e,
    bank: b,
  }
};
"""

CODE_APPEND_LEDGER = """// Step 7 Phase A: finance/ledger_2026.csv への追記。
// auto_record / review_required → AI 推奨 or ルール値で追記、skipped_not_business → ledger 触らず。
// 重複検知: 取引先 + 金額 + 日付の3点一致でスキップ。
// git commit/push は Phase B 以降(現状は週次レビューで人間がまとめてコミット)。
// runOnceForEachItem: 各 item ごとに逐次走るため、複数同時着信時も fs append のレースは発生しない。
const fs = require('fs');

const data = $json;

// 業務無関係スキップ: ledger 操作なし、Slack 通知(skip)はそのまま下流へ
if (data.flow === 'skipped_not_business' || !data.ledger_row) {
  return { json: { ...data, append_status: 'skipped_not_business' } };
}

const r = data.ledger_row;
const LEDGER_PATH = '/data/finance/ledger_2026.csv';

// RFC 4180 準拠: カンマ・改行・ダブルクォート・先頭末尾の空白を含む値のみクォート。
// 既存手動行(クォートなし)とフォーマットを揃え、混在を避ける。
const csvField = (v) => {
  const s = (v == null) ? '' : String(v);
  if (/[,"\\n\\r]/.test(s) || /^\\s/.test(s) || /\\s$/.test(s)) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
};

const newRow = [
  r.date,
  r.type,
  r.category,
  r.vendor,
  r.description || '',
  r.amount_jpy,
  r.payment_method,
  r.apportionment_pct,
  r.net_amount,
  r.evidence_url || '',
  r.note || '',
].map(csvField).join(',');

if (!fs.existsSync(LEDGER_PATH)) {
  throw new Error('Ledger file not found: ' + LEDGER_PATH);
}

// 重複検知(雑な部分一致だが、CSV カラム値をクォート前提で照合)
const existing = fs.readFileSync(LEDGER_PATH, 'utf-8');
const isDup = existing.split(/\\r?\\n/).some(line => {
  if (!line.trim()) return false;
  return line.includes('"' + r.date + '"')
    && line.includes('"' + r.vendor + '"')
    && line.includes('"' + r.amount_jpy + '"');
});

if (isDup) {
  return {
    json: {
      ...data,
      append_status: 'duplicate',
      slack_text: ':information_source: 重複スキップ\\n─────────\\n取引先: ' + r.vendor
        + '\\n金額: ¥' + r.amount_jpy.toLocaleString()
        + '\\n日付: ' + r.date
        + '\\n─────────\\n既に同一取引が ledger に記録されているため、追記しませんでした。',
    }
  };
}

// 末尾改行を保証して追記
const needsNewline = existing.length > 0 && !existing.endsWith('\\n');
fs.appendFileSync(LEDGER_PATH, (needsNewline ? '\\n' : '') + newRow + '\\n');

// 上流の Slack テキスト「ledger に追加予定」を「ledger に追加完了」に置換
const updatedSlackText = (data.slack_text || '').replace('ledger に追加予定', 'ledger に追加完了');

return {
  json: {
    ...data,
    append_status: 'appended',
    slack_text: updatedSlackText,
  }
};
"""


def http_node(node_id: str, name: str, x: int, y: int, body_json: str) -> dict:
    return {
        "parameters": {
            "method": "POST",
            "url": "https://api.anthropic.com/v1/messages",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpCustomAuth",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [{"name": "content-type", "value": "application/json"}]
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
        "credentials": {"httpCustomAuth": {"name": "Anthropic API"}},
    }


def code_node(
    node_id: str, name: str, x: int, y: int, code: str, mode: str = "runOnceForAllItems"
) -> dict:
    params: dict = {"language": "javaScript", "jsCode": code}
    # n8n Code typeVersion 2 のデフォルトは runOnceForAllItems。明示する場合は mode を含める。
    if mode != "runOnceForAllItems":
        params["mode"] = mode
    return {
        "parameters": params,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [x, y],
        "id": node_id,
        "name": name,
    }


def switch_eq_node(
    node_id: str, name: str, x: int, y: int, left_expr: str, branches: list[tuple[str, str]]
) -> dict:
    """branches = [(rightValue, outputKey), ...]"""
    rules = []
    for right, key in branches:
        rules.append(
            {
                "conditions": {
                    "options": {
                        "caseSensitive": True,
                        "leftValue": "",
                        "typeValidation": "loose",
                        "version": 2,
                    },
                    "conditions": [
                        {
                            "leftValue": left_expr,
                            "rightValue": right,
                            "operator": {"type": "string", "operation": "equals"},
                        }
                    ],
                    "combinator": "and",
                },
                "renameOutput": True,
                "outputKey": key,
            }
        )
    return {
        "parameters": {"rules": {"values": rules}, "options": {"fallbackOutput": "extra"}},
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [x, y],
        "id": node_id,
        "name": name,
    }


def build_workflow() -> dict:
    nodes = [
        # 1. Gmail Trigger(credential は Step 5 で接続)
        # simple=false で mailparser 整形済みの from/subject/date/text フィールドを取得
        {
            "parameters": {
                "pollTimes": {"item": [{"mode": "everyMinute"}]},
                "simple": False,
                "filters": {"q": "newer_than:1d"},
                "options": {},
            },
            "type": "n8n-nodes-base.gmailTrigger",
            "typeVersion": 1.2,
            "position": [0, 300],
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Gmail Trigger",
        },
        # 2. Code: Load Configs
        code_node(
            "22222222-2222-2222-2222-222222222222",
            "Load Configs",
            220, 300,
            CODE_LOAD_CONFIGS,
        ),
        # 3. Code: Determine Bank
        code_node(
            "33333333-3333-3333-3333-333333333333",
            "Determine Bank",
            440, 300,
            CODE_DETERMINE_BANK,
        ),
        # 4. Switch: Bank Found?(true → Extract、それ以外は無視出力)
        switch_eq_node(
            "44444444-4444-4444-4444-444444444444",
            "Bank Found?",
            660, 300,
            "={{ String($json.bank_matched) }}",
            [("true", "matched")],
        ),
        # 5. HTTP Request: Extract
        http_node(
            "55555555-5555-5555-5555-555555555555",
            "Extract (Claude)",
            880, 300,
            http_body_extract(),
        ),
        # 6. Code: Parse + Rule Match
        code_node(
            "66666666-6666-6666-6666-666666666666",
            "Parse + Rule Match",
            1100, 300,
            CODE_PARSE_EXTRACT,
            mode="runOnceForEachItem",
        ),
        # 7. Switch: Vendor Rule Hit?
        switch_eq_node(
            "77777777-7777-7777-7777-777777777777",
            "Rule Hit?",
            1320, 300,
            "={{ String($json.rule_matched) }}",
            [("true", "rule_matched"), ("false", "rule_unmatched")],
        ),
        # 8a. Code: Apply Rule(rule 一致)
        code_node(
            "88888888-8888-8888-8888-88888888aaaa",
            "Apply Rule",
            1540, 200,
            CODE_APPLY_RULE,
            mode="runOnceForEachItem",
        ),
        # 8b. HTTP Request: Classify(rule 未一致)
        http_node(
            "88888888-8888-8888-8888-88888888bbbb",
            "Classify (Claude)",
            1540, 400,
            http_body_classify(),
        ),
        # 9. Code: Format From AI
        code_node(
            "99999999-9999-9999-9999-999999999999",
            "Format From AI",
            1760, 400,
            CODE_FORMAT_FROM_AI,
            mode="runOnceForEachItem",
        ),
        # 10. Merge(Apply Rule と Format From AI を集約 — Append モード)
        # ルール一致 / 未定義どちらか片方しか実行されないので、両入力を待つ Combine ではなく
        # 到達した側をそのまま下流に流す Append が正解。
        {
            "parameters": {"mode": "append", "options": {}},
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3.1,
            "position": [1980, 300],
            "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "name": "Merge Paths",
        },
        # 11. Code: Append Ledger(TODO Step 7)
        code_node(
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "Append Ledger",
            2200, 300,
            CODE_APPEND_LEDGER,
            mode="runOnceForEachItem",
        ),
        # 12. HTTP Request: Post to Slack(URL は Step 6 で .env に設定)
        {
            "parameters": {
                "method": "POST",
                "url": "={{ $env.SLACK_WEBHOOK_URL_SAMPLE02 }}",
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [{"name": "content-type", "value": "application/json"}]
                },
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={\n  \"text\": {{ JSON.stringify($json.slack_text) }}\n}",
                "options": {},
            },
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [2420, 300],
            "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
            "name": "Post to Slack",
        },
    ]

    connections = {
        "Gmail Trigger": {"main": [[{"node": "Load Configs", "type": "main", "index": 0}]]},
        "Load Configs": {"main": [[{"node": "Determine Bank", "type": "main", "index": 0}]]},
        "Determine Bank": {"main": [[{"node": "Bank Found?", "type": "main", "index": 0}]]},
        "Bank Found?": {
            # output 0: matched, output 1: fallback(extra)。matched のみ Extract に繋ぐ
            "main": [[{"node": "Extract (Claude)", "type": "main", "index": 0}], []]
        },
        "Extract (Claude)": {
            "main": [[{"node": "Parse + Rule Match", "type": "main", "index": 0}]]
        },
        "Parse + Rule Match": {"main": [[{"node": "Rule Hit?", "type": "main", "index": 0}]]},
        "Rule Hit?": {
            "main": [
                [{"node": "Apply Rule", "type": "main", "index": 0}],
                [{"node": "Classify (Claude)", "type": "main", "index": 0}],
            ]
        },
        "Apply Rule": {"main": [[{"node": "Merge Paths", "type": "main", "index": 0}]]},
        "Classify (Claude)": {"main": [[{"node": "Format From AI", "type": "main", "index": 0}]]},
        "Format From AI": {"main": [[{"node": "Merge Paths", "type": "main", "index": 1}]]},
        "Merge Paths": {"main": [[{"node": "Append Ledger", "type": "main", "index": 0}]]},
        "Append Ledger": {"main": [[{"node": "Post to Slack", "type": "main", "index": 0}]]},
    }

    return {
        "id": "Sample02ExpBot01",
        "name": "Sample02 Expense Auto Detector",
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {"executionOrder": "v1"},
        "versionId": "2",
        "meta": {},
        "tags": [],
    }


def main():
    workflow = build_workflow()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"Generated: {OUT_PATH}")
    print(f"Size: {size_kb:.1f} KB")
    print(f"Nodes: {len(workflow['nodes'])}")
    print(f"Connections: {len(workflow['connections'])}")


if __name__ == "__main__":
    main()
