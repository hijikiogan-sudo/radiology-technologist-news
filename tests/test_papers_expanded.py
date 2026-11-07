"""新着配信と目次の補完で、日付・重複・取得失敗を扱う回帰テスト。"""
import json
import sys
from pathlib import Path
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import update_news as u


def contents(day='2026/10/20', issue='2', title='MRIの安全管理', doi='10.1234/example', author='山田 太郎, 佐藤 花子'):
    return f'''<div id="search-resultslist-wrap"><ul><li>
    <div class="searchlist-title"><a href="https://www.jstage.jst.go.jp/article/jjmrm/46/{issue}/46_123/_article/-char/ja">{title}</a></div>
    <div class="searchlist-authortags customTooltip" title="{author}">山田 太郎, 佐 ...</div>
    <div class="searchlist-additional-info">発行日: 2026年<br>公開日: {day}<br>[早期公開] 公開日: 2026/09/01</div>
    <div class="searchlist-doi"><a href="https://doi.org/{doi}">DOI</a></div>
    <div class="abstract">本文は取り込まない。</div></li></ul></div>'''


def atom(day, early=False):
    label = '早期公開日' if early else '公開日'
    return f'''<feed><entry><summary><![CDATA[
    [ タイトル ] MRIの安全管理 [ 著者 ] 山田 太郎
    [ {label} ] {day} [ DOI ] https://doi.org/10.1234/example
    ]]></summary><id>tag:jstage:/jjmrm_advpub_0_123</id></entry></feed>'''


def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(u, 'PAPERS_JSON', tmp_path/'papers.json')
    monkeypatch.setattr(u, 'JOURNALS', (('日本磁気共鳴医学会雑誌', 'jjmrm', 'MRI'),))
    monkeypatch.setattr(u, 'SOURCE_STATUS', {})
    return u.datetime.now(u.JST).date().isoformat()


def test_early_publication_date_does_not_leak_into_authors():
    items = u.parse_jstage_atom(atom('2026-10-20', early=True))
    assert items[0]['published'].startswith('2026-10-20')
    assert items[0]['authors'] == '山田 太郎'


def test_contents_use_publication_date_full_authors_and_doi():
    item, = u.parse_jstage_contents(contents(title='MRIの<sup>新しい</sup>安全管理'))
    assert item['published'].startswith('2026-10-20')
    assert item['authors'] == '山田 太郎, 佐藤 花子'
    assert item['url'] == 'https://doi.org/10.1234/example'
    assert '<sup>' not in item['title']
    assert '本文' not in str(item)


def test_contents_skip_supplements_front_matter_and_invalid_dates():
    assert not u.parse_jstage_contents(contents(issue='Supplement2'))
    assert not u.parse_jstage_contents(contents(title='編集後記'))
    assert not u.parse_jstage_contents(contents(title='青木先生を偲ぶ'))
    assert not u.parse_jstage_contents(contents(day='2026/02/31'))


def test_contents_subtitle_is_not_mistaken_for_author():
    page = contents(title='乳房MRIの現在と未来：', author='山口 健')
    page = page.replace('<div class="searchlist-authortags customTooltip"', '<div class="searchlist-authortags" title="マルチパラメトリックMRIからの展開">副題</div><div class="searchlist-authortags customTooltip"', 1)
    item, = u.parse_jstage_contents(page)
    assert item['title'] == '乳房MRIの現在と未来： マルチパラメトリックMRIからの展開'
    assert item['authors'] == '山口 健'


def test_contents_fill_an_empty_rss(monkeypatch, tmp_path):
    day = setup(monkeypatch, tmp_path)
    monkeypatch.setattr(u, 'fetch', lambda url: '<feed/>' if 'sryCd=' in url else contents(day.replace('-', '/')))
    items = u.update_papers()
    assert len(items) == 1 and items[0]['category'] == '安全管理'
    assert u.SOURCE_STATUS['日本磁気共鳴医学会雑誌']['contents_items'] == 1


def test_same_doi_in_rss_and_contents_is_saved_once(monkeypatch, tmp_path):
    day = setup(monkeypatch, tmp_path)
    monkeypatch.setattr(u, 'fetch', lambda url: atom(day) if 'sryCd=' in url else contents(day.replace('-', '/')))
    assert len(u.update_papers()) == 1
    assert len(u.update_papers()) == 1


def test_older_and_future_contents_are_not_marked_as_new(monkeypatch, tmp_path):
    day = setup(monkeypatch, tmp_path)
    now = u.datetime.now(u.JST).date()
    page = contents((now-timedelta(days=u.PAPER_DAYS+1)).strftime('%Y/%m/%d'))
    page += contents((now+timedelta(days=1)).strftime('%Y/%m/%d'), doi='10.1234/future')
    monkeypatch.setattr(u, 'fetch', lambda url: '<feed/>' if 'sryCd=' in url else page)
    assert u.update_papers() == []


def test_contents_failure_keeps_working_rss(monkeypatch, tmp_path):
    day = setup(monkeypatch, tmp_path)
    def fetch(url):
        if 'sryCd=' in url:
            return atom(day)
        raise OSError('temporary failure')
    monkeypatch.setattr(u, 'fetch', fetch)
    assert len(u.update_papers()) == 1
    assert 'error' not in u.SOURCE_STATUS['日本磁気共鳴医学会雑誌']
    assert 'warning' in u.SOURCE_STATUS['日本磁気共鳴医学会雑誌']


def test_failed_sources_do_not_erase_saved_papers(monkeypatch, tmp_path):
    day = setup(monkeypatch, tmp_path)
    old = {'journal': '日本磁気共鳴医学会雑誌', 'title': '保存済み', 'url': 'https://doi.org/10.1234/old', 'published': day, 'added': day, 'category': 'MRI', 'authors': ''}
    u.PAPERS_JSON.write_text(json.dumps({'items': [old]}))
    def fail(url):
        raise OSError('temporary failure')
    monkeypatch.setattr(u, 'fetch', fail)
    assert u.update_papers() == [old]
    assert 'error' in u.SOURCE_STATUS['日本磁気共鳴医学会雑誌']
