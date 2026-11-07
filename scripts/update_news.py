import json, os, re, smtplib, unicodedata, xml.etree.ElementTree as ET
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
import unicodedata
from urllib.parse import quote, urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

ROOT = Path(__file__).resolve().parents[1]
NEWS_JSON = ROOT / 'news.json'
ARCHIVE_DIR = ROOT / 'archive'      # 200件からあふれた記事を月ごとに保存
MAX_RECENT = 200
RETENTION_DAYS = 365                # これより古い記事と毎日のまとめは消す
META_JSON = ROOT / 'news_meta.json'
KAGAWA_JSON = ROOT / 'kagawa.json'  # 香川県技師会のお知らせ(すべて)と求人案内。画面では別枠に出す
SEMINARS_JSON = ROOT / 'seminars.json'  # 技師会の研修・講習会の日程  # 最終更新時刻と新着件数(画面の右上に表示)
HTML_DIR = ROOT / 'daily_html'


def feed_date(item):
    """Date used for the daily edition; keep the original publication date intact."""
    return item.get('featured_date') or item.get('date')


def build_daily_html(items, date_str):
    special = [x for x in items if feed_date(x) == date_str and x.get('track') != 'general']
    general = [x for x in items if feed_date(x) == date_str and x.get('track') == 'general']

    def esc(s):
        return (str(s or '').replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace(chr(34),'&quot;'))

    def card(x):
        return ('<article class="card"><div class="meta"><span class="tag">' + esc(x.get('category')) + '</span><span class="imp">重要度 ' + esc(x.get('importance')) + '</span><span class="date">' + esc(x.get('date')) + '</span></div><h2>' + esc(x.get('headline')) + '</h2>' + ('<p>' + esc(x.get('summary')) + '</p>' if x.get('summary') else '') + ('<div class="why"><b>ポイント：</b>' + esc(x.get('why')) + '</div>' if x.get('why') else '') + '<a href="' + esc(x.get('url')) + '" target="_blank" rel="noopener">' + esc(x.get('source') or '情報源') + ' ↗</a></article>')

    def section(title, badge, data, empty):
        body = ''.join(card(x) for x in data) or '<div class="empty">' + empty + '</div>'
        return '<section><div class="section-title"><h2>' + title + '</h2><span class="badge">' + badge + '</span></div>' + body + '</section>'

    return ('<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>放射線技師ニュース ' + date_str + '</title><style>body{margin:0;background:#f3f6f9;color:#17212b;font-family:-apple-system,BlinkMacSystemFont,"Noto Sans JP","Yu Gothic",sans-serif}main{max-width:900px;margin:auto;padding:16px}header,.card{background:#fff;border:1px solid #dfe5eb;border-radius:16px;padding:18px;margin:12px 0}h1{font-size:25px;margin:0 0 8px}h2{font-size:18px;line-height:1.5;margin:10px 0}.meta{display:flex;gap:7px;flex-wrap:wrap;font-size:12px;color:#687585}.tag,.imp,.badge{border:1px solid #d3dbe4;border-radius:999px;padding:4px 9px}p{font-size:14px;line-height:1.8}.why{background:#f7f9fb;border-radius:10px;padding:11px;font-size:13px;line-height:1.7}.section-title{display:flex;justify-content:space-between;align-items:center;margin-top:26px}.empty{background:#fff;border-radius:12px;padding:16px;color:#687585}</style></head><body><main>'
            '<header><h1>🔥 今日の放射線部門ニュース</h1><div>' + date_str + '</div></header>'
            + section('専門ニュース','放射線・医療実務',special,'本日の専門ニュースはありません。')
            + section('一般ニュース','一般メディア・周辺動向',general,'本日の一般ニュースはありません。')
            + '</main></body></html>')
JST = timezone(timedelta(hours=9))

QUERIES = [
    '"診療放射線技師" OR "放射線技師"',
    '"放射線部" CT MRI FPD',
    '"放射線" 被ばく 線量管理 安全管理',
    '核医学 SPECT PET "放射線技師"',
    '放射線 AI 画像診断 読影支援',
    '診療報酬 放射線 画像診断 補助金',
    'CT MRI 医療 画像診断 放射線',
    '医用画像 AI CT MRI 病院',
    '放射線 医療機器 CT MRI 最新',
    '放射線治療 医療機器 最新',
    'マンモグラフィ 医療機器 放射線',
    'FPD X線撮影 医療 最新',
    '胃がん検診 X線 OR 胃透視 OR バリウム',
    '胃部X線検査 OR 胃X線検診 診療放射線技師',
    'がん検診 マンモグラフィ OR 胸部X線 精度管理',
    '人間ドック OR 健診 放射線技師 OR 画像',
    '血管撮影 OR IVR OR アンギオ 放射線技師 OR 被ばく',
    '超音波検査 OR エコー検査 診療放射線技師 OR 検査技師',
    'site:jart.jp "診療放射線技師"',
    'site:jsrt.or.jp "診療放射線技師" OR "放射線技術"',
    'site:radiology.jp "診療放射線技師" OR "放射線"',
    'site:jsnm.org 核医学 "放射線技師"',
    'site:jastro.or.jp 放射線治療 "放射線技師"',
    'site:jsmp.org 医学物理 放射線治療 OR 線量管理',
    'site:mhlw.go.jp "診療放射線技師" 放射線',
    'site:pmda.go.jp 放射線 CT MRI 医療機器',
    'site:nra.go.jp 医療 放射線 安全',
]

OFFICIAL = (
    'jart.jp',
    'jsrt.or.jp',
    'jrs.or.jp',
    'radiology.jp',
    'jsnm.org',
    'jastro.or.jp',
    'jsmp.org',
    'mhlw.go.jp',
    'nra.go.jp',
    'pmda.go.jp',
    'mext.go.jp',
    'med-safe.jp',
    'jcqhc.or.jp',
    'jsgcs.or.jp',
    'qabcs.or.jp',
    'jastro.or.jp', 'jsmp.org', 'jsmrm.jp', 'jsir.or.jp', 'jsum.or.jp', 'jsnmt.org', 'jsct-tech.org',
    'kagawart.jp', 'jsrt-chushi.jp', 'info.pmda.go.jp',
    'oart.jp', 'ehimeart.com', 'tart.web5.jp', 'kochi-art.org',
    'jabts.jp', 'jss.org', 'ct-ninteikikou.jp', 'jbcs.gr.jp', 'mrifan.net', 'dcis.kenkyuukai.jp',
    'jabcs.jp', 'jscts.org', 'radiation-therapy.jp', 'jert.info',
)

CATEGORIES = (
    '制度',
    '職能',
    '学術',
    'AI',
    'CT',
    'MRI',
    '一般撮影',
    '安全管理',
    '核医学',
    '放射線治療',
    '教育',
    '診療報酬・補助金',
    '検診',
    'マンモグラフィ',
    '血管撮影',
    '超音波',
    'その他'
)

# ChatGPTの日次編集版で確認した「部門で直ちに周知・検討したい」公式情報。
# RSSの短いタイトルを、ホームページでも実務に使える要約と重要度で表示する。
# featured_date は掲載日ではなく、日次ニュースとして選定した日を表す。
CURATED_SPECIALIST = (
    (
        '第66回放射線治療セミナー',
        {
            'category': '放射線治療',
            'importance': '高',
            'summary': 'IGRTを支える教育体制、運用の基礎、臨床上の注意点や工夫を扱うWebセミナー。申込は10月1日正午～11月26日正午。',
            'why': 'IGRTの運用の基礎から臨床上の注意点まで学べます。治療に関わるなら申込期間を確認しておきましょう。',
            'source': '日本放射線技術学会（JSRT）',
            'featured_date': '2026-09-22',
        },
    ),
    (
        '実地で学ぶMRI安全管理セミナー',
        {
            'category': 'MRI',
            'importance': '高',
            'summary': 'MRI安全管理を実地で学ぶセミナーの案内。',
            'why': 'MRI室の安全管理を実地で学べる内容です。MRIに関わるなら確認しておきましょう。',
            'source': '日本放射線技術学会（JSRT）',
            'featured_date': '2026-09-22',
        },
    ),
    (
        '診断X線領域の線量測定基礎Webセミナー（血管撮影領域CBCT編）',
        {
            'category': '安全管理',
            'importance': '高',
            'summary': '血管撮影領域CBCTの線量測定を学ぶWebセミナー。',
            'why': '血管撮影・IVRの患者線量の評価と最適化を基礎から学べます。',
            'source': '日本放射線技術学会（JSRT）',
            'featured_date': '2026-09-22',
        },
    ),
    (
        '医療放射線安全管理講習会（WEB）',
        {
            'category': '安全管理',
            'importance': '高',
            'summary': '立入検査、タスク・シフト、グリーンラジオロジー、IVR、核医学治療などを扱う講習会。',
            'why': '立入検査への対応、医療放射線の安全管理、タスク・シフトの要点をまとめて学べます。',
            'source': '日本診療放射線技師会（JART）',
            'featured_date': '2026-09-22',
        },
    ),
)

DIRECT_TERMS = (
    '診療放射線技師',
    '放射線技師',
    '放射線部',
    '放射線科',
    '診療用放射線',
)

STRONG_MODALITY_TERMS = (
    '胃透視', '胃X線', '胃部X線', 'バリウム', '上部消化管造影', '胃がん検診', '乳がん検診', '肺がん検診',
    '血管撮影', 'IVR', 'アンギオ', '超音波検査', 'エコー検査',
    'CT',
    'MRI',
    'FPD',
    '一般撮影',
    'マンモグラフィ',
    '核医学',
    'SPECT',
    'PET',
    '放射線治療',
    '被ばく',
    '線量管理',
    '画像診断AI',
    '画像診断支援',
    '読影支援',
    'STAT',
    'X線撮影',
    'タスクシフト',
    'タスクシェア',
    '放射線安全',
    '医療被ばく',
    '線量最適化',
    '画像診断',
)

BROAD_MODALITY_TERMS = (
    '画像診断',
    '読影',
    '医用画像',
    '放射線',
    '医療画像',
)

BAD_TERMS = (
    '漫画',
    'マンガ',
    '芸能',
    '俳優',
    '女優',
    'アイドル',
    'タレント',
    'グラビア',
    '写真集',
    '求人',
    '転職',
    '保険',
)

NOISE_TITLE_TERMS = (
    '受付期間：',
    '開催日：',
    '会誌・投稿',
    '活動紹介',
    '技師会概要',
    '市場調査',
    '市場規模',
    '市場動向',
    '市場レポート',
    '画像ギャラリー',
    'フォトギャラリー',
)

NON_RADIOLOGY_TERMS = (
    'ポケモン', 'ポケカ', '資産形成', '投資', '株式投資', '副業',
    '競馬', '競輪', '競艇', 'ギャンブル', '仮想通貨', '暗号資産'
)

MARKET_REPORT_DOMAINS = (
    'newscast.jp', 'atpress.ne.jp'
)

SOURCE_STATUS = {}  # 取得元ごとの結果(news_meta.json に記録して、取れなくなったら気付けるように)


_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; radiology-technologist-news; +https://hijikiogan-sudo.github.io/radiology-technologist-news/)',
    'Accept': 'text/html,application/xhtml+xml,application/xml,application/rss+xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ja,en;q=0.5',
}


def fetch_bytes(url, timeout=60):
    with urlopen(Request(url, headers=_HEADERS), timeout=timeout) as r:
        return r.read(), r.headers.get_content_charset()


def fetch(url, timeout=60):
    """ページの文字コード(ヘッダーか meta の指定、なければUTF-8)で読む。PMDAの回収一覧はEUC-JP。"""
    return decode_page(*fetch_bytes(url, timeout))


def decode_page(raw, cs):
    if not cs:
        m = re.search(rb'<meta[^>]+charset=["\']?([A-Za-z0-9_\-]+)', raw[:3000], re.I) or re.search(rb'encoding=["\']([A-Za-z0-9_\-]+)', raw[:200])
        cs = m.group(1).decode() if m else 'utf-8'
        if not m:   # 指定のない古いページ(高知県技師会など)は Shift_JIS のことがある
            try:
                raw.decode('utf-8')
            except UnicodeDecodeError:
                cs = 'cp932'
    try:
        return raw.decode(cs, 'ignore')
    except LookupError:
        return raw.decode('utf-8', 'ignore')



def fetch_with_cookies(url, timeout=60):
    """m3.com学会研究会(kenkyuukai.jp)はクッキーがないと転送を繰り返すので、クッキーを保持して読む。"""
    opener = build_opener(HTTPCookieProcessor())
    with opener.open(Request(url, headers=_HEADERS), timeout=timeout) as r:
        return decode_page(r.read(), r.headers.get_content_charset())


def clean_html(s):
    return ' '.join(
        unescape(re.sub(r'<[^>]+>', ' ', s or '')).split()
    )


def rss(q):
    root = ET.fromstring(
        fetch(
            'https://news.google.com/rss/search?q='
            + quote(q + ' when:2d')
            + '&hl=ja&gl=JP&ceid=JP:ja'
        )
    )

    out = []

    for it in root.findall('./channel/item'):
        try:
            dt = parsedate_to_datetime(
                it.findtext('pubDate', '')
            ).astimezone(JST)
        except Exception:
            continue

        title = unescape(it.findtext('title', ''))
        link = it.findtext('link', '')
        desc = clean_html(
            it.findtext('description', '')
        )[:700]

        se = it.find('source')
        src = se.text if se is not None else ''

        if title and link:
            out.append({
                'title': title,
                'url': link,
                'description': desc,
                'source': src,
                'published': dt.isoformat(),
            })

    return out


def norm(s):
    return re.sub(
        r'[^0-9a-zぁ-んァ-ヶ一-龠]',
        '',
        str(s or '').lower()
    )


def dom(url):
    m = re.search(r'https?://([^/]+)', url or '')
    return (
        m.group(1).lower().replace('www.', '')
        if m else ''
    )


def is_official(url):
    d = dom(url)
    return any(
        d == z or d.endswith('.' + z)
        for z in OFFICIAL
    )


def basis(x, k):
    """判定に使う値。元のページから取った要約(summary_tried 付き)は表示専用で、判定には使わない
    (背景説明の語で分類・重要度・関連判定が変わってしまうため)。"""
    if k == 'summary' and x.get('summary_tried'):
        return ''
    return x.get(k, '')


def article_text(x):
    return ' '.join(
        str(basis(x, k) or '')
        for k in (
            'title',
            'headline',
            'description',
            'summary',
            'source'
        )
    ).lower()


def relevant(x):
    # 医療安全情報は取得時に放射線関連だけを選んでいるので、そのまま残す
    if 'recallno=' in x.get('url', ''):   # PMDAの医療機器回収は放射線関連の機器だけ
        return recall_is_imaging(x.get('headline') or x.get('title') or '')
    if dom(x.get('url', '')) in SAFETY_INFO_DOMAINS:
        return True
    # 医薬品の供給状況は、取得時に造影剤・放射性医薬品だけを選んでいる
    if x.get('url', '').startswith(SUPPLY_PAGE + '#'):
        return True
    # 放射線系学会のサイトから直接取った記事は、学会の性質上すべて対象にする
    if any(dom(x.get('url', '')) == d or dom(x.get('url', '')).endswith('.' + d) for d in SOCIETY_DOMAINS):
        return True

    if dom(x.get('url', '')) == 'mhlw.go.jp' and MHLW_EXTRA_PATTERN.search(x.get('title') or x.get('headline') or ''):
        return True

    text = article_text(x)

    if any(k.lower() in text for k in BAD_TERMS):
        return False

    if any(k.lower() in text for k in NON_RADIOLOGY_TERMS):
        return False

    direct = any(
        k.lower() in text
        for k in DIRECT_TERMS
    )

    strong = any(
        k.lower() in text
        for k in STRONG_MODALITY_TERMS
    )

    broad = any(
        k.lower() in text
        for k in BROAD_MODALITY_TERMS
    )

    if is_official(x.get('url', '')):
        return direct or strong or broad

    return (
        direct
        or strong
        or (
            broad
            and any(
                k in text
                for k in (
                    '医療',
                    '病院',
                    '患者',
                    '診断',
                    '画像',
                    '放射線'
                )
            )
        )
    )


