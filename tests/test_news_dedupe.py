"""重複記事の判定と統合のテスト (python -m pytest tests/test_news_dedupe.py)。"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402


def same(a, b):
    return u.same_story(u.canonical_title(a), u.canonical_title(b))


# --- 同じ記事としてまとめるべきもの ---------------------------------

def test_outlet_suffix_is_ignored():
    assert same(
        '少女に…29歳放射線技師を停職処分 - FNNプライムオンライン',
        '少女に…29歳放射線技師を停職処分 - Excite エキサイト',
    )


def test_image_prefix_and_parenthesised_outlet_are_ignored():
    assert same(
        '【画像】少女にわいせつ行為した不同意性交と児童買春の疑いで逮捕され不起訴 公立病院の29歳放射線技師を停職処分 - ライブドアニュース',
        '少女にわいせつ行為した不同意性交と児童買春の疑いで逮捕され不起訴 公立病院の29歳放射線技師を停職処分 (東海テレビ) - Yahoo!ニュース',
    )


def test_gallery_page_suffix_is_ignored():
    assert same(
        '同業者からの共感続々。放射線技師のお仕事あるあるを描く“ギャル技師ちゃん”誕生のきっかけとは？【著者インタビュー】 3枚目/全44枚 1448871 - ダ・ヴィンチWeb',
        '同業者からの共感続々。放射線技師のお仕事あるあるを描く“ギャル技師ちゃん”誕生のきっかけとは？【著者インタビュー】 - Yahoo!ニュース',
    )


def test_jart_date_prefix_and_truncation():
    assert same(
        '2026/10/01 会告/告示 2026年度 調査委員会企画 第2回 診療放射線技師のための調査研究スキルアップセミナーの開催について 量的調査（アンケート／定量・統計）編',
        '2026年度調査委員会企画 第2回 診療放射線技師のための調査研究スキルアップセミナー - 日本診療放射線技師会',
    )


# --- 別の記事として残すべきもの -------------------------------------

def test_different_update_dates_stay_separate():
    assert not same(
        '告示研修（実技研修）2026年度 開催日程（2026/10/14更新） - 日本診療放射線技師会',
        '告示研修（実技研修）2026年度 開催日程（2026/9/24更新） - 日本診療放射線技師会',
    )


def test_series_parts_stay_separate():
    assert not same('放射線から発展の原動力へ（最終章） - vietnam.vn', '放射線から発展の原動力へ（第3部） - Vietnam.vn')


def test_short_common_prefix_is_not_enough():
    assert not same('MRI安全管理セミナー - jsrt.or.jp', 'MRI安全管理セミナー 第8回 実地で学ぶ - jsrt.or.jp')


# --- 統合時に情報を失わないこと --------------------------------------

def _item(headline, source, url, date='2026-10-16'):
    return {'date': date, 'category': 'その他', 'importance': '低', 'headline': headline,
            'summary': headline, 'why': '', 'source': source, 'url': url, 'track': 'general'}


def test_clean_db_keeps_duplicate_outlets_as_also(monkeypatch):
    monkeypatch.setattr(u, 'relevant', lambda x: True)
    monkeypatch.setattr(u, 'is_news_item', lambda x: True)
    t = '公立病院の29歳放射線技師を停職処分 不同意性交と児童買春の疑い'
    db = [
        _item(t + ' - FNNプライムオンライン', 'FNNプライムオンライン', 'https://a.example/1'),
        _item('【画像】' + t + ' - ライブドアニュース', 'ライブドアニュース', 'https://b.example/2'),
        _item(t + ' (東海テレビ) - Yahoo!ニュース', 'Yahoo!ニュース', 'https://c.example/3'),
    ]
    out = u.clean_db(copy.deepcopy(db))
    assert len(out) == 1
    assert out[0]['url'] == 'https://a.example/1'
    assert [a['url'] for a in out[0]['also']] == ['https://b.example/2', 'https://c.example/3']
    # 2回目の実行でも結果が変わらない(毎朝の再処理で増えたり消えたりしない)
    again = u.clean_db(copy.deepcopy(out))
    assert again[0]['also'] == out[0]['also']
