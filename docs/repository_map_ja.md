# リポジトリ構成

現在の研究対象は、Hermesを必要としない三方式の比較実験である。
初期の外付けHermes制御器も、実験履歴と再現手順のために保持する。
この文書は役割と読む順序を整理し、既存のコード・採点・アーカイブの配置は変更しない。

## 1. 最初に見る場所

| 場所 | 役割 |
|---|---|
| [README](../README.md) | 現在地と実行入口 |
| [最新結果](results_20261126_ja.md) / [考察](discussion_20261126_ja.md) | 実験結果、根拠、解釈の限界 |
| [文書索引](README.md) | 仕様、運用手順、歴史的監査への案内 |
| [experiments](../experiments/README.md) | 公開結果と当時のmanifest・検証記録 |
| [CONTRIBUTING](../CONTRIBUTING.md) | 変更・検証・証拠保全の方針 |

## 2. 現行の比較実験：`hiergoal/study*`

| ファイル | 責務 | 確認したい問い |
|---|---|---|
| [`study.py`](../hiergoal/study.py) | `prepare`・`check`・`run`・`collect`、実行制御、記録、再生監査 | いつ呼び出し、故障を導入し、終了するか |
| [`study_protocol.py`](../hiergoal/study_protocol.py) | プロファイル、試行割付、上限、manifest、ソース指紋 | 何を実行前に固定するか |
| [`study_tasks.py`](../hiergoal/study_tasks.py) | 三課題族、公開診断、非公開最終採点、故障 | 何を成功と判定し、何を壊すか |
| [`study_scale.py`](../hiergoal/study_scale.py) | 複合課題、階層の規模・深さ・依存設定 | 規模条件で何が変わるか |
| [`study_planning.py`](../hiergoal/study_planning.py) | 初期計画、構造検証、状態、実行可能な葉の選択 | 目標と依存関係をどう表すか |
| [`study_mechanisms.py`](../hiergoal/study_mechanisms.py) | 葉の指示改訂、再計画許可、局所性などの証拠集計 | 変更をどこまで許し、何を確認するか |
| [`study_api.py`](../hiergoal/study_api.py) / [`study_wire.py`](../hiergoal/study_wire.py) | API通信、応答・利用量・診断、送信形式 | モデルと何を送受信するか |
| [`study_analysis.py`](../hiergoal/study_analysis.py) | 比較、費用、課題単位の集計、有限基準、レポート | 成否と不確かさをどう解釈するか |
| [`study_suite.py`](../hiergoal/study_suite.py) | 互換なmechanism・scale・reliabilityの再生と9要件照合 | 複数profileを同じ文脈で評価できるか |
| [`study_archive.py`](../hiergoal/study_archive.py) | 公開許可項目への投影、レシート、ハッシュ・再集計検証 | 何を公開し、元結果との対応をどう確認するか |

変更箇所を探す際は、[比較実験プロトコル](method_study_ja.md)と対象関数を対応させる。
採点はモデルの自己申告ではなくホスト側で行う。現在の再計画は失敗した葉の指示を更新する方式で、
階層の分割・統合を実装したものではない。

## 3. 初期Hermes経路

| 場所 | 責務 |
|---|---|
| [`controller.py`](../hiergoal/controller.py) / [`core.py`](../hiergoal/core.py) | 外付け階層制御、Hermes実行、依存関係、再計画、保存状態 |
| [`cases.py`](../hiergoal/cases.py) / [`benchmark.py`](../hiergoal/benchmark.py) | 固定台帳課題の欠陥条件と反復スケジュール |
| [`preflight.py`](../hiergoal/preflight.py) / [`preflight_luna.py`](../hiergoal/preflight_luna.py) | 任意のOpenCode ACP経路／直接OpenAI経路の実行前確認 |
| [`provenance.py`](../hiergoal/provenance.py) / [`report.py`](../hiergoal/report.py) | 実行元の記録、独立評価に照合した公開レポート |
| [`ci.py`](../hiergoal/ci.py) / [`ci_report.py`](../hiergoal/ci_report.py) | CIでの導入確認・実行・終了状態・公開結果 |
| [`fixtures/ledger_release`](../fixtures/ledger_release) | エージェントが修正する台帳課題と可視テスト |
| [`evaluation/test_release.py`](../evaluation/test_release.py) | エージェントの作業領域とは別の受入検証 |
| [`ci/hermes.json`](../ci/hermes.json) | CIで固定するHermes実装条件 |
| [`scripts`](../scripts) | Hermes導入、バックエンド設定、実行補助、stream集計 |

