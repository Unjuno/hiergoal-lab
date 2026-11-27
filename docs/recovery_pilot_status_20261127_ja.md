# Controlled Recovery Pilot：構築完了・認証停止の記録

2026-11-27（日本時間）。この文書は実行後の状況整理であり、凍結プロトコルを変更しない。

## 結論

**比較基盤を構築し、実API実行を開始したが、最初の要求が`HTTP 401 / expired_secret_key`で拒否された。24件の修復試行は未実施で、有効性は未判定である。**

使用中のGitHub Actions secret `OPENAI_API_KEY`は存在したが、OpenAIが期限切れを報告した。
今回の直接の停止理由は、この認証エラーである。呼出し過多やGitHubの実行時間枠を原因とする証拠は今回の記録にはない。
通信エラー時の事前規則に従って追加送信せず停止し、欠測を失敗や成功に置き換えなかった。

## 構築したもの

- 同じ故障後状態から固定指示Aと一度の再計画Bを比較するrunner。
- 準備成功成果物への決定的な故障注入、checkpoint保存、別オブジェクトとしての復元。
- 元の正解・準備履歴・hidden採点を修復モデルへ渡さない入力構成。
- 応答、パッチ、指示変更、目標状態、独立採点、予算の再生監査。
- 一時的な無関係フィールド変更を含む局所性の計測。
- 中断時の送信数と未知使用量を保持する会計。
- 明示的な起動と、全trace・checksumを含む永続保存。

新しい6課題・12ペア・24割当、各準備／修復8呼出し・64,000 tokens、Bの再計画一回、モデル`gpt-6-luna`、reasoning `low`、batch 1を固定した。
詳細は[事前プロトコル](controlled_recovery_protocol_ja.md)を参照する。

## 検証と今回の観測

| 段階 | 観測 | 解釈 |
|---|---|---|
| 最終コードの全回帰テスト | GitHub Actionsで358/358 PASS | 既存304件と新規54件のソフトウェア検証 |
| オフライン模擬実行 | 準備12、修復24、全36フェーズの再生監査PASS | 装置の動作検証。実モデル性能ではない |
| 一度限りの起動検証 | PASS | 実装・protocol・予算・所有者・起動コミットを照合 |
| API設定の存在確認 | PASS | キーが空でないことだけを確認。キーの有効性を保証しない |
| 最初の実API送信 | 1回、`HTTP 401`、`expired_secret_key` | 初期計画生成で認証拒否 |
| 適格な準備成果物 | 0/12 | 準備1枠UNCERTAIN、11枠未実施 |
| 修復試行 | 0/24 | 24枠すべて`NOT_RUN_BATCH_STOP` |
| 使用量 | 入力・出力合計ともnull、既知部分0 | 使用量未取得。無料・課金0とは主張しない |
| 中断trace監査 | 1/1 PASS | 送信、認証エラー、停止、未知使用量が整合 |
| 実験全体 | 装置UNCERTAIN、監査INCOMPLETE、有効性UNCERTAIN | 実モデルによる比較は未完了 |

実行ホスト：Ubuntu系Linux、Python 3.12.3、Intel Xeon 6975P-C、4論理CPU、観測クロック3613.784–3897.867 MHz、batch 1。
推論側ハードウェアは観測不可。今回は認証で停止したため、モデル性能の速度測定はない。

## 実行識別子と一次記録

- 実装commit：[`ceacd88007e27e1aefa09ae64c3db3cb77757852`](https://github.com/Unjuno/hiergoal-lab/commit/ceacd88007e27e1aefa09ae64c3db3cb77757852)
- 実行commit：[`510409cf9bb580a1e8cf180cbb92405f6ac61214`](https://github.com/Unjuno/hiergoal-lab/commit/510409cf9bb580a1e8cf180cbb92405f6ac61214)
- protocol ID：`d36c836de43c41cb0248a95abaa6af810c0eafd896f606207b20ba4b7a3533a1`
- 実行run：[45917876892 / attempt 1](https://github.com/Unjuno/hiergoal-lab/actions/runs/45917876892)
- 実行commitのオフラインCI：[45917876875 / success](https://github.com/Unjuno/hiergoal-lab/actions/runs/45917876875)
- [全保存ファイル](../experiments/controlled-recovery/run-45917876892-attempt-1/)
- [認証エラーを記録したtrace](../experiments/controlled-recovery/run-45917876892-attempt-1/preparations/scale-data_transform-heldout-000-small-d3-sparse-9fd3bc86-r2/trace.jsonl)
- [集計](../experiments/controlled-recovery/run-45917876892-attempt-1/summary.json)、[監査](../experiments/controlled-recovery/run-45917876892-attempt-1/audits.json)、[公開時のchecksum](../experiments/controlled-recovery/run-45917876892-attempt-1/publication.json)

保存した12証拠ファイルのサイズ・SHA-256を再確認し、中断traceをローカルでも再生監査した。publication receiptを含めて13ファイルを保存している。
既存v2.5の15指紋対象ファイルと、開始時点の既存101実験ファイルはバイト単位で保持した。

## 再開に必要な操作

1. 有効なAPIキーで、リポジトリの[Actions secret `OPENAI_API_KEY`](https://github.com/Unjuno/hiergoal-lab/settings/secrets/actions)を更新する。キー本体をissue・commit・チャット・実験記録に載せない。
2. [Controlled recovery pilot workflow](https://github.com/Unjuno/hiergoal-lab/actions/workflows/controlled-recovery.yml)の**Run workflow**から、branch `main`、mode `run`で新規実行する。

既存runの**Re-run jobs**は使用しない。初回attemptのみ許可する仕組みなので拒否される。
新規runは同じ凍結条件で全割当を開始し、この認証停止記録を上書きしない。これは観測された修復失敗の引き直しではない。今回は準備モデルの応答も修復成績も取得していない。
キー更新は認証情報の操作で、接続されているGitHubツールにはsecretsの書換機能がない。実装変更や実験条件の緩和で解決する問題ではない。

## 科学的な現在地

AI計画の局所修正、障害回復の同一状態復元、因果実験の対応比較を検証できる装置は整った。
ただし実モデルによる回復改善、費用効率、一般化について、今回の実行から肯定・否定の結論は出せない。
次に必要なのは同じ条件での有効なモデル応答であり、課題や成功基準を変更する根拠は得られていない。
