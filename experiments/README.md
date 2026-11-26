# 実験記録の索引

2026-11-26（日本時間）時点の記録を、現行版・履歴・後継版のある記録に分けて案内する。
**元の manifest、結果、監査判定、公開時のハッシュは変更しない。**
研究上の現在地は [結果と解釈](../docs/results_20261126_ja.md)、機械可読な対応表は
[index.json](index.json) を参照する。索引のパスはリポジトリルート相対。

## 1. 区分と読み方

| 区分 | 意味 | 意味しないこと |
| --- | --- | --- |
| `current` | 現行プロトコル v2.5 で保存された観測 | 手法の有効性が合格、または旧 manifest を現行ソースで再実行可能 |
| `archive` | 当時の実行・解析として保持する履歴 | 現行版と混合してよい独立な再現実験 |
| `superseded` | 後継設計・再実行が存在する過去記録 | 元の失敗や不確実な結果の削除・訂正 |

次の判定を分けて読む。

- **CI 成功**: workflow の対象ステップが正常終了した。
- **audit PASS**: 保存された試行が、その監査規則に整合した。課題に失敗した試行も audit PASS になり得る。
- **task PASS / FAIL**: 試行が元の採点条件と予算の下で課題を達成したか。
- **有限要件 R1–R9 の PASS / FAIL / UNCERTAIN**: 各行に明示された範囲と閾値を満たしたか。
- **study の有効性判定**: 比較群との差を、凍結された別の判定規則で評価した結果。

`COMPLETED` は予定された試行の終端記録がそろった状態であり、全課題の成功を意味しない。
`UNCERTAIN` と `NOT_RUN` を成功へ読み替えない。

## 2. 保存済み method live 実行（6 件）

各リンクは当時公開された `summary.md`。詳細な元の数値は同じディレクトリの
`summary.json` と `trials.csv` にある。P/F/U/N は順に task の PASS/FAIL/UNCERTAIN/NOT_RUN。

| 区分 | Profile / Run | 版 | 予定 | P / F / U / N | audit の内訳 | 位置づけ |
| --- | --- | --- | ---: | --- | --- | --- |
| archive | [pilot / 45656888380](method-study-live/pilot/run-45656888380-attempt-1/summary.md) | v2.4 | 18 | 10 / 8 / 0 / 0 | PASS 18 | 開発課題での小規模実行 |
| archive | [mechanism / 45658610566](method-study-live/mechanism/run-45658610566-attempt-1/summary.md) | v2.4 | 108 | 98 / 10 / 0 / 0 | PASS 108 | 強制サブゴール障害と再計画の記録 |
| superseded | [scale / 45667519808](method-study-live/scale/run-45667519808-attempt-1/summary.md) | v2.4 | 252 | 168 / 0 / 63 / 21 | PASS 169、FAIL 62、NOT_RUN 21 | 監査不整合と HTTP 400 を含む中断記録 |
| current | [scale / 45703053665](method-study-live/scale/run-45703053665-attempt-1/summary.md) | v2.5 | 252 | 215 / 37 / 0 / 0 | PASS 252 | 全件完了。有限の規模耐性基準は FAIL |
| current | [study / 45729335900](method-study-live/study/run-45729335900-attempt-1/summary.md) | v2.5 | 216 | 176 / 40 / 0 / 0 | PASS 216 | 凍結した比較評価の判定は FAIL |
| current | [reliability / 45732751285](method-study-live/reliability/run-45732751285-attempt-1/summary.md) | v2.5 | 720 | 717 / 3 / 0 / 0 | PASS 720 | 小規模12課題の反復。有限 R9 は PASS |

これは記録の一覧であり、行を足して一つの成功率や標本数にしない。Profile ごとに課題、
障害、予算、反復数、プロトコル版が異なる。

### 各 live ディレクトリの内容

