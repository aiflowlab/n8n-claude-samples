# Sample02 動作例(7 ケース)

各ケースの入力メール → 抽出結果 → ledger 追記 / Slack 通知 の対比。

---

## ケース 01: Anthropic 月額(ルール一致 / 自動記録)

**入力メール**
- 送信元: `direct@mail.bk.mufg.jp`
- 件名: 【三菱UFJ-VISAデビット】ご利用のお知らせ
- 利用先: ANTHROPIC PBC NEW YORK US
- 金額: 15,586 円(US$199.00)

**抽出結果**
```json
{ "transaction_date": "2026-05-29", "amount_jpy": 15586, "vendor_raw": "ANTHROPIC PBC" }
```

**処理**: vendor_rules 一致(anthropic) → カテゴリ: サービス利用料 / 按分率: 100%

**ledger 追記**
```
2026-05-29, 経費, サービス利用料, Anthropic, Anthropic(月額), 15586, デビット(MUFG), 100, 15586, -, -
```

**Slack 通知**: ✅ 完了通知(自動記録済み)

---

## ケース 02: Anthropic 少額チャージ(ルール一致 / 自動記録)

**入力メール**
- 送信元: `direct@mail.bk.mufg.jp`
- 利用先: ANTHROPIC PBC NEW YORK US
- 金額: 895 円(US$5.50)

**処理**: vendor_rules 一致(anthropic) → カテゴリ: サービス利用料 / 按分率: 100%

**ledger 追記**
```
2026-06-15, 経費, サービス利用料, Anthropic, Anthropic(月額), 895, デビット(MUFG), 100, 895, -, -
```

**Slack 通知**: ✅ 完了通知

---

## ケース 03: n8n 月額(ルール一致 / 楽天カード)

**入力メール**
- 送信元: `info@mail.rakuten-card.co.jp`
- 件名: カード利用のお知らせ(本人ご利用分)
- 利用先: N8N.IO
- 金額: 3,150 円(20.00 USD)

**ポイント**: 銀行フォーマットが MUFG と異なるが Claude が差を吸収して抽出

**処理**: vendor_rules 一致(n8n) → カテゴリ: サービス利用料 / 按分率: 100%

**ledger 追記**
```
2026-07-02, 経費, サービス利用料, n8n, n8n(月額), 3150, クレジット(楽天カード), 100, 3150, -, -
```

**Slack 通知**: ✅ 完了通知

---

## ケース 04: Amazon 低額(ルール未定義 / AI 判定 → 要レビュー)

**入力メール**
- 送信元: `direct@mail.bk.mufg.jp`
- 利用先: AMAZON.CO.JP
- 金額: 3,300 円

**処理**: vendor_rules 未定義 → Claude が business_context を参照して判定
- is_business_related: true
- recommended_apportionment_range: 70〜100%
- decision_hint: review_required(書籍か私用品か判断できない)

**ledger 追記**
```
2026-06-02, 経費, 消耗品費, Amazon, Amazon.co.jp, 3300, デビット(MUFG), 70, 2310, -, ⚠ 要レビュー(AI 推奨按分率 70-100%)
```

**Slack 通知**: ⚠ 要レビュー通知(AI 推奨値で記録済み、按分率を要確認)

---

## ケース 05: Amazon 高額(ルール未定義 / AI 判定 → 要レビュー / 三井住友)

**入力メール**
- 送信元: `statement@vpass.ne.jp`(三井住友 VPass)
- 利用先: AMAZON.CO.JP
- 金額: 45,000 円

**ポイント**: 3 銀行目のフォーマット。高額のため AI も慎重に判定

**処理**: vendor_rules 未定義 → AI 判定
- is_business_related: true
- decision_hint: review_required

**Slack 通知**: ⚠ 要レビュー通知

---

## ケース 06: ドメイン更新(ルール未定義 / AI 判定 → 要レビュー)

**入力メール**
- 送信元: `direct@mail.bk.mufg.jp`
- 利用先: ONAMAE COM(お名前.com)
- 金額: 1,628 円

**処理**: vendor_rules 未定義 → AI 判定
- is_business_related: true
- recommended_apportionment_range: 100%
- decision_hint: review_required(ドメイン更新と推定されるが確認推奨)

**Slack 通知**: ⚠ 要レビュー通知

---

## ケース 07: 西友ネットスーパー(ルール未定義 / AI 判定 → スキップ推奨)

**入力メール**
- 送信元: `direct@mail.bk.mufg.jp`
- 利用先: SEIYU NET SUPER
- 金額: 820 円

**処理**: vendor_rules 未定義 → AI 判定
- is_business_related: false
- recommended_apportionment_range: 0%
- decision_hint: skip_not_business(食料品・日用品と判定)

**ledger 追記**: なし

**Slack 通知**: ⏭ スキップ通知(業務関連なしと判定)

---

## 経路サマリ

| 経路 | ケース数 | 説明 |
|---|---|---|
| ルール一致 → 自動記録 | 3 件(01/02/03) | vendor_rules に登録済みの取引先、ノータッチで ledger 追記 |
| AI 判定 → 要レビュー | 3 件(04/05/06) | 業務関連の可能性ありで AI 推奨値記録、Slack で確認促す |
| AI 判定 → スキップ | 1 件(07) | 業務関連なしと判定、ledger に記録しない |
