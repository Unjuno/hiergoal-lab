# 保存済み実験の結果と解釈 — 2026-11-26

## 1. 結論と対象

**階層の管理、限定した局所再計画、独立採点を伴う回復の動作事例は得られた。
一方、現在の実装が flat retry より高い成功率や低い費用をもたらすという有効性は支持されていない。**
これは、現在の実装と選んだ課題に対する結論であり、階層的計画一般の無効性を証明するものではない。

本書は2026-11-26（日本時間）までの保存済み結果の整理である。新しい推論・実験、
元結果の再採点、閾値の変更は行っていない。全保存先と source commit / protocol ID は
[実験索引](../experiments/README.md) と [機械可読索引](../experiments/index.json) を参照する。
表の数値はそれぞれの元記録から取り、異なる profile や版の成績を合算しない。

## 2. 初期 Hermes 実験で確認されたこと

| 保存記録 | 当時の結果 | 言える範囲 |
| --- | --- | --- |
| [pilot 45452695213](../experiments/hermes-live/pilot/run-45452695213-attempt-1/summary.md) | 1 / 1 PASS、再計画0 | 実 Hermes を外付け controller で動かした1事例 |
| [benchmark 45455153574](../experiments/hermes-live/benchmark/run-45455153574-attempt-1/summary.md) | 8 / 8 PASS、再計画2、その後の検証済みPASS 2 | 同じCSV ledgerの4初期欠陥条件を各2反復した動作例 |

当時の source は `14ca1496e82ac34fc3fcbe8047f178002efd7fb7`、Hermes は
`caafe5389ae585ef77387a962aee05b1bcf17029`、OpenAI/Luna の `gpt-6-luna`。
実行条件は各 `ci-result.json` に残る。比較群がないため、階層化や再計画による改善量は推定できない。
8実行は8種類の独立な実務課題でもない。

今回保存した [curated レポート](../experiments/hermes-live/README.md)には元の raw stream と
個別 grading ファイルが含まれない。**当時の監査レポートに成功が記録されたこと**と、
**今回その raw 証拠を独立再生したこと**を区別する。後者は実施できていない。
Hermes native `/goal`・`/subgoal`・Kanban への統合も、この実験の達成事項には含めない。
手法自体の比較評価に、native 統合は必須ではない。

## 3. Method study の主な結果

3方式はいずれも同じ model を使う。`flat_retry` は階層なし、`hierarchy_fixed` は固定階層、
`hierarchy_adaptive` は失敗した葉の命令を限定的に改訂する。
対象はコード式の修復、データ変換、資源制約付きスケジューリングの合成課題。
原設定は各 [manifest](../experiments/index.json) に残す。

### 3.1 現行 v2.5 の全割当試行

| Profile | 予定試行 | task PASS / FAIL | audit PASS | 保存された分析判定 |
| --- | ---: | --- | ---: | --- |
| [study](../experiments/method-study-live/study/run-45729335900-attempt-1/summary.md) | 216 | 176 / 40 | 216 / 216 | 凍結した比較評価の `decision=FAIL` |
| [scale](../experiments/method-study-live/scale/run-45703053665-attempt-1/summary.md) | 252 | 215 / 37 | 252 / 252 | 記述用profileの全体判定は `UNCERTAIN`、有限の規模耐性 R8 は `FAIL` |
| [reliability](../experiments/method-study-live/reliability/run-45732751285-attempt-1/summary.md) | 720 | 717 / 3 | 720 / 720 | 記述用profileの全体判定は `UNCERTAIN`、有限の反復基準 R9 は `PASS` |

3実行とも `execution.json` は `COMPLETED`、API error trial は0、`UNCERTAIN` / `NOT_RUN` は0。
監査合格・全件完了と、課題失敗は両立する。

### 3.2 fault 条件に割り当てられた試行の最終 PASS

| Profile | flat_retry | hierarchy_fixed | hierarchy_adaptive |
| --- | ---: | ---: | ---: |
| study | 36 / 36 | 26 / 36 | 26 / 36 |
| scale | 42 / 42 | 32 / 42 | 32 / 42 |
| reliability | 120 / 120 | 118 / 120 | 119 / 120 |

これは障害条件への**割当**を分母とした最終受理数であり、すべてが実際の障害回復を測った試行ではない。
元数値は上記各 `summary.md` の arm/condition 表と、同じ保存先の `trials.csv` で確認できる。

### 3.3 失敗した段階

