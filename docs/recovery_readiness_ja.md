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
