# Controlled Recovery Pilot — 実行準備・最終統合検証

2026-11-27 JST。今回は実モデル実行・APIキー更新を行わない。既存の
[凍結プロトコル](controlled_recovery_protocol_ja.md) と
[初回停止記録](recovery_pilot_status_20261127_ja.md) は変更しない。

## 準備完了の基準

| 検査 | 合格条件 |
|---|---|
| 条件の固定 | 初回実行のmanifestと新規prepareのmanifestが完全一致（6課題、12ペア、24修復枠） |
| 実行経路 | 共有準備→障害注入→両腕の分岐→独立採点→監査→集計 |
| 比較条件 | 12組すべてで開始checkpoint・計画・成果物の指紋一致 |
| 結果保全 | 永続保存用のexport・verifyと保存コピーの全trace再監査が成立 |
| 異常停止 | 途中の通信障害で完了済みペア・未知使用量・未実施枠が保存される |
| 準備失敗 | 引き直さず対応する2修復枠を未実施として保存、残りを続行 |
| 非実行経路 | prepare・collect・承認なしrunは通信を開始しない |

追加した [統合テスト](../tests/test_controlled_recovery_readiness.py) は
本番CLI・Responses用変換・監査・公開用保存処理を、メモリ内の模擬HTTP応答で連結して検査する。
ソケット接続を禁止し、ダミー認証文字列を使用する。参照解は模擬応答生成側でのみ使う。
模擬の「live形式」記録は一時ディレクトリに閉じ、実測記録として公開しない。
このテストが通っても実モデル性能・実API疎通・実請求・GitHubへの実モデル結果の保存成功を保証しない。

## 確認コマンド（API推論なし）

```bash
python3 -m unittest discover -s tests -p 'test_controlled_recovery*.py' -v
python3 -m hiergoal.recovery check --output runs/recovery-check-new
python3 -m hiergoal.recovery prepare --output runs/recovery-prepared-new
```

GitHub Actionsの通常push検証でもテストを実行する。
実行準備の確認と実験実施は別扱いとする。初回停止記録を上書きしない。

## 実験起動時

[Controlled recovery pilot](https://github.com/Unjuno/hiergoal-lab/actions/workflows/controlled-recovery.yml)
で Run workflow → branch main → mode run を明示的に選ぶ。
実行には有効な既存の認証設定が必要。今回の準備確認では認証設定に触れない。
通常pushと既定のprepareでは推論を行わない。Re-run jobsは使用しない。

実験の比較要因・予算・課題・モデル・停止条件・採点・凍結ソースは変更していない。
本試験の条件はパイロット観測後、別の事前固定プロトコルで定める。

## 最終確認結果 — 2026-11-27 JST

検査対象commit: [`9d4e4f0db53501b3d3aa310445a17afdab309550`](https://github.com/Unjuno/hiergoal-lab/commit/9d4e4f0db53501b3d3aa310445a17afdab309550)。
専用の[prepare run 46005888978](https://github.com/Unjuno/hiergoal-lab/actions/runs/46005888978) は2026-11-27 22:19:18 JSTに正常終了。

| 項目 | 実測された確認結果 |
|---|---|
| 全回帰テスト | 362/362 PASS（新規統合テスト4/4） |
| オフライン模擬実行 | 準備12/12、対応比較12/12、修復24/24、全36フェーズの監査PASS |
| 模擬HTTP通し検査 | 本番CLI、変換、採点、集計、保存用export/verify、保存コピーの再監査PASS |
| 異常系 | 模擬503、準備失敗、保存後改変、承認なし起動の検査PASS |
| プロトコル | 初回manifestと完全一致する検査PASS、IDは `d36c836de43c41cb0248a95abaa6af810c0eafd896f606207b20ba4b7a3533a1` |
| 本番通信 | 0件。認可結果prepare、実推論・公開ジョブはskipped |
| 保存 | オフライン確認と未実施manifestの[CI artifact](https://github.com/Unjuno/hiergoal-lab/actions/runs/46005888978/artifacts/15200682585)。模擬HTTPのlive形式記録は一時領域から外に保存しない |
| 過去の証拠 | 検査前後で凍結23ファイルおよび79の既存証拠ファイルのGit blob SHA一致 |

検査環境: Ubuntu 24.04、Python 3.12.3、Intel Xeon 6975P-C、4論理CPU、オフライン模擬実行の観測クロック2700–3897.059 MHz、batch 1。回帰テスト全体のCI記録は66.680秒（性能比較ではない）。

判定: **実験装置のオフライン準備 PASS**。認証・提供側動作と実モデルの比較結果は未検証。実験科学上の有効性はUNCERTAIN。今回の検証でモデル・予算・課題・採点・停止条件を変更していない。追加の本番実行は開始しない。
