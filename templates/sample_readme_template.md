# Sample XX — [サンプル名]

[1〜2 行で何をするワークフローかを説明]

## こんな方におすすめ

- [ターゲット読者 1]
- [ターゲット読者 2]
- [ターゲット読者 3]

## 構成

[ノード数] ノードの n8n ワークフロー:

```
[ノード名1] → [ノード名2] → ... → [ノード名N]
```

詳細は [samples/sampleXX/demo/flow.md](./demo/flow.md) を参照。

## 検証結果

- **[指標1]**: [値]
- **[指標2]**: [値]
- **[指標3]**: [値]

詳細は [samples/sampleXX/demo/test_results.md](./demo/test_results.md) を参照。

## スクリーンショット

- [ワークフロー全体](./demo/screenshots/workflow_canvas.png)
- [主要な出力例 1](./demo/screenshots/[filename].png)
- [主要な出力例 2](./demo/screenshots/[filename].png)

## 動かし方

### 前提

- Docker(n8n 用)
- Python 3.10+
- Anthropic API キー
- [サンプル固有の前提条件]

### 1. [セットアップ手順 1]

```bash
[コマンド例]
```

### 2. n8n を起動(Docker Compose)

```bash
docker compose up -d
# http://localhost:5678 にアクセスして初期セットアップ
```

### 3. ワークフローをビルド・インポート

```bash
cd samples/sampleXX
python3 scripts/build_n8n_workflow.py
```

生成された `n8n/sampleXX_workflow.json` を n8n UI からインポート。インポート後は **Unpublish → Publish** で Active 化。

### 4. ローカル検証

```bash
cd samples/sampleXX
python3 scripts/[test_script].py
```

### 5. [サンプル固有の動作確認手順]

[説明]

## ディレクトリ構成

```
sampleXX/
├── n8n/
│   └── sampleXX_workflow.json    # n8n ワークフロー定義(import 用)
├── prompts/
│   └── [prompt].md               # プロンプト解説
├── scripts/
│   ├── test_[name].py            # 精度ローカル検証
│   └── build_n8n_workflow.py     # ワークフロー JSON ビルダー
├── testcases/
│   └── [testcases].[ext]         # テストケース
└── demo/
    ├── flow.md                   # アーキテクチャ図と設計ポイント
    ├── test_results.md           # 検証結果サマリ
    ├── examples.md               # 入出力対比
    └── screenshots/              # 各種スクリーンショット
```
