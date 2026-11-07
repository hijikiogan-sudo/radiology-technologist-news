"""学会・厚労省の新着の直接取得テスト (python -m pytest tests/test_news_official_sources.py)。

フィクスチャは実際のページの構造(2026年10月時点)を写したもの。
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402

JSRT_HTML = '''<table><tr>
 <th class="w5em">2026/10/27</th>
 <td class="w5em"><img src="category-news-other.png" alt="14_他団体からのご案内"></td>
 <td><a href="https://www.jsrt.or.jp/data/news/70512/">［案内板］【JST-RISTEX】12/1（火）SOLVEトラスト枠　公開イベント開催のご案内</a></td>
</tr><tr>
 <th class="w5em">2026/10/20</th><td></td>
 <td><a href="https://www.jsrt.or.jp/data/news/70338/">［お知らせ］2026年度　第3回単純X線撮影における品質管理セミナー</a></td>
</tr></table>'''

JRS_HTML = '''<dl>
<dt><time datetime="2026-10-23">2026年10月23日</time></dt>
<dd><a href="member_info/relation/20261023_02.html">【JIRA（日本画像医療システム工業会）】2026年度 画像医療システム産業研究会 開催のご案内</a></dd><dt><time datetime="2026-10-21">2026年10月21日</time></dt>
<dd><a href="specialist/s_information/20261021_01.html">令和9年度からの放射線科領域研修を希望する方へ</a></dd>
</dl>'''

JSNM_RSS = '''<?xml version="1.0"?><rss><channel>
<item><title>ピロリン酸テクネチウム（99mTc）注射液の保険診療上の取扱いについて</title><link>https://jsnm.org/archives/10420/</link><pubDate>Sat, 10 Oct 2026 02:15:54 +0000</pubDate></item>
<item><title><![CDATA[Lu-177-PSMA-I&#038;T治験適正使用マニュアル(第2版)を掲載]]></title><link>https://jsnm.org/archives/10435/</link><pubDate>Mon, 26 Oct 2026 00:28:26 +0000</pubDate></item>
</channel></rss>'''

MHLW_RDF = '''<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/">
<item rdf:about="https://www.mhlw.go.jp/a"><title>診療放射線技師の業務に関する疑義解釈について</title><link>https://www.mhlw.go.jp/stf/a.html</link><dc:date>2026-10-24T10:00:00+09:00</dc:date></item>
<item rdf:about="https://www.mhlw.go.jp/b"><title>雇用調整助成金の支給状況</title><link>https://www.mhlw.go.jp/stf/b.html</link><dc:date>2026-10-24T10:00:00+09:00</dc:date></item>
</rdf:RDF>'''


def test_parse_jsrt():
    items = u.parse_jsrt(JSRT_HTML)
    assert [x['url'] for x in items] == ['https://www.jsrt.or.jp/data/news/70512/', 'https://www.jsrt.or.jp/data/news/70338/']
    assert items[1]['published'].startswith('2026-10-20')


def test_parse_jrs_resolves_relative_links():
    items = u.parse_jrs(JRS_HTML)
    assert items[1] == {'title': '令和9年度からの放射線科領域研修を希望する方へ',
                        'url': 'https://www.radiology.jp/specialist/s_information/20261021_01.html',
                        'published': '2026-10-21T00:00:00+09:00'}


def test_parse_rss2_and_rss1():
    j = u.parse_rss(JSNM_RSS)
    assert j[1]['title'] == 'Lu-177-PSMA-I&T治験適正使用マニュアル(第2版)を掲載'   # CDATAと実体参照を戻す
    assert j[0]['published'].startswith('2026-10-10T11:15')                        # 日本時間に
    m = u.parse_rss(MHLW_RDF)
    assert [x['title'] for x in m] == ['診療放射線技師の業務に関する疑義解釈について', '雇用調整助成金の支給状況']


def test_direct_official_news_filters_and_limits(monkeypatch):
    pages = {u.JSRT_NEWS: JSRT_HTML, u.JRS_TOP: JRS_HTML, u.JSNM_FEED: JSNM_RSS, u.MHLW_FEED: MHLW_RDF}
    monkeypatch.setattr(u, 'fetch', lambda url: pages[url])

    class FixedNow(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 27, 9, 0, tzinfo=u.JST)
    monkeypatch.setattr(u, 'datetime', FixedNow)
    got = {x['title']: x for x in u.direct_official_news()}
    assert 'ピロリン酸テクネチウム（99mTc）注射液の保険診療上の取扱いについて' in got
    assert '診療放射線技師の業務に関する疑義解釈について' in got
    assert '雇用調整助成金の支給状況' not in got                 # 厚労省は放射線・診療報酬関連だけ
    assert got['令和9年度からの放射線科領域研修を希望する方へ']['source'] == '日本医学放射線学会'


def test_one_source_failing_does_not_stop_others(monkeypatch):
    def fetch(url):
        if url == u.JSRT_NEWS:
            raise OSError('down')
        return {u.JRS_TOP: JRS_HTML, u.JSNM_FEED: JSNM_RSS, u.MHLW_FEED: MHLW_RDF}[url]
    monkeypatch.setattr(u, 'fetch', fetch)
    monkeypatch.setattr(u, 'DIRECT_DAYS', 100000)
    sources = {x['source'] for x in u.direct_official_news()}
    assert sources == {'日本医学放射線学会', '日本核医学会', '厚生労働省'}


def test_insurance_handling_is_high():
    x = {'headline': 'ピロリン酸テクネチウム（99mTc）注射液の保険診療上の取扱いについて', 'summary': '', 'source': '日本核医学会', 'url': 'https://jsnm.org/archives/10420/'}
    assert u.importance(x, False) == '高'
    assert u.relevant(x)
    x['importance'] = '高'
    assert '算定' in u.technologist_note(x)