def is_news_item(x):
    url = x.get('url', '')
    title = (
        x.get('title')
        or x.get('headline')
        or ''
    ).strip()

    if '/activity/lifelong-study' in url:
        return False

    # 技師会サイトの求人の掲載案内
    if re.match(r'^求人(情報)?\s*(を)?掲載|^求人情報です', title):
        return False

    # 県技師会の会報の掲載案内(中身は個別のお知らせとして別に載る)
    if re.search(r'(岡放技ニュース|技師会だより).{0,12}\d+月号', title):
        return False

    if re.search(r'^画像\s*\d+\s*/\s*\d+', title):
        return False

    if title in (
        '日本診療放射線技師会誌JART',
        'みんなに知ってもらいたい診療放射線技師のこと',
        '日本診療放射線技師会について',
        '都道府県診療放射線技師会・放射線技師会',
        '活動紹介',
        '会誌・投稿',
        '一般向け情報',
        '技師会概要',
        '医療被ばく個別相談センター',
        '放射線被ばく相談員',
    ):
        return False

    # 技師会サイトのメニュー(「〇〇の情報をご紹介しています。 詳細を見る」)
    if title.endswith('詳細を見る'):
        return False

    if any(
        k in title
        for k in NOISE_TITLE_TERMS
    ):
        return False

    # 見出しが取れなかったページ(「Untitled - 日本診療放射線技師会」など)
    if re.match(r'^\s*(untitled|no title|無題)\s*(-|$)', title, flags=re.I):
        return False

    # リンク先のURLや、本文の一部(「登録期限： 11 月 20 日」など)がそのまま見出しになったもの
    if re.match(r'^\s*(https?://|(登録|申込|応募|提出)(期限|締切)\s*[：:])', title):
        return False

    # 学会の運営報告(議事録・事業報告など)は研修・制度の情報ではない
    if ADMIN_REPORT_PATTERN.search(title) or MENU_TITLE_PATTERN.match(title):
        return False

    if is_market_report(x):
        return False

    if is_foreign_local_news(x):
        return False

    if is_light_read(x):
        return False

    if is_off_topic(x):
        return False

    return True


ADMIN_REPORT_PATTERN = re.compile(r'(理事会|総会|社員総会)議事録|総会審議結果|事業報告書|決算報告|入札広告|代議員会')
# 学会サイトのメニュー名(「[AOSR] Education & Training」のような英語だけの短い見出し)
MENU_TITLE_PATTERN = re.compile(r'^\s*(\[[^\]]+\]\s*)?[A-Za-z][A-Za-z &/-]{0,35}$')


# 技師の業務に関係しない記事(寄付の募集・個人ブログや専門家コラム・動物医療・漫画・サイトの保守告知など)
OFF_TOPIC_SOURCES = ('readyfor', 'fundinno', 'campfire', '株探', 'jijico', '公明党', 'tonomatsuri')
OFF_TOPIC_PATTERN = re.compile(
    r'【クラファン】|ご寄付を|ご支援を'   # 募集ページそのもの(資金難を報じる記事は残す)
    r'|[:：]\s*ブログ\s*[:：]|のブログ'
    r'|^【画像】'                          # 同じ記事の画像ページ(本文の記事は別に取り込まれる)
    r'|ペット|動物(総合)?病院|動物医療|獣医'
    r'|リレー\s*・?\s*フォー\s*・?\s*ライフ'   # がん患者支援のチャリティー行事
    r'|ラジエーションハウス|\d+巻は.*発売'
    r'|^\s*[\[［【]?(システム|サーバー?|サイト)?メンテナンス(情報|のお知らせ)?'
    r'|市場\s*[：:]'                        # 「日本AI医療画像処理システム市場：…」型の市場レポート
    r'|就職評価|偏差値'
)


def is_off_topic(x):
    source = str(x.get('source') or '').lower()
    if any(s in source for s in OFF_TOPIC_SOURCES):
        return True
    title = str(x.get('title') or x.get('headline') or '')
    return bool(OFF_TOPIC_PATTERN.search(title))


# 業務に役立たない読み物(漫画風の体験談・釣り見出し・闘病記・事件報道)
LIGHT_READ_SOURCES = ('trill', '選挙ドットコム')
LIGHT_READ_PATTERN = re.compile(
    r'→.*…|….*→'                     # 「…患者のネイルに→感心するも…」型の漫画記事
    r'|顔面蒼白|まさかの|即答した正体|あるあるを描く|著者インタビュー'
    r'|【闘病】|闘病記'
    r'|殺意|殺害|刺殺|遺体|わいせつ|盗撮|児童買春'
)


def is_light_read(x):
    source = str(x.get('source') or '').lower()
    if any(s in source for s in LIGHT_READ_SOURCES):
        return True
    title = str(x.get('title') or x.get('headline') or '')
    return bool(LIGHT_READ_PATTERN.search(title))


# 海外の地方病院ニュースを機械翻訳した配信元(装置の故障・導入など現地の話題が大半)
FOREIGN_LOCAL_SOURCES = ('vietnam.vn', 'laodong.vn', 'vnexpress', 'baomoi', 'tuoitre', 'thanhnien')


def is_foreign_local_news(x):
    source = str(x.get('source') or '').lower()
    url = str(x.get('url') or '').lower()
    return any(s in source or s in url for s in FOREIGN_LOCAL_SOURCES)


# 同じ団体の配信元名の表記ゆれをそろえる(表示とフィルタの一貫性のため)
SOURCE_ALIASES = (
    (r'^(公益社団法人\s*)?日本放射線技術学会(（JSRT）|\(JSRT\))?$|^jsrt(\.or\.jp)?$', '日本放射線技術学会'),
    (r'^(公益社団法人\s*)?日本診療放射線技師会(（JART）|\(JART\))?$|^jart(\.jp)?$', '日本診療放射線技師会'),
    (r'^(公益社団法人\s*)?日本医学放射線学会(（JRS）|\(JRS\))?$|^radiology\.jp$', '日本医学放射線学会'),
    (r'readyfor', 'READYFOR'),
)


def normalize_sources(item):
    item['source'] = normalize_source(item.get('source'))
    for a in item.get('also') or []:
        a['source'] = normalize_source(a.get('source'))
    return item


def normalize_source(source):
    s = str(source or '').strip()
    for pattern, name in SOURCE_ALIASES:
        if re.search(pattern, s, flags=re.I):
            return name
    return s


# 市場調査会社の宣伝記事(「〇〇市場、2035年に89億米ドルへ」など)は実務に役立たないので除外する
MARKET_REPORT_SOURCES = (
    'pando.life', 'spherical insights', 'indexbox', 'sns insider',
    'global information', 'gii', 'researchandmarkets', 'report ocean',
    'kenresearch', 'market research',
)


def is_market_report(x):
    title = str(x.get('title') or x.get('headline') or '')
    source = str(x.get('source') or '').lower()
    if any(s in source for s in MARKET_REPORT_SOURCES):
        return True
    if re.search(r'マーケットリサーチ|マーケット調査|市場調査レポート|CAGR|年平均成長率', title, flags=re.I):
        return True
    if '市場' not in title:
        return False
    return bool(re.search(
        r'CAGR|年平均成長率|億\s*米?ドル|万\s*米?ドル|市場規模|市場予測|世界市場|市場分析|市場の(最新)?動向|成長見通し'
        r'|\d{4}年\s*(から|～|〜|-)\s*\d{4}年|トップ\s*\d+\s*企業|メーカーランキング',
        title, flags=re.I,
    ))


def parse_nearby_date(html, pos):
    dates = re.findall(
        r'(20\d{2})[/.年](\d{1,2})[/.月](\d{1,2})',
        clean_html(html[max(0, pos - 1800):pos])
    )

    if dates:
        y, m, d = dates[-1]
        return (
            f'{y}-{int(m):02d}-{int(d):02d}'
            'T00:00:00+09:00'
        )

    return None


def direct_jart():
    out = []

    try:
        html = fetch('https://www.jart.jp/')

        for m in re.finditer(
            r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>'
            r'\s*(?P<title>.*?)\s*</a>',
            html,
            re.I | re.S
        ):
            title = clean_html(m.group('title'))
            href = urljoin(
                'https://www.jart.jp/',
                m.group('href')
            )
            date = parse_nearby_date(
                html,
                m.start()
            )

            test_item = {
                'title': title,
                'source': 'JART',
                'url': href,
            }

            if (
                title
                and date
                and '/news/info/' in href.lower()
                and relevant(test_item)
                and is_news_item(test_item)
            ):
                out.append({
                    'title': title,
                    'url': href,
                    'description': title,
                    'source': 'JART',
                    'published': date,
                })

    except Exception as e:
        print('JART direct error:', e)

    return out


# --------------------------------------------------
# 医療安全情報(日本医療機能評価機構・PMDA)を直接取得する
# --------------------------------------------------
SAFETY_INFO_DOMAINS = ('med-safe.jp', 'pmda.go.jp', 'info.pmda.go.jp')
MED_SAFE_LIST = 'https://www.med-safe.jp/contents/info/'
PMDA_SAFETY_LIST = 'https://www.pmda.go.jp/safety/info-services/medical-safety-info/0001.html'
# 放射線部門に関係しそうな号だけを取り込む
SAFETY_RADIOLOGY_TERMS = (
    'MRI', 'CT', '造影', '放射線', '画像', 'X線', 'エックス線', 'レントゲン', '撮影', '透視', '血管撮影',
    '核医学', 'RI', '被ばく', '植込', '植え込', 'ペースメーカ', '検査', '読影', '金属',
)


def _is_radiology_safety(title):
    return any(_term_in(k, title.lower()) for k in SAFETY_RADIOLOGY_TERMS)


def parse_med_safe(html, limit=3):
    """医療機能評価機構の一覧から、新しい号(番号の大きい順)の放射線関連を返す。"""
    found = {}
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']*med-safe_(?P<no>\d+)\.pdf)["\'][^>]*>(?P<text>.*?)</a>', html, re.I | re.S):
        text = clean_html(m.group('text'))
        no = int(m.group('no'))
        # 「医療機器等・検査 No.239：患者に植込まれた医療機器の確認不足（第2報）」→ 題名部分
        title = re.sub(r'^.*?No\.?\s*\d+\s*[:：]\s*', '', text).strip() or text
        if not title or no in found or 'まとめ' in text:
            continue
        found[no] = {'no': no, 'title': title, 'text': text, 'url': urljoin(MED_SAFE_LIST, m.group('href'))}
    items = [found[k] for k in sorted(found, reverse=True)]
    # 分類名(「医療機器等・検査」など)も含めて判定する
    return [x for x in items if _is_radiology_safety(x['text'])][:limit] if items else []


def parse_pmda_safety(html, limit=3):
    """PMDA医療安全情報の表から、発行年月つきで放射線関連を返す(新しい順)。"""
    out = []
    for row in re.split(r'<tr[\s>]', html, flags=re.I)[1:]:
        no = re.search(r'No\.?\s*(\d+)|>\s*(\d{1,3})\s*<', row)
        ym = re.search(r'(20\d{2})年\s*(\d{1,2})月', row)
        link = re.search(r'<a[^>]+href=["\'](?P<href>[^"\']+\.pdf)["\'][^>]*>(?P<text>.*?)</a>', row, re.I | re.S)
        if not (ym and link):
            continue
        title = clean_html(link.group('text'))
        if not title or title.startswith('[') or '掲示用' in title:
            continue
        out.append({
            'no': int(next(g for g in no.groups() if g)) if no else 0,
            'title': title,
            'url': urljoin(PMDA_SAFETY_LIST, link.group('href')),
            'published': f'{int(ym.group(1)):04d}-{int(ym.group(2)):02d}-01',
        })
    out.sort(key=lambda x: (x['published'], x['no']), reverse=True)
    return [x for x in out if _is_radiology_safety(x['title'])][:limit]


def direct_safety_info():
    """放射線に関係する医療安全情報を、記事の形(title/url/source/published)で返す。"""
    out = []
    now = datetime.now(JST)
    try:
        for x in parse_med_safe(fetch(MED_SAFE_LIST)):
            out.append({
                'title': f'医療安全情報 No.{x["no"]}：{x["title"]}',
                'url': x['url'], 'description': '', 'source': '日本医療機能評価機構',
                # 一覧に発行日がないため、初めて見つけた日を日付にする
                'published': now.isoformat(),
            })
        SOURCE_STATUS['医療機能評価機構'] = {'picked': sum(1 for x in out if x['source'] == '日本医療機能評価機構')}
    except Exception as e:
        print('med-safe direct error:', e)
        SOURCE_STATUS['医療機能評価機構'] = {'error': f'{type(e).__name__}: {e}'[:160]}
    try:
        for x in parse_pmda_safety(fetch(PMDA_SAFETY_LIST)):
            if (now.date() - datetime.fromisoformat(x['published']).date()).days > 120:
                continue
            out.append({
                'title': f'PMDA医療安全情報 No.{x["no"]}：{x["title"]}',
                'url': x['url'], 'description': '', 'source': 'PMDA',
                'published': datetime.fromisoformat(x['published']).replace(tzinfo=JST).isoformat(),
            })
        SOURCE_STATUS['PMDA'] = {'picked': sum(1 for x in out if x['source'] == 'PMDA')}
    except Exception as e:
        print('PMDA direct error:', e)
        SOURCE_STATUS['PMDA'] = {'error': f'{type(e).__name__}: {e}'[:160]}
    print(f'Safety info candidates: {len(out)}')
    return out


# --------------------------------------------------
# 技師会(JART)の研修・講習会一覧から日程を読む
# 例: 「告示研修 受付前 告示研修（実技研修）東京都2026/11/23 受付期間：2026/9/18〜2026/11/8
#      開催日：2026/11/23〜2026/11/23 開催地域：東京都 …」
# --------------------------------------------------
JART_SEMINAR_PAGES = ('https://www.jart.jp/', 'https://www.jart.jp/seminar/')
_JDATE = r'(20\d{2})\s*[/年]\s*(\d{1,2})\s*[/月]\s*(\d{1,2})日?(?:\s*[（(][^）)]*[）)])?'
_JRANGE = _JDATE + r'\s*[〜～\-－~]\s*' + _JDATE


def _jd(g):
    d = _to_date(g[0], g[1], g[2])
    return d.isoformat() if d else ''


def parse_jart_seminars(html, base='https://www.jart.jp/'):
    out = {}
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']*/seminar/[^"\']+)["\'][^>]*>(?P<text>.*?)</a>', html, re.I | re.S):
        text = re.sub(r'\s+', ' ', clean_html(m.group('text'))).strip()
        ev = re.search(r'開催日\s*[:：]\s*' + _JRANGE, text)
        if not ev:
            continue
        ap = re.search(r'受付期間\s*[:：]\s*' + _JRANGE, text)
        head = text.split('受付期間')[0] if '受付期間' in text else text.split('開催日')[0]
        st = re.search(r'(申込み可|受付前|申込み不可|受付終了|満員|定員に達しました)', head)
        status = st.group(1) if st else ''
        kind, title = '', head
        if st:
            kind = head[:st.start()].strip()
            title = head[st.end():].strip()
        place = ''
        pm = re.search(r'開催地域\s*[:：]\s*(\S+)', text)
        if pm:
            place = pm.group(1)
        url = urljoin(base, m.group('href'))
        g = ev.groups()
        out[url] = {
            'title': title, 'url': url, 'kind': kind, 'status': status,
            'event_start': _jd(g[:3]), 'event_end': _jd(g[3:6]),
            'apply_start': _jd(ap.groups()[:3]) if ap else '', 'apply_end': _jd(ap.groups()[3:6]) if ap else '',
            'place': place,
        }
    return list(out.values())


