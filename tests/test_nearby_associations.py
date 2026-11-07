"""近県(岡山・愛媛・徳島・高知)の技師会の読み取りのテスト (python -m pytest tests/test_nearby_associations.py)。"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402


KOCHI_HTML = '''
<TABLE><TBODY>
<TR><TD bgcolor="#ffffff"></TD><TD></TD><TD></TD></TR>
<TR>
  <TD bgcolor="#ffffb3">R8.10.27</TD>
  <TD bgcolor="#ffffb3"><A href="endaiboshu20261203.pdf" target="_self"><IMG src="image4.gif"></A></TD>
  <TD bgcolor="#ffffb3"><FONT color="#000000">令和8年度高知県診療放射線技師学術大会</FONT>演題募集<FONT color="#ff0000">NEW</FONT></TD>
</TR>
<TR>
  <TD bgcolor="#ffffb3">R8.10.26</TD>
  <TD bgcolor="#ffffb3"><A href="ehimegenshiryoku20261101.pdf" target="_blank"><IMG src="image1.gif"></A></TD>
  <TD bgcolor="#ffffb3">原子力災害医療基礎研修のご案内【<B>締切10/29</B>】（<A href="ehimegenshiryoku20261101.pdf">募集要項</A>）</TD>
</TR>
<TR>
  <TD bgcolor="#ffffb3">R7.12.24</TD>
  <TD bgcolor="#ffffb3"><A href="https://www.jart.jp/news/x" target="_blank"><IMG src="image1.gif"></A></TD>
  <TD bgcolor="#ffffb3">セミナーのお知らせ</TD>
</TR>
</TBODY></TABLE>
'''


def test_kochi_rows_use_reiwa_dates_and_third_cell_titles():
    got = {x['url']: x for x in u.parse_kochi(KOCHI_HTML)}
    a = got['http://www.kochi-art.org/endaiboshu20261203.pdf']
    assert a['title'] == '令和8年度高知県診療放射線技師学術大会 演題募集'
    assert a['published'].startswith('2026-10-27')
    b = got['http://www.kochi-art.org/ehimegenshiryoku20261101.pdf']
    assert b['title'] == '原子力災害医療基礎研修のご案内【 締切10/29 】'
    assert got['https://www.jart.jp/news/x']['published'].startswith('2025-12-24')


def test_shift_jis_page_without_charset_is_decoded(monkeypatch):
    raw = '<TD>R8.11.2</TD><TD>技師会だより</TD>'.encode('cp932')
    monkeypatch.setattr(u, 'fetch_bytes', lambda url, timeout=60: (raw, None))
    assert '技師会だより' in u.fetch('http://www.kochi-art.org/news.htm')


EHIME_HTML = '''
<ul class="events">
<li><span>2027/1/23〜1/24</span> <a href="https://ehimeart.com/xo_event/taikai19">第19回 愛媛県診療放射線技師学術大会</a></li>
<li><span>{past}</span> <a href="https://ehimeart.com/xo_event/kenkyukai9">第9回 中予救急画像研究会</a></li>
</ul>
<ul class="news">
<li><span>2026/9/14</span> <a href="https://ehimeart.com/site/images/2026/09/a.pdf">「第19回愛媛県診療放射線技師学術大会」演題募集開始のお知らせ</a></li>
</ul>
'''


def test_ehime_events_go_to_schedule_and_news_skips_events(monkeypatch):
    past = (datetime.now(u.JST).date() - timedelta(days=3)).strftime('%Y/%-m/%-d')
    html = EHIME_HTML.format(past=past)
    monkeypatch.setattr(u, 'fetch', lambda url, timeout=60: html)
    events = u.update_ehime_schedule()
    assert [x['title'] for x in events] == ['第19回 愛媛県診療放射線技師学術大会']   # 終わった行事は入れない
    assert events[0]['event_start'] == '2027-01-23' and events[0]['place'] == '愛媛'
    news = u.parse_dated_links(html, u.EHIME_TOP, r'^(?!.*xo_event)')
    assert [x['title'] for x in news] == ['「第19回愛媛県診療放射線技師学術大会」演題募集開始のお知らせ']


@pytest.mark.parametrize('headline', [
    '求人情報です。岡山労災病院',
    '岡放技ニュース１０月号です。',
    '「技師会だより」R8年11月号掲載',
    'リレーフォーライフジャパンin高知参加者募集！',
])
def test_association_housekeeping_is_excluded(headline):
    assert not u.is_news_item({'headline': headline, 'summary': '', 'source': '岡山県診療放射線技師会', 'url': 'https://www.oart.jp/x'})


@pytest.mark.parametrize('headline, expected', [
    ('第３０２回美作放射線技師研究会のお知らせ', True),
    ('「高知県血管造影技術向上お勉強会（KATSUO会）」開催のお知らせ', True),
])
def test_association_seminars_are_kept(headline, expected):
    x = {'headline': headline, 'summary': '', 'source': '高知県診療放射線技師会', 'url': 'http://www.kochi-art.org/a.pdf'}
    assert u.is_news_item(x) is expected
    assert u.relevant(x)


def test_angiography_wording_is_angio_category():
    assert u.category({'headline': '高知県血管造影技術向上お勉強会', 'summary': '', 'source': ''}) == '血管撮影'


RECRUIT_HTML = '''
<section class="article-data"><h3>求人案内</h3>
<h4>2026年10月</h4><table class="table01"><tr><th>施設名</th><td>医療法人社団厚仁会　厚仁病院</td></tr>
<tr><th>住所</th><td>香川県丸亀市通町１３３番地</td></tr><tr><th>電話番号</th><td>0877-23-2311</td></tr>
<tr><th>募集人数</th><td>パート1人</td></tr><tr><th>業務内容</th><td>ＣＴ検査・一般撮影などの撮影をお願いします。</td></tr>
<tr><th>その他</th><td>月に２回程度です。<br>
※掲載は12月末ごろまで</td></tr><tr><th>人事担当</th><td>山田 太郎</td></tr></table></section>
'''


def test_kagawa_recruit_is_parsed_without_personal_names():
    jobs = u.parse_kart_recruit(RECRUIT_HTML)
    assert jobs == [{'month': '2026年10月', 'facility': '医療法人社団厚仁会 厚仁病院', 'address': '香川県丸亀市通町１３３番地',
                     'tel': '0877-23-2311', 'positions': 'パート1人', 'work': 'ＣＴ検査・一般撮影などの撮影をお願いします。',
                     'note': '月に２回程度です。 / ※掲載は12月末ごろまで'}]
    assert '山田' not in str(jobs)


def test_kagawa_file_keeps_all_notices_and_previous_jobs_on_error(monkeypatch, tmp_path):
    day = (datetime.now(u.JST).date() - timedelta(days=5)).strftime('%Y/%m/%d')
    top = f'<li>{day} <a href="article/data.php?nid=509">求人情報 掲載しました</a></li>'
    def fake_fetch(url, timeout=60):
        if 'recruit' in url:
            raise OSError('down')
        return top
    monkeypatch.setattr(u, 'fetch', fake_fetch)
    monkeypatch.setattr(u, 'KAGAWA_JSON', tmp_path / 'kagawa.json')
    (tmp_path / 'kagawa.json').write_text('{"recruit": [{"facility": "前回の病院"}]}', encoding='utf-8')
    out = u.update_kagawa()
    assert [x['headline'] for x in out['news']] == ['求人情報 掲載しました']   # ニュースでは外す掲載案内も別枠には出す
    assert out['recruit'] == [{'facility': '前回の病院'}]


# --- 追加の学会(初期状態は画面でチェックなし) ---------------------------

def test_jabts_meeting_dates_with_fullwidth_digits():
    html = '''<h3 class="wp-block-heading">第54回日本乳腺甲状腺超音波医学会学術集会</h3>
    <p>会期：2026年９月26日〜27日 <strong>オンデマンド配信：2026年10月14日～11月15日</strong><br>会場：別府国際コンベンションセンター</p>
    <p>詳細は<a href="https://www.c-linkage.co.jp/jabts54/">ホームページ</a></p>'''
    x = u.parse_jabts_meeting(html)
    assert (x['title'], x['event_start'], x['event_end']) == ('第54回日本乳腺甲状腺超音波医学会学術集会', '2026-09-26', '2026-09-27')
    assert x['url'] == 'https://www.c-linkage.co.jp/jabts54/' and x['source'] == '日本乳腺甲状腺超音波医学会'


def test_jabts_past_meeting_is_not_scheduled(monkeypatch):
    html = '<h3>第1回日本乳腺甲状腺超音波医学会学術集会</h3><p>会期：2001年9月26日</p>'
    monkeypatch.setattr(u, 'fetch', lambda url, timeout=60: html)
    assert u.update_jabts_schedule() == []


def test_shift_jis_page_with_cookies_is_decoded():
    raw = '<meta charset="Shift_JIS"><dt>2024/05/03</dt><dd>第16回DCIS研究会</dd>'.encode('cp932')
    assert '第16回DCIS研究会' in u.decode_page(raw, None)


def test_dcis_list_reads_dt_dates():
    html = '''<dl class="news_list"><dt>2024/05/03</dt><dd><a href="../information/information_detail.asp?id=147933">【イベント】第16回DCIS研究会が開催されます。</a></dd></dl>'''
    got = u.parse_dated_links(html, u.DCIS_NEWS, r'information_detail\.asp')
    assert got[0]['published'].startswith('2024-05-03') and got[0]['url'].endswith('id=147933')


def test_ct_board_blocks_drop_new_mark():
    html = '''<p class="title_news1">2026/10/7 X線CT認定技師の皆様へ<span>NEW!</span></p><p class="news1">第10回機構主催講習会の概要を更新しました。</p>
    <p class="title_news1">2026/9/1 </p><p class="news1">別のお知らせです。</p>'''
    got = u.parse_dated_blocks(html, 'https://www.ct-ninteikikou.jp/', 'slash')
    assert 'NEW!' not in got[0]['title'] and 'X線CT認定技師' in got[0]['title']


@pytest.mark.parametrize('name, expected', [('日本超音波検査学会', '超音波'), ('MRIfan.net', 'MRI'),
                                            ('日本X線CT専門技師認定機構', 'CT'), ('日本乳癌学会', 'マンモグラフィ'),
                                            ('DCIS研究会', 'マンモグラフィ'), ('日本乳腺甲状腺超音波医学会', '超音波')])
def test_new_societies_have_default_category(name, expected):
    assert u.SPECIALTY_DEFAULT_CATEGORY[name] == expected
