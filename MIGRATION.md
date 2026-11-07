# 2026年11月7日の移行

この文書は、READMEとAGENTS.mdに記録した移行準備時点の公開設定を補足します。

- リポジトリ: https://github.com/hijikiogan-sudo/radiology-technologist-news
- 公開先: https://hijikiogan-sudo.github.io/radiology-technologist-news/
- 公開方式: GitHub Actions。mainのサイト用ファイルをPagesへ配信します。
- 収集: 既存の `.github/workflows/update-news.yml` を利用します。予約時刻は日本時間の1:23、3:53、8:23、13:23です。予約どおりの開始・終了は保証されません。
- 配信: 新規追加した `.github/workflows/deploy-pages.yml` が、通常のmainへのpush、手動実行、または収集ワークフローの成功後に最新のmainを公開します。

自動処理のGITHUB_TOKENで保存した変更は、通常のpushイベントやPagesのブランチ公開を起動しません。そのため、収集の完了イベントを利用する専用の配信処理を追加しました。個人アクセストークンを新たに用意する必要はありません。

Pagesのアップロード対象は画面・データ・アイコン・過去記事だけです。開発用のテストやスクリプトはサイト配信物に含めていません（公開リポジトリ内では閲覧できます）。

旧Git履歴と原本はMac内の別バックアップに保全しています。このリポジトリはニュース専用の新しい履歴です。同居していた別企画とClaudeの会話ログは含めていません。

作業を再開するときは、まずAGENTS.mdを読みます。画面を変更したらsw.jsのVERSIONを上げます。収集データは自動更新されるため、新しい作業の前にGitHub側の最新コミットを確認し、未保存の変更がある場合は上書きしないよう別の作業場所で統合してください。

旧公開先のブラウザに保存された個人設定は、新しいURLへ自動では移りません。対応項目はアプリの設定画面から端末間の受け渡しを利用します。既読状態等の対象外項目があります。

参考: [GitHub Pagesの公開元設定](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)、[独自ワークフローによる公開](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