ROMAJI_PREF = {
    'hokkaido': '北海道', 'sapporo': '北海道', 'aomori': '青森', 'iwate': '岩手', 'miyagi': '宮城', 'sendai': '宮城',
    'akita': '秋田', 'yamagata': '山形', 'fukushima': '福島', 'ibaraki': '茨城', 'tochigi': '栃木', 'gunma': '群馬',
    'saitama': '埼玉', 'chiba': '千葉', 'tokyo': '東京', 'kanagawa': '神奈川', 'yokohama': '神奈川', 'niigata': '新潟',
    'toyama': '富山', 'ishikawa': '石川', 'kanazawa': '石川', 'fukui': '福井', 'yamanashi': '山梨', 'nagano': '長野',
    'gifu': '岐阜', 'shizuoka': '静岡', 'aichi': '愛知', 'nagoya': '愛知', 'mie': '三重', 'shiga': '滋賀', 'kyoto': '京都',
    'osaka': '大阪', 'hyogo': '兵庫', 'kobe': '兵庫', 'nara': '奈良', 'wakayama': '和歌山', 'tottori': '鳥取',
    'shimane': '島根', 'okayama': '岡山', 'hiroshima': '広島', 'yamaguchi': '山口', 'tokushima': '徳島',
    'kagawa': '香川', 'takamatsu': '香川', 'ehime': '愛媛', 'matsuyama': '愛媛', 'kochi': '高知', 'fukuoka': '福岡',
    'saga': '佐賀', 'nagasaki': '長崎', 'kumamoto': '熊本', 'oita': '大分', 'miyazaki': '宮崎', 'kagoshima': '鹿児島',
    'okinawa': '沖縄', 'web': 'オンライン', 'online': 'オンライン',
}


def parse_qabcs_seminars(xml):
    """精中機構の講習会RSS(日付=開催日)から、技師向け(撮影・超音波技術)の講習会だけを返す。"""
    out = []
    for x in parse_rss(xml):
        url, title = x['url'], x['title']
        path = re.sub(r'^https?://[^/]+', '', url).lower()
        # URLの _g は技師向け、_d は医師向け
        is_tech = bool(re.search(r'_g/', path)) or ('技術' in title and '医師' not in title)
        if not is_tech:
            continue
        place = next((p for p in PREFECTURES if p in title), '')
        if not place:
            m = re.search(r'_([a-z]+)\.html', path)
            place = ROMAJI_PREF.get(m.group(1), '') if m else ''
        day = x['published'][:10]
        out.append({
            'title': title, 'url': url, 'kind': '精中機構', 'status': '',
            'event_start': day, 'event_end': day, 'apply_start': '', 'apply_end': '', 'place': place,
            'category': '超音波' if '/us/' in path or '超音波' in title else 'マンモグラフィ',
        })
    return out


