"""分野別の専門学会の取得テスト (python -m pytest tests/test_news_specialty_sources.py)。
フィクスチャは2026年10月時点の各サイトの構造を写したもの。"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402

JASTRO = '''
<section class="event_thumbnail"><div class="slick-slide"><a href="https://www.c-linkage.co.jp/jcerg2027/"><h3>第40回高精度放射線外部照射部会学術大会</h3><p>2027年5月28日(金)〜29日(土)</p></a></div></section>
<ul class="news_list">
 <li class="news_mem"><span class="news_cat_icon">会員向け</span><time>2026.10.13</time><span class="news_ttl"><a href="/member/news/2026/20261013.pdf">2025年度（2026年）社員総会開催のお知らせ</a></span></li>
 <li class="news_medi"><span class="news_cat_icon">医療関係者</span><time>2026.10.01</time><span class="news_ttl"><a href="https://www.congre.co.jp/jastro2026/index.html">日本放射線腫瘍学会学術大会2026 参加登録を開始いたしました。</a></span></li>
</ul>'''

JSMRM = '''<div class="box_news">
 <div class="date_news">2026年10月13日 <span class="ico_p">学会から</span> </div>
 <div class="title_news"><a href="https://www.jsmrm.jp/modules/news/index.php?content_id=758">第54回日本磁気共鳴医学会大会 インタビュー</a></div>
 <div class="date_news">2026年10月2日 <span class="ico_p">学会から</span> </div>
 <div class="title_news"><a href="https://www.jsmrm.jp/modules/news/index.php?content_id=757">情報更新：肝MRエラストグラフィ撮像条件</a></div>
 <a href="https://www.jsmrm.jp/modules/about/">学会について(メニュー)</a>
</div>'''

JSCT = '''<article id="20220622"><h3></h3><p><a href="./docs/jsct2022_result.pdf"><b>JSCT 2022 第10回学術大会 優秀研究発表賞のお知らせ</b></a></p><p class="date">2022/08/04</p></article>'''

JMRTS = '''
<li class="dropdown"><a href="#">更新・セミナー</a><ul><li><a href="./seminar/seminar2.html">MR医療安全セミナー</a></li></ul></li>
<li class="col-xs-12"><div> <span class="label label-default label-topics">お知らせ</span> <span class="date"><font color="red"><strong>【ハイブリッド開催：11/29(日)】</strong></font><a href="seminar/seminar2.html">第17回MR医療安全セミナー開催のお知らせ＜2026.10&gt;</a></span></div></li>
<li class="col-xs-12"><div> <span class="label label-default label-topics">安全情報</span> <span class="date"><a href="safety/survey.html">MRI関連デバイス添付文書の不具合情報に関する調査へのご協力のお願い＜2026.10＞</a></span></div></li>
<li class="col-xs-12"><div> <span class="label label-default label-topics">認定研究会</span> <span class="date"><font color="red"><strong>【現地開催：11/7(土)】</strong></font><a href="kenkyukai/kochi.html">第10回高知MRI技術研究会開催のお知らせ＜2026.10&gt;</a></span></div></li>
<li class="col-xs-12"><div> <span class="label label-default label-topics">認定研究会</span> <span class="date"><font color="red"><strong>【Web開催：11/12(木)】</strong></font><a href="kenkyukai/kansai.html">第114回関西MRI技術研究会開催のお知らせ＜2026.10&gt;</a></span></div></li>
<li class="col-xs-12"><div> <span class="label label-default label-topics">認定研究会</span> <span class="date"><font color="red"><strong>【現地開催：11/7(土)】</strong></font><a href="kenkyukai/kobe.html">2026年度第2回神戸MRの会開催のお知らせ＜2026.9&gt;</a></span></div></li>
<li class="col-xs-12"><div> <span class="label label-default label-topics">試験/更新</span> <span class="date"><a href="exam/22.html">第22回磁気共鳴(MR)専門技術者認定試験のご案内＜2026.7＞</a></span></div></li>
'''


def test_dated_links_jastro_skips_event_banner():
    items = u.parse_dated_links(JASTRO, 'https://www.jastro.or.jp/', start='news_list')
    assert [x['title'] for x in items] == ['2025年度（2026年）社員総会開催のお知らせ', '日本放射線腫瘍学会学術大会2026 参加登録を開始いたしました。']
    assert items[0]['url'] == 'https://www.jastro.or.jp/member/news/2026/20261013.pdf'
    assert items[0]['published'].startswith('2026-10-13')


def test_dated_links_jsmrm_with_link_filter():
    items = u.parse_dated_links(JSMRM, 'https://www.jsmrm.jp/', r'/modules/news/')
    assert [x['published'][:10] for x in items] == ['2026-10-13', '2026-10-02']


def test_dated_links_date_after_link():
    items = u.parse_dated_links(JSCT, 'https://www.jsct-tech.org/')
    assert items == [{'title': 'JSCT 2022 第10回学術大会 優秀研究発表賞のお知らせ',
                      'url': 'https://www.jsct-tech.org/docs/jsct2022_result.pdf', 'published': '2022-08-04T00:00:00+09:00'}]


def test_jmrts_splits_news_and_events():
    news, events = u.parse_jmrts(JMRTS, today=date(2026, 10, 27))
    assert [x['title'] for x in news] == ['MRI関連デバイス添付文書の不具合情報に関する調査へのご協力のお願い',
                                         '第22回磁気共鳴(MR)専門技術者認定試験のご案内']
    assert news[0]['published'].startswith('2026-10-27')      # 今月の掲載は見つけた日
    assert news[1]['published'].startswith('2026-07-01')
    ev = {x['title']: x for x in events}
    assert ev['第17回MR医療安全セミナー開催のお知らせ']['event_start'] == '2026-11-29'
    assert ev['第10回高知MRI技術研究会開催のお知らせ']['place'] == '高知'
    assert ev['第114回関西MRI技術研究会開催のお知らせ']['place'] == 'オンライン'
    assert ev['2026年度第2回神戸MRの会開催のお知らせ']['place'] == '兵庫'
    assert all(x['category'] == 'MRI' for x in events)


def test_specialty_source_category_default(monkeypatch):
    monkeypatch.setattr(u, 'relevant', lambda x: True)
    x = {'date': '2026-10-15', 'headline': '第100回学術集会 演題募集開始のお知らせ', 'summary': '', 'source': '日本超音波医学会',
         'url': 'https://www.jsum.or.jp/news/100/', 'importance': '中', 'category': 'その他', 'why': '', 'track': 'official'}
    assert u.clean_db([x])[0]['category'] == '超音波'


def test_specialty_sources_are_configured():
    names = {n for n, *_ in u.SPECIALTY_SOURCES}
    assert {'日本放射線腫瘍学会', '日本磁気共鳴医学会', '日本IVR学会', '日本超音波医学会', '日本核医学技術学会', '日本CT技術学会', '日本医学物理学会'} <= names


def test_society_guideline_is_high():
    x = {'headline': 'IVR手技施行に関する診療体制についてのガイドライン', 'summary': '', 'source': '日本IVR学会', 'url': 'https://www.jsir.or.jp/x/'}
    assert u.importance(x, False) == '高'
    x['importance'] = '高'
    assert 'プロトコル' in u.technologist_note(x)


def test_guideline_seminar_or_public_comment_is_not_high():
    for h in ('医療情報システム安全管理ガイドライン対応研修プログラムのご案内', '「画像診断ガイドライン」パブリックコメント募集'):
        assert u.importance({'headline': h, 'summary': '', 'source': '日本医学放射線学会', 'url': 'https://www.radiology.jp/x'}, False) == '中'
