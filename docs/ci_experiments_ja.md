# Hermes / OpenAI API 実験ワークフローの操作資料

> **現在の位置づけ（2026年11月26日 JST）。** 実Hermesのpilotとbenchmarkは実施済みで、現在は既存結果を整理し、追加実験の計画を検討する段階である。[結果と主張範囲](results_20261126_ja.md)を先に参照する。本書は既存ワークフローの操作仕様を説明するもので、追加実験の開始予定ではない。手動実行の既定modeは、API推論を行わない`check`である。

通常の `offline.yml` は模擬 Hermes によるソフトウェア検証です。
`live-experiment.yml` は固定版の **実際の Hermes Agent** をインストールし、
手動で選んだmodeに応じて互換性確認、OpenAI APIへの接続、課題の実行、証拠の集計を行います。
プッシュ時は実際の CLI の互換性確認だけを行い、API キーを渡しません。

## 1. 新しい実行を計画した場合の設定・操作

以下は新しい実行の対象・条件を決めた後に使う操作手順です。既存のpilotやbenchmarkを未実施扱いに戻して繰り返す手順ではありません。API実験を追加する場合は、その目的とプロトコルを別に固定します。

1. APIを使うmodeでキーが未登録の場合は、このリポジトリの **Settings → Secrets and variables → Actions → New repository secret** で
   `OPENAI_API_KEY` を登録します。登録済みのキーは再登録不要です。`check`にはAPIキーは不要です。コード、Issue、チャットにはキーを貼りません。
2. **Actions → Hermes live experiment → Run workflow** を開きます。
3. API推論を含めない互換性確認は、既定の `mode: check` を使います。
4. API接続確認を新たに行う場合は `mode: smoke`、`soft_budget_usd: 1` を明示し、Summary の **API connection: PASS** を確認します。
5. 課題実験を新たに行う場合だけ、計画した `pilot`（1課題）または `benchmark`（8試行）を明示します。初回の実験ではpilotで計測経路を確認してからbenchmarkへ進みました。

`gpt-6-luna` がその API プロジェクトで利用できること、API 請求設定が有効であることが前提です。
ChatGPT の契約だけで API 利用権や API 残高が確認できたとは扱いません。
キー未登録、モデルへのアクセス不可、残高・利用上限、通信障害では後続の有料課題を開始せず、
診断コードを Summary に残します。自動的に別モデルへ切り替えません。

| mode | 実際の処理 | 課題数 | API 推論 |
|---|---|---:|---|
| `check` | 固定 Hermes のインストール、バージョン・CLI 引数・隔離起動後の停止確認 | 0 | なし |
| `smoke` | ツールなしで固定の短い応答を要求し、終了イベント・モデル・使用量を検証 | 0 | あり |
| `pilot` | 接続確認後、`legacy` を新しい作業領域で 1 回実行 | 1 | あり |
| `benchmark` | 接続確認後、既存の 4 不具合プロファイルを各 2 回実行 | 8 | あり |

パイロットは計測系の確認です。課題の正当な `FAIL` も観測値であり、成功するまで繰り返してから
都合のよい試行だけを報告してはいけません。接続失敗や証拠欠損は課題の失敗と区別します。

## 2. 固定する実装条件

| 項目 | 条件 |
|---|---|
| Runner | GitHub-hosted `ubuntu-24.04`、1 ジョブ内で逐次実行 |
| Hermes | `v0.23.3`、commit `caafe5389ae585ef77387a962aee05b1bcf17029` |
| Python | `3.14.10`。この Hermes の実行依存は Python 3.14 が必要 |
| 依存管理 | `uv 0.13.9`、固定 Hermes の `uv.lock` に対して `uv sync --locked --no-dev` |
| API 経路 | `openai-api` → `https://api.openai.com/v1` |
| モデル | `gpt-6-luna`、reasoning `low`。別モデルへの自動フォールバックなし |
| 1 課題の上限 | Hermes 起動 12 回、各会話ターンのツール呼び出し反復 18、再計画 2 回 |
| 時間制限 | Hermes 本体 540 秒/起動、後片付けを含むコントローラ 600 秒/起動 |
| 全体時間 | pilot 2 時間、benchmark 5 時間。上限到達は途中打ち切りとして記録 |
| 順序 | seed `1729`、4 ケース × 2 回。モデルの乱数を固定する seed ではない |
| 隔離 | 毎回新しい課題 workspace、さらに各 Hermes 起動に新しい `HERMES_HOME` |

Hermes と Python の固定値は `ci/hermes.json` に置きます。変更時はこの表とワークフローの
`setup-uv` 指定も合わせて更新し、別プロトコルとして扱います。
環境情報には実際の CPU 名、論理 CPU 数、観測時のクロック範囲、メモリ、OS イメージと版、
Python、Git commit、Hermes commit を保存します。ホストのクロックや負荷は制御していません。
速度の比較に使う場合はホスト条件の差も考慮します。

新しい Hermes の `stream-json` は別プロセスのゲートウェイを使います。
CLI の終了だけでゲートウェイが停止したとは扱いません。
専用アダプターは同じ専用 home に対して `hermes gateway stop --yes` を実行し、
停止を確認できなければ次の有料呼び出しへ進ませません。
ハードキャンセルや runner 自体の喪失時には回収・後片付けを保証できないため、結果は未確定です。

## 3. 費用の扱い