def update_seminars():
    """技師会の研修日程を seminars.json に保存する。取れなかった日は前回分を残す。"""
    today = datetime.now(JST).date().isoformat()
    found = {}
    for page in JART_SEMINAR_PAGES:
        try:
            for x in parse_jart_seminars(fetch(page), page):
                found[x['url']] = x
        except Exception as e:
            print('JART seminar error:', page, e)
            SOURCE_STATUS.setdefault('技師会の研修一覧', {})['error'] = f'{type(e).__name__}: {e}'[:160]
    for x in update_kart_schedule():
        found[x['url']] = x
    for x in update_ehime_schedule():
        found[x['url']] = x
    for x in update_jabts_schedule():
        found[x['url']] = x
    try:
        ev = parse_jmrts(fetch(JMRTS_TOP))[1]
        for x in ev:
            found[x['url'] + '#' + x['event_start']] = x
        SOURCE_STATUS['MR認定研究会・セミナー'] = {'listed': len(ev)}
    except Exception as e:
        print('JMRTS seminar error:', e)
        SOURCE_STATUS['MR認定研究会・セミナー'] = {'error': f'{type(e).__name__}: {e}'[:160]}
    try:
        q = parse_qabcs_seminars(fetch(QABCS_FEED))
        for x in q:
            found[x['url']] = x
        SOURCE_STATUS['精中機構の講習会'] = {'listed': len(q)}
    except Exception as e:
        print('QABCS seminar error:', e)
        SOURCE_STATUS['精中機構の講習会'] = {'error': f'{type(e).__name__}: {e}'[:160]}
    try:
        old = json.loads(SEMINARS_JSON.read_text(encoding='utf-8')).get('items', [])
    except Exception:
        old = []
    if not found:
        items = old
    else:
        items = list(found.values())
    # 終わった研修は外す。何年も続く常設のオンライン講座は「随時」として残す
    items = [x for x in items if (x.get('event_end') or x.get('event_start') or '') >= today]
    items.sort(key=lambda x: (x.get('event_start') or '9999', x.get('title') or ''))
    SEMINARS_JSON.write_text(json.dumps({'checked_at': datetime.now(JST).isoformat(timespec='minutes'),
                                         'items': items}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'JART seminars: {len(found)} found, {len(items)} upcoming')
    SOURCE_STATUS.setdefault('技師会の研修一覧', {}).update({'listed': len(found), 'upcoming': len(items)})


# --------------------------------------------------
# 学会・厚労省の新着を直接取得する
# --------------------------------------------------
SOCIETY_DOMAINS = ('jsrt.or.jp', 'radiology.jp', 'jsnm.org', 'jsgcs.or.jp', 'jastro.or.jp', 'jsmp.org', 'jsmrm.jp',
                   'jsir.or.jp', 'jsum.or.jp', 'jsnmt.org', 'jsct-tech.org', 'kagawart.jp', 'jsrt-chushi.jp',
                   'jabcs.jp', 'jscts.org', 'radiation-therapy.jp', 'jert.info',
                   'oart.jp', 'ehimeart.com', 'tart.web5.jp', 'kochi-art.org',
                   'jabts.jp', 'jss.org', 'ct-ninteikikou.jp', 'jbcs.gr.jp', 'mrifan.net', 'dcis.kenkyuukai.jp')
JSRT_NEWS = 'https://www.jsrt.or.jp/data/'
JRS_TOP = 'https://www.radiology.jp/'
JSNM_FEED = 'https://jsnm.org/feed/'
MHLW_FEED = 'https://www.mhlw.go.jp/stf/news.rdf'
# 厚労省の新着のうち、放射線の語がなくても部門で確認したいもの(診療報酬・病院のシステムの安全)
MHLW_EXTRA_PATTERN = re.compile(
    r'診療報酬改定|医療情報システムの安全管理|医療機関.*サイバー|サイバーセキュリティ.*医療'
    r'|不正アクセス.*(注意喚起|セキュリティ対策)|ランサムウェア'
)
JSGCS_TOP = 'https://www.jsgcs.or.jp/'
JMRTS_TOP = 'https://plaza.umin.ac.jp/~JMRTS/'
KART_TOP = 'https://kagawart.jp/'
KART_SCHEDULE = 'https://kagawart.jp/article/schedulelist.php?y={y}&m={m}'
KART_RECRUIT = 'https://kagawart.jp/recruit/'
KAGAWA_NEWS_DAYS = 60   # 別枠に出すお知らせの期間(ニュースの判定で外れるものも含めて全部)
KAGAWA_NEWS_MAX = 15
JSRT_CHUSHI_FEED = 'https://jsrt-chushi.jp/?feed=rss2'
# 近県の技師会(四国・岡山)。愛媛はRSSが空なのでトップのお知らせ一覧、高知は古い表形式のお知らせ欄を読む
OART_FEED = 'https://www.oart.jp/feed/'
EHIME_TOP = 'https://ehimeart.com/'
TART_TOP = 'https://tart.web5.jp/'
KOCHI_NEWS = 'http://www.kochi-art.org/news.htm'
DCIS_NEWS = 'http://dcis.kenkyuukai.jp/information/'
NEARBY_ASSOCIATIONS = ('岡山県診療放射線技師会', '愛媛県診療放射線技師会', '徳島県診療放射線技師会', '高知県診療放射線技師会')
# 地元の会は更新がまばらなので、取り込む期間を長めに
LOCAL_DAYS = {'香川県診療放射線技師会': 45, '日本放射線技術学会 中国・四国支部': 60, '日本乳癌検診学会': 60,
              '日本CT検診学会': 45, '日本放射線治療専門放射線技師認定機構': 60,
              '日本乳腺甲状腺超音波医学会': 60, '日本X線CT専門技師認定機構': 60, 'DCIS研究会': 60,
              **{name: 45 for name in NEARBY_ASSOCIATIONS}}

# 分野ごとの専門学会。(表示名, URL, 読み方, 既定の分類, リンク条件, 読み始める目印)
# 読み方: rss = RSS、list = 日付とリンクが並ぶお知らせ一覧(parse_dated_links)
SPECIALTY_SOURCES = (
    ('日本放射線腫瘍学会', 'https://www.jastro.or.jp/', 'list', '放射線治療', '.', 'news_list'),
    ('日本医学物理学会', 'https://www.jsmp.org/feed/', 'rss', '放射線治療', None, None),
    ('日本磁気共鳴医学会', 'https://www.jsmrm.jp/', 'list', 'MRI', '/modules/news/', 'box_news'),
    ('日本IVR学会', 'https://www.jsir.or.jp/feed/', 'rss', '血管撮影', None, None),
    ('日本超音波医学会', 'https://www.jsum.or.jp/feed/', 'rss', '超音波', None, None),
    ('日本核医学技術学会', 'https://jsnmt.org/news/feed/', 'rss', '核医学', None, None),
    ('日本CT技術学会', 'https://www.jsct-tech.org/', 'list', 'CT', '.', None),
    # 検診・認定機構('blocks' は「日付 → 本文」が並ぶ一覧。5番目は日付の書き方)
    ('日本乳癌検診学会', 'https://www.jabcs.jp/', 'blocks', 'マンモグラフィ', 'jp', None),
    ('日本CT検診学会', 'https://www.jscts.org/index.php?page=update', 'blocks', '検診', 'yy', None),
    ('日本放射線治療専門放射線技師認定機構', 'https://www.radiation-therapy.jp/news/index.shtml', 'blocks', '放射線治療', 'slash', None),
    # 日本救急撮影技師認定機構(jert.info)はRSSに記事が入っておらず、一覧にも日付がないため取り込まない
    # 以下は画面の「情報を集める先」で初期状態はチェックなし(index.html の SRC_DEFAULT_OFF)
    ('日本乳腺甲状腺超音波医学会', 'https://jabts.jp/feed/', 'rss', '超音波', None, None),
    ('日本超音波検査学会', 'https://www.jss.org/feed/', 'rss', '超音波', None, None),
    ('日本X線CT専門技師認定機構', 'https://www.ct-ninteikikou.jp/', 'blocks', 'CT', 'slash', None),
    ('日本乳癌学会', 'https://www.jbcs.gr.jp/index.php', 'list', 'マンモグラフィ', r'modules/info/index\.php', 'box_newstop'),
    ('MRIfan.net', 'https://mrifan.net/feed/', 'rss', 'MRI', None, None),
)
# 専門学会の記事で、分類が一般的なもの(その他・学術・教育・制度)になった場合は学会の分野を使う
SPECIALTY_DEFAULT_CATEGORY = {name: cat for name, _, _, cat, *_ in SPECIALTY_SOURCES}
SPECIALTY_DEFAULT_CATEGORY['日本磁気共鳴専門技術者認定機構'] = 'MRI'
SPECIALTY_DEFAULT_CATEGORY['香川県診療放射線技師会'] = '教育'
SPECIALTY_DEFAULT_CATEGORY['日本放射線技術学会 中国・四国支部'] = '教育'
SPECIALTY_DEFAULT_CATEGORY.update({name: '教育' for name in NEARBY_ASSOCIATIONS})
SPECIALTY_DEFAULT_CATEGORY['DCIS研究会'] = 'マンモグラフィ'

QABCS_FEED = 'https://www.qabcs.or.jp/rss2.xml'
BLOCK_DATES = {
    'jp': re.compile(r'(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日'),
    'yy': re.compile(r'(?<![\d.])(\d{2})\.(\d{2})\.(\d{2})(?![\d.])'),
    'slash': re.compile(r'(?<!\d)(20\d{2})/(\d{1,2})/(\d{1,2})(?!\d)'),
}
# 役員会の報告などは研修・制度の情報ではないので除く
BLOCK_SKIP = re.compile(r'理事会|社員総会|寄付|役員一覧|賛助会員|理事長挨拶')


def parse_dated_blocks(html, base, fmt):
    """「日付」のあとに本文(リンク付きのことが多い)が続く一覧を読む。

    日付から次の日付までを1件とみなし、見出し(hN)があればそれを、なければ本文を題名にする。
    同じページへのリンクが何度も出てくる(「〇〇を更新しました」)ので、URLには日付を付けて区別する。
    """
    html = re.sub(r'<(script|style)\b.*?</\1>', '', html, flags=re.S | re.I)
    dates = list(BLOCK_DATES[fmt].finditer(html))
    out = {}
    for i, m in enumerate(dates):
        seg = html[m.end():dates[i + 1].start() if i + 1 < len(dates) else m.end() + 1500]
        y, mo, d = m.groups()
        dt = _to_date(int(y) + 2000 if len(y) == 2 else y, mo, d)
        h = re.search(r'<h[1-6][^>]*>(.*?)</h[1-6]>', seg, re.S | re.I)
        title = clean_html(h.group(1) if h else seg).replace('NEW!', ' ')
        title = re.sub(r'^[\s　:：|｜]+', '', title)
        title = re.sub(r'\s+', ' ', title).strip()
        title = re.sub(r'(?<=[^\x00-\x7f]) | (?=[^\x00-\x7f])', '', title)[:90]   # タグの境目に入った空白
        if not dt or len(title) < 4 or BLOCK_SKIP.search(title):
            continue
        a = re.search(r'<a\b[^>]*href=["\']([^"\']+)["\']', seg, re.I)
        if not a:
            url = base.split('#')[0] + f'#d{dt:%Y%m%d}-{len(dates) - i}'   # 記事ごとのリンクがない一覧
        else:
            url = urljoin(base, unescape(a.group(1)))
            if '#' not in url:
                url += f'#d{dt:%Y%m%d}'
        out.setdefault(url, {'title': title, 'url': url, 'published': datetime(dt.year, dt.month, dt.day, tzinfo=JST).isoformat()})
    return list(out.values())


DIRECT_MAX_PER_SOURCE = 5   # 初回に古い記事がまとめて入らないよう、1回あたりの上限
DIRECT_DAYS = 21            # これより古い記事は取り込まない(学会は更新がまばらなため3週間)


def parse_rss(xml):
    """RSS 2.0(item/pubDate)と RSS 1.0(rdf:item/dc:date)の両方に対応。"""
    out = []
    for it in re.findall(r'<item\b[^>]*>(.*?)</item>', xml, re.S | re.I):
        title = re.search(r'<title>(.*?)</title>', it, re.S)
        link = re.search(r'<link>(.*?)</link>', it, re.S)
        pub = re.search(r'<pubDate>(.*?)</pubDate>', it, re.S) or re.search(r'<dc:date>(.*?)</dc:date>', it, re.S)
        if not (title and link):
            continue
        t = unescape(re.sub(r'<!\[CDATA\[|\]\]>', '', title.group(1))).strip()
        try:
            raw = pub.group(1).strip() if pub else ''
            dt = parsedate_to_datetime(raw) if re.match(r'[A-Za-z]{3},', raw) else datetime.fromisoformat(raw.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=JST)
            published = dt.astimezone(JST).isoformat()
        except Exception:
            continue
        out.append({'title': t, 'url': unescape(link.group(1).strip()), 'published': published})
    return out


def parse_jsrt(html):
    """<tr><th>2026/10/27</th>…<a href=".../data/news/70512/">［案内板］…</a></tr>"""
    out = []
    for row in re.split(r'<tr[\s>]', html, flags=re.I)[1:]:
        d = re.search(r'(20\d{2})/(\d{1,2})/(\d{1,2})', row)
        a = re.search(r'<a[^>]+href=["\'](?P<h>[^"\']*/data/news/\d+/?)["\'][^>]*>(?P<t>.*?)</a>', row, re.I | re.S)
        if d and a:
            dt = _to_date(*d.groups())
            if dt:
                out.append({'title': clean_html(a.group('t')), 'url': urljoin(JSRT_NEWS, a.group('h')),
                            'published': datetime(dt.year, dt.month, dt.day, tzinfo=JST).isoformat()})
    return out


def parse_jrs(html):
    """<dt><time datetime="2026-10-23">…</time></dt><dd><a href="member_info/…">題名</a></dd>"""
    out = []
    for m in re.finditer(r'<time[^>]+datetime=["\'](20\d{2}-\d{2}-\d{2})["\'][^>]*>.*?</time>\s*(?:</dt>)?\s*<dd>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
        out.append({'title': clean_html(m.group(3)), 'url': urljoin(JRS_TOP, m.group(2)),
                    'published': datetime.fromisoformat(m.group(1)).replace(tzinfo=JST).isoformat()})
    return out


def parse_jsgcs(html):
    """<article><span class="date">2026.10.13</span>…<a href=".../archives/51">題名</a></article>"""
    out = {}
    for art in re.findall(r'<article\b[^>]*>(.*?)</article>', html, re.S | re.I):
        d = re.search(r'(20\d{2})[./](\d{1,2})[./](\d{1,2})', art)
        a = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', art, re.S | re.I)
        if d and a:
            dt = _to_date(*d.groups())
            url = urljoin(JSGCS_TOP, a.group(1))
            if dt and url not in out:
                out[url] = {'title': clean_html(a.group(2)), 'url': url,
                            'published': datetime(dt.year, dt.month, dt.day, tzinfo=JST).isoformat()}
    return list(out.values())


_DATE_ANY = re.compile(r'(20\d{2})\s*[./年-]\s*(\d{1,2})\s*[./月-]\s*(\d{1,2})日?')


def parse_dated_links(html, base, href_re=r'.', start=None):
    """「日付 + リンク」が並ぶお知らせ一覧を読む汎用の処理。

    各リンクについて、直前のリンクとの間(直前の文字)にある日付を優先し、なければ
    次のリンクまでの間(直後の文字)にある日付を使う。リンク文字の中の日付は使わない
    (イベント紹介のバナーなどを拾わないため)。
    """
    if start and start in html:
        html = html[html.index(start):]
    anchors = list(re.finditer(r'<a\b[^>]*href=["\']([^"\'#][^"\']*)["\'][^>]*>(.*?)</a>', html, re.S | re.I))
    out = {}
    for i, m in enumerate(anchors):
        href, title = m.group(1), clean_html(m.group(2))
        if len(title) < 6 or not re.search(href_re, href):
            continue
        prev_end = anchors[i - 1].end() if i else max(0, m.start() - 400)
        next_start = anchors[i + 1].start() if i + 1 < len(anchors) else m.end() + 300
        before = clean_html(html[max(prev_end, m.start() - 400):m.start()])
        after = clean_html(html[m.end():min(next_start, m.end() + 300)])
        d = (list(_DATE_ANY.finditer(before)) or [None])[-1] or _DATE_ANY.search(after)
        if not d:
            continue
        dt = _to_date(*d.groups()[:3])
        url = urljoin(base, href)
        if dt and url not in out:
            out[url] = {'title': title, 'url': url, 'published': datetime(dt.year, dt.month, dt.day, tzinfo=JST).isoformat()}
    return list(out.values())


CITY_PREF = {'神戸': '兵庫', '函館': '北海道', '札幌': '北海道', '仙台': '宮城', '横浜': '神奈川', '名古屋': '愛知',
             '金沢': '石川', '博多': '福岡', '高松': '香川', '松山': '愛媛'}


def parse_jmrts(html, today=None):
    """日本磁気共鳴専門技術者認定機構のトップ一覧。

    <li><span class="label">お知らせ</span><span class="date">【現地開催：11/7(土)】<a href="…">第10回高知MRI技術研究会開催のお知らせ＜2026.10></a></span></li>
    戻り値: (記事のリスト, 研究会・セミナーの日程のリスト)
    """
    today = today or datetime.now(JST).date()
    news, events = [], []
    for li in re.findall(r'<li[^>]*>(.*?)</li>', html, re.S | re.I):
        lab = re.search(r'class=["\'][^"\']*label[^"\']*["\'][^>]*>(.*?)</span>', li, re.S | re.I)
        a = re.search(r'<a[^>]+href=["\']([^"\'#][^"\']*)["\'][^>]*>(.*?)</a>', li, re.S | re.I)
        if not (lab and a):
            continue
        label = clean_html(lab.group(1))
        text = clean_html(a.group(2))
        ym = re.search(r'[＜<]\s*(20\d{2})\.(\d{1,2})\s*[＞>]', unescape(text))
        title = re.sub(r'\s*[＜<]\s*20\d{2}\.\d{1,2}\s*[＞>]\s*$', '', unescape(text)).strip()
        url = urljoin(JMRTS_TOP, a.group(1))
        ev = re.search(r'【([^】]*?)開催[:：]\s*(\d{1,2})/(\d{1,2})', clean_html(li))
        if ev:
            mode, mm, dd = ev.group(1), int(ev.group(2)), int(ev.group(3))
            dt = _to_date(today.year, mm, dd)
            if dt and (today - dt).days > 60:
                dt = _to_date(today.year + 1, mm, dd)
            if not dt:
                continue
            place = 'オンライン' if re.search(r'web|ウェブ|オンライン', mode, re.I) else ''
            if not place:
                place = next((p for p in PREFECTURES if p in title), '') or next((v for k, v in CITY_PREF.items() if k in title), '')
            events.append({'title': title, 'url': url, 'kind': 'JMRTS', 'status': '', 'event_start': dt.isoformat(),
                           'event_end': dt.isoformat(), 'apply_start': '', 'apply_end': '', 'place': place,
                           'category': 'MRI', 'source': '日本磁気共鳴専門技術者認定機構'})
            continue
        if not ym:
            continue
        y, m = int(ym.group(1)), int(ym.group(2))
        # 一覧には年月しかないので、今月の掲載分は「見つけた日」を日付にする
        if (y, m) == (today.year, today.month):
            published = datetime.combine(today, datetime.min.time()).replace(tzinfo=JST)
        else:
            published = datetime(y, m, 1, tzinfo=JST)
        news.append({'title': f'{title}' if label in title else title, 'url': url, 'published': published.isoformat(), 'label': label})
    return news, events


# --------------------------------------------------
# PMDA: 医療機器の回収(クラスI・II)のうち放射線関連
# --------------------------------------------------
PMDA_RECALL_LIST = 'https://www.info.pmda.go.jp/kaisyuu/rcidx{fy:02d}-{cls}k.html'
RECALL_DEVICE_TERMS = (
    'X線', 'エックス線', 'Ｘ線', 'CT', 'ＣＴ', '断層撮影', 'MR', 'ＭＲ', '磁気共鳴', '放射線治療', '線形加速', '粒子線',
    '核医学', 'ガンマカメラ', 'PET', 'ＰＥＴ', 'SPECT', 'ＳＰＥＣＴ', '超音波画像診断', '乳房', 'マンモ', '透視', '血管撮影',
    '造影剤注入', 'インジェクタ', '画像診断', '画像処理', '線量計', '撮影装置', 'イメージング', 'FPD', 'ＦＰＤ', '放射線',
)


def recall_is_imaging(text):
    """英字の語は単語単位で見る(「ARCHITECT」「OCT」の CT に当てないため)。"""
    t = unicodedata.normalize('NFKC', text).lower()
    return any(_term_in(unicodedata.normalize('NFKC', k), t) for k in RECALL_DEVICE_TERMS)


def parse_pmda_recalls(html, cls):
    """<tr><td>2-13015</td><td>2026/10/27</td><td>医療機器</td><td>一般名</td><td><a href="/rgo/MainServlet?recallno=…">販売名</a></td><td>業者</td>"""
    out = []
    for row in re.split(r'<tr[\s>]', html, flags=re.I)[1:]:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S | re.I)   # 全角英数(ＣＴ・ＲａｙＳｔａｔｉｏｎ)は半角にそろえる
        if len(cells) < 6:
            continue
        no, day, kind, generic, product_html, maker = cells[:6]
        d = re.search(r'(20\d{2})/(\d{1,2})/(\d{1,2})', day)
        a = re.search(r'href=["\']?([^"\'\s>]+)', product_html, re.I)   # PMDAは引用符なしの HREF=/rgo/…
        generic, product, maker = (unicodedata.normalize('NFKC', clean_html(v)) for v in (generic, product_html, maker))
        if not (d and a) or not recall_is_imaging(generic + ' ' + product):
            continue
        dt = _to_date(*d.groups())
        out.append({
            'title': f'医療機器の回収(クラス{"I" if cls == 1 else "II"})：{product}({generic})',
            'url': urljoin('https://www.info.pmda.go.jp/kaisyuu/', a.group(1)),
            'published': datetime(dt.year, dt.month, dt.day, tzinfo=JST).isoformat(),
            'maker': maker,
        })
    return out


def direct_pmda_recalls():
    now = datetime.now(JST)
    fy = (now.year if now.month >= 4 else now.year - 1) % 100   # 年度は4月始まり
    out = []
    for cls in (1, 2):
        try:
            html = fetch(PMDA_RECALL_LIST.format(fy=fy, cls=cls))
            items = parse_pmda_recalls(html, cls)
            picked = [x for x in items if (now - datetime.fromisoformat(x['published'])).days <= DIRECT_DAYS][:10]
            st = {'listed': len(items), 'picked': len(picked)}
            if not items and 'recallno' in html:   # 一覧は読めたが、放射線関連の回収がないだけ
                st['empty_ok'] = True
            elif not items:   # 読み取れなかったときは、原因を調べられるようページの一部を残す
                k = html.find('recallno')
                st['sample'] = re.sub(r'\s+', ' ', html[max(0, k - 700):k + 300] if k >= 0 else html[:600])
                st['bytes'] = len(html)
            SOURCE_STATUS[f'PMDA回収クラス{"I" if cls == 1 else "II"}'] = st
            out += [{'title': x['title'], 'url': x['url'], 'description': x['maker'], 'source': 'PMDA', 'published': x['published']} for x in picked]
        except Exception as e:
            print('PMDA recall error:', cls, e)
            SOURCE_STATUS[f'PMDA回収クラス{"I" if cls == 1 else "II"}'] = {'error': f'{type(e).__name__}: {e}'[:160]}
    return out


# --------------------------------------------------
# 厚労省「医療用医薬品供給状況」(Excel)のうち造影剤・放射性医薬品
# --------------------------------------------------
SUPPLY_PAGE = 'https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/kouhatu-iyaku/04_00003.html'
SUPPLY_JSON = ROOT / 'supply.json'
IMAGING_DRUG_CLASSES = ('Ｘ線造影剤', 'X線造影剤', '放射性医薬品')
IMAGING_DRUG_INGREDIENTS = re.compile(r'ガド|ペルフルブタン|マンガン|フェルモキシ|フェルカルボ|超常磁性')


def _excel_day(v):
    try:
        n = int(float(v))
        return (datetime(1899, 12, 30) + timedelta(days=n)).date().isoformat() if n > 30000 else ''
    except (TypeError, ValueError):
        return ''


def supply_category(cls, ingredient):
    if 'バリウム' in ingredient:
        return '検診'
    if cls == '放射性医薬品':
        return '核医学'
    if re.search(r'ガド|マンガン|フェル|超常磁性', ingredient):
        return 'MRI'
    if 'ペルフルブタン' in ingredient:
        return '超音波'
    return 'CT'


def parse_supply_rows(rows):
    """Excelの行(見出し行を含む)から、造影剤・放射性医薬品だけを取り出す。見出しの文字で列を探す。"""
    rows = list(rows)
    # 表の上に題名の行があることもあるので、「成分名」を含む行を見出しとみなす
    h = next((i for i, r in enumerate(rows[:15]) if any('成分名' in str(v or '') for v in r)), 0)
    rows = rows[h:]
    head = [str(c or '') for c in rows[0]]
    def col(keys, default=None):
        for i, h in enumerate(head):
            if all(k in h for k in keys):
                return i
        return default if default is not None and default < len(head) else None
    # 見出しの文字で探し、見つからなければ 2026年10月時点の列の位置を使う
    c = {'cls': col(('薬効分類',), 1), 'ing': col(('成分名',), 2), 'spec': col(('規格',), 3), 'yj': col(('YJ',), 4),
         'name': col(('品名',), 5), 'maker': col(('製造販売業者',), 6), 'status': col(('出荷対応',), 11),
         'changed': col(('更新日',), 12), 'reason': col(('理由',)), 'outlook': col(('見込み',)),
         'new': col(('今回掲載時',), 20)}
    if None in (c['cls'], c['ing'], c['name'], c['status']):
        raise ValueError('供給状況の見出しが見つかりません: ' + ' / '.join(h[:10] for h in head[:12]))
    # 全角英数(１００ｍＬ「Ｆ」)は読みやすいよう半角にそろえる
    def get(r, k):
        v = str(r[c[k]]).strip() if c[k] is not None and c[k] < len(r) and r[c[k]] is not None else ''
        return unicodedata.normalize('NFKC', v) if k in ('spec', 'name', 'maker') else v
    out = []
    for r in rows[1:]:
        cls, ing = get(r, 'cls'), get(r, 'ing')
        if not (cls in IMAGING_DRUG_CLASSES or IMAGING_DRUG_INGREDIENTS.search(ing)):
            continue
        out.append({
            'class': cls, 'ingredient': ing, 'spec': get(r, 'spec'), 'yj': get(r, 'yj'), 'product': get(r, 'name'),
            'maker': get(r, 'maker'), 'status': re.sub(r'^[①-⑤]', '', get(r, 'status')),
            'changed': _excel_day(r[c['changed']]) if c['changed'] is not None and c['changed'] < len(r) else '',
            'reason': re.sub(r'^[0-9０-９]+[．.]', '', get(r, 'reason')), 'outlook': re.sub(r'^[ア-エ][．.]\s*', '', get(r, 'outlook')),
            'new': get(r, 'new').lower().startswith('new'),
            'category': supply_category(cls, ing),
        })
    return out


def update_supply():
    """供給状況の一覧を supply.json に保存し、今回の掲載で状況が変わった品目を記事の形で返す。"""
    try:
        page = fetch(SUPPLY_PAGE)
        m = re.search(r'href=["\']([^"\']+\.xlsx)["\'][^>]*>([^<]*供給状況[^<]*)', page)
        if not m:
            raise ValueError('Excelへのリンクが見つかりません')
        xurl = urljoin(SUPPLY_PAGE, m.group(1))
        as_of = re.search(r'（([^）]*現在)）', m.group(2))
        import io
        import openpyxl
        raw, _ = fetch_bytes(xurl)
        wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        rows = parse_supply_rows(wb.worksheets[0].iter_rows(values_only=True))
    except Exception as e:
        print('Supply error:', e)
        SOURCE_STATUS['造影剤の供給状況'] = {'error': f'{type(e).__name__}: {e}'[:160]}
        return []
    limited = [x for x in rows if x['status'] and '通常出荷' not in x['status']]
    SUPPLY_JSON.write_text(json.dumps({
        'as_of': as_of.group(1) if as_of else '', 'source': SUPPLY_PAGE, 'checked_at': datetime.now(JST).isoformat(timespec='minutes'),
        'items': sorted(limited, key=lambda x: ('供給停止' not in x['status'], x['ingredient'], x['product'])),
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    SOURCE_STATUS['造影剤の供給状況'] = {'listed': len(rows), 'limited': len(limited)}
    today = datetime.now(JST).date().isoformat()
    news = []
    for x in rows:
        if not x['new']:
            continue
        state = x['status'] if '通常出荷' not in x['status'] else '通常出荷に回復'
        news.append({
            'title': f'{"放射性医薬品" if x["class"] == "放射性医薬品" else "造影剤"}の{"供給回復" if state == "通常出荷に回復" else state}：{x["product"]}({x["ingredient"]})',
            'url': f'{SUPPLY_PAGE}#{x["yj"] or x["product"]}-{x["status"]}',
            'description': '', 'source': '厚生労働省(医薬品供給状況)', 'published': (x['changed'] or today) + 'T00:00:00+09:00',
        })
    return news[:8]


# --------------------------------------------------
# 学会誌の新着論文(J-STAGEの雑誌ごとの新着RSS)
# --------------------------------------------------
PAPERS_JSON = ROOT / 'papers.json'
JSTAGE_RSS = 'https://www.jstage.jst.go.jp/AF05S010NewRssDld?btnaction=JT0041&sryCd={code}&rssLang=ja'
JOURNALS = (
    ('日本放射線技術学会雑誌', 'jjrt', None),
    ('日本消化器がん検診学会雑誌', 'jsgcs', '検診'),
    ('日本乳癌検診学会誌', 'jjabcs', 'マンモグラフィ'),
)
PAPER_DAYS = 180     # これより古い論文は残さない
PAPER_MAX = 150


PAPER_SKIP = re.compile(r'^(講演プログラム|プログラム|日程表|会場案内|扉|表紙|目次|奥付|会告|編集後記|投稿規定|執筆要項|正誤表|お知らせ|学会記事|会員名簿|役員名簿|索引|広告)|抄録集|講演抄録$')


def parse_jstage_atom(xml):
    """J-STAGEの新着(Atom)。論文名・著者・公開日・DOIは summary の中に入っている。

    <entry><title>新着記事を登載しました。誌名</title><summary><![CDATA[ [ タイトル ] … [ 著者 ] … [ 公開日 ] 2026-10-21 [ DOI ] https://doi.org/… ]]></summary>
    """
    out = []
    for ent in re.findall(r'<entry\b[^>]*>(.*?)</entry>', xml, re.S | re.I):
        m = re.search(r'<summary[^>]*>(.*?)</summary>', ent, re.S | re.I)
        if not m:
            continue
        txt = unescape(re.sub(r'<!\[CDATA\[|\]\]>', '', m.group(1)))
        def field(name):
            f = re.search(r'\[\s*' + name + r'\s*\](.*?)(?=\[\s*(?:タイトル|著者|公開日|DOI)\s*\]|$)', txt, re.S)
            return re.sub(r'\s+', ' ', f.group(1)).strip() if f else ''
        title, authors, day, doi = field('タイトル'), field('著者'), field('公開日'), field('DOI')
        title = clean_html(title)   # <I>Helicobacter pylori</I> などの斜体タグ
        # 学術集会の抄録号(Supplement)は講演名が大量に並ぶので除く
        ident = re.search(r'<id>(.*?)</id>', ent, re.S)
        if ident and re.search(r'supplement', ident.group(1), re.I):
            continue
        link = re.search(r'<link[^>]+href=["\']([^"\']+)', ent)
        url = doi if doi.startswith('http') else (link.group(1) if link else '')
        if not title or not url or not re.match(r'20\d{2}-\d{2}-\d{2}', day) or PAPER_SKIP.search(title):
            continue
        out.append({'title': title, 'url': url, 'published': day + 'T00:00:00+09:00', 'authors': authors})
    return out


def update_papers():
    """各誌の新着論文を papers.json に追記する(前回分は残し、古いものから落とす)。"""
    try:
        old = json.loads(PAPERS_JSON.read_text(encoding='utf-8')).get('items', [])
    except Exception:
        old = []
    found = {x['url']: x for x in old}
    now = datetime.now(JST)
    for name, code, default_cat in JOURNALS:
        url = JSTAGE_RSS.format(code=code)
        try:
            page = fetch(url)
            items = parse_jstage_atom(page) if '<feed' in page[:500] else parse_rss(page)
        except Exception as e:
            SOURCE_STATUS[name] = {'error': f'{type(e).__name__}: {e}'[:160]}
            continue
        st = {'listed': len(items), 'feed_entries': page.count('<entry')}
        if not items and ('<feed' in page[:500] or '<rss' in page[:500]):   # 新着がないだけ
            st['empty_ok'] = True
        added = 0
        for x in items:
            title = re.sub(r'\s+', ' ', x['title']).strip()
            if not title or x['url'] in found:
                continue
            cat = category({'headline': title, 'summary': '', 'source': ''})
            found[x['url']] = {'journal': name, 'title': title, 'url': x['url'], 'published': x['published'][:10],
                               'authors': x.get('authors', ''),
                               'added': now.date().isoformat(),
                               'category': cat if cat != 'その他' or not default_cat else default_cat}
            added += 1
        st['added'] = added
        SOURCE_STATUS[name] = st
    cutoff = (now - timedelta(days=PAPER_DAYS)).date().isoformat()
    keep = sorted((x for x in found.values() if max(x['published'], x.get('added', '')) >= cutoff),
                  key=lambda x: (x.get('added', ''), x['published']), reverse=True)[:PAPER_MAX]
    PAPERS_JSON.write_text(json.dumps({'checked_at': now.isoformat(timespec='minutes'), 'items': keep},
                                      ensure_ascii=False, indent=1), encoding='utf-8')
    return keep


def update_kart_schedule():
    """香川県診療放射線技師会の予定表(今月から3か月分)を研修日程の形で返す。"""
    now = datetime.now(JST).date()
    out = []
    for k in range(4):
        y, m = now.year + (now.month - 1 + k) // 12, (now.month - 1 + k) % 12 + 1
        url = KART_SCHEDULE.format(y=y, m=m)
        try:
            for x in parse_dated_links(fetch(url), url, r'schedule\.php\?nid='):
                day = x['published'][:10]
                out.append({'title': x['title'], 'url': x['url'], 'kind': 'KART', 'status': '', 'event_start': day, 'event_end': day,
                            'apply_start': '', 'apply_end': '', 'place': '香川', 'source': '香川県診療放射線技師会',
                            'category': (lambda c: c if c != 'その他' else '職能')(category({'headline': x['title'], 'summary': '', 'source': ''}))})
        except Exception as e:
            SOURCE_STATUS['香川県技師会の予定表'] = {'error': f'{type(e).__name__}: {e}'[:160]}
            return out
    SOURCE_STATUS['香川県技師会の予定表'] = {'listed': len(out)}
    return out


def parse_jabts_meeting(html):
    """日本乳腺甲状腺超音波医学会のトップにある学術集会の案内(RSSには載らない)を読む。

    <h3>第54回日本乳腺甲状腺超音波医学会学術集会</h3><p>会期：2026年９月26日〜27日…会場：…</p><p>…<a href="…">
    """
    h = re.search(r'<h\d[^>]*>\s*(第[0-9０-９]+回日本乳腺甲状腺超音波医学会学術集会)\s*</h\d>(.{0,1500})', html, re.S)
    if not h:
        return None
    body = unicodedata.normalize('NFKC', clean_html(h.group(2)))
    d = re.search(r'会期[:：]\s*(20\d{2})年(\d{1,2})月(\d{1,2})日(?:\s*[〜~～-]\s*(?:(\d{1,2})月)?(\d{1,2})日)?', body)
    if not d:
        return None
    y, m1, d1, m2, d2 = d.groups()
    start = _to_date(y, m1, d1)
    end = _to_date(y, m2 or m1, d2) if d2 else start
    a = re.search(r'<a\b[^>]*href=["\'](https?://[^"\']+)["\']', h.group(2), re.I)
    place = next((p for p in PREFECTURES if p in body), '')
    return {'title': unicodedata.normalize('NFKC', clean_html(h.group(1))), 'url': a.group(1) if a else 'https://jabts.jp/',
            'kind': 'JABTS', 'status': '', 'event_start': start.isoformat(), 'event_end': (end or start).isoformat(),
            'apply_start': '', 'apply_end': '', 'place': place, 'source': '日本乳腺甲状腺超音波医学会', 'category': '超音波'} if start else None


def update_jabts_schedule():
    """学術集会の日程を返す。終わった回は出さない。"""
    try:
        x = parse_jabts_meeting(fetch('https://jabts.jp/'))
    except Exception as e:
        SOURCE_STATUS['JABTS学術集会'] = {'error': f'{type(e).__name__}: {e}'[:160]}
        return []
    SOURCE_STATUS['JABTS学術集会'] = {'listed': 1 if x else 0, 'empty_ok': True}
    return [x] if x and x['event_end'] >= datetime.now(JST).date().isoformat() else []


def parse_kart_recruit(html):
    """香川県技師会の求人案内。<h4>2026年10月</h4><table><tr><th>施設名</th><td>…</td></tr>…</table>

    人事担当者の個人名は載せない。
    """
    fields = {'施設名': 'facility', '住所': 'address', '電話番号': 'tel', '募集人数': 'positions',
              '業務内容': 'work', 'その他': 'note'}
    out, month = [], ''
    for m in re.finditer(r'<h4[^>]*>(.*?)</h4>|<table\b[^>]*>(.*?)</table>', html, re.S | re.I):
        if m.group(1) is not None:
            month = clean_html(m.group(1))
            continue
        job = {'month': month}
        for th, td in re.findall(r'<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>', m.group(2), re.S | re.I):
            key = fields.get(clean_html(th))
            if key:
                job[key] = clean_html(re.sub(r'<br\s*/?>', ' / ', td, flags=re.I)).replace(' / /', ' /').strip(' /')
        if job.get('facility'):
            out.append(job)
    return out


def update_kagawa():
    """香川県技師会のお知らせ(ニュースの判定に関係なく全部)と求人案内を kagawa.json に保存する。
    取れなかった部分は前回分を残す。行事予定は seminars.json(update_kart_schedule)にある。"""
    try:
        old = json.loads(KAGAWA_JSON.read_text(encoding='utf-8'))
    except Exception:
        old = {}
    now = datetime.now(JST)
    out = {'checked_at': now.isoformat(timespec='minutes'), 'recruit_url': KART_RECRUIT,
           'news': old.get('news', []), 'recruit': old.get('recruit', [])}
    try:
        listed = parse_dated_links(fetch(KART_TOP), KART_TOP, r'data\.php\?nid=')
        recent = [x for x in listed if (now - datetime.fromisoformat(x['published'])).days <= KAGAWA_NEWS_DAYS]
        recent.sort(key=lambda x: x['published'], reverse=True)
        out['news'] = [{'headline': x['title'], 'url': x['url'], 'date': x['published'][:10],
                        'source': '香川県診療放射線技師会',
                        'category': 'その他' if x['title'].startswith('求人') else
                        (lambda c: c if c != 'その他' else '教育')(category({'headline': x['title'], 'summary': '', 'source': ''}))}
                       for x in recent[:KAGAWA_NEWS_MAX]]
        SOURCE_STATUS['香川県技師会のお知らせ(別枠)'] = {'listed': len(out['news'])}
    except Exception as e:
        SOURCE_STATUS['香川県技師会のお知らせ(別枠)'] = {'error': f'{type(e).__name__}: {e}'[:160]}
    try:
        out['recruit'] = parse_kart_recruit(fetch(KART_RECRUIT))
        SOURCE_STATUS['香川県技師会の求人'] = {'listed': len(out['recruit'])}
        if not out['recruit']:   # 求人がない時期もある
            SOURCE_STATUS['香川県技師会の求人']['empty_ok'] = True
    except Exception as e:
        SOURCE_STATUS['香川県技師会の求人'] = {'error': f'{type(e).__name__}: {e}'[:160]}
    KAGAWA_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    return out


def update_ehime_schedule():
    """愛媛県診療放射線技師会のトップにある行事予定(日付は開催日)を研修日程の形で返す。"""
    today = datetime.now(JST).date().isoformat()
    try:
        listed = parse_dated_links(fetch(EHIME_TOP), EHIME_TOP, r'xo_event')
    except Exception as e:
        SOURCE_STATUS['愛媛県技師会の行事予定'] = {'error': f'{type(e).__name__}: {e}'[:160]}
        return []
    out = []
    for x in listed:
        day = x['published'][:10]
        if day < today:
            continue
        out.append({'title': x['title'], 'url': x['url'], 'kind': 'EHIME', 'status': '', 'event_start': day, 'event_end': day,
                    'apply_start': '', 'apply_end': '', 'place': '愛媛', 'source': '愛媛県診療放射線技師会',
                    'category': (lambda c: c if c != 'その他' else '職能')(category({'headline': x['title'], 'summary': '', 'source': ''}))})
    SOURCE_STATUS['愛媛県技師会の行事予定'] = {'listed': len(out)}
    return out


def parse_kochi(html):
    """高知県診療放射線技師会のお知らせ欄(news.htm)。

    <TR><TD>R8.10.27</TD><TD><A href="endaiboshu20261203.pdf"><IMG …></A></TD><TD>題名<FONT>NEW</FONT></TD></TR>
    日付は令和の年(R8 = 2026年)、リンクは画像のボタンなので題名は3つ目の欄から取る。
    """
    out = {}
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S | re.I):
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S | re.I)
        if len(cells) < 3:
            continue
        d = re.match(r'\s*R\s*(\d{1,2})\.(\d{1,2})\.(\d{1,2})', clean_html(cells[0]))
        a = re.search(r'<a[^>]+href=["\']([^"\'#][^"\']*)["\']', row, re.I)
        if not (d and a):
            continue
        dt = _to_date(2018 + int(d.group(1)), d.group(2), d.group(3))
        title = re.sub(r'\s*NEW\s*$|\s*[（(]\s*(募集要項|案内|ご案内)\s*[）)]\s*$', '', clean_html(cells[2])).strip()
        url = urljoin(KOCHI_NEWS, a.group(1))
        if dt and title and url not in out:
            out[url] = {'title': title, 'url': url, 'published': datetime(dt.year, dt.month, dt.day, tzinfo=JST).isoformat()}
    return list(out.values())


def direct_official_news():
    """学会(技術学会・医学放射線学会・核医学会)と厚労省の新着を、記事の形で返す。"""
    sources = (
        ('日本放射線技術学会', JSRT_NEWS, parse_jsrt),
        ('日本医学放射線学会', JRS_TOP, parse_jrs),
        ('日本核医学会', JSNM_FEED, parse_rss),
        ('厚生労働省', MHLW_FEED, parse_rss),
        ('日本消化器がん検診学会', JSGCS_TOP, parse_jsgcs),
        ('日本磁気共鳴専門技術者認定機構', JMRTS_TOP, lambda html: parse_jmrts(html)[0]),
        ('香川県診療放射線技師会', KART_TOP, lambda html: parse_dated_links(html, KART_TOP, r'data\.php\?nid=')),
        ('日本放射線技術学会 中国・四国支部', JSRT_CHUSHI_FEED, parse_rss),
        ('岡山県診療放射線技師会', OART_FEED, parse_rss),
        # 愛媛のトップには行事予定(xo_event、日付は開催日)も並ぶので、お知らせだけを読む
        ('愛媛県診療放射線技師会', EHIME_TOP, lambda html: parse_dated_links(html, EHIME_TOP, r'^(?!.*xo_event)')),
        ('徳島県診療放射線技師会', TART_TOP, lambda html: parse_dated_links(html, TART_TOP)),
        ('高知県診療放射線技師会', KOCHI_NEWS, parse_kochi),
        ('DCIS研究会', DCIS_NEWS, lambda html: parse_dated_links(html, DCIS_NEWS, r'information_detail\.asp')),
    ) + tuple(
        (name, url, parse_rss if kind == 'rss' else
         (lambda html, _u=url, _f=flt: parse_dated_blocks(html, _u, _f)) if kind == 'blocks' else
         (lambda html, _u=url, _f=flt, _s=start: parse_dated_links(html, _u, _f, _s)))
        for name, url, kind, _cat, flt, start in SPECIALTY_SOURCES
    )
    now = datetime.now(JST)
    out = []
    for name, url, parser in sources:
        try:
            page = fetch_with_cookies(url) if 'kenkyuukai.jp' in url else fetch(url)
            items = parser(page)
        except Exception as e:
            print(f'{name} direct error:', e)
            SOURCE_STATUS[name] = {'error': f'{type(e).__name__}: {e}'[:160]}
            continue
        picked = []
        for x in sorted(items, key=lambda x: x['published'], reverse=True):
            try:
                age = (now - datetime.fromisoformat(x['published'])).days
            except Exception:
                continue
            if age > LOCAL_DAYS.get(name, DIRECT_DAYS) or not x['title']:
                continue
            item = {'title': x['title'], 'url': x['url'], 'description': '', 'source': name, 'published': x['published']}
            # 厚労省は省全体の新着なので、放射線に関係するもの(毎日の整理で残る基準と同じ)だけ
            if name == '厚生労働省' and not relevant(item):
                continue
            if not is_news_item(item):
                continue
            picked.append(item)
            if len(picked) >= DIRECT_MAX_PER_SOURCE:
                break
        print(f'{name}: {len(items)} listed, {len(picked)} picked')
        SOURCE_STATUS[name] = {'listed': len(items), 'picked': len(picked)}
        if not items:   # 1件も読めなかったときは、原因を調べられるようページの冒頭を残す
            SOURCE_STATUS[name]['sample'] = re.sub(r'\s+', ' ', page[:700])
        out.extend(picked)
    return out


# 上から順に最初に当てはまったカテゴリを使う。
# 英字の語は単語単位で判定する(「AI」「CT」「RI」が他の単語の一部に当たらないように)。
CATEGORY_RULES = (
    ('診療報酬・補助金', ('診療報酬', '報酬改定', '補助金', '助成金', '加算', '施設基準')),
    ('職能', ('STAT', 'タスクシフト', 'タスク・シフト', 'タスクシェア', 'タスク・シェア', '業務範囲',
              '職能', '告示研修', '静脈路', '筋注')),
    ('安全管理', ('安全管理', '医療安全', '放射線安全', '放射線防護', '被ばく', '線量管理', '線量測定',
                  '診断参考レベル', 'DRL', '品質管理', '個人情報', '脆弱性', 'サイバー', '不正アクセス', '情報漏えい',
                  '情報漏洩', 'セキュリティ対策', 'ランサムウェア',
                  '限定出荷', '出荷停止', '供給停止', '供給不足', '供給回復', 'リコール', '自主回収', '医療機器の回収')),
    ('放射線治療', ('放射線治療', '放射線療法', '照射', '寡分割', '定位放射線', 'リニアック', '陽子線',
                    '粒子線', '重粒子', 'BNCT', 'IGRT', 'IMRT', 'SBRT', 'ZAP-X', 'サイバーナイフ', 'トモセラピー')),
    ('核医学', ('核医学', '放射性医薬品', 'RI内用', 'セラノスティクス', 'リガンド療法', '核種', 'サイクロトロン',
                'SPECT', 'PET', 'MIBG', 'Ac225', 'Lu-177', 'ルテチウム', '99mTc', 'テクネチウム', 'PSMA')),
    ('血管撮影', ('血管撮影', '血管造影', 'アンギオ', 'IVR', 'インターベンショナル', 'DSA', '心カテ', '心臓カテーテル',
                  'カテーテル治療', '血管内治療', '脳血管内')),
    # マンモグラフィ: 乳がん検診の記事もこちら(超音波・検診より先に判定)
    ('マンモグラフィ', ('マンモ', '乳房撮影', '乳房X線', 'トモシンセシス', '乳がん検診', '乳癌検診', '精度管理中央機構')),
    # 超音波: 「妊婦健診のエコー」などは検診より超音波として扱う
    ('超音波', ('超音波', 'エコー検査', 'エコー', 'ultrasound', 'ultrasonography')),
    # 検診: 胃透視など検診で行う撮影も含める(CT・一般撮影より先に判定)
    ('検診', ('検診', '健診', '人間ドック', 'ドック', '胃透視', '胃X線', '胃部X線', 'バリウム', '上部消化管造影',
              '対策型', '任意型', '消化器がん検診', '読影認定')),
    ('CT', ('CT', 'コンピュータ断層', 'computed tomography', 'フォトンカウンティング')),
    ('MRI', ('MRI', 'MR研究会', '磁気共鳴', 'magnetic resonance', 'テスラ')),
    ('一般撮影', ('一般撮影', '単純X線', 'X線撮影', 'レントゲン', 'FPD', '骨密度', '透視', '生殖腺')),
    ('AI', ('AI', '人工知能', '画像診断支援', '読影支援', '深層学習', 'ディープラーニング', '言語モデル')),
    ('制度', ('制度', '厚生労働省', '医政', '法改正', '省令', '立入検査', '施設認定', '認証申請')),
    ('教育', ('教育', '人材育成', '国家試験', '研修', '認定', 'セミナー', '講習', '講演会', 'eラーニング', 'e-ラーニング', '留学')),
    ('学術', ('学術', '演題募集', '会誌', '研究', '学会', 'ガイドライン', 'パブリックコメント', '論文', 'ESMO', 'ASTRO', 'RSNA')),
)


def _term_in(term, text):
    if re.fullmatch(r'[A-Za-z0-9\-]+', term):
        return re.search(r'(?<![a-z0-9])' + re.escape(term.lower()) + r'(?![a-z0-9])', text) is not None
    return term.lower() in text


def category(x):
    # 配信元名(「日本放射線技術学会」の「学会」など)では判定しない
    t = ' '.join(
        str(basis(x, k) or '') for k in ('title', 'headline', 'description', 'summary')
    ).lower()

    for cat, terms in CATEGORY_RULES:
        if any(_term_in(k, t) for k in terms):
            return cat

    return 'その他'


def is_specialist(x):
    """
    放射線部門の実務に直接関係するニュースか判定する。
    「診療放射線技師」という語がなくても、
    CT/MRI/核医学/放射線治療/線量管理/画像診断AI等なら専門扱い。
    """

    text = article_text(x)
    title = (x.get('title') or x.get('headline') or '').lower()
    domain = dom(x.get('url', ''))

    if any(k.lower() in text for k in NON_RADIOLOGY_TERMS):
        return False

    if re.search(r'^画像\s*\d+\s*/\s*\d+', title):
        return False

    if domain in MARKET_REPORT_DOMAINS and any(
        k in title for k in ('市場', '市場規模', '市場動向', 'シェア', '成長分析', '業界予測', '市場レポート')
    ):
        return False

    direct_context = (
        '業務', '業務範囲', 'タスクシフト', 'タスクシェア', '教育', '研修',
        '国家試験', '資格', '認定', '職能', 'STAT', '学会', '病院',
        '放射線部', '放射線科', '検査', '撮影', '被ばく', '線量', '画像',
        'CT', 'MRI', '核医学', 'SPECT', 'PET', '放射線治療', '診療', '制度',
        '講習', '実習', '告示研修', '養成', '確保', 'アンケート', 'ガイドライン'
    )

    if any(k.lower() in text for k in DIRECT_TERMS):
        # 「放射線技師」という語だけの一般記事は専門扱いしない
        if any(k.lower() in text for k in direct_context):
            return True

    specialist_terms = (
        'CT',
        'MRI',
        'FPD',
        '一般撮影',
        'マンモグラフィ',
        '核医学',
        'SPECT',
        'PET',
        '放射線治療',
        '被ばく',
        '線量管理',
        '医療被ばく',
        '線量最適化',
        '放射線安全',
        '画像診断AI',
        '画像診断支援',
        '読影支援',
        '医用画像',
        'X線撮影',
        'タスクシフト',
        'タスクシェア',
        '診療用放射線',
        '診療報酬',
        '放射線医療機器',
    )

    # 公式機関の更新は、職能・制度・安全・教育に直接関係する場合に
    # 専門ニュースとして採用する。一般メディアのCT/MRI言及だけでは
    # 専門枠に入れず、一般ニュース側で扱う。
    if is_official(x.get('url', '')):
        return any(k.lower() in text for k in specialist_terms)

    return False


# Google News 経由だと URL が news.google.com になるため、配信元名でも公式情報を判定する。
OFFICIAL_SOURCE_NAMES = (
    '日本診療放射線技師会', 'jart',
    '日本放射線技術学会', 'jsrt',
    '日本医学放射線学会',
    '日本核医学会', '日本核医学技術学会',
    '日本放射線腫瘍学会',
    '日本医学物理学会',
    '日本磁気共鳴医学会',
    '厚生労働省', '原子力規制委員会',
    '医薬品医療機器総合機構', 'pmda',
    '日本医療機能評価機構',
    '日本消化器がん検診学会', '精中機構',
    '日本放射線腫瘍学会', '日本医学物理学会', '日本磁気共鳴医学会', '日本磁気共鳴専門技術者認定機構',
    '日本ivr学会', '日本超音波医学会', '日本核医学技術学会', '日本ct技術学会',
    '香川県診療放射線技師会', '中国・四国支部',
    '岡山県診療放射線技師会', '愛媛県診療放射線技師会', '徳島県診療放射線技師会', '高知県診療放射線技師会',
    '日本乳腺甲状腺超音波医学会', '日本超音波検査学会', '日本x線ct専門技師認定機構', 'dcis研究会', '日本乳癌学会', 'mrifan.net',
    '日本乳癌検診学会', '日本ct検診学会', '日本放射線治療専門放射線技師認定機構', '日本救急撮影技師認定機構',
)

# 高: 自分の部署で確認・対応が必要になりうる情報
IMPORTANCE_HIGH_TERMS = (
    # 制度・報酬・法令
    '診療報酬', '報酬改定', '補助金', '法改正', '省令', '施行規則', '医療法',
    'タスクシフト', 'タスクシェア', '業務範囲', '指定規則',
    # 放射線安全
    '医療被ばく', '被ばく線量', '線量管理', '診断参考レベル', 'drl',
    # 薬剤・装置の供給と安全性
    '限定出荷', '出荷停止', '供給停止', '供給不足', '出荷調整',
    'リコール', '自主回収', '安全性情報', '添付文書改訂', '医療機器の回収',
    # 医療事故の再発防止情報(医療機能評価機構・PMDAの医療安全情報など)
    '医療安全情報', '注意喚起', '再発防止', '医療事故',
    # 点数の変更
    '管理加算', '加算', '保険診療',
    # 会員・患者情報
    '個人情報漏えい', '個人情報漏洩', '不審アクセス', 'サイバー攻撃',
    # 指針
    'ガイドライン改訂', 'ガイドライン公表', 'ガイドラインを改訂', '指針改訂',
)

# 研修・講習会などの開催案内は「高」の語を含んでも「中」までにする
EVENT_TERMS = (
    '研修', '講習', 'セミナー', '講演会', '学術大会', '勉強会', 'ウェビナー',
    '開催', '開講', '募集', '参加者',
)

# 中: 国内の装置・AIの承認や導入
IMPORTANCE_MID_TERMS = (
    '供給回復',
    '薬事承認', '承認取得', '国内初', '日本初', '国内で初', '保険適用',
)

# 低: 業務への影響が小さい話題
IMPORTANCE_LOW_TERMS = (
    '逮捕', '停職', '懲戒', '書類送検', '不起訴',
    'ペット', '動物病院', '犬', '猫',
    '市場規模', '市場予測', '億米ドル', 'cagr',
    'ベトナム', 'vietnam', '韓国',
    '漫画', 'マンガ', 'インタビュー', '体験', 'フェア',
)


def is_official_source(x):
    src = str(x.get('source') or '').lower()
    return any(name.lower() in src for name in OFFICIAL_SOURCE_NAMES)


def importance(x, official):
    # 判定は見出しと要約だけで行う(配信元名に含まれる語で誤判定しないため)
    t = ' '.join(
        str(basis(x, k) or '') for k in ('title', 'headline', 'description', 'summary')
    ).lower()
    official = official or is_official_source(x)

    def has(terms):
        return any(k.lower() in t for k in terms)

    if has(IMPORTANCE_LOW_TERMS) and not official:
        return '低'

    # 「画像診断ガイドライン2026年度版の全記事の公開」のように語が離れている場合も拾う
    guideline_release = re.search(r'(ガイドライン|指針).{0,30}(公開|公表|改訂|発刊|刊行)', t) \
        or (official and re.search(r'ガイドライン|指針|提言|勧告', t) and not re.search(r'研修|セミナー|講習|講演|募集|パブリックコメント|対応研修', t))
    # 学会・団体の声明は撮影手技の見直しなど実務に直結する
    official_statement = official and '声明' in t

    if has(IMPORTANCE_HIGH_TERMS) or guideline_release or official_statement:
        if has(EVENT_TERMS):
            return '中'
        return '高'

    if official:
        return '中'

    if has(IMPORTANCE_MID_TERMS):
        return '中'

    return '低'


# 記事ごとの一言(ポイント)。上から順に最初に当てはまったものを使う。
# どれにも当てはまらない記事は空欄にする(全記事に同じ定型文を付けない)。
# 研修の案内や新製品の話題など、記事の種類を言い直すだけになる一言は入れない。
TECHNOLOGIST_NOTES = (
    (('限定出荷', '出荷停止', '供給停止', '供給不足', '出荷調整'),
     '自施設で使っている薬剤か確認し、代替品や検査予定への影響を把握しておきましょう。'),
    (('供給回復',),
     '供給が通常に戻りました。代替品に切り替えていた場合は戻す時期を確認しましょう。'),
    (('リコール', '自主回収', '安全性情報', '添付文書改訂', '医療機器の回収'),
     '自施設に該当する機器・薬剤がないか確認しておきましょう。'),
    (('個人情報漏えい', '個人情報漏洩', '不審アクセス'),
     '登録しているメールアドレスに不審なメールが届いていないか注意しましょう。'),
    (('サイバー攻撃', 'ランサムウェア'),
     'PACS・RISが止まったときに検査をどう続けるか、ダウンタイム時の手順を確認しておきましょう。'),
    (('医療安全情報', '注意喚起', '再発防止', '医療機能評価機構'),
     '自分の検査で同じ確認漏れが起きないか、問診やチェックの手順を見直すきっかけにしましょう。'),
    (('声明',),
     '撮影手技の見直しにつながる内容です。推奨が変わった点と根拠を確認しておきましょう。'),
    (('__guideline_release__',),
     '推奨内容の変更点を確認し、普段の撮影条件やプロトコルと照らし合わせておきましょう。'),
    (('診療報酬', '報酬改定', '施設基準', '加算', '保険診療'),
     '算定要件や点数の変更点を押さえておきましょう。担当する検査の算定に関わることがあります。'),
    (('告示研修',),
     '業務範囲の拡大に伴う告示研修です。未受講なら日程と申込方法を確認しておきましょう。'),
    (('パブリックコメント', 'パブコメ'),
     '意見募集の締切と、改訂される点を確認しておきましょう。'),
    (('原稿募集', '留学生', '候補者', '公募'),
     '応募条件と締切を確認しておきましょう。'),
    (('受験票', '認定試験', '検査士試験'),
     '受験する場合は、試験日や受験票などの案内を見落とさないよう確認しておきましょう。'),
    (('認定更新', '資格更新', '更新申請', '新規申請', '認定施設', '施設認定', '認定証'),
     '自分や施設が対象か確認し、申請の期限と必要な単位・書類を確認しておきましょう。'),
    (('認証申請', '認証一覧'),
     '自施設の装置・ソフトウェアが対象になるか確認しておきましょう。'),
    (('脆弱性', '一時閉鎖', '一時休止', '視聴できない', '視聴不具合', 'ページが開かない'),
     '会員ページやeラーニングを使う予定があれば、止まる時間や再開の時期を確認しておきましょう。'),
    (('マニュアル', 'q&a', 'q＆a', '基本的考え方', '診断基準'),
     '自施設の手順やプロトコルと違いがないか照らし合わせておきましょう。'),
    (('アンケート', '実態調査', '調査へのご協力'),
     '対象者と回答期限を確認しておきましょう。'),
    (('法改正', '省令', '施行規則', '医療法', '指定規則', '業務範囲', 'タスクシフト', 'タスクシェア'),
     '自分の業務範囲や手順に関わる変更がないか確認しておきましょう。'),
    (('医療被ばく', '被ばく線量', '線量管理', '診断参考レベル', 'drl'),
     '線量管理やDRLとの比較の考え方を見直すきっかけになります。'),
)


def technologist_note(x):
    """重要度「低」以外の記事に、判定理由に応じた一言を返す。"""
    if x.get('importance') == '低':
        return ''
    t = ' '.join(
        str(basis(x, k) or '') for k in ('title', 'headline', 'description', 'summary')
    ).lower()
    # ガイドラインかどうかは見出しで決める(元のページの要約には「提言」などが背景説明として出てくるため)
    head = ' '.join(str(x.get(k) or '') for k in ('title', 'headline')).lower()
    flags = {
        '__guideline_release__': bool(re.search(r'(ガイドライン|指針).{0,30}(公開|公表|改訂|発刊|刊行)', head)
                                      or ((is_official(x.get('url', '')) or is_official_source(x))
                                          and re.search(r'ガイドライン|指針|提言|勧告', head)
                                          and not re.search(r'研修|セミナー|講習|講演|募集|パブリックコメント', head))),
    }
    for terms, note in TECHNOLOGIST_NOTES:
        if any(flags.get(k) if k in flags else k.lower() in t for k in terms):
            return note
    return ''


PREFECTURES = (
    '北海道', '青森', '岩手', '宮城', '秋田', '山形', '福島', '茨城', '栃木', '群馬', '埼玉', '千葉', '東京', '神奈川',
    '新潟', '富山', '石川', '福井', '山梨', '長野', '岐阜', '静岡', '愛知', '三重', '滋賀', '京都', '大阪', '兵庫',
    '奈良', '和歌山', '鳥取', '島根', '岡山', '広島', '山口', '徳島', '香川', '愛媛', '高知', '福岡', '佐賀', '長崎',
    '熊本', '大分', '宮崎', '鹿児島', '沖縄',
)
_DATE_YMD = re.compile(r'(?<!\d)(20\d{2})/(\d{1,2})/(\d{1,2})(?!\d)')
_DATE_MD = re.compile(r'(?<!\d)(\d{1,2})月(\d{1,2})日')
_NOT_EVENT_AFTER = re.compile(r'^\s*(\d{1,2}[:：]\d{2}\s*)?(更新|追記|掲載|発売|付)')


def _to_date(y, m, d):
    try:
        return datetime(int(y), int(m), int(d)).date()
    except ValueError:
        return None


def extract_schedule(x):
    """研修・講習会の案内から開催日(または申込締切)と開催地を取り出す。

    戻り値: {'event_date': 'YYYY-MM-DD', 'event_kind': '開催'|'申込締切', 'event_place': str} または {}
    """
    head = str(x.get('headline') or x.get('title') or '')
    text = head + ' ' + str(basis(x, 'summary') or '')
    low = text.lower()
    if not (any(k.lower() in low for k in EVENT_TERMS) or '告示研修' in text):
        return {}
    if any(k in text for k in ('報告', '中止', '延期', '遅延')):
        return {}
    try:
        base = datetime.fromisoformat(str(x.get('date'))[:10]).date()
    except ValueError:
        base = datetime.now(JST).date()

    def md_date(m, d):
        dt = _to_date(base.year, m, d)
        if dt and (base - dt).days > 60:      # 「1月9日」が年明けを指す場合
            dt = _to_date(base.year + 1, m, d)
        return dt

    found = None
    # 申込締切: 「申込は10月1日正午～11月26日正午」のように範囲の終わりを使う
    m = re.search(r'(申込|申し込み|受付|締切|〆切)[^。]{0,30}?[～〜\-－]\s*(\d{1,2})月(\d{1,2})日', text) \
        or re.search(r'(申込|申し込み|受付)(締切|期限)[はが：:\s]*(\d{1,2})月(\d{1,2})日', text)
    if m:
        mm, dd = m.groups()[-2:]
        dt = md_date(mm, dd)
        if dt:
            found = (dt, '申込締切')
    if not found:
        head_wo_prefix = re.sub(r'^\s*\d{4}/\d{1,2}/\d{1,2}\s+(お知らせ|会告/告示|会告|告示)', '', head)
        for pat, conv in ((_DATE_YMD, lambda g: _to_date(*g)), (_DATE_MD, lambda g: md_date(*g))):
            for mt in pat.finditer(head_wo_prefix):
                if _NOT_EVENT_AFTER.match(head_wo_prefix[mt.end():]):
                    continue
                dt = conv(mt.groups())
                if dt:
                    found = (dt, '開催')
                    break
            if found:
                break
    if not found:
        return {}
    place = ''
    for pref in PREFECTURES:
        if pref in head:
            place = pref
            break
    if not place and re.search(r'web|ウェブ|オンライン|eラーニング|e-ラーニング|ウェビナー', low):
        place = 'オンライン'
    return {'event_date': found[0].isoformat(), 'event_kind': found[1], 'event_place': place}


def clean_summary(x):
    """見出しをそのまま繰り返しているだけの要約は空にする。"""
    summary = str(x.get('summary') or '').strip()
    source = str(x.get('source') or '').strip()
    if source and summary.endswith(source):
        summary_wo_source = summary[:-len(source)].strip()
    else:
        summary_wo_source = summary
    head = canonical_title(x.get('headline') or x.get('title'))
    if canonical_title(summary_wo_source) == head:
        return ''
    body = canonical_title(re.sub(r'\s+\S+$', '', summary))  # 末尾の媒体名を除く
    if not summary or same_story(head, canonical_title(summary)) or same_story(head, body):
        return ''
    return summary


# --------------------------------------------------
# 記事の要約(元のページの説明文か本文の最初の段落)
# --------------------------------------------------
SUMMARY_MAX_PER_RUN = 40   # 1回に読みに行く記事数(新着を先に、残りで過去分を少しずつ埋める)
SUMMARY_LEN = 140
_SITE_DESCRIPTIONS = {}    # サイト共通の説明文(どの記事にも同じ文が入っているもの)は要約に使わない
GNEWS_DECODE = 'https://news.google.com/_/DotsSplashUi/data/batchexecute'


def resolve_google_news(url):
    """Googleニュースの転送URLから元記事のURLを得る(非公開の仕組みなので、失敗したら空を返す)。"""
    m = re.search(r'news\.google\.com/(?:rss/)?articles/([^?/]+)', url)
    if not m:
        return url
    aid = m.group(1)
    try:
        page = fetch('https://news.google.com/rss/articles/' + aid, timeout=15)
        sg = re.search(r'data-n-a-sg="([^"]+)"', page)
        ts = re.search(r'data-n-a-ts="([^"]+)"', page)
        if not (sg and ts):
            return ''
        req = [['Fbv4je', '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
                f'"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{aid}",{ts.group(1)},"{sg.group(1)}"]']]
        body = ('f.req=' + quote(json.dumps([req]))).encode()
        headers = dict(_HEADERS, **{'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'})
        with urlopen(Request(GNEWS_DECODE, data=body, headers=headers), timeout=15) as r:
            text = r.read().decode('utf-8', 'ignore')
        real = json.loads(json.loads(text.split('\n\n')[1])[0][2])[1]
        return real if real.startswith('http') else ''
    except Exception as e:
        print('Google News decode error:', type(e).__name__, e)
        return ''


def _meta_description(page):
    for pat in (r'<meta[^>]+property=["\']og:description["\'][^>]*content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:description',
                r'<meta[^>]+name=["\']description["\'][^>]*content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*name=["\']description'):
        m = re.search(pat, page, re.I)
        if m:
            return clean_html(m.group(1))
    return ''


def _first_paragraph(page):
    body = re.sub(r'(?is)<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>', ' ', page)
    for p in re.findall(r'(?is)<p[^>]*>(.*?)</p>', body):
        t = clean_html(p)
        if 40 <= len(t) <= 800 and '。' in t and not re.search(r'cookie|クッキー|JavaScript|ログイン|Copyright|©', t, re.I):
            return t
    return ''


def shorten(text, limit=SUMMARY_LEN):
    """文の切れ目でなるべく短くする。"""
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= limit:
        # サイト側で途中まで切られた説明文は、続きがあることが分かるようにする
        return text if not text or re.search(r'[。！？!?）」』.…]$', text) else text + '…'
    cut = text.rfind('。', 0, limit)
    return text[:cut + 1] if cut >= limit // 3 else text[:limit].rstrip() + '…'


def site_description(url):
    root = re.match(r'https?://[^/]+/', url + '/')
    key = root.group(0) if root else url
    if key not in _SITE_DESCRIPTIONS:
        try:
            _SITE_DESCRIPTIONS[key] = _meta_description(fetch(key, timeout=15))
        except Exception:
            _SITE_DESCRIPTIONS[key] = ''
    return _SITE_DESCRIPTIONS[key]


GREETING = re.compile(r'の候|ご清祥|ご清栄|ご健勝|お慶び申し上げ|御礼申し上げ|ご高配|お世話になって')


def drop_greetings(text):
    """手紙の書き出し(時候のあいさつ・お礼)の文は要約から除く。"""
    return ''.join(s for s in re.findall(r'[^。]+。?', text) if not GREETING.search(s)).strip()


def page_summary(page, url):
    desc = _meta_description(page)
    site = site_description(url)
    # 「題名｜サイト全体の紹介文」の形(香川県技師会など)も、記事の要約ではない
    if desc and (desc == site or (site and site in desc) or len(desc) < 20):
        desc = ''
    return shorten(drop_greetings(desc or _first_paragraph(page)))


def fetch_summary(url):
    real = resolve_google_news(url)
    if not real or re.search(r'\.(pdf|docx?|xlsx?|zip)(\?|$)', real, re.I):
        return ''
    try:
        page = fetch(real, timeout=15)
    except Exception as e:
        print('summary fetch error:', type(e).__name__, real[:80])
        return ''
    return page_summary(page, real)


_TITLE_PLUS_SITE = re.compile(r'^(.{4,}?)\s*[｜|]\s*\S')


def fill_summaries(items, new_urls):
    """要約が空の記事に、元のページから要約を付ける。一度試した記事は summary_tried を付けて再取得しない。"""
    for x in items:   # 以前に付けた「題名｜サイト全体の紹介文」の要約は、取り直す
        m = _TITLE_PLUS_SITE.match(x.get('summary') or '') if x.get('summary_tried') else None
        if m and m.group(1).strip() == (x.get('headline') or '').strip() \
                and (lambda site, rest: site and rest and site.startswith(rest))(   # 要約は140字で切ってある
                    site_description(x.get('url', '')), x['summary'][m.end() - 1:].rstrip('…').strip()):
            x['summary'] = ''
            x.pop('summary_tried')
    todo = [x for x in items if not x.get('summary') and not x.get('summary_tried')]
    todo.sort(key=lambda x: x.get('url') not in new_urls)   # 新着を先に
    filled = 0
    for x in todo[:SUMMARY_MAX_PER_RUN]:
        x['summary_tried'] = datetime.now(JST).date().isoformat()
        s = fetch_summary(x.get('url', ''))
        if s:
            x['summary'] = s
            x['summary'] = clean_summary(x)
            filled += bool(x['summary'])
    SOURCE_STATUS['要約'] = {'tried': min(len(todo), SUMMARY_MAX_PER_RUN), 'filled': filled, 'remaining': max(0, len(todo) - SUMMARY_MAX_PER_RUN)}
    print(f'summaries: {filled} filled, {SOURCE_STATUS["要約"]["remaining"]} remaining')


def score(x):
    t = article_text(x)
    s = 0

    if any(
        k.lower() in t
        for k in DIRECT_TERMS
    ):
        s += 12

    if is_official(x.get('url', '')) \
            or x.get('source') == 'JART':
        s += 4

    if any(
        k.lower() in t
        for k in (
            '制度',
            '診療報酬',
            '補助金',
            '安全管理',
            '被ばく',
            '線量管理',
            '装置更新',
            'タスクシフト',
            'タスクシェア',
            'ガイドライン',
        )
    ):
        s += 4

    if any(
        k.lower() in t
        for k in STRONG_MODALITY_TERMS
    ):
        s += 3

    if any(
        k.lower() in t
        for k in (
            'CT',
            'MRI',
            'SPECT',
            'PET',
            'FPD',
            'マンモグラフィ',
            '放射線治療',
        )
    ):
        s += 2

    if any(
        k.lower() in t
        for k in (
            '漫画',
            'マンガ',
            '芸能',
            '俳優',
            '女優',
            'アイドル',
            'タレント',
        )
    ):
        s -= 20

    return s


def archive_items(items):
    """news.json から外れる記事を archive/YYYY-MM.json に追記し、月の一覧を更新する。"""
    if not items:
        return
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    by_month = {}
    for x in items:
        month = str(feed_date(x) or x.get('date') or '')[:7]
        if re.fullmatch(r'20\d{2}-\d{2}', month):
            by_month.setdefault(month, []).append(x)
    for month, new in by_month.items():
        path = ARCHIVE_DIR / f'{month}.json'
        try:
            old = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            old = []
        urls = {x.get('url') for x in old}
        merged = old + [x for x in new if x.get('url') not in urls]
        merged.sort(key=lambda x: str(feed_date(x) or ''), reverse=True)
        path.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding='utf-8')
    write_archive_index()


def write_archive_index():
    months = []
    for path in sorted(ARCHIVE_DIR.glob('20??-??.json'), reverse=True):
        try:
            months.append({'month': path.stem, 'count': len(json.loads(path.read_text(encoding='utf-8')))})
        except Exception:
            continue
    (ARCHIVE_DIR / 'index.json').write_text(json.dumps({'months': months}, ensure_ascii=False, indent=1), encoding='utf-8')


def retention_cutoff(today=None):
    """この日付より前のデータは保存期間切れ。"""
    return ((today or datetime.now(JST).date()) - timedelta(days=RETENTION_DAYS)).isoformat()


def is_expired(item, cutoff):
    """日付が読めない記事は、誤って消さないよう残す。"""
    day = str(feed_date(item) or '')[:10]
    return bool(re.fullmatch(r'20\d{2}-\d{2}-\d{2}', day)) and day < cutoff


def prune_old_data(cutoff):
    """月別アーカイブと daily_html から保存期間切れの分を消す。"""
    changed = False
    for path in ARCHIVE_DIR.glob('20??-??.json'):
        try:
            items = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        keep = [x for x in items if not is_expired(x, cutoff)]
        if len(keep) == len(items):
            continue
        changed = True
        if keep:
            path.write_text(json.dumps(keep, ensure_ascii=False, indent=1), encoding='utf-8')
        else:
            path.unlink()
    if changed:
        write_archive_index()
    for path in HTML_DIR.glob('放射線技師ニュース_*.html'):
        day = path.stem.rsplit('_', 1)[-1]
        if re.fullmatch(r'20\d{2}-\d{2}-\d{2}', day) and day < cutoff:
            path.unlink()


SITE_URL = 'https://hijikiogan-sudo.github.io/radiology-technologist-news/'


def build_notice(items):
    """要確認の新着をメール本文にする。"""
    lines = [f'今日の要確認が{len(items)}件あります。', '']
    for x in items:
        lines.append('■ ' + str(x.get('headline') or ''))
        if x.get('why'):
            lines.append('  ポイント: ' + x['why'])
        lines.append('  ' + str(x.get('source') or '') + '  ' + str(x.get('url') or ''))
        lines.append('')
    lines.append('一覧: ' + SITE_URL)
    subject = f'【技師ニュース】要確認 {len(items)}件: ' + str(items[0].get('headline') or '')[:40]
    return subject, '\n'.join(lines)


def notify_high(items):
    """新しく入った要確認を Gmail で自分宛てに知らせる。

    GitHub の Secrets に GMAIL_USER と GMAIL_APP_PASSWORD を登録したときだけ動く
    (NOTIFY_TO を登録すると宛先を変えられる。未登録なら GMAIL_USER 宛て)。
    """
    if not items:
        return 'no-items'
    return send_mail(*build_notice(items))


def send_mail(subject, body):
    user, password = os.environ.get('GMAIL_USER'), os.environ.get('GMAIL_APP_PASSWORD')
    if not (user and password):
        print('Mail notice skipped: GMAIL_USER / GMAIL_APP_PASSWORD not set')
        return 'not-configured'
    to = os.environ.get('NOTIFY_TO') or user
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'], msg['From'], msg['To'] = subject, user, to
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30) as smtp:
            smtp.login(user, password.replace(' ', ''))
            smtp.send_message(msg)
        print('Mail notice sent:', subject)
        return 'sent'
    except Exception as e:
        print('Mail notice error:', e)
        return 'error'


