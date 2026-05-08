#!/usr/bin/env python3
"""Sample01 返信ドラフトプロンプト 3 種を Anthropic API で叩き、品質を検証。

Usage:
    cd samples/sample01
    python3 scripts/test_draft.py

各テストケースの expected.urgency に応じて 3 種のプロンプトから選んで叩く。
評価軸:
  - 文字数(緊急: 200-300, 通常: 300-400, 簡易: 150-250)
  - 確認質問の有無(? or ? を含むか)
  - 禁止語の不在(現時点では / 念のため / 取り急ぎ / ご検討のほど)
  - 出力本文を表示して目視確認
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SAMPLE_DIR = Path(__file__).resolve().parents[1]
TESTCASE_PATH = SAMPLE_DIR / "testcases" / "inquiries.jsonl"
ENV_PATH = ROOT / ".env"

MODEL = "claude-haiku-4-5-20251001"
API_URL = "https://api.anthropic.com/v1/messages"

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

USER_TEMPLATE = """以下の問い合わせメールに対する返信ドラフトを作成してください。

<inquiry>
<sender_name>{sender_name}</sender_name>
<subject>{subject}</subject>
<body>
{body}
</body>
</inquiry>

<classification>
<category>{category}</category>
<urgency>{urgency}</urgency>
<sentiment>{sentiment}</sentiment>
</classification>"""

URGENCY_TO_PROMPT = {
    "高": ("urgent", SYSTEM_URGENT, (200, 300)),
    "中": ("normal", SYSTEM_NORMAL, (300, 400)),
    "低": ("simple", SYSTEM_SIMPLE, (150, 250)),
}

FORBIDDEN_PHRASES = ["現時点では", "念のため", "取り急ぎ", "ご検討のほど"]


def load_api_key() -> str:
    if not ENV_PATH.exists():
        sys.exit(f"ERROR: {ENV_PATH} not found")
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line.startswith("ANTHROPIC_API_KEY"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("ERROR: ANTHROPIC_API_KEY not found")


def call_api(api_key: str, system: str, sender_name: str, subject: str, body: str,
             category: str, urgency: str, sentiment: str) -> tuple[str, dict]:
    user_prompt = USER_TEMPLATE.format(
        sender_name=sender_name, subject=subject, body=body,
        category=category, urgency=urgency, sentiment=sentiment,
    )
    payload = {
        "model": MODEL,
        "max_tokens": 800,
        "temperature": 0,
        "system": system,
        "messages": [{"role": "user", "content": user_prompt}],
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
    return text, raw


QUESTION_PATTERNS = [
    "?", "?",
    "ですか", "でしょうか", "ますか", "ますでしょうか",
    "いただけますか", "いただけますでしょうか",
    "いただけますと", "いただけますなら",
    "お聞かせ", "お知らせください", "お教えください",
]


def evaluate(text: str, length_range: tuple[int, int]) -> dict:
    char_count = len(text.replace("\n", "").replace(" ", "").replace(" ", ""))
    has_question = any(p in text for p in QUESTION_PATTERNS)
    forbidden_hits = [p for p in FORBIDDEN_PHRASES if p in text]
    has_markdown = bool(re.search(r"\*\*|^#+\s|^-\s|^\*\s", text, re.MULTILINE))
    in_range = length_range[0] <= char_count <= length_range[1]
    return {
        "char_count": char_count,
        "in_range": in_range,
        "has_question": has_question,
        "forbidden_hits": forbidden_hits,
        "has_markdown": has_markdown,
        "length_range": length_range,
    }


def main():
    api_key = load_api_key()
    cases = []
    with TESTCASE_PATH.open() as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    print(f"Running {len(cases)} draft generations against {MODEL}\n")
    print("=" * 80)

    total_input_tokens = 0
    total_output_tokens = 0
    pass_count = {"length": 0, "question": 0, "no_forbidden": 0, "no_markdown": 0, "all": 0}

    for case in cases:
        cid = case["id"]
        inp = case["input"]
        cls = case["expected"]
        urgency = cls["urgency"]
        prompt_kind, system, length_range = URGENCY_TO_PROMPT[urgency]

        try:
            text, raw = call_api(
                api_key, system,
                sender_name=inp["sender_name"], subject=inp["subject"], body=inp["body"],
                category=cls["category"], urgency=urgency, sentiment=cls["sentiment"],
            )
        except urllib.error.HTTPError as e:
            print(f"[{cid}] HTTP ERROR: {e.code}\n{e.read().decode('utf-8')}")
            sys.exit(1)

        usage = raw.get("usage", {})
        total_input_tokens += usage.get("input_tokens", 0)
        total_output_tokens += usage.get("output_tokens", 0)

        ev = evaluate(text, length_range)
        all_pass = ev["in_range"] and ev["has_question"] and not ev["forbidden_hits"] and not ev["has_markdown"]
        if ev["in_range"]: pass_count["length"] += 1
        if ev["has_question"]: pass_count["question"] += 1
        if not ev["forbidden_hits"]: pass_count["no_forbidden"] += 1
        if not ev["has_markdown"]: pass_count["no_markdown"] += 1
        if all_pass: pass_count["all"] += 1

        status = "PASS" if all_pass else "FAIL"
        print(f"\n[{cid}] {status}  (prompt: {prompt_kind}, urgency: {urgency})")
        print(f"  字数: {ev['char_count']}  期待範囲: {length_range[0]}-{length_range[1]}  {'✓' if ev['in_range'] else '✗'}")
        print(f"  確認質問: {'✓' if ev['has_question'] else '✗ なし'}")
        print(f"  禁止語: {'✓ なし' if not ev['forbidden_hits'] else '✗ ' + ', '.join(ev['forbidden_hits'])}")
        print(f"  Markdown: {'✓ なし' if not ev['has_markdown'] else '✗ あり'}")
        print(f"  --- 出力 ---")
        for line in text.split("\n"):
            print(f"  {line}")

        time.sleep(0.3)

    n = len(cases)
    print("\n" + "=" * 80)
    print("SUMMARY")
    print(f"  全要件 PASS:    {pass_count['all']}/{n}")
    print(f"  字数範囲内:     {pass_count['length']}/{n}")
    print(f"  確認質問あり:   {pass_count['question']}/{n}")
    print(f"  禁止語なし:     {pass_count['no_forbidden']}/{n}")
    print(f"  Markdown なし:  {pass_count['no_markdown']}/{n}")
    print(f"  Tokens: in={total_input_tokens}, out={total_output_tokens}")
    cost_usd = total_input_tokens / 1_000_000 * 1.0 + total_output_tokens / 1_000_000 * 5.0
    print(f"  Estimated cost: ${cost_usd:.5f}")


if __name__ == "__main__":
    main()
