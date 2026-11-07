"""記事ごとの一言(ポイント)と要約整理のテスト (python -m pytest tests/test_news_notes.py)。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402


def note(headline, importance='中'):
    return u.technologist_note({'headline': headline, 'summary': '', 'importance': importance})


@pytest.mark.parametrize('headline, expected', [
    ('ガストログラフィン®経口・注腸用「限定出荷」継続のお知らせ', '代替品'),
    ('画像診断ガイドライン2026年度版の全記事の公開について', 'プロトコル'),
    ('股関節撮影時の生殖腺遮蔽の見直しについて（声明）', '撮影手技の見直し'),
    ('診療報酬改定による現場影響度調査に関するアンケート', '算定要件'),
    ('告示研修（実技研修）大阪府2026/12/13', '告示研修'),
    ('「放射線治療」特集号の原稿募集について', '応募条件'),
    ('「画像診断ガイドライン」パブリックコメント募集', '意見募集'),
])
def test_note_matches_reason(headline, expected):
    assert expected in note(headline)


@pytest.mark.parametrize('headline', [
    '第62回秋季臨床大会 JRS-NEXT企画 開催報告',           # 終わった催しの報告
    '更新講習会の開催遅延について',                         # 申込を促す案内ではない
    '日本医学放射線学会賞',                                   # 当てはまる理由がない
])
def test_no_note_when_nothing_specific(headline):
    assert note(headline) == ''


def test_low_importance_gets_no_note():
    assert note('ガストログラフィン「限定出荷」', importance='低') == ''


@pytest.mark.parametrize('headline, summary, source', [
    ('停職処分 公立病院の29歳放射線技師 - FNNプライムオンライン', '停職処分 公立病院の29歳放射線技師 FNNプライムオンライン', 'FNNプライムオンライン'),
    ('［お知らせ］専門部会誌-秋号（電子版）閲覧のご案内 - 公益社団法人 日本放射線技術学会',
     '［お知らせ］専門部会誌-秋号（電子版）閲覧のご案内 公益社団法人 日本放射線技術学会', '公益社団法人 日本放射線技術学会'),
])
def test_summary_repeating_headline_is_cleared(headline, summary, source):
    assert u.clean_summary({'headline': headline, 'summary': summary, 'source': source}) == ''


def test_real_summary_is_kept():
    s = 'IGRTを支える教育体制、運用の基礎、臨床上の注意点や工夫を扱うWebセミナー。'
    assert u.clean_summary({'headline': '第66回放射線治療セミナー', 'summary': s, 'source': 'jsrt.or.jp'}) == s


@pytest.mark.parametrize('headline, expected', [
    ('2027年度 胃がん検診専門技師認定更新に関するお知らせ', '申請の期限'),
    ('2027年度 新規大腸CT検査技術認定施設申請手続きに関するお知らせ', '申請の期限'),
    ('第41回超音波検査士認定試験：受験票の発送日について', '受験票'),
    ('128列以上CTの認証申請について', '装置・ソフトウェア'),
    ('【重要】「JARTIS」の一時閉鎖について (PHP脆弱性対応)', 'eラーニング'),
    ('Lu-177-PSMA-I&T治験適正使用マニュアル(第2版)を掲載', 'プロトコル'),
    ('乳がん検診における乳房構成に関するQ＆Aを掲載しました。', 'プロトコル'),
    ('第6回 科学技術系専門職の男女共同参画実態調査（大規模アンケート）', '回答期限'),
])
def test_note_for_society_notices(headline, expected):
    assert expected in note(headline)


def test_guideline_note_ignores_background_in_summary():
    x = {'headline': '第6回 科学技術系専門職の男女共同参画実態調査（大規模アンケート）', 'importance': '中',
         'summary': 'これまでの調査結果に基づく提言は、国の政策の資料としても活用されてきました。',
         'source': '日本放射線技術学会', 'url': 'https://www.jsrt.or.jp/data/news/70530/'}
    assert '回答期限' in u.technologist_note(x)


# --- ポイント(定型文を付けない) ---------------------------------------------

@pytest.mark.parametrize('headline', [
    '「第46回 さぬき美じょん」開催のお知らせ',
    '第6回 MRI fan net Web講演会のご案内',
    '医学生・研修医セミナー30周年記念誌を掲載しました。',
    '新型CT装置が薬事承認を取得',
    '2026年度 第3回単純X線撮影における品質管理セミナー',
    '書籍『RI内用療法の線量評価　基礎から実践まで』刊行のお知らせ',
    '医用超音波の基礎（連載第4回/全10回）',
])
def test_plain_announcements_have_no_stock_point(headline):
    assert note(headline) == ''


@pytest.mark.parametrize('headline, word', [
    ('造影剤の限定出荷について', '代替品'),
    ('医療安全情報 No.200 MRI検査室への持ち込み', '確認漏れ'),
    ('診療報酬改定の施設基準について', '算定'),
    ('令和8年度 告示研修のご案内', '告示研修'),
])
def test_points_that_tell_what_to_do_remain(headline, word):
    assert word in note(headline)

