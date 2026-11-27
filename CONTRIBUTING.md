# 開発・記録整理の進め方

現在の研究状況は[結果の現在地](docs/results_20261126_ja.md)、実装の役割は[構成案内](docs/repository_map_ja.md)を参照する。
既存の観測と次の仮説を区別し、比較上の有効性を確認できていない結果も残す。

## ローカル確認

リポジトリ直下でPython 3.11以降を使う。通常の単体テスト・method study装置の確認は標準ライブラリで動き、HermesのインストールやAPIキーを必要としない。
実Hermes経路は別途固定されたPython・依存環境を使う。[実Hermes操作ガイド](docs/ci_experiments_ja.md)を参照する。

```bash
python3 -m unittest discover -s tests -v
bash -n scripts/setup_opencode_free.sh scripts/smoke.sh scripts/experiment.sh scripts/install_ci_hermes.sh
python3 -m hiergoal.controller --dry-run
```

method studyの装置を確認する場合だけ、該当するprofileのオフライン確認を行う。
次は模擬応答を使うソフトウェア検証で、実モデルの有効性を測定しない。

```bash
python3 -m hiergoal.study check --profile pilot --output runs/local-check-pilot
```

## ファイルの置き場所

| 内容 | 置き場所 |
|---|---|
| 実装・採点・実験管理 | `hiergoal/`、`evaluation/`、`fixtures/` |
| 回帰テスト | `tests/` |
| 実行・環境補助 | `scripts/`、`ci/`、`.github/workflows/` |
| 現在の説明・結果の考察・過去の監査 | `docs/`。対象版と時点を索引に記す |
| 保存する実験記録 | `experiments/`。元のrun/profile/attemptを保持する |
| 一時的な出力・ローカル検証 | `runs/`。git対象外 |

## 凍結された証拠を扱うとき

- 既存runの`manifest.json`、`results.json`、`trials.csv`、公開receiptを整理目的で上書きしない。
- 事後分析は別文書・別ディレクトリに置き、元runと使用した解析版を示す。
- `hiergoal.study_protocol.SOURCE_FILES`には実装だけでなく4つの文書とmethod workflowが含まれる。注記の追記でも将来のprotocol IDが変わる。単なる導線整理は索引・別紙で行う。
- 手法や採点を変えた場合は、新しい条件としてmanifestを作る。過去のmanifestを新しい実装に合わせて書き換えない。
- 過去runの完全な再生には、元の実行ソースとraw artifactが必要。公開集計のみでraw trace再監査済みとは主張しない。
- `experiments/index.json`の集計・状態は保存された一次ファイルから確認し、試行FAIL、監査FAIL、workflow結論、有効性判定を混ぜない。

## 実モデル実験の開始とCI

追加実験は研究目的・比較条件・予算・停止条件を決めた別作業として行う。整理作業や通常のpushから実モデル推論は開始しない。

| workflow | push時 | 手動実行の既定 | API推論を伴う選択 |
|---|---|---|---|
| `offline.yml` | オフライン検証 | 手動dispatchなし | なし |
| `method-study.yml` | 対象ファイル変更時は`prepare` | `prepare` | 明示的な`run` |
| `live-experiment.yml` | 対象ファイル変更時は`check` | `check` | 明示的な`smoke`・`pilot`・`benchmark` |
| `controlled-recovery.yml` | 通常の変更はオフライン検証・`prepare` | `prepare` | 明示的な`run`、または所有者が承認した単独の一度限りの起動依頼追加 |

Hermes workflowの`check`は実Hermesのインストール・CLI確認を含むが、モデルAPIは呼ばない。
既存の有料実行フラグ・認証経路を省略する変更は行わない。
Controlled Recoveryの専用起動依頼は実装commit・protocol・予算の一致を検査し、変更や再実行を受け付けない。[専用プロトコル](docs/controlled_recovery_protocol_ja.md)を参照する。

## 変更を説明する

変更の理由、実際の変更点、確認した範囲と限界を記す。記録整理だけの場合は、新実験を実施したように書かない。
リンク・件数・保存ファイルの指紋を確認し、必要な回帰テストを一度実行する。過去の全実験を毎回再実行する必要はない。
