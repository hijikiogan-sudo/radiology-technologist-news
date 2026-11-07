"""ノイズ記事の除外とカテゴリ分類のテスト (python -m pytest tests/test_news_filters.py)。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402


def item(headline, source=''):
    return {'headline': headline, 'summary': headline, 'source': source, 'url': 'https://news.google.com/x'}


@pytest.mark.parametrize('headline, source', [
    ('フォトンカウンティングCT市場、2035年に89億4,000万米ドルへ拡大予測｜SNS Insider調査', 'ニコニコニュース'),
    ('核医学機器市場の最新動向：力強い成長と競争、2026年から2033年にかけて予測CAGR', 'pando.life'),
    ('グローバル核医学ソフトウェア市場におけるトップ10企業', 'Spherical Insights'),
    ('PET核医学イメージングメーカーランキング', 'pando.life'),
    ('Untitled - 日本診療放射線技師会', '日本診療放射線技師会'),
])
def test_noise_is_excluded(headline, source):
    assert not u.is_news_item(item(headline, source))


@pytest.mark.parametrize('headline, source', [
    ('ガストログラフィン®経口・注腸用「限定出荷」継続のお知らせ', '日本診療放射線技師会'),
    ('EIZO、医用画像表示モニター2機種を発売へ 24.1型と27型', 'Dellows News'),
    ('病院のCT・MRI画像を受診者のスマートフォンへ。検査画像転送サービス「スマぞう」販売開始', 'news.infoseek.co.jp'),
])
def test_real_news_is_kept(headline, source):
    assert u.is_news_item(item(headline, source))


@pytest.mark.parametrize('headline, expected', [
    ('局所進行直腸癌の術前療法で短期放射線療法＋抗PD-1抗体が有意に延長', '放射線治療'),
    ('計画用 CT は放射線治療の出発点', '放射線治療'),
    ('試薬不足のためPET/CT装置が稼働していない', '核医学'),
    ('α線放出核種Ac225を用いる放射線リガンド療法薬', '核医学'),
    ('【画像】レントゲン画像に写ったハート形の物体', '一般撮影'),
    ('告示研修（実技研修）大阪府2026/12/13', '職能'),
    ('ガストログラフィン®経口・注腸用「限定出荷」継続のお知らせ', '安全管理'),
    ('fcuro、キヤノンメディカルと提携 救急CT読影AIなどの認知を拡大', 'CT'),
    ('国産2nm半導体を医療AIに活用へ', 'AI'),
])
def test_category(headline, expected):
    assert u.category(item(headline)) == expected


@pytest.mark.parametrize('headline', [
    'Mayo Clinic director comments on project',   # 「director」「project」の ct は CT ではない
    'Siemens Healthineers Detector Update',       # 「Detector」の ct
    'Primary care trial',                          # 「Primary」「trial」の ri / ai
])
def test_ascii_terms_match_whole_words_only(headline):
    assert u.category(item(headline)) == 'その他'


def test_source_name_is_not_used_for_category():
    # 配信元「日本放射線技術学会」の「学会」で学術に入れない
    assert u.category(item('動画視聴システム更新に伴う一時休止のお知らせ', '日本放射線技術学会')) == 'その他'


# --- 海外の地方ニュース・配信元名・医療安全情報 ---------------------

@pytest.mark.parametrize('source', ['Vietnam.vn', 'vietnam.vn', 'Laodong.vn'])
def test_foreign_local_news_is_excluded(source):
    assert not u.is_news_item(item('カントー腫瘍病院の放射線治療装置が依然として故障している', source))


def test_foreign_news_in_japanese_media_is_kept():
    assert u.is_news_item(item('Mayo Clinicの膵がんAI、放射線科医が見逃すリスクシグナルを検出', 'remio'))


@pytest.mark.parametrize('raw, expected', [
    ('公益社団法人 日本放射線技術学会', '日本放射線技術学会'),
    ('日本放射線技術学会（JSRT）', '日本放射線技術学会'),
    ('jsrt.or.jp', '日本放射線技術学会'),
    ('JART', '日本診療放射線技師会'),
    ('日本診療放射線技師会（JART）', '日本診療放射線技師会'),
    ('公益社団法人日本医学放射線学会', '日本医学放射線学会'),
    ('クラウドファンディング - READYFOR', 'READYFOR'),
    ('Yahoo!ニュース', 'Yahoo!ニュース'),
])
def test_source_names_are_unified(raw, expected):
    assert u.normalize_source(raw) == expected


@pytest.mark.parametrize('headline', [
    'MRI検査時の体内植込み機器等の確認忘れで再度の注意喚起─医療安全情報',
    '患者の体内に植込まれた医療機器等を十分に確認せずにMRI検査を実施してしまう医療事故が依然として散発—医療機能評価機構',
    '画像診断管理加算2「175点→166点」は本当に減収なのか？',
])
def test_safety_and_fee_items_are_high(headline):
    x = {'headline': headline, 'summary': headline, 'source': 'GemMed', 'url': 'https://news.google.com/x'}
    assert u.importance(x, False) == '高'
    x['importance'] = '高'
    assert u.technologist_note(x) != ''


# --- 読み物系(体験談・釣り見出し・闘病記・事件報道)の除外 ---------------

@pytest.mark.parametrize('headline, source', [
    ('MRI検査中に地震が…！緊急時に役立つまさかの機能に「勉強になった」', 'TRILL'),
    ('MRI検査前…患者のネイルに「めっちゃ綺麗ですね」→感心するも…告げられた事実に技師「では延期ですね」', 'ライブドアニュース'),
    ('同業者からの共感続々。放射線技師のお仕事あるあるを描く“ギャル技師ちゃん”誕生のきっかけとは？【著者インタビュー】', 'ライブドアニュース'),
    ('【闘病】“かなり初期”の『乳がん』でも抗がん剤と放射線25回', 'Yahoo!ニュース'),
    ('遺族が悲痛な陳述 放射線技師を夢見た20歳の女子大学生を刺殺', 'TBS NEWS DIG'),
])
def test_light_reads_are_excluded(headline, source):
    assert not u.is_news_item(item(headline, source))


@pytest.mark.parametrize('headline', [
    '画像診断管理加算2「175点→166点」は本当に減収なのか？',      # 「→」でも点数の話は残す
    'MRI検査時の体内植込み機器等の確認忘れで再度の注意喚起─医療安全情報',
])
def test_practical_items_with_similar_wording_are_kept(headline):
    assert u.is_news_item(item(headline, 'mbp-japan.com'))


# --- 検診 ---------------------------------------------------------

@pytest.mark.parametrize('headline', [
    '胃がん検診の受診率向上へ 胃部X線検査の精度管理を強化',
    '胃透視でのバリウム誤嚥を防ぐポイント',
    '人間ドックで胸部CTを選べる自治体が増加',          # CTより検診を優先
    'ユカリア、健診サービスで「からだ健康度AI解析」開始 胸部CTで筋肉量を可視化',
])
def test_screening_category(headline):
    assert u.category(item(headline)) == '検診'


def test_fluoroscopy_news_is_relevant():
    assert u.relevant({'headline': '胃透視の撮影手順を標準化', 'summary': '', 'source': '日本消化器がん検診学会', 'url': 'https://news.google.com/x'})


# --- 血管撮影・超音波 ------------------------------------------------

@pytest.mark.parametrize('headline, expected', [
    ('血管撮影室の被ばく低減に向けたIVR医との連携', '安全管理'),       # 被ばくは安全管理を優先(従来どおり)
    ('最新のバイプレーン血管撮影装置を導入 脳血管内治療に対応', '血管撮影'),
    ('IVRナースと技師のチーム医療', '血管撮影'),
    ('心臓カテーテル検査室をリニューアル', '血管撮影'),
    ('超音波スクリーニング研修講演会2026東京のご案内', '超音波'),
    ('腹部エコー検査の描出のコツ', '超音波'),
    ('マンモグラフィーと超音波検査の併用は慎重にすべき？乳がん検診', 'マンモグラフィ'),   # マンモを優先
    ('妊婦健診のエコー検査で胎児が小さめと言われたら', '超音波'),
])
def test_angio_and_ultrasound_category(headline, expected):
    assert u.category(item(headline)) == expected


def test_politician_pages_are_excluded():
    assert not u.is_news_item(item('大阪市の胃がん検診｜50歳以上の対象・料金・予約', '選挙ドットコム'))


# --- マンモグラフィ --------------------------------------------------

@pytest.mark.parametrize('headline', [
    '対策型乳がん検診にトモシンセシス導入を検討',
    '「痛くない乳がん検診」の効果は？',
    '検診マンモグラフィ撮影認定技師の更新講習',
    '乳房撮影時のポジショニングの工夫',
])
def test_mammography_category(headline):
    assert u.category(item(headline)) == 'マンモグラフィ'


def test_gastric_screening_stays_in_screening():
    assert u.category(item('胃がん検診の胃部X線検査で使うバリウムの改良')) == '検診'


def test_market_research_without_the_word_market_is_excluded():
    assert not u.is_news_item(item('デジタルサブトラクションアンギオグラフィーシステムマーケットリサーチ：調査方法＋業界分析＋売上規模、年平均成長率（CAGR）', 'pando.co'))