- **study:** 40件の失敗はすべて階層方式で、初期計画段階の1論理呼び出し・patch 0・replan 0。
  実行作業や障害注入に到達していない。公開診断は `OTHER_RECORDED_DIAGNOSTIC` に一般化されている。
  詳細な形式違反の内訳は raw artifact の別解析に依存し、公開CSVだけからは再構成できない。
- **scale:** 37件の失敗は35件が `TOKEN_BUDGET_AFTER`、2件が `CALL_BUDGET`。
  最重条件（73目標、48葉、5レベル、120依存辺）の adaptive fault は0 / 6だが、6件すべて障害注入前の
  トークン予算失敗である。「注入された障害を6件修復できなかった」とは解釈しない。
- **reliability:** 3件の失敗は2件がトークン予算、1件が呼び出し予算。いずれも障害注入前。
  adaptive は割当120件中119件で最終受理されたが、障害対象への受理済み再計画を伴う厳密な回復条件は113 / 120。

根拠: [study 試行表](../experiments/method-study-live/study/run-45729335900-attempt-1/trials.csv)、
[scale 試行表](../experiments/method-study-live/scale/run-45703053665-attempt-1/trials.csv)、
[reliability の R1 証拠](../experiments/method-study-live/reliability/run-45732751285-attempt-1/summary.json)。

### 3.4 割当と障害実現の区別

| Profile | flat の障害実現数 | fixed の障害実現数 | adaptive の障害実現数 |
| --- | ---: | ---: | ---: |
| study | 20 / 36 | 16 / 36 | 15 / 36 |
| scale | 42 / 42 | 33 / 42 | 34 / 42 |
| reliability | 120 / 120 | 118 / 120 | 119 / 120 |

Study は環境変更が必ずしも判定失敗を起こさず、階層方式では計画段階の失敗もある。
Scale / reliability は初期解決の成功後に強制障害を注入するため、初期解決に失敗すると障害が実現しない。
障害実現済みだけに条件づけた回復率は補助的な記述であり、方式全体の比較では割当試行を残す。
根拠は各 `summary.json` の `requirement_evidence` → R1 → `fault_accounting`。

## 4. 費用と測定条件

以下は fault 割当全試行における、**1試行当たりの論理呼び出し数／入力＋出力token の中央値**。
初期計画は各階層方式へ論理計上する。共有cache適用後の実API使用量や請求額とは異なる。
成功した試行だけを選んだ数値ではなく、失敗も含む。

| Profile | flat_retry | hierarchy_fixed | hierarchy_adaptive |
| --- | ---: | ---: | ---: |
| study | 2 / 2,932.5 | 3.5 / 6,509.5 | 5 / 8,187 |
| scale | 2 / 12,222 | 14 / 87,192 | 15 / 93,724.5 |
| reliability | 2 / 9,983.5 | 10 / 43,687.5 | 11 / 47,867 |

出典は各 `summary.json` の `by_arm_condition` → `costs`。
現在の観測では階層方式の管理・実行費用が大きい。ただし、入力の再送、段階的処理、追加の検証作業、
計画生成のそれぞれが費用へ及ぼした因果効果は、これらの比較だけでは分離できない。

共通条件は OpenAI backend / `gpt-6-luna` / reasoning `low` / batch 1 / Python 3.12.3。
ホストは4論理CPU。モデル側のHWとクロックは観測不能。

| Profile | ホストCPU / 観測MHz範囲 | 1試行の上限 calls / replans / total tokens | 課題・反復 |
| --- | --- | --- | --- |
| study | Intel Xeon 6975P-C / 2700–3882.82 | 12 / 3 / 64,000 | 12 task ID、各条件3反復 |
| scale | AMD EPYC 9V45 / 2596.098–4234.098 | 64 / 8 / 512,000 | 3課題族の7規模設定、各条件2反復 |
| reliability | Intel Xeon 6975P-C / 2700–3901.452 | 24 / 4 / 128,000 | 12 task ID、各条件10反復、小規模のみ |

根拠: [study host](../experiments/method-study-live/study/run-45729335900-attempt-1/host.json)、
[scale host](../experiments/method-study-live/scale/run-45703053665-attempt-1/host.json)、
[reliability host](../experiments/method-study-live/reliability/run-45732751285-attempt-1/host.json) と各 `manifest.json`。
反復は独立な新課題を増やさない。Scale の規模違いは同じ source instance を共有し、深さの変更は
実行する certification leaf も増やす。Profile 間の数値を、同一条件の改善前後として扱わない。

## 5. 9要件の現在地

保存された v2.5 の要件判定を、そのまま並べる。PASS は各reportの有限な範囲に限られ、
行やprofileを選んで統一PASSを構成しない。

