# v2.5: scale実験の再開

## 目的と変更

run 45667519808 の62件の監査例外は、実行時の葉の辞書順を
canonical JSONの文字列順で再生したために起きた。共有計画と元モデル応答の
既存の一致検査をすべて維持したうえで、凍結課題と元応答から計画を再構築する。
部分的な修正、S10以降の葉、共有計画の再利用を回帰検査する。

単発のHTTP 400で残りの全試行を打ち切る処理も変更する。
この実行方針はmanifestのexecution_policyとprotocol_idへ含める。
v2.4の記録は書き換えず、新しい実行として保存する。

## 凍結する継続方針

- 各試行の終了直後に所有側監査を実行する。監査不合格は全体停止する。
- statusがUNCERTAIN、diagnosticが正確にOPENAI_HTTP_400、
  protocol_okとinvariant_okがtrue、監査PASSである試行だけを継続対象とする。
- 当該試行はUNCERTAINのまま残す。失敗要求は再送しない。
- 最初の2件は次の予定試行へ進む。run全体で3件目に達すると
  HTTP_400_TRIAL_ERROR_LIMITで停止する。成功を挟んでもカウントを戻さない。
- この上限はHTTP 400の影響を受けた**試行数**を数える。
  失敗した共有初期計画の再利用も1試行と数え、実際のAPI要求回数と混同しない。
- 401/403/429、他のHTTPエラー、通信結果不明、装置エラー、root異常は
  従来どおり全体停止する。429の待機・自動再試行はこの変更に含めない。
- execution.jsonにはapi_error_trial_idsとcontinued_api_error_trial_idsを保存する。
  公開アーカイブでも予定順・監査結果・診断との整合性を検証する。
- completedは終端結果を保存した試行数。UNCERTAINも含む。
  全予定試行を訪れたCOMPLETEDと、科学的に完全な実験は区別する。
  UNCERTAINが一つでも残ればcomplete_audited_executionはfalseのままである。
- 最後の予定試行にHTTP 400が出た場合、そのIDはエラー一覧には入り、
  後続がないので継続一覧には入れない。3件目なら上限の停止理由も保存する。

## 診断と変更しない評価条件

HTTPエラーでは、status、安全な識別子に制限したerror type/code/param、
request ID、要求開始・終了時刻、送信入力のハッシュ等を保持する。
自由文のエラー本文と認証情報は記録しない。結果不明の使用量はnullを維持し、
確定済み部分と分ける。

課題、3手法、モデル、採点器、根目標、故障注入、論理費用の定義、
試行ごとのcalls/replans/token/time上限は変更しない。
旧scaleの28件の予算FAILを成功へ変更せず、失敗試行だけを選んで再実行しない。
再開は新しいv2.5のscale全252試行として行う。

## 再開手順

GitHub ActionsのMethod validation studyでmain、mode=run、profile=scaleを指定する。
既存workflow_dispatchの明示的実行経路を使う。通常のpushはオフライン準備のみで、
有料API実験を起動しない。

完了後は科学的なFAILも含めて集計する。モデルの失敗は実験結果であり、
監査を緩めたり上限を後付けで増やしたりして合格へ寄せない。
