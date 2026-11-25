# 実API実験の開始条件と永続保存

## 現行改訂 v2.4（2026-11-26 JST）

[9要件の再監査](method_reaudit_v2_4_ja.md)で、状態記録の欠落、送信スキーマの順序、公開レシートの不整合を修正した。reliabilityは12複合課題への強制サブゴール故障を各10反復し、mechanismと同じ予算を使う。R4は課題族別の修復成績を新しい有限基準で判定する。旧結果を混合しない。実API側の成功はオフライン検査とは別に確認する。

## v2.3の開始前確認（2026-11-25）

- [全オフラインCI](https://github.com/Unjuno/hiergoal-lab/actions/runs/45628804840): success。全5プロファイルの模擬検証を含む。
- [実験準備](https://github.com/Unjuno/hiergoal-lab/actions/runs/45628804738): success。API実行は含まない。
- v2.3の厳格な出力スキーマを実モデルが受理するか、実トークン消費と成功率が改善するかは未確認。オフライン成功はその根拠にならない。

## 実験開始

1. リポジトリ Actions → [Method validation study](https://github.com/Unjuno/hiergoal-lab/actions/workflows/method-study.yml) → Run workflow。
2. Branch: main / mode: run / profile: pilot。
3. Actions secret `OPENAI_API_KEY` が必要。値はチャット、ログ、Gitに記載しない。実APIに接続するため課金が発生し得る。上限は論理トークン・呼出・時間の契約であり厳密な請求上限ではない。
4. 完全な18試行の監査結果を確認する。次に mechanism 108試行を別runとして実行。pilotは自由階層のスキーマ、mechanismは指定階層のスキーマを実際に通す。両方の互換性が確認されてから study 216、scale 252、reliability 720へ進む。
5. 旧版との成績混合や失敗試行の除外はしない。新しいソースハッシュを持つmanifestで記録する。

## 永続保存

手動で明示的に開始したmain上のlive実験について、終了後（失敗・未完了を含む）に回帰・再生監査の結果を公開用に投影する。別jobが同じrun/attemptに対応する公開ファイルのみ検証し、mainに非強制pushする。

保存先: `experiments/method-study-live/<profile>/run-<run_id>-attempt-<attempt>/`

- publication.json: run/attempt/実行コミット・結果件数・監査完了判定・ファイルSHA-256。
- manifest.json / host.json / execution.json（存在する場合）: 実験条件、実行環境、終了状況。
- results.json / trials.csv: 全割当の状態と集計指標。NOT_RUN / UNCERTAINも保持。
- summary.json / summary.md: 既存の分析器で再生成し、元集計と完全一致することを確認した分析。

生のモデル応答、プロンプト、トレース、成果物、任意の診断文字列や認証情報はGitに格納しない。診断は固定コードに置換する。詳細トレースは従来のActions成果物に残る（保存期限30日）。Gitに保存される集計だけから生トレースを再生できるとは主張しない。

準備・回収が成立しない場合はNO_COLLECTED_RESULTSの公開レシートのみを保存する。分析内容が投影前後で異なる場合は公開を失敗させる。強制キャンセル、ランナー消失、write権限制約、ブランチ保護、競合の継続などで自動保存が失敗し得る。公開jobの成功とmain上のファイルを確認すること。保存先が既に存在する場合は完全一致の場合にのみ成功扱いとする。prepareとpushは引き続きAPIを呼ばず、公開jobも実行しない。

## 変更範囲

前回のv2.3自動保存追加ではモデル、比較条件、試行数、資源上限、採点、効果判定を変更しなかった。今回のv2.4では上記の反復試験と有限判定を明示的に改訂する。新しいソースハッシュを持つmanifestを生成し、旧実行を新基準で再ラベル付けしない。公開verifyはhashだけでなく、結果行から再計算した完了状態とsummary/CSVの一致も検査する。liveの開始と自動保存の実環境での成功は別途確認する必要がある。

mechanism・scale・reliabilityの完全なrunディレクトリを取得後、次の一括監査で9要件を照合できる。実API呼出しは発生しない。

```bash
python -m hiergoal.study_suite --mechanism runs/method-mechanism --scale runs/method-scale --reliability runs/method-reliability --output runs/method-requirements
```

工程検査と実証判定はrequirements.jsonのengineering_decisionとempirical_decisionに分ける。完全な再生には生トレース・共有計画が必要であり、公開集計だけでは不足する。