| 要件 | study | scale | reliability |
| --- | --- | --- | --- |
| R1 強制サブゴール失敗・改訂・回復 | UNCERTAIN | UNCERTAIN | UNCERTAIN |
| R2 階層・状態遷移・改訂差分 | UNCERTAIN | PASS | PASS |
| R3 root契約の不変性 | PASS | PASS | PASS |
| R4 課題族と有限回復基準 | UNCERTAIN | FAIL | PASS |
| R5 無関係な目標・成果物の保持 | UNCERTAIN | UNCERTAIN | PASS |
| R6 失敗証拠に基づく有界再計画 | PASS | PASS | PASS |
| R7 独立最終採点と記録整合 | PASS | PASS | PASS |
| R8 規模耐性 | UNCERTAIN | FAIL | UNCERTAIN |
| R9 有限の反復基準 | UNCERTAIN | UNCERTAIN | PASS |

Reliability のPASSは7項目。R1のUNCERTAINは障害未実現試行が残ること等に基づく保存判定であり、
回復事例が一切なかったという意味ではない。
現存する mechanism run は v2.4、scale / reliability は v2.5なので、source signatureをそろえた
現行版の suite 合格を主張できない。R8の観測上のFAILも、機能テストPASSでは相殺できない。

また、rootの同一性は保存された契約・状態・要求snapshotに対する検査であり、任意の自然言語目標の
意味が変質しないという一般的保証ではない。再計画の「必要性」は定義した失敗・進捗条件への一致であり、
再計画が結果を改善したという因果証明ではない。最終採点の独立性も、実装済み採点器の誤りがないことまでは保証しない。

## 6. 履歴を混同しないための整理

- v1–v2.4 の旧 manifest と oracle 検証は [履歴索引](../experiments/README.md) に残す。
  Oracle 成功を live 成功率として数えない。
- v2.2 の216監査行は live108＋oracle108。v2.3 の586応答は共有計画を含む論理応答の再シリアライズであり、新規推論はない。
- [旧 scale 45667519808](../experiments/method-study-live/scale/run-45667519808-attempt-1/summary.md)は
  168 PASS、63 UNCERTAIN、21 NOT_RUN、監査FAIL62の公開記録を保持する。
  [v2.5 の原因修正](method_resume_v2_5_ja.md)や診断的再解析で元の結果を上書きしない。
- 新 v2.5 scale は全252件の別実行。旧runのHTTP 400を、API呼び出し過多や無料workflow制限のせいと断定する根拠はない。
  新runではAPIエラー0、課題FAIL37はローカルの予算上限に由来する。
- Git収録のmethod結果は公開用の構造化情報。raw trace を伴う独立再監査をこの整理で実施したとは記さない。

## 7. 事実・解釈・未検証仮説

| 種類 | 内容 | 次に切り分ける対象 |
| --- | --- | --- |
| 観測事実 | 現行studyでは階層方式に初期計画段階の失敗が集中した | 計画形式の成立と、成立後の問題解決能力 |
| 観測事実 | scaleでは予算失敗が支配的で、最重条件は初期解決を完了できなかった | 初期計画・実行・検証・障害回復それぞれの費用 |
| 観測事実 | 小規模reliabilityでは限定した回復と反復基準を満たす記録がある | 他方式より有利になる課題条件と再計画の追加効果 |
| 解釈 | 現行の階層化による便益が、追加管理費用を上回ったとは示せていない | 同じ予算・情報条件での対比較 |
| 未検証仮説 | 全体情報の繰り返し提示と細かな段階実行が負担を増やす | 情報範囲と階層制御の効果を分けた比較 |
| 未検証仮説 | 現行課題には一度の大きな修正で解けるものが多く、分割の利点が小さい | 事前選定した未見の複数段階課題での再評価 |
| 未検証仮説 | 葉の命令改訂だけでは構造的な計画誤りを直せない | 構造変更を別介入として定義した検証 |

これらは次の実験設計に使う仮説であり、この整理によって検証済みになったものではない。
計画理論では依存関係と部分再計画、情報工学では入力の局所化と通信量、実験計画法では
割当と障害実現の分母・反復の依存性を、それぞれ切り分ける必要がある。
追加実験では、有効性の主張・主要測度・予算・停止規則・合否条件を事前に固定する。

## ERROR CHECK

元のtask結果とaudit結果を分け、障害割当と実現、最終成果物受理と対象再計画後回復、
oracleとlive、旧版と現行版を区別した。保存結果の再ラベル付けは行っていない。
「動作した」「有限基準を満たした」「比較群より有利だった」を同じ結論として扱わない。