`soft_budget_usd` は接続確認と課題の **観測済みトークン使用量から算出する名目費用** の
停止しきい値です。現在の価格表を照合した請求額でも、プロバイダー側の強制上限でもありません。
計算は既存プロトコルの入力 100 万トークンあたり 0.10 USD、出力 100 万トークンあたり
0.50 USD を使います。実際の請求額は OpenAI Platform 側で確認します。

- 入力値は 0 より大きく 12 以下。初期値は 1 USD。
- 課題ごとの名目しきい値は最大 1.50 USD。残額がそれより少なければ残額を適用します。
- 接続確認の観測費用を差し引いてから課題を開始します。
- 開始済みの API リクエスト、内部リトライや補助呼び出しを、この値で厳密に制限することはできません。
- トークン計測が欠けた場合は追加の有料課題を止め、費用を不明として扱います。
- 8 試行に総額 6 USD を指定しても、各試行に 1.50 USD を必ず割り当てられるわけではありません。
  総額や時間制限で打ち切られた試行を、通常条件の完走と混同しません。

## 4. 結果の取得

Actions の実行ページに **接続・実験・基盤の別々の判定** と試行表を表示します。
同じページの Artifacts から `hermes-<mode>-<run_id>-<attempt>` をダウンロードできます。
保存期間は 14 日です。

初期のpilot・benchmarkで公開されたレポートは、[Hermes実験記録](../experiments/hermes-live/README.md)にも出所と指紋付きで保存しています。この保存物にも元のraw streamや個別採点ファイルは含まれません。

| ファイル | 内容 |
|---|---|
| `ci-result.json` | 実行条件、診断コード、API 接続判定、実験判定、全体の観測名目費用 |
| `summary.json` | ベンチマーク全体、PASS / FAIL / UNCERTAIN / NOT_RUN、中央値と範囲 |
| `attempts.csv` | 1 行 1 試行。使用トークン、ツール数、再計画数、時間、観測名目費用 |
| `report-task-XX.json` | 個別試行の受け入れ証拠を再検証したレポートとファイル指紋 |
| `summary.md` | Actions Summary と同じ読みやすい概要 |

未実行や初期化失敗では、存在しないベンチマークの `summary.json` は作りません。
プラン生成前に失敗して `state.json` がない場合も、取得できる記録を残して `UNCERTAIN` とします。
課題ごとの Hermes 起動回数は API リクエスト回数ではありません。
Hermes 時間は各 CLI 起動と停止確認に要した時間の合計であり、環境のインストール時間は含みません。

公開リポジトリの成果物として扱うため、アップロード対象は項目を限定した集計結果だけです。
生のプロンプト、API 応答本文、stderr、ワークスペース全体、Hermes home、API キーはアップロードしません。
失敗時も診断コードと利用可能な証拠を保存しますが、raw ログは runner 終了後に残りません。
詳しいプロバイダー障害の調査には、新しい試行として手元の隔離環境で再現する必要があります。

GitHub CLI を設定済みなら、計画した操作を画面の代わりに次の形式で指定できます。`smoke`はAPI要求を発行するため、接続確認を追加する場合だけ選びます。

```bash
# API 推論なしの互換性確認（手動実行の既定mode）
gh workflow run live-experiment.yml --repo Unjuno/hiergoal-lab \
  -f mode=check

# 新しい API 接続確認を計画した場合
gh workflow run live-experiment.yml --repo Unjuno/hiergoal-lab \
  -f mode=smoke -f soft_budget_usd=1

# 実行 ID を確認
gh run list --repo Unjuno/hiergoal-lab --workflow live-experiment.yml --limit 5

# 上で表示された実行 ID に置き換える
gh run watch RUN_ID --repo Unjuno/hiergoal-lab --exit-status
gh run download RUN_ID --repo Unjuno/hiergoal-lab --dir ./experiment-results
```

REST API からの開始は GitHub の `workflow_dispatch`、取得は workflow runs / artifacts の
正式な API を使えます。GitHub 操作用のトークンと `OPENAI_API_KEY` は別物です。

## 5. 判定の読み方

| 判定対象 | PASS が意味すること |
|---|---|
| check | 実際の固定 Hermes が起動し、必要な CLI 引数がある。API 接続は未検証 |
| API connection | ツールなしの要求に期待の応答があり、モデル・終了イベント・使用量が検証できた |
| pilot | 当該 1 課題の外部受け入れテストと保存証拠が一致した |
| benchmark | 全 8 試行が分類可能で、既存の工学的目標である証拠付き成功 6 件以上を満たした |

実験が FAIL または UNCERTAIN なら、課題プログラムのプロセス終了コードだけが 0 でも
ワークフローを成功扱いにしません。反対に、check が緑でも API 接続や課題成功は主張しません。
4 種類は同一の小規模プロジェクトの不具合配置です。今回のデータだけで階層化の優位性や
一般のエージェント成功率を結論づけることはできません。

## 一次資料

- [Hermes 固定ソース](https://github.com/NousResearch/hermes-agent/tree/caafe5389ae585ef77387a962aee05b1bcf17029)
- [Hermes CLI / gateway の制約](https://github.com/NousResearch/hermes-agent/blob/caafe5389ae585ef77387a962aee05b1bcf17029/hermes_cli/gateway_chat.py)
- [Hermes の Python と依存関係](https://github.com/NousResearch/hermes-agent/blob/caafe5389ae585ef77387a962aee05b1bcf17029/pyproject.toml)
- [GitHub 手動ワークフロー](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
