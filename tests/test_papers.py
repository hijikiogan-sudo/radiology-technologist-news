"""学会誌の新着論文(J-STAGE RSS)のテスト。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402

RSS = '''<?xml version="1.0" encoding="UTF-8"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<item rdf:about="https://www.jstage.jst.go.jp/article/jsgcs/64/5/64_1/_article/-char/ja"><title>胃X線検診における撮影体位の検討</title>
<link>https://www.jstage.jst.go.jp/article/jsgcs/64/5/64_1/_article/-char/ja</link><dc:date>2026-10-20</dc:date></item>
<item><title>大腸内視鏡の受診率</title><link>https://www.jstage.jst.go.jp/article/jsgcs/64/5/64_2/_article/-char/ja</link><dc:date>2026-10-20</dc:date></item>
</rdf:RDF>'''


def test_papers_are_saved_and_kept(monkeypatch, tmp_path):
    monkeypatch.setattr(u, 'PAPERS_JSON', tmp_path / 'papers.json')
    monkeypatch.setattr(u, 'JOURNALS', (('日本消化器がん検診学会雑誌', 'jsgcs', '検診'),))
    monkeypatch.setattr(u, 'fetch', lambda url: RSS)
    out = u.update_papers()
    assert [x['title'] for x in out] == ['胃X線検診における撮影体位の検討', '大腸内視鏡の受診率']
    assert out[0]['journal'] == '日本消化器がん検診学会雑誌' and out[0]['published'] == '2026-10-20'
    assert {x['category'] for x in out} == {'検診'}
    # 次の回にフィードから消えても、前回分は残る
    monkeypatch.setattr(u, 'fetch', lambda url: '<rss></rss>')
    out2 = u.update_papers()
    assert len(out2) == 2
    assert json.loads((tmp_path / 'papers.json').read_text())['items'][0]['url'].startswith('https://www.jstage.jst.go.jp/')


ATOM = '''<?xml version="1.0" encoding="utf-8"?> <feed xmlns="http://www.w3.org/2005/Atom" xml:lang="ja"> <title>J-STAGE</title>
<entry> <title><![CDATA[新着記事を登載しました。日本放射線技術学会雑誌]]></title> <link href="http://www.jstage.jst.go.jp/browse/jjrt/-char/ja"/>
<summary><![CDATA[ [ タイトル ] 先天性心疾患に対する小児心臓CTにおけるsplit-bolus法の有用性 [ 著者 ] 池野 裕介,森下 勝 [ 公開日 ] 2026-10-21 [ DOI ] https://doi.org/10.6009/jjrt.26-1700 ]]></summary>
<id>tag:jstage.jst.go.jp:/WhatsNew/ja/NewArticle/jjrt_82_12_82_26-1700</id></entry>
<entry> <title><![CDATA[新着記事を登載しました。日本消化器がん検診学会雑誌]]></title> <link href="http://www.jstage.jst.go.jp/browse/jsgcs/-char/ja"/>
<summary><![CDATA[ [ タイトル ] 講演プログラム [ 著者 ] [ 公開日 ] 2026-10-15 [ DOI ] https://doi.org/10.11404/jsgcs.64.993 ]]></summary></entry>
</feed>'''


def test_jstage_atom():
    items = u.parse_jstage_atom(ATOM)
    assert items == [{'title': '先天性心疾患に対する小児心臓CTにおけるsplit-bolus法の有用性',
                      'url': 'https://doi.org/10.6009/jjrt.26-1700', 'published': '2026-10-21T00:00:00+09:00',
                      'authors': '池野 裕介,森下 勝'}]


def test_atom_feed_is_used(monkeypatch, tmp_path):
    monkeypatch.setattr(u, 'PAPERS_JSON', tmp_path / 'papers.json')
    monkeypatch.setattr(u, 'JOURNALS', (('日本放射線技術学会雑誌', 'jjrt', None),))
    monkeypatch.setattr(u, 'fetch', lambda url: ATOM)
    out = u.update_papers()
    assert len(out) == 1 and out[0]['category'] == 'CT' and out[0]['authors'].startswith('池野')


def test_supplement_and_italic():
    xml = '''<feed><entry><summary><![CDATA[ [ タイトル ] 胃がん検診の未来 [ 著者 ] [ 公開日 ] 2026-10-15 [ DOI ] https://doi.org/10.11404/jsgcs.64.993 ]]></summary>
<id>tag:jstage.jst.go.jp:/WhatsNew/ja/NewArticle/jsgcs_64_Supplement2_64_64.993</id></entry>
<entry><summary><![CDATA[ [ タイトル ] <I>Helicobacter pylori</I> 未感染胃の検討 [ 著者 ] 山田 [ 公開日 ] 2026-10-20 [ DOI ] https://doi.org/10.11404/jsgcs.64.500 ]]></summary>
<id>tag:jstage.jst.go.jp:/WhatsNew/ja/NewArticle/jsgcs_64_5_64_500</id></entry></feed>'''
    items = u.parse_jstage_atom(xml)
    assert [x['title'] for x in items] == ['Helicobacter pylori 未感染胃の検討']