# --------------------------------------------------
# 情報源の不調(取れない日が続いたら画面とメールで知らせる)
# --------------------------------------------------
HEALTH_SKIP = ('メール通知', '要約', '不調の通知')
HEALTH_ALERT_DAYS = 3   # 3日続けて取れなかったら知らせる(1日だけの失敗は相手のサイトの一時的な不調が多い)


def source_failing(st):
    return bool(st.get('error')) or (st.get('listed') == 0 and not st.get('empty_ok'))


def track_source_health(status, previous, today):
    """前回の news_meta.json の記録と合わせて、失敗が続いている日数を記録する。知らせる情報源の名前を返す。"""
    alert = []
    for name, st in status.items():
        if name in HEALTH_SKIP or not isinstance(st, dict):
            continue
        prev = previous.get(name) if isinstance(previous.get(name), dict) else {}
        if not source_failing(st):
            st['last_ok'] = today.isoformat()
            continue
        if prev.get('last_ok'):
            st['last_ok'] = prev['last_ok']
        st['failing_since'] = prev.get('failing_since') or today.isoformat()
        days = (today - datetime.fromisoformat(st['failing_since']).date()).days + 1
        st['failing_days'] = days
        if prev.get('alerted'):
            st['alerted'] = True
        elif days >= HEALTH_ALERT_DAYS:
            st['alerted'] = True
            alert.append(name)
    return alert


