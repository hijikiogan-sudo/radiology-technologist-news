"""技師会の研修一覧の読み取りテスト (python -m pytest tests/test_news_seminars.py)。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402

# 実際の一覧と同じ形(1つのリンクの中に分類・受付状態・題名・受付期間・開催日・開催地域が並ぶ)
HTML = '''
<ul>
<li><a href="/seminar/告示研修実技研修東京都2026/11/23"><span class="cat">告示研修</span> <span class="st">受付前</span>
 <h3>告示研修（実技研修）東京都2026/11/23</h3><dl><dt>受付期間：</dt><dd>2026/9/18〜2026/11/8</dd>
 <dt>開催日：</dt><dd>2026/11/23〜2026/11/23</dd><dt>開催地域：</dt><dd>東京都</dd></dl><p>医政発0709第7号に基づく業務範囲…</p></a></li>
<li><a href="https://www.jart.jp/seminar/2026年度第1回-stat画像所見報告セミナー">生涯教育 申込み可 2026年度第1回 STAT画像所見報告セミナー
 受付期間：2026年9月15日（火）～2026年10月28日（水） 開催日：2026/11/12〜2026/11/12 開催地域：JART</a></li>
<li><a href="/seminar/ethics-guidelines-seminar">生涯教育 申込み可 倫理指針オンラインセミナー 受付期間：2022/11/21〜2027/03/31 開催日：2022/11/21〜2027/03/31</a></li>
<li><a href="/seminar/">研修一覧</a></li>
<li><a href="/news/info/123">お知らせ 開催日：2026/12/1〜2026/12/1</a></li>
</ul>
'''


def test_entries_are_parsed():
    items = {x['title']: x for x in u.parse_jart_seminars(HTML)}
    t = items['告示研修（実技研修）東京都2026/11/23']
    assert (t['kind'], t['status'], t['event_start'], t['apply_end'], t['place']) == ('告示研修', '受付前', '2026-11-23', '2026-11-08', '東京都')
    assert t['url'].startswith('https://www.jart.jp/seminar/')
    stat = items['2026年度第1回 STAT画像所見報告セミナー']
    assert (stat['status'], stat['apply_start'], stat['apply_end'], stat['event_start']) == ('申込み可', '2026-09-15', '2026-10-28', '2026-11-12')
    assert len(items) == 3            # 一覧ページへのリンクと /news/ のリンクは対象外


def test_update_keeps_previous_when_fetch_fails(tmp_path, monkeypatch):
    path = tmp_path / 'seminars.json'
    path.write_text(json.dumps({'items': [{'title': '前回分', 'event_end': '2099-01-01'}, {'title': '終了済み', 'event_end': '2000-01-01'}]}), encoding='utf-8')
    monkeypatch.setattr(u, 'SEMINARS_JSON', path)
    monkeypatch.setattr(u, 'fetch', lambda url: (_ for _ in ()).throw(OSError('down')))
    u.update_seminars()
    items = json.loads(path.read_text(encoding='utf-8'))['items']
    assert [x['title'] for x in items] == ['前回分']    # 終わった研修だけ外れる
