# 放射線技師ニュース 引き継ぎメモ

Codex・Claude のどちらで作業しても、まずこのファイルを読んでから始める。回答は日本語で。

## 何のサイトか
- 診療放射線技師向けのニュースを毎朝自動で集めて載せる GitHub Pages のサイト。
  公開先: https://hijikiogan-sudo.github.io/radiology-technologist-news/
- リポジトリ: `hijikiogan-sudo/radiology-technologist-news`(main に直接コミット)。
  `beer-save/`・`ion-chemistry/` は別の企画なので、このサイトの作業では触らない。

## 作業のきまり
- コミット・push は、ユーザーに確かめてから行う。
- ChatGPT のプロジェクト同期の資料は変更しない。
- ファイルを消すときは完全削除ではなくゴミ箱へ移す。
- 「全記事に同じ定型文を付けない」。重要度「低」の記事にはポイント(`why`)を付けない。
  研修の案内や新製品の話題のように、記事の種類を言い直すだけの一言も付けない(`TECHNOLOGIST_NOTES`)。
- 元ページから取った要約は表示専用。分類・重要度・ポイント・日程の判定には使わない(`basis()`)。

## 仕組み
- `scripts/update_news.py` が収集と整理のすべて。書き出すもの:
  `news.json`(最新200件。古い分は `archive/YYYY-MM.json`)、`news_meta.json`(情報源ごとの取得状況)、
  `seminars.json`(研修日程)、`kagawa.json`(香川県技師会の別枠)、`supply.json`、`papers.json`、`daily_html/`。
- 保存期間は1年(`RETENTION_DAYS`)。日付が1年より前の記事(`news.json`・`archive/`)と `daily_html/` は、
  更新のたびに `prune_old_data()` などが消す。GitHub Actions 上の自動処理なのでゴミ箱は通らず、git の履歴には残る。
- `clean_db()` が毎日、全記事を判定し直す(関係あり・ニュースか・分類・重要度・ポイント・日程)。
  手書きのポイント(`apply_curated_specialist`)が優先される。
- `.github/workflows/update-news.yml`: 毎日 1:23・3:53・8:23・13:23(日本時間)に予約。実際は4〜5時間遅れて動くことが多い。
  `scripts/update_news.py` を push したときも実行される。
  Gmail の通知は Secrets(`GMAIL_USER`・`GMAIL_APP_PASSWORD`・`NOTIFY_TO`)を登録したときだけ動く(2026-11 時点で未登録)。
- `index.html` は1ファイルの画面。変えたら `sw.js` の `VERSION` を1つ上げる(上げないと古い画面が残る)。
- 画面の設定(担当分野・情報を集める先・欄の並び・あとで読むなど)は、見る人の端末のブラウザ(localStorage)に保存し、
  サーバーには送らない。職場のスタッフがそれぞれ自分の設定で使う前提。端末間の受け渡しは `SYNC_KEYS` の項目だけ。

## 変更したときの確かめ方
1. テスト: `python -m pytest -q tests`(pytest が必要)。GitHub 上ではテストは走らない。
2. 実データでの試し: リポジトリを作業用の場所に複製し、Gmail の環境変数を外して
   `python scripts/update_news.py` を実行。`news.json` を今のものと比べ、
   既存の記事の分類・重要度が意図せず変わっていないかを見る。
3. 画面の確認は、複製先で簡易サーバーを立ててブラウザで見る。

## 情報源を足すとき
- 学会・技師会の新着は `direct_official_news()` の一覧に足す。読み方は RSS(`parse_rss`)、
  日付つきのお知らせ一覧(`parse_dated_links`)、日付→本文の並び(`parse_dated_blocks`)、
  または専用の関数(例: 高知県技師会の `parse_kochi`)。
- あわせて `OFFICIAL`・`SOCIETY_DOMAINS`・`OFFICIAL_SOURCE_NAMES` にドメインと名前を、
  更新がまばらな会は `LOCAL_DAYS` に取り込む日数を足す。
- 研修の予定表は `update_seminars()` に足す(香川・愛媛・JART・MR認定機構・精中機構)。
- 画面側の `index.html` の `SRC_GROUPS`(設定の「情報を集める先」)にも、配信元の名前(記事の `source`)を足す。
  足し忘れると「一般メディア」扱いになり、学会ごとに表示・非表示を選べない。
  初期状態をチェックなしにする配信元は `SRC_DEFAULT_OFF` にも足す(JABTS・JSS・日本乳癌学会・DCIS研究会・X線CT認定機構・MRIfan.net)。

## 現在の情報源(地域)
- 香川県技師会(お知らせ・予定表・求人案内)、JSRT 中国・四国支部
  香川県技師会の分は画面で別枠(「香川県技師会」)にまとめ、ほかの一覧・日程・今日の3本には出さない。
  お知らせの全件と求人は `update_kagawa()` が `kagawa.json` に書く(ニュースの判定で外れるものも含む)。
- 岡山県(RSS)、愛媛県(お知らせ・行事予定)、徳島県(お知らせ)、高知県(お知らせ欄 news.htm、Shift_JIS)

## 残っていること
- Gmail 通知の設定(ユーザー本人がアプリパスワードを登録する)。
- `~/Documents/AI作業場/Codex作業場/放射線技師ニュース`(古い作業記録)は iCloud の都合で
  ゴミ箱へ移せず、ユーザーが手で移す予定。