def build_health_notice(names, status):
    lines = [f'{HEALTH_ALERT_DAYS}日以上続けて記事を取れていない情報源があります。サイトの作りが変わった可能性があります。', '']
    for name in names:
        st = status[name]
        why = st.get('error') or '一覧から記事を読み取れませんでした'
        lines.append(f'■ {name}（{st.get("failing_since")}から{st.get("failing_days")}日）')
        lines.append(f'  {why}')
        lines.append('')
    lines.append('一覧: ' + SITE_URL)
    return f'【技師ニュース】情報源の不調 {len(names)}件: ' + '、'.join(names)[:40], '\n'.join(lines)


def notify_source_health(previous):
    alert = track_source_health(SOURCE_STATUS, previous, datetime.now(JST).date())
    SOURCE_STATUS['不調の通知'] = {'result': send_mail(*build_health_notice(alert, SOURCE_STATUS)) if alert else 'no-items',
                                'items': len(alert)}


def load():
    try:
        return json.loads(
            NEWS_JSON.read_text(
                encoding='utf-8'
            )
        )
    except Exception:
        return []


def apply_curated_specialist(item):
    """Apply editor-reviewed detail without replacing the original source URL."""
    title = str(item.get('headline') or item.get('title') or '')
    for needle, metadata in CURATED_SPECIALIST:
        if needle in title:
            item.update(metadata)
            item['track'] = 'official'
            break
    return item


