#!/usr/bin/env python3
"""Sample02 抽出+分類プロンプトを Anthropic API で叩き、testcases.jsonl の期待値と照合する。

検証する観点:
    - extract: Tool Use で transaction_date / amount_jpy / amount_original / vendor_raw を抽出
    - rule_match: vendor_rules.example.json の match_patterns で vendor_raw を OR 照合
    - classify: rule 未一致のケースで decision_hint と按分率レンジが期待通りか

Usage:
    cd samples/sample02
    python3 scripts/test_extract.py

前提:
    side-hustle/.env に ANTHROPIC_API_KEY=... が入っていること
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # side-hustle/
SAMPLE_DIR = Path(__file__).resolve().parents[1]  # samples/sample02/
TESTCASE_PATH = SAMPLE_DIR / "testcases" / "testcases.jsonl"
EXTRACT_PROMPT = SAMPLE_DIR / "prompts" / "extract.md"
CLASSIFY_PROMPT = SAMPLE_DIR / "prompts" / "classify.md"
BANK_SENDERS_PATH = SAMPLE_DIR / "config" / "bank_senders.example.json"
VENDOR_RULES_PATH = SAMPLE_DIR / "config" / "vendor_rules.example.json"
BUSINESS_CONTEXT_PATH = SAMPLE_DIR / "config" / "business_context.md"
ENV_PATH = ROOT / ".env"

MODEL = "claude-haiku-4-5-20251001"
API_URL = "https://api.anthropic.com/v1/messages"


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


def extract_md_block(md_path: Path, header: str, fence: str = "```") -> str:
    """Markdown ファイル内の "## {header}" 直後の最初のコードブロックを返す。"""
    text = md_path.read_text()
    pattern = re.compile(
        rf"^##\s+{re.escape(header)}\s*$.*?{re.escape(fence)}(?:json)?\n(.*?)\n{re.escape(fence)}",
        re.DOTALL | re.MULTILINE,
    )
    m = pattern.search(text)
    if not m:
        sys.exit(f"ERROR: '## {header}' のコードブロックが {md_path} に見つかりません")
    return m.group(1)


def call_api(api_key: str, payload: dict) -> dict:
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
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_extract(api_key: str, system: str, tool_def: dict, user_prompt: str) -> tuple[dict, dict]:
    payload = {
        "model": MODEL,
        "max_tokens": 512,
        "temperature": 0,
        "system": system,
        "tools": [tool_def],
        "tool_choice": {"type": "tool", "name": tool_def["name"]},
        "messages": [{"role": "user", "content": user_prompt}],
    }
    raw = call_api(api_key, payload)
    for block in raw.get("content", []):
        if block.get("type") == "tool_use" and block.get("name") == tool_def["name"]:
            return block["input"], raw
    return {}, raw


def call_classify(api_key: str, system: str, user_prompt: str) -> tuple[dict, dict]:
    prefill = "{"
    payload = {
        "model": MODEL,
        "max_tokens": 512,
        "temperature": 0,
        "system": system,
        "messages": [
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": prefill},
        ],
    }
    raw = call_api(api_key, payload)
    text = prefill + raw["content"][0]["text"]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        parsed = {"_parse_error": str(e), "_raw_text": text}
    return parsed, raw


def match_vendor_rule(vendor_raw: str, vendor_rules: dict) -> tuple[str | None, dict | None]:
    """vendor_raw が match_patterns のいずれかを部分一致で含むかを大小無視で判定。"""
    upper = vendor_raw.upper()
    for key, rule in vendor_rules.items():
        if key.startswith("_") or not isinstance(rule, dict):
            continue
        for pat in rule.get("match_patterns", []):
            if pat.upper() in upper:
                return key, rule
    return None, None


def build_extract_user_prompt(case_input: dict) -> str:
    return (
        "以下のクレカ明細メールから取引情報を抽出してください。\n\n"
        f"<email_subject>\n{case_input['subject']}\n</email_subject>\n\n"
        f"<email_received_at>\n{case_input['received_at']}\n</email_received_at>\n\n"
        f"<email_body>\n{case_input['body']}\n</email_body>"
    )


def build_classify_user_prompt(extracted: dict, business_context: str) -> str:
    return (
        "以下の取引情報について、ユーザーの業務関連性と按分率を判定してください。\n\n"
        f"<user_business_context>\n{business_context}\n</user_business_context>\n\n"
        "<transaction>\n"
        f"取引先(原文): {extracted.get('vendor_raw', '')}\n"
        f"金額: {extracted.get('amount_jpy', '')} 円\n"
        f"原通貨: {extracted.get('amount_original', '')}\n"
        f"ご利用区分: {extracted.get('transaction_category', '')}\n"
        f"取引日: {extracted.get('transaction_date', '')}\n"
        "</transaction>"
    )


def check_extract(actual: dict, expected: dict) -> list[str]:
    """Returns list of failure messages (empty if all pass)."""
    fails = []
    for k in ("transaction_date", "amount_jpy"):
        if actual.get(k) != expected[k]:
            fails.append(f"extract.{k}: expected={expected[k]!r} actual={actual.get(k)!r}")
    vendor_raw = actual.get("vendor_raw", "")
    if expected["vendor_raw_substr"] not in vendor_raw:
        fails.append(
            f"extract.vendor_raw: '{expected['vendor_raw_substr']}' not in {vendor_raw!r}"
        )
    amount_original = actual.get("amount_original", "") or ""
    for kw in expected.get("amount_original_keywords", []):
        if kw not in amount_original:
            fails.append(
                f"extract.amount_original: keyword '{kw}' not in {amount_original!r}"
            )
    return fails


def check_rule_match(actual_key: str | None, expected: dict) -> list[str]:
    fails = []
    actual_matched = actual_key is not None
    if actual_matched != expected["matched"]:
        fails.append(f"rule_match.matched: expected={expected['matched']} actual={actual_matched}")
    if expected["matched"] and actual_key != expected.get("vendor_key"):
        fails.append(
            f"rule_match.vendor_key: expected={expected['vendor_key']!r} actual={actual_key!r}"
        )
    return fails


def check_classify(actual: dict, expected: dict) -> list[str]:
    fails = []
    if actual.get("is_business_related") != expected["is_business_related"]:
        fails.append(
            f"classify.is_business_related: expected={expected['is_business_related']} "
            f"actual={actual.get('is_business_related')}"
        )
    hint = actual.get("decision_hint")
    if hint not in expected["decision_hint_in"]:
        fails.append(
            f"classify.decision_hint: expected_in={expected['decision_hint_in']} actual={hint!r}"
        )
    appor = actual.get("recommended_apportionment")
    lo, hi = expected["recommended_apportionment_range"]
    if not (isinstance(appor, (int, float)) and lo <= appor <= hi):
        fails.append(
            f"classify.recommended_apportionment: expected in [{lo},{hi}] actual={appor!r}"
        )
    return fails


def main():
    api_key = load_api_key()
    extract_system = extract_md_block(EXTRACT_PROMPT, "System プロンプト")
    classify_system = extract_md_block(CLASSIFY_PROMPT, "System プロンプト")
    tool_def_text = extract_md_block(EXTRACT_PROMPT, "Tool 定義(record_expense)")
    tool_def = json.loads(tool_def_text)
    business_context = BUSINESS_CONTEXT_PATH.read_text()
    vendor_rules = json.loads(VENDOR_RULES_PATH.read_text())

    cases = []
    with TESTCASE_PATH.open() as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    print(f"Running {len(cases)} test cases against {MODEL}\n" + "=" * 80)

    pass_count = 0
    failures = []
    total_in_tokens = 0
    total_out_tokens = 0
    classify_called = 0

    for case in cases:
        cid = case["id"]
        note = case.get("note", "")
        case_fails: list[str] = []

        # 1. Extract
        try:
            extracted, raw = call_extract(
                api_key,
                extract_system,
                tool_def,
                build_extract_user_prompt(case["input"]),
            )
        except urllib.error.HTTPError as e:
            print(f"[{cid}] HTTP ERROR (extract): {e.code} {e.reason}")
            print(e.read().decode("utf-8"))
            sys.exit(1)
        usage = raw.get("usage", {})
        total_in_tokens += usage.get("input_tokens", 0)
        total_out_tokens += usage.get("output_tokens", 0)
        case_fails.extend(check_extract(extracted, case["expected"]["extract"]))

        # 2. Rule match
        vendor_raw = extracted.get("vendor_raw", "")
        rule_key, rule = match_vendor_rule(vendor_raw, vendor_rules)
        case_fails.extend(check_rule_match(rule_key, case["expected"]["rule_match"]))

        # 3. Classify (only if rule did not match)
        actual_classify = None
        if rule_key is None:
            classify_called += 1
            try:
                actual_classify, raw_c = call_classify(
                    api_key,
                    classify_system,
                    build_classify_user_prompt(extracted, business_context),
                )
            except urllib.error.HTTPError as e:
                print(f"[{cid}] HTTP ERROR (classify): {e.code} {e.reason}")
                print(e.read().decode("utf-8"))
                sys.exit(1)
            usage_c = raw_c.get("usage", {})
            total_in_tokens += usage_c.get("input_tokens", 0)
            total_out_tokens += usage_c.get("output_tokens", 0)
            if case["expected"]["classify"] is None:
                case_fails.append("classify: expected to skip (rule matched), but rule did not match")
            else:
                case_fails.extend(check_classify(actual_classify, case["expected"]["classify"]))
        else:
            if case["expected"]["classify"] is not None:
                case_fails.append(
                    f"classify: expected to run (rule unmatched), but rule '{rule_key}' matched"
                )

        # Report
        if not case_fails:
            print(f"[{cid}] OK   {note}")
            pass_count += 1
        else:
            print(f"[{cid}] FAIL {note}")
            for msg in case_fails:
                print(f"    - {msg}")
            failures.append(cid)
            # 失敗時は extract / classify の actual を見られるように出す
            print(f"    extract.actual = {json.dumps(extracted, ensure_ascii=False)}")
            if actual_classify is not None:
                print(f"    classify.actual = {json.dumps(actual_classify, ensure_ascii=False)}")

        time.sleep(0.3)

    n = len(cases)
    print("=" * 80)
    print("SUMMARY")
    print(f"  PASS: {pass_count}/{n} ({pass_count * 100 // n}%)")
    if failures:
        print(f"  FAILURES: {', '.join(failures)}")
    print(f"  classify calls: {classify_called}")
    print(f"  Tokens: in={total_in_tokens}, out={total_out_tokens}")
    # Haiku 4.5 pricing: $1/MTok in, $5/MTok out
    cost_usd = total_in_tokens / 1_000_000 * 1.0 + total_out_tokens / 1_000_000 * 5.0
    print(f"  Estimated cost: ${cost_usd:.5f} (Haiku 4.5)")

    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
