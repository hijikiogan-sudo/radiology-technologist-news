"""医療安全情報(医療機能評価機構・PMDA)の直接取得のテスト (python -m pytest tests/test_news_safety_info.py)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402

# 実際の一覧ページと同じ形(年ごとのブロックに「分類 No.N：題名」のリンクが並ぶ)
MED_SAFE_HTML = '''
<h2>最新の医療安全情報</h2>
<p><a href="https://www.med-safe.jp/pdf/med-safe_239.pdf">医療機器等・検査 No.239：患者に植込まれた医療機器の確認不足（第2報）</a></p>
<h2>過去の医療安全情報</h2>
<div class="year">2026年（No.230～）
 <a href="https://www.med-safe.jp/pdf/med-safe_239.pdf">医療機器等・検査 No.239：患者に植込まれた医療機器の確認不足（第2報）</a>
 <a href="https://www.med-safe.jp/pdf/med-safe_238.pdf">薬剤 No.238：術前に休薬すべき糖尿病治療薬の休薬忘れ</a>
 <a href="https://www.med-safe.jp/pdf/med-safe_236.pdf">治療・処置・検査 No.236：<span>パニック値の</span>報告後の対応漏れ</a>
 <a href="https://www.med-safe.jp/pdf/med-safe_235.pdf">まとめ No.235：2025年に提供した医療安全情報（画像検査を含む）</a>
 <a href="/pdf/med-safe_201.pdf">検査 No.201：MRI検査時の金属の持ち込み</a>
</div>
'''

PMDA_HTML = '''
<table>
<tr><th>No.</th><th>発行年月日</th><th>タイトル</th></tr>
<tr><td>73</td><td>2026年4月</td><td><a href="/files/000280293.pdf">インスリン専用注射器の使用について</a></td></tr>
<tr><td>72</td><td>2026年2月</td><td><a href="/files/000278635.pdf">胃瘻カテーテル取扱い時の注意について</a></td></tr>
<tr><td>58</td><td>2020年8月</td><td><a href="/files/000236000.pdf">MRI検査時の注意について（その2）</a></td></tr>
</table>
'''


def test_med_safe_picks_newest_radiology_items():
    items = u.parse_med_safe(MED_SAFE_HTML)
    assert [x['no'] for x in items] == [239, 236, 201]          # 薬剤(238)・まとめ(235)は除く、重複(239)は1件
    assert items[0]['title'] == '患者に植込まれた医療機器の確認不足（第2報）'
    assert items[2]['url'] == 'https://www.med-safe.jp/pdf/med-safe_201.pdf'   # 相対パスも絶対URLに


def test_pmda_picks_radiology_rows_with_month():
    items = u.parse_pmda_safety(PMDA_HTML)
    assert len(items) == 1
    assert items[0]['no'] == 58 and items[0]['published'] == '2020-08-01'
    assert items[0]['url'] == 'https://www.pmda.go.jp/files/000236000.pdf'


def test_parsers_survive_unexpected_html():
    assert u.parse_med_safe('<html>メンテナンス中</html>') == []
    assert u.parse_pmda_safety('') == []


def test_fetch_failure_does_not_break_update(monkeypatch):
    def boom(url):
        raise OSError('network down')
    monkeypatch.setattr(u, 'fetch', boom)
    assert u.direct_safety_info() == []


def test_safety_item_is_high_and_kept(monkeypatch):
    monkeypatch.setattr(u, 'fetch', lambda url: MED_SAFE_HTML if 'med-safe' in url else PMDA_HTML)
    raw = u.direct_safety_info()
    assert raw[0]['title'].startswith('医療安全情報 No.239')
    item = u.make_item(raw[0])
    assert item['importance'] == '高'
    assert item['why']                                # 一言が付く
    assert item['source'] == '日本医療機能評価機構'
    assert u.clean_db([item])                          # 毎日の再処理で落ちない
