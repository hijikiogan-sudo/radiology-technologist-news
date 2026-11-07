"""重要度(高・中・低)判定のテスト (python -m pytest tests/test_news_importance.py)。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402

GNEWS = 'https://news.google.com/rss/articles/xxx'  # Google News 経由は URL で公式判定できない


def imp(headline, source):
    x = {'headline': headline, 'summary': headline, 'source': source, 'url': GNEWS}
    return u.importance(x, u.is_official(GNEWS))


@pytest.mark.parametrize('headline, source', [
    ('ガストログラフィン®経口・注腸用「限定出荷」継続のお知らせ', '日本診療放射線技師会'),
    ('【重要】メール配信システムへの不審アクセスに伴う個人情報漏えいの可能性について', '日本診療放射線技師会'),
    ('画像診断ガイドライン2026年度版の全記事の公開について', '公益社団法人日本医学放射線学会'),
    ('股関節撮影時の生殖腺遮蔽の見直しについて（声明）', '日本診療放射線技師会'),
    ('令和8年度診療報酬改定の概要', '日本経済新聞'),
])
def test_high(headline, source):
    assert imp(headline, source) == '高'


@pytest.mark.parametrize('headline, source', [
    # 公式のお知らせは、Google News 経由でも「中」になる
    ('2026年度 画像医療システム産業研究会 開催のお知らせ', '日本診療放射線技師会'),
    ('第 54 回日本放射線技術学会秋季学術大会プログラム概要', '日本放射線技術学会'),
    # 「安全管理」を含んでも研修の開催案内は「中」まで
    ('医療安全管理者養成研修の開催について', '日本診療放射線技師会'),
    ('厚生労働省より「医療情報システム安全管理ガイドライン対応研修プログラム」のご案内', '日本診療放射線技師会'),
    # 国内の装置導入
    ('兵庫医科大学病院、「Elekta Evo」で国内初の治療を開始', '毎日新聞'),
])
def test_mid(headline, source):
    assert imp(headline, source) == '中'


@pytest.mark.parametrize('headline, source', [
    ('公立病院の29歳放射線技師を停職処分', 'FNNプライムオンライン'),
    ('ペット向けのがん放射線治療・ロボット手術、鳥取大が29年秋導入へ', '朝日新聞'),
    ('AI医療画像・放射線診断市場、2035年に220億米ドルへ', 'Newscast.jp'),
    ('ハノイ医科大学は、東南アジアで初めてとなる5テスラMRI装置を導入', 'Vietnam.vn'),
    ('放射線技師のお仕事あるあるを描く“ギャル技師ちゃん”誕生のきっかけとは？【著者インタビュー】', 'ライブドアニュース'),
])
def test_low(headline, source):
    assert imp(headline, source) == '低'


def test_curated_importance_is_kept(monkeypatch):
    """手動で指定した重要度は自動判定で上書きしない。"""
    monkeypatch.setattr(u, 'relevant', lambda x: True)
    monkeypatch.setattr(u, 'is_news_item', lambda x: True)
    needle, meta = u.CURATED_SPECIALIST[0]
    item = {'date': '2026-09-20', 'category': 'その他', 'importance': '低', 'headline': f'［お知らせ］{needle} - jsrt.or.jp',
            'summary': '', 'why': '', 'source': 'jsrt.or.jp', 'url': 'https://example.com/a', 'track': 'general'}
    out = u.clean_db([item])
    assert out[0]['importance'] == meta.get('importance', out[0]['importance'])