def canonical_title(title):
    """Collapse duplicate titles that differ only by outlet name or decoration.

    Google News titles end with " - 媒体名", syndicated copies add "【画像】" or
    "(東海テレビ)", and JART's own list prefixes "2026/10/19 お知らせ".
    """
    t = str(title or '').strip()
    t = re.sub(r'\s+-\s+[^-]{1,40}$', '', t)                      # " - ライブドアニュース"
    # "(東海テレビ)" "（PR TIMES）" のような媒体名だけを外す。
    # "（2026/10/14更新）" "（第3部）" のように記事を区別する括弧は残す。
    m = re.search(r'\s*[\(（]([^()（）]{1,20})[\)）]\s*$', t)
    if m and not re.search(r'[0-9０-９第部章編回版号更新]', m.group(1)):
        t = t[:m.start()]
    t = re.sub(r'\s*\d+枚目/全\d+枚.*$', '', t)                    # "3枚目/全44枚 1448871"
    t = re.sub(r'^\s*(?:【[^】]{1,30}】|［[^］]{1,10}］|\[[^\]]{1,10}\])\s*', '', t)   # 【画像】【JIRA…】［案内板］［お知らせ］
    t = re.sub(r'^\s*\d{4}/\d{1,2}/\d{1,2}\s+(?:お知らせ|会告/告示|会告|告示)?\s*', '', t)
    return norm(t)


