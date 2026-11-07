"""日本消化器がん検診学会・精中機構の取得テスト (python -m pytest tests/test_news_screening_sources.py)。
フィクスチャは実際のページ/RSSの構造(2026年10月時点)を写したもの。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402

JSGCS_HTML = '''
<article><span class="date">2026.10.13</span><span class="title">
 <a href="https://www.jsgcs.or.jp/importants/archives/51">対策型大腸がん検診における免疫便潜血検査陽性者に対する精密検査の基本的考え方</a> <span class="new">NEW</span></span></article>
<article><span class="date">2026.10.20</span><span class="topicIcon publication">刊行物</span><span class="title">
 <a href="https://www.jsgcs.or.jp/news/archives/1146">学会誌64巻Suppl（第64回大会抄録号）が公開されました。</a></span></article>
<article class="last"><span class="title">日付のない記事</span></article>
'''

QABCS_RSS = '''<rss><channel>
<item><title>令和８年度福島県医師会マンモグラフィ読影講習会</title><link>https://www.qabcs.or.jp/mmg_d/schedule/fukushima_270327.html</link><pubDate>Sat, 27 Mar 2027 00:00:00 +0900</pubDate></item>
<item><title>第３回京都乳房超音波技術講習会</title><link>https://www.qabcs.or.jp/us/schedule_us_g/270321_kyoto.html</link><pubDate>Sun, 21 Mar 2027 13:48:48 +0900</pubDate></item>
<item><title>第31回乳房超音波医師講習会</title><link>https://www.qabcs.or.jp/us/schedule_us_d/270314_fukuoka.html</link><pubDate>Sun, 14 Mar 2027 13:41:57 +0900</pubDate></item>
<item><title>第53回乳房超音波技術更新講習会</title><link>https://www.qabcs.or.jp/us/schedule_us_update_g/270313_fukuoka.html</link><pubDate>Sat, 13 Mar 2027 15:07:45 +0900</pubDate></item>
<item><title>マンモグラフィ撮影技術講習会（香川）</title><link>https://www.qabcs.or.jp/mmg_g/schedule/kagawa_270220.html</link><pubDate>Sat, 20 Feb 2027 00:00:00 +0900</pubDate></item>
</channel></rss>'''


def test_parse_jsgcs():
    items = u.parse_jsgcs(JSGCS_HTML)
    assert [x['url'] for x in items] == ['https://www.jsgcs.or.jp/importants/archives/51', 'https://www.jsgcs.or.jp/news/archives/1146']
    assert items[0]['published'].startswith('2026-10-13')


def test_jsgcs_items_are_kept_as_screening():
    x = {'headline': '対策型大腸がん検診における免疫便潜血検査陽性者に対する精密検査の基本的考え方', 'summary': '',
         'source': '日本消化器がん検診学会', 'url': 'https://www.jsgcs.or.jp/importants/archives/51'}
    assert u.relevant(x) and u.is_news_item(x)
    assert u.category(x) == '検診'


def test_qabcs_keeps_only_technologist_courses():
    items = {x['title']: x for x in u.parse_qabcs_seminars(QABCS_RSS)}
    assert set(items) == {'第３回京都乳房超音波技術講習会', '第53回乳房超音波技術更新講習会', 'マンモグラフィ撮影技術講習会（香川）'}
    k = items['第３回京都乳房超音波技術講習会']
    assert (k['event_start'], k['place'], k['category']) == ('2027-03-21', '京都', '超音波')
    m = items['マンモグラフィ撮影技術講習会（香川）']
    assert (m['event_start'], m['place'], m['category']) == ('2027-02-20', '香川', 'マンモグラフィ')
    assert items['第53回乳房超音波技術更新講習会']['place'] == '福岡'     # URLの地名から
