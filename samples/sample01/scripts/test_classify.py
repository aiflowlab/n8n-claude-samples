#!/usr/bin/env python3
"""Sample01 分類プロンプトを Anthropic API で叩き、テストケースとの一致率を出す。

Usage:
    cd samples/sample01
    python3 scripts/test_classify.py

前提:
    side-hustle/.env に ANTHROPIC_API_KEY=... が入っていること
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # side-hustle/
SAMPLE_DIR = Path(__file__).resolve().parents[1]  # samples/sample01/
TESTCASE_PATH = SAMPLE_DIR / "testcases" / "inquiries.jsonl"
ENV_PATH = ROOT / ".env"

MODEL = "claude-haiku-4-5-20251001"
API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """あなたは BtoB 企業の顧客対応窓口で、受信した問い合わせメールを分類するアシスタントです。

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

USER_TEMPLATE = """以下の問い合わせメールを分類してください。

<inquiry>
<sender_name>{sender_name}</sender_name>
<sender_email>{sender_email}</sender_email>
<subject>{subject}</subject>
<body>
{body}
</body>
</inquiry>"""

PREFILL = "{"


def load_api_key() -> str:
    if not ENV_PATH.exists():
        sys.exit(f"ERROR: {ENV_PATH} not found")
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("ANTHROPIC_API_KEY"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("ERROR: ANTHROPIC_API_KEY not found in .env")


def call_api(api_key: str, sender_name: str, sender_email: str, subject: str, body: str) -> tuple[dict, dict]:
    """Returns (parsed_json_output, raw_response)."""
    user_prompt = USER_TEMPLATE.format(
        sender_name=sender_name, sender_email=sender_email, subject=subject, body=body
    )
    payload = {
        "model": MODEL,
        "max_tokens": 256,
        "temperature": 0,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": PREFILL},
        ],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    text = raw["content"][0]["text"]
    full_json_text = PREFILL + text
    try:
        parsed = json.loads(full_json_text)
    except json.JSONDecodeError as e:
        parsed = {"_parse_error": str(e), "_raw_text": full_json_text}
    return parsed, raw


def compare(expected: dict, actual: dict) -> dict:
    """Returns per-field match dict."""
    fields = ["category", "urgency", "sentiment", "recommended_response_deadline"]
    return {f: expected.get(f) == actual.get(f) for f in fields}


def main():
    api_key = load_api_key()
    cases = []
    with TESTCASE_PATH.open() as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    print(f"Running {len(cases)} test cases against {MODEL}\n")
    print("=" * 80)

    field_correct = {"category": 0, "urgency": 0, "sentiment": 0, "recommended_response_deadline": 0}
    all_correct_count = 0
    total_input_tokens = 0
    total_output_tokens = 0
    failures = []

    for case in cases:
        cid = case["id"]
        inp = case["input"]
        expected = case["expected"]
        note = case.get("note", "")

        try:
            actual, raw = call_api(api_key, **inp)
        except urllib.error.HTTPError as e:
            print(f"[{cid}] HTTP ERROR: {e.code} {e.reason}")
            print(e.read().decode("utf-8"))
            sys.exit(1)
        except Exception as e:
            print(f"[{cid}] ERROR: {e}")
            continue

        usage = raw.get("usage", {})
        total_input_tokens += usage.get("input_tokens", 0)
        total_output_tokens += usage.get("output_tokens", 0)

        match = compare(expected, actual)
        all_match = all(match.values())
        if all_match:
            all_correct_count += 1
        for f, ok in match.items():
            if ok:
                field_correct[f] += 1

        status = "OK " if all_match else "DIFF"
        print(f"[{cid}] {status}  {note}")
        if not all_match:
            failures.append(cid)
            for f in ["category", "urgency", "sentiment", "recommended_response_deadline"]:
                mark = "✓" if match[f] else "✗"
                print(f"    {mark} {f}: expected={expected.get(f)!r}  actual={actual.get(f)!r}")
        time.sleep(0.3)

    n = len(cases)
    print("\n" + "=" * 80)
    print("SUMMARY")
    print(f"  All-fields match: {all_correct_count}/{n} ({all_correct_count*100//n}%)")
    for f, c in field_correct.items():
        print(f"  {f:35s} {c}/{n} ({c*100//n}%)")
    if failures:
        print(f"  Failures: {', '.join(failures)}")
    print(f"  Tokens: in={total_input_tokens}, out={total_output_tokens}")
    # Haiku 4.5 pricing: $1/MTok in, $5/MTok out
    cost_usd = total_input_tokens / 1_000_000 * 1.0 + total_output_tokens / 1_000_000 * 5.0
    print(f"  Estimated cost: ${cost_usd:.5f}")


if __name__ == "__main__":
    main()