| ファイル | 用途 |
| --- | --- |
| `manifest.json` | 凍結された課題・順序・予算・モデル・source hashes・protocol ID |
| `results.json` / `trials.csv` | 成功、失敗、不確実、未実行を含む公開試行記録 |
| `summary.json` / `summary.md` | 集計、比較、要件ごとの判定と限界 |
| `execution.json` | 訪れた試行数、完了・中断、停止理由 |
| `host.json` | 実行時の source commit とホスト条件 |
| `publication.json` | 公開対象の SHA-256、公開ステップ、監査済み全件実行の判定 |

公開アーカイブには raw prompt、response、trace、作業成果物を含めない。
Git 収録物の整合確認と、生 trace を用いた独立再生は異なる。

### 旧 scale の扱い

[v2.5 修正記録](../docs/method_resume_v2_5_ja.md)は、v2.4 の監査62件で生じた
葉の順序の再生不整合と、単発 HTTP 400 後の継続方針を説明している。
旧 run の公開結果は上表のまま保存し、診断的な再解析値で上書きしない。
run 45703053665 は v2.5 で252試行を新たに実行した別データであり、旧 run の成功への再ラベル付けではない。

## 3. v1–v2.4 の設計・オフライン記録

| 保存先 | 区分 | 内容と限界 |
| --- | --- | --- |
| [method-study-v1](method-study-v1/) | superseded | pilot / study の旧 manifest。準備は実行証拠ではない |
| [method-study-v2](method-study-v2/) | superseded | 旧 manifest、228 単体テストと1,314 oracle 軌跡の保存記録 |
| [method-study-v2.1](method-study-v2.1/) | superseded | 旧 manifest、242 単体テストと1,314 oracle 軌跡の保存記録 |
| [v2.2 事後監査](method-study-v2.2/results/HGL-MECH-FOLLOWUP-20261125-01/README_ja.md) | archive | run 45566463441 の live 108件＋oracle 108件をオフライン監査。216件の live 実行ではない |
| [v2.3 wire 回帰解析](method-study-v2.3/results/HGL-WIRE-REGRESSION-20261125-01/summary.json) | archive | 旧論理応答586件の損失のない再シリアライズ。新規推論0。JSON byte削減は実token削減や有効性向上の測定ではない |
| [method-study-v2.4](method-study-v2.4/) | superseded | 275 単体テスト、1,314 oracle 軌跡、9要件のソフトウェア検証 |

Oracle の正解応答によるチェックは実装検証であり、モデルの成功率を測定していない。
旧 manifest は保存時の source hashes と結びついているため、新しい実行には実行対象ソースで
新規 `prepare` が必要。古い結果のディレクトリを出力先として再利用しない。

## 4. 初期 Hermes 実験（保存レポート）

| 実行 | 当時の監査レポートの記録 | 制限 |
| --- | --- | --- |
| [pilot / 45452695213](hermes-live/pilot/run-45452695213-attempt-1/summary.md) | 1 / 1 PASS、再計画0 | 動作事例1件 |
| [benchmark / 45455153574](hermes-live/benchmark/run-45455153574-attempt-1/summary.md) | 8 / 8 PASS、再計画2、再計画後PASS 2 | 同じCSV ledgerの4欠陥profileを各2反復。比較群なし |

実 Hermes と OpenAI/Luna を外付け controller から呼び出した記録であり、
Hermes native `/goal`・`/subgoal`・Kanban への統合を実装した証拠ではない。
保存された curated artifact は raw stream と個別 grading ファイルを含まないため、
当時の監査レポートの再読と、raw trace の独立再生を区別する。
2026-11-26 の取り込みで、元 curated artifact のファイルをバイト一致で保存した。
これは追加実験ではない。[保存物と限界](hermes-live/README.md)、各 `provenance.json`、
[index.json](index.json) に元 Actions、artifact の識別子とハッシュを記録している。

## 5. 研究上の現在地

機能の動作事例と限定した反復回復は記録された。現在の比較結果は、adaptive が flat / fixed より
有利だという主張を支持していない。現行 v2.5 の scale / reliability と旧 v2.4 の mechanism を
混ぜた「9要件統一PASS」はない。既存の失敗を保持し、追加実験の仮説・測度・予算・合否条件を
別途固定してから実行する。詳しくは [結果と解釈](../docs/results_20261126_ja.md) を参照。
