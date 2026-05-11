# Sample02 テスト結果サマリ

## ユニットテスト(test_extract.py)

- 実行日: 2026-05-09
- テストケース: 7 件(MUFG 5 件 / 楽天カード 1 件 / 三井住友 1 件)
- 結果: **7/7 全件 PASS**
- 検証項目: transaction_date / amount_jpy / vendor_raw_substr / amount_original_keywords / rule_match.matched / classify.decision_hint
- API コスト: 約 6 円(Haiku 4.5、extract 7 calls + classify 4 calls)

## E2E 検証(Step 8 / 実 Gmail)

- 実行日: 2026-05-10
- 対象: 4 経路全分岐を実メールで疎通確認

| 経路 | 内容 | 結果 |
|---|---|---|
| Bank not found | 非業務メール(送信元ホワイトリスト外) | スキップ ✓ |
| Rule hit → 自動記録 | Anthropic 月額(vendor_rules 一致) | ledger 追記 + 完了通知 ✓ |
| AI 判定 → 要レビュー | Amazon(ルール未定義・業務関連あり) | AI 推奨値で ledger 追記 + 要レビュー通知 ✓ |
| AI 判定 → 要レビュー | お名前.com(ルール未定義・業務関連あり) | AI 推奨値で ledger 追記 + 要レビュー通知 ✓ |

### ledger 追記実績(E2E 確認分)

| 取引先 | 金額 | 按分率 | 種別 | 備考 |
|---|---|---|---|---|
| Anthropic | 15,586 円 | 100% | ルール一致 | 自動記録 |
| Amazon | 3,300 円 | AI 推奨値 | AI 判定 | ⚠ 要レビュー |
| お名前.com | 1,628 円 | 100% | AI 判定 | ⚠ 要レビュー |

## 検証環境

| 項目 | 値 |
|---|---|
| n8n バージョン | 2.18.7 |
| Claude モデル | claude-haiku-4-5-20251001 |
| Gmail | aiflowlab.jp@gmail.com(業務専用) |
| 対応銀行/カード | 三菱UFJ VISAデビット / 楽天カード / 三井住友 VPass |

## 技術的ハマりポイント(記録)

- **n8n Switch ノードの型判定**: boolean 値をそのまま渡すとエラー。`String(value)` で文字列化が必要(n8n 2.18.7 / v3.2 仕様)
- **Gmail Trigger の Simplify**: デフォルト ON だと本文(`text`)が返らない。`Simplify: false` 必須
- **Code ノードの multi-item 対応**: `runOnceForAllItems` + `.first()` では複数メール同時着信時に取りこぼしが発生。`runOnceForEachItem` + `$input.item` で対応済み
