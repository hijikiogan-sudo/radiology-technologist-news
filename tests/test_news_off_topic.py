"""技師の業務に関係しない記事の除外テスト (python -m pytest tests/test_news_off_topic.py)。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402


def item(headline, source=''):
    return {'headline': headline, 'summary': headline, 'source': source, 'url': 'https://news.google.com/x'}


@pytest.mark.parametrize('headline, source', [
    ('【クラファン】医療格差解消へ 導入100施設超の遠隔画像診断支援システム、11月4日募集開始', '株探'),
    ('多様ながんから血液がんまで、治療を支え続けた放射線治療装置の更新を', 'READYFOR'),
    ('有明地域の頼れる病院であり続ける。老朽化したMRI更新にご支援を', ''),
    ('〈今期売上高5.86億円見込〉100施設超が導入する遠隔画像診断支援システム', 'FUNDINNO'),
    ('胃がん検診を受けました : ブログ : 習志野市', '公明党'),
    ('生成AIで遠隔画像診断支援を革新！', 'JIJICO'),
    ('【画像】乳がん検診で「要精密検査」クリニックの選び方を専門医が解説', 'ライブドアニュース'),
    ('ペット向けのがん放射線治療やロボット手術、鳥取大に拠点', '読売新聞'),
    ('診察室8部屋、MRI・CT完備の動物総合病院がリニューアルオープン', 'Yahoo!ニュース'),
    ('鳥取大学が獣医学教育医療センター新設へ', 'TBS NEWS DIG'),
    ('『ラジエーションハウス』21巻は11月18日発売', ''),
    ('メンテナンス情報（11/4）', '日本医学放射線学会'),
    ('メンテナンス情報 - 日本医学放射線学会', '日本医学放射線学会'),
    ('【システムメンテナンスのお知らせ】会員ページ', '日本放射線技術学会'),
    ('日本AI医療画像処理システム市場：診断の自動化、画像精度の向上', 'ニコニコニュース'),
    ('「放射線に興味がない人は絶対入らないで！」“就職評価の高い西日本の私立大学”', 'news.nicovideo.jp'),
])
def test_off_topic_is_excluded(headline, source):
    assert not u.is_news_item(item(headline, source))


@pytest.mark.parametrize('headline, source', [
    ('駒沢大学とシーメンス、画像診断の人材育成拠点 操作やメンテなど', '日本経済新聞'),
    ('装置のメンテナンス体制を見直し 保守点検の手引き改訂', '日本診療放射線技師会'),
    ('【健康大百科】がんに対する最新の放射線治療', '日テレNEWS NNN'),
    ('ViewSend ICT、遠隔画像診断のAI開発・業務自動化で資金調達', '医療テックニュース'),
    ('住友重機械工業、BNCT治療で再発髄膜腫の適応承認を取得', 'ニュースメディアVOIX'),
    ('危機に直面する兵庫県立病院 クラウドファンディング実施も見えない“解決策”', 'ktv.jp'),
    ('［お知らせ］「放射線治療」特集号の原稿募集について 第83巻第11号', '日本放射線技術学会'),
])
def test_related_news_is_kept(headline, source):
    assert u.is_news_item(item(headline, source))


@pytest.mark.parametrize('headline', [
    'https://forms.gle/KsBXcPw9Qfancdot9',
    '登録期限： 11 月 20 日（金） 正午 - 日本放射線技術学会',
    '第2回理事会議事録(2026)を公開しました',
    '2025年度総会議事録を公開しました',
    '総会審議結果のご報告',
    '2025年度事業報告書',
])
def test_admin_reports_and_url_titles_are_excluded(headline):
    assert not u.is_news_item(item(headline, '日本CT技術学会'))


def mhlw(title):
    return {'title': title, 'url': 'https://www.mhlw.go.jp/stf/newpage_00001.html', 'source': '厚生労働省', 'description': ''}


@pytest.mark.parametrize('title', [
    '不正アクセスによる情報漏えい等の事案を踏まえたセキュリティ対策の徹底について（注意喚起）',
    '令和10年度診療報酬改定に係る答申について',
    '医療情報システムの安全管理に関するガイドライン 第7.0版',
])
def test_mhlw_items_for_the_department_are_kept(title):
    assert u.relevant(mhlw(title))


@pytest.mark.parametrize('title', [
    '「年金の日」・「ねんきん月間」のお知らせ',
    '歯科衛生士の業務のあり方等に関する検討会　中間報告',
    '中央最低賃金審議会 (目安に関する小委員会)',
])
def test_unrelated_mhlw_items_are_dropped(title):
    assert not u.relevant(mhlw(title))


@pytest.mark.parametrize('headline', [
    '[AOSR] Education & Training',
    '2026年度 第2回代議員会開催（JDDW開催時）について',
    '2026/10/19 お知らせ (入札広告) 「日本診療放射線技師会誌ＪＡＲＴ」の編集・印刷',
    '少女にわいせつ行為した疑いで逮捕され不起訴 公立病院の29歳放射線技師を停職処分',
])
def test_menu_admin_and_crime_items_are_excluded(headline):
    assert not u.is_news_item(item(headline, '日本医学放射線学会'))


@pytest.mark.parametrize('headline', ['JRC 2027 Call for Abstracts', 'RSNA 2026 速報'])
def test_english_titles_with_content_are_kept(headline):
    assert u.is_news_item(item(headline, '日本医学放射線学会'))


@pytest.mark.parametrize('headline, expected', [
    ('不正アクセスによる情報漏えい等の事案を踏まえたセキュリティ対策の徹底について（注意喚起）', '安全管理'),
    ('第66回総会 演題募集開始のお知らせ', '学術'),
    ('電子版JART会誌（電子ブックシステム）のご案内', '学術'),
    ('駒沢大学とシーメンス、画像診断の人材育成拠点', '教育'),
])
def test_category_fixes(headline, expected):
    assert u.category(item(headline)) == expected