この経路は[Hermes CI手順](ci_experiments_ja.md)から使う。
`fixtures/`と`evaluation/`は初期Hermes課題用であり、現行method studyの採点は`study_tasks.py`側にある。

## 4. テストとworkflow

### オフラインテスト

[`tests/`](../tests)は主に次の二群を持つ。ファイル名で対象を辿れる。

| 群 | 主な対象 |
|---|---|
| `test_study*.py` | 割付・課題・計画・API形式・予算・記録順序・再生・解析・公開・9要件 |
| その他の `test_*.py` | Hermes制御器、課題、事前確認、Luna経路、CI、公開レポート、再開 |

テストは`python3 -m unittest discover -s tests -v`で実行する。
装置の模擬検証には`python3 -m hiergoal.study check`を用いる。
実モデル性能の判断には[実行結果](results_20261126_ja.md)が必要である。

### GitHub Actions

| Workflow | 通常の役割 | モデル実行を行う入口 |
|---|---|---|
| [`offline.yml`](../.github/workflows/offline.yml) | push / pull request時の単体テスト、模擬試行、manifest準備、9要件の工程検査 | なし |
| [`method-study.yml`](../.github/workflows/method-study.yml) | 指定ファイルのpush時、または手動`prepare`でオフライン検証・準備 | 手動`mode=run`のみ |
| [`live-experiment.yml`](../.github/workflows/live-experiment.yml) | 指定ファイルのpush時、または手動`check`で実Hermesの導入・CLI確認 | 手動`smoke` / `pilot` / `benchmark` |

通常のpushでモデル推論は起動しない。インストール・CLI確認の成功と実モデル実行の成功を区別する。
各workflowの対象ファイル、入力既定値、権限はYAMLを正とする。

## 5. 保存物と再現に必要な証拠

| 場所・形式 | 内容 | 用途と限界 |
|---|---|---|
| `runs/` | ローカルのmanifest、計画、raw trace、成果物、集計など | Git対象外。再生に必要な完全なrunを保持する |
| `experiments/method-study-live/` | 公開許可項目に限定した実API結果、条件、完了状態、公開レシート | 公開結果の確認。raw traceの代わりにはならない |
| [`experiments/hermes-live/`](../experiments/hermes-live/README.md) | 初期Hermesの公開用監査レポート、集計、取り込み元の指紋 | Actions artifactから保存。元のraw stream・採点ファイルは含まない |
| `experiments/method-study-v*/` | 当時のmanifest、オフライン検証、回帰診断など | 版ごとの履歴。現在のモデル性能と混同しない |
| Actions artifact | workflowが保存した完全runまたは公開レポート | 内容と保持期限はworkflowごとに異なる。初期Hermesの保存物にraw traceは含まれない |

公開ディレクトリにあるファイルの役割は次のとおり。

| ファイル | 確認する内容 |
|---|---|
| `manifest.json` | 割付、条件、予算、モデル、ソース指紋 |
| `execution.json` | 実行の進捗・終了・継続判定 |
| `host.json` | 実行ホストの測定条件 |
| `results.json` / `trials.csv` | 個別結果、欠測、費用、監査状態 |
| `summary.json` / `summary.md` | 集計、比較、要件別の判定 |
| `publication.json` | 実行ID・attempt・実行コミット、公開内容の照合情報 |

全ファイルが必ず存在するとは限らない。未回収や未完了のレシートを成功扱いにせず、
[アーカイブ索引](../experiments/README.md)と各runの記録を読む。

## 6. 指紋対象と歴史的本文

[`study_protocol.SOURCE_FILES`](../hiergoal/study_protocol.py)は、10のPythonソース、
4文書、`method-study.yml`の計15ファイルを指紋対象とする。
対象の文書は以下の4つである。

- [比較実験プロトコル](method_study_ja.md)
- [9要件の監査](method_requirements_audit_ja.md)
- [v2.4再監査](method_reaudit_v2_4_ja.md)
- [v2.5修正記録](method_resume_v2_5_ja.md)

これらは当時の本文を保持する。現在の進捗は[最新結果](results_20261126_ja.md)に記載し、
仕様変更は新しい指紋とmanifestで扱う。異なる版の記録を混合したり、旧結果を上書きしたりしない。
`study_suite`もソース・モデル・分析条件の互換性を検査する。

[文書索引へ戻る](README.md)
