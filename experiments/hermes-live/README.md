# 初期Hermes実験の保存レポート

2026-11-26に、既存のGitHub Actions artifactから公開用に整理済みのレポートを取り込んだ。
各ファイルは元ZIP内のバイト列を保持し、`provenance.json`に実行ID・ソースcommit・artifact ID・SHA-256を記録している。
この取り込みは追加実験ではない。

| 実行 | 保存先 | 当時のレポートに記録された結果 |
|---|---|---|
| [Pilot 45452695213](https://github.com/Unjuno/hiergoal-lab/actions/runs/45452695213) | [pilot/run-45452695213-attempt-1](pilot/run-45452695213-attempt-1/) | 1/1 PASS、再計画0回 |
| [Benchmark 45455153574](https://github.com/Unjuno/hiergoal-lab/actions/runs/45455153574) | [benchmark/run-45455153574-attempt-1](benchmark/run-45455153574-attempt-1/) | 8/8 PASS、再計画2回、その後の検証済み成功2回 |

同じCSV台帳課題の4欠陥条件を2回ずつ実行した外付けcontrollerの実験で、比較対象はない。
Hermes native機能の統合検証や、階層方式の優越性の証拠としては扱わない。

## 保存されているものと限界

- `summary.json` / `summary.md`：当時の集計。
- `attempts.csv`：試行ごとの記録。
- `ci-result.json`：ソース・モデル・ホスト・実行条件と判定。
- `report-task-*.json`：当時の監査レポートと証拠ファイルの指紋。
- `provenance.json`：今回の取り込み元と各保存ファイルの指紋。

元のJSONLストリームと個別採点ファイルはartifactに含まれない。
保存レポートの内容は確認できるが、このディレクトリだけでは当時のraw証拠を独立に再生できない。
過去の監査結果を、今回新たに実行・再監査した結果へ置き換えない。

[全実験の索引](../README.md) · [現在の結果と限界](../../docs/results_20261126_ja.md)