MIN_PREFIX_MATCH = 24


def same_story(a, b):
    """True when two canonical titles are the same story (one may be truncated)."""
    if not a or not b:
        return False
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    return len(short) >= MIN_PREFIX_MATCH and long_.startswith(short)


def find_story(key, kept):
    """Return the already-kept item whose title is the same story as key."""
    for k, item in kept:
        if same_story(key, k):
            return item
    return None


def merge_duplicate(keep, dup):
    """Record a duplicate's outlet on the kept item instead of discarding it."""
    also = keep.setdefault('also', [])
    urls = {keep.get('url')} | {a.get('url') for a in also}
    for entry in [{'source': dup.get('source'), 'url': dup.get('url')}] + list(dup.get('also') or []):
        if entry.get('url') and entry['url'] not in urls:
            also.append({'source': entry.get('source') or dom(entry['url']), 'url': entry['url']})
            urls.add(entry['url'])
    if not also:
        keep.pop('also', None)


def clean_db(db):
    today = datetime.now(JST).date()
    out = []
    kept = []  # (canonical title, item)
    seen_urls = set()

    for x in db:
        try:
            item_date = datetime.fromisoformat(
                str(x.get('date', '')).replace(
                    'Z',
                    '+00:00'
                )
            ).date()

            if item_date > today:
                continue

        except Exception:
            continue

        if not relevant(x):
            continue

        if not is_news_item(x):
            continue

        x = apply_curated_specialist(x)
        k = canonical_title(x.get('headline'))

        if not k and not x.get('url'):
            continue

        if x.get('url') in seen_urls:
            continue

        # 同じ記事の別媒体版は捨てずに、残す1件の「他の配信元」に記録する。
        original = find_story(k, kept) if k else None
        if original is not None:
            merge_duplicate(original, x)
            seen_urls.add(x.get('url'))
            continue

        seen_urls.add(x.get('url'))
        seen_urls.update(a.get('url') for a in x.get('also') or [])
        kept.append((k, x))

        # 分類ルールの改善を過去分にも反映する(手動指定のカテゴリは後で上書きされる)
        x['category'] = category(x)
        # 専門学会の記事は、一般的な分類なら学会の分野にそろえる
        if x['category'] in ('その他', '学術', '教育', '制度') and normalize_source(x.get('source')) in SPECIALTY_DEFAULT_CATEGORY:
            x['category'] = SPECIALTY_DEFAULT_CATEGORY[normalize_source(x.get('source'))]
        x['importance'] = importance(
            x,
            is_official(x.get('url', '')) or x.get('source') == 'JART'
        )
        x['summary'] = clean_summary(x)
        x['why'] = technologist_note(x)
        for k in ('event_date', 'event_kind', 'event_place'):
            x.pop(k, None)
        x.update(extract_schedule(x))

        # 過去データも現行の選定基準で再分類し、表示のズレを残さない。
        # 重要度「高」は業務に直結するので、一般メディア発でも専門ニュース側に出す
        x['track'] = (
            'official'
            if is_specialist(x) or x.get('importance') == '高'
            else 'general'
        )

        out.append(normalize_sources(apply_curated_specialist(x)))

    return out


def make_item(x):
    official = (
        is_official(x.get('url', ''))
        or x.get('source') == 'JART'
    )

    item = {
        'date': x['published'][:10],
        'category': category(x),
        'importance': importance(
            x,
            official
        ),
        'headline': x['title'],
        'summary': re.sub(
            r'\s+',
            ' ',
            x.get('description', '')
        ).strip()[:220],
        'why': '',
        'source': (
            x.get('source')
            or dom(x['url'])
        ),
        'url': x['url'],
        'track': (
            'official'
            if official
            else 'general'
        ),
    }
    item['summary'] = clean_summary(item)
    item['why'] = technologist_note(item)
    item.update(extract_schedule(item))
    return normalize_sources(apply_curated_specialist(item))


def main():
    cutoff = (
        datetime.now(JST)
        - timedelta(hours=72)
    )
    ongoing_cutoff = (
        datetime.now(JST)
        - timedelta(days=30)
    )

    db = clean_db(load())

    known_titles = [canonical_title(x.get('headline')) for x in db]
    known_urls = {x.get('url') for x in db}
    for x in db:
        known_urls.update(a.get('url') for a in x.get('also') or [])

    def is_known(item):
        if item['url'] in known_urls:
            return True
        k = canonical_title(item['title'])
        return any(same_story(k, t) for t in known_titles)

    candidates = {}

    # JART直接取得
    for x in direct_jart():
        try:
            if datetime.fromisoformat(
                x['published']
            ) < cutoff:
                continue
        except Exception:
            continue

        if not is_known(x):
            candidates[x['url']] = x

    # 医療安全情報(新しい号だけ。既にある号は is_known で除く)
    safety_new = [x for x in direct_safety_info() if not is_known(x)]
    # 学会・厚労省の新着(Googleニュースの件数枠とは別に入れる)
    official_new = [x for x in direct_official_news() if not is_known(x)]
    # PMDAの医療機器回収と、造影剤の供給状況の変化
    official_new += [x for x in direct_pmda_recalls() + update_supply() if not is_known(x)]
    update_papers()

    # Google News RSS
    for q in QUERIES:
        try:
            for x in rss(q):

                try:
                    published = datetime.fromisoformat(
                        x['published']
                    )
                except Exception:
                    continue

                if published < cutoff:
                    if not (is_official(x.get('url','')) and any(k.lower() in article_text(x) for k in ('継続','アンケート','募集','受付','ガイドライン','研修','講習')) and published >= ongoing_cutoff):
                        continue

                if not relevant(x):
                    continue

                if not is_news_item(x):
                    continue

                if not is_known(x):
                    candidates[x['url']] = x

        except Exception as e:
            print('RSS error:', e)

    # --------------------------------------------------
    # 専門ニュースと一般ニュースを分離して選ぶ
    # --------------------------------------------------

    fresh = list(candidates.values())

    specialist = [
        x for x in fresh
        if is_specialist(x)
    ]

    general = [
        x for x in fresh
        if not is_specialist(x)
    ]

    specialist.sort(
        key=lambda x: (
            score(x),
            x.get('published', '')
        ),
        reverse=True
    )

    general.sort(
        key=lambda x: (
            score(x),
            x.get('published', '')
        ),
        reverse=True
    )

    # --------------------------------------------------
    # 専門ニュース
    # 最大5件
    # 「技師」という語がなくても実務関連なら採用
    # --------------------------------------------------

    added = []
    specialist_titles = set()

    # 医療安全情報・学会・厚労省の新着は件数枠とは別に必ず載せる
    for x in safety_new + official_new:
        item = make_item(x)
        item['track'] = 'official'
        added.append(item)
        specialist_titles.add(canonical_title(x['title']))

    for x in specialist:
        if len(specialist_titles) >= 5:
            break
        k = canonical_title(x['title'])

        if not k or any(same_story(k, t) for t in specialist_titles):
            continue

        specialist_titles.add(k)

        item = make_item(x)

        # 専門ニュースとして明示
        item['track'] = 'official'

        added.append(item)

    # --------------------------------------------------
    # 一般ニュース
    # 最大5件
    # 専門ニュースとは別枠
    # --------------------------------------------------

    general_titles = set()

    for x in general:
        if len(general_titles) >= 5:
            break
        k = canonical_title(x['title'])

        if not k or any(same_story(k, t) for t in specialist_titles | general_titles):
            continue

        general_titles.add(k)

        item = make_item(x)
        item['track'] = 'general'

        added.append(item)

    # --------------------------------------------------
    # DBへ保存
    # --------------------------------------------------

    final = clean_db(
        added + db
    )

    # 万一、新規データが全部clean_dbで落ちても
    # 既存データを壊さない
    if added and not final:
        final = added + db

    fill_summaries(final[:MAX_RECENT], {x['url'] for x in added})

    # 保存期間を過ぎた記事は消し、上限を超えた分は月別アーカイブへ移す
    cutoff = retention_cutoff()
    final = [x for x in final if not is_expired(x, cutoff)]
    archive_items(final[MAX_RECENT:])
    final = final[:MAX_RECENT]
    NEWS_JSON.write_text(
        json.dumps(final, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )

    update_seminars()
    update_kagawa()

    # 今回新しく入った記事のうち、毎日の整理を通って「高」になったものだけ知らせる
    added_urls = {x['url'] for x in added}
    new_high = [x for x in final if x.get('url') in added_urls and x.get('importance') == '高']
    SOURCE_STATUS['メール通知'] = {'result': notify_high(new_high), 'items': len(new_high)}
    try:
        previous = json.loads(META_JSON.read_text(encoding='utf-8')).get('sources') or {}
    except Exception:
        previous = {}
    notify_source_health(previous)

    META_JSON.write_text(
        json.dumps({
            'checked_at': datetime.now(JST).isoformat(timespec='minutes'),
            'added': len(added),
            'total': len(final),
            'sources': SOURCE_STATUS,
        }, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )

    HTML_DIR.mkdir(parents=True, exist_ok=True)
    today_str = datetime.now(JST).date().isoformat()
    (HTML_DIR / f'放射線技師ニュース_{today_str}.html').write_text(
        build_daily_html(final, today_str),
        encoding='utf-8'
    )
    prune_old_data(cutoff)

    print(
        f'Added {len(added)} new items; '
        f'database now has {len(final[:200])} items.'
    )

    print(
        f'Specialist candidates: '
        f'{len(specialist)}'
    )

    print(
        f'General candidates: '
        f'{len(general)}'
    )

    for x in added:
        print(
            x['date'],
            x['track'],
            x['category'],
            x['headline']
        )


if __name__ == '__main__':
    main()
