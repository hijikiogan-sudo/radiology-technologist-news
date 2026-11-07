"""元のページから要約を作る処理のテスト (python -m pytest tests/test_news_summary.py)。ネットには接続しない。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402

URL = 'https://www.example.or.jp/news/1/'


def test_og_description_is_used(monkeypatch):
    monkeypatch.setattr(u, 'site_description', lambda url: 'サイト全体の説明です。')
    page = '<meta property="og:description" content="第5回MR安全セミナーをオンデマンドで配信します。受講料は無料です。">'
    assert u.page_summary(page, URL) == '第5回MR安全セミナーをオンデマンドで配信します。受講料は無料です。'


def test_site_wide_description_falls_back_to_paragraph(monkeypatch):
    monkeypatch.setattr(u, 'site_description', lambda url: '日本放射線技術学会の公式サイトです。')
    page = ('<meta name="description" content="日本放射線技術学会の公式サイトです。">'
            '<nav><p>トップページへ戻る。ログインはこちら。</p></nav>'
            '<p>短い。</p>'
            '<p>放射線防護の基本を振り返るWebセミナーを開催します。申込は11月20日までです。</p>')
    assert u.page_summary(page, URL) == '放射線防護の基本を振り返るWebセミナーを開催します。申込は11月20日までです。'


def test_nothing_usable_gives_empty(monkeypatch):
    monkeypatch.setattr(u, 'site_description', lambda url: '')
    assert u.page_summary('<p>Copyright © 2026 学会。All rights reserved.</p>', URL) == ''


def test_shorten_cuts_at_sentence_end():
    text = 'あ' * 60 + '。' + 'い' * 200
    assert u.shorten(text) == 'あ' * 60 + '。'


def test_shorten_marks_text_cut_by_the_site():
    assert u.shorten('安全委員会議事録アーカイブは以') == '安全委員会議事録アーカイブは以…'


def test_fill_summaries_tries_new_items_first_and_only_once(monkeypatch):
    calls = []
    monkeypatch.setattr(u, 'fetch_summary', lambda url: calls.append(url) or f'{url}の説明です。')
    monkeypatch.setattr(u, 'SUMMARY_MAX_PER_RUN', 1)
    old = {'headline': '古い記事', 'summary': '', 'url': 'https://a.jp/old', 'source': 'A'}
    new = {'headline': '新しい記事', 'summary': '', 'url': 'https://a.jp/new', 'source': 'A'}
    u.fill_summaries([old, new], {'https://a.jp/new'})
    assert calls == ['https://a.jp/new']
    assert new['summary'] == 'https://a.jp/newの説明です。' and new['summary_tried']
    u.fill_summaries([old, new], set())
    assert calls == ['https://a.jp/new', 'https://a.jp/old']


def test_non_google_url_is_returned_as_is():
    assert u.resolve_google_news(URL) == URL


def test_letter_greetings_are_dropped(monkeypatch):
    monkeypatch.setattr(u, 'site_description', lambda url: '')
    page = ('<meta name="description" content="春暖の候、ますますご清祥のこととお慶び申し上げます。平素は格別のご高配を賜り、厚く御礼申し上げます。'
            ' さて、放射線科研修指導者資格の認定期限が2026年12月31日となっておりますので、更新の手続きをご案内します。">')
    assert u.page_summary(page, URL) == 'さて、放射線科研修指導者資格の認定期限が2026年12月31日となっておりますので、更新の手続きをご案内します。'


def test_page_summary_does_not_change_judgement():
    """元のページから取った要約の語(「株式投資型」など)で、記事が消えたり分類が変わったりしない。"""
    x = {'headline': 'ViewSend ICT、遠隔画像診断のAI開発・業務自動化で資金調達', 'source': '医療テックニュース',
         'url': 'https://news.google.com/x', 'importance': '低',
         'summary': '株式投資型クラウドファンディングを11月4日から実施すると発表した。', 'summary_tried': '2026-11-03'}
    assert u.relevant(x)
    php = {'headline': 'PHP脆弱性に関するお知らせ', 'url': 'https://www.jart.jp/news/1.html', 'source': '日本診療放射線技師会',
           'summary': 'タスク・シフトの告示研修の申込ページも一時停止します。', 'summary_tried': '2026-11-03'}
    assert u.category(php) == '安全管理'


SITE = '一般社団法人香川県診療放射技師会は、主に香川県に在住または勤務する診療放射線技師で構成された一般社団法人です。'


def test_title_plus_site_description_is_not_a_summary(monkeypatch):
    monkeypatch.setattr(u, 'site_description', lambda url: SITE)
    page = ('<meta name="description" content="スキルアップセミナー開催のお知らせ｜' + SITE + '">'
            '<p>今回は「電離放射線健康診断」をテーマに、各施設の運用や個々の疑問を話し合うミーティングにしたいと思います。</p>')
    assert u.page_summary(page, 'https://kagawart.jp/article/data.php?nid=1').startswith('今回は「電離放射線健康診断」')


def test_old_title_plus_site_summaries_are_retried(monkeypatch):
    monkeypatch.setattr(u, 'site_description', lambda url: SITE)
    monkeypatch.setattr(u, 'fetch_summary', lambda url: '取り直した要約です。')
    bad = {'headline': 'スキルアップセミナー開催のお知らせ', 'url': 'https://kagawart.jp/article/data.php?nid=1',
           'summary': 'スキルアップセミナー開催のお知らせ｜' + SITE[:30] + '…', 'summary_tried': '2026-11-01'}   # 140字で切った形
    good = {'headline': '別の記事', 'url': 'https://example.jp/a', 'summary': '別の記事｜本文の要約', 'summary_tried': '2026-11-01'}
    u.fill_summaries([bad, good], set())
    assert bad['summary'] == '取り直した要約です。'
    assert good['summary'] == '別の記事｜本文の要約'
