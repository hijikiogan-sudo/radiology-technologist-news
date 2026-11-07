"""研修の開催日・申込締切・開催地の読み取りテスト (python -m pytest tests/test_news_schedule.py)。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402


def sched(headline, summary='', date='2026-10-21'):
    return u.extract_schedule({'headline': headline, 'summary': summary, 'date': date})


@pytest.mark.parametrize('headline, summary, date, expected', [
    ('告示研修（実技研修）大阪府2026/12/13 - 日本診療放射線技師会', '', '2026-09-28', ('2026-12-13', '開催', '大阪')),
    ('告示研修（実技研修）東京都2027/1/9 - 日本診療放射線技師会', '', '2026-10-21', ('2027-01-09', '開催', '東京')),
    ('［お知らせ］医工連携：臨床ニーズマッチング会の開催について（10月23日）', '', '2026-10-16', ('2026-10-23', '開催', '')),
    ('［お知らせ］第66回放射線治療セミナー', 'IGRTを扱うWebセミナー。申込は10月1日正午～11月26日正午。', '2026-09-20',
     ('2026-11-26', '申込締切', 'オンライン')),
    ('冬季講習会のご案内（1月15日）', '', '2026-11-30', ('2027-01-15', '開催', '')),   # 年をまたぐ
])
def test_schedule_is_extracted(headline, summary, date, expected):
    r = sched(headline, summary, date)
    assert (r.get('event_date'), r.get('event_kind'), r.get('event_place')) == expected


@pytest.mark.parametrize('headline', [
    '告示研修（実技研修）2026年度 開催日程（2026/10/14更新）',     # 更新日は開催日ではない
    '【重要】不審アクセスについて (お詫び) 10月23日17:20追記',     # 研修の案内ではない
    '2026/10/19 お知らせ (入札広告) 会誌の編集・印刷業務',          # 先頭は掲載日
    '『ラジエーションハウス』21巻は11月18日発売',                    # 研修ではない
    '第62回秋季臨床大会 開催報告（10月5日）',                         # 終わった催し
])
def test_non_schedule_dates_are_ignored(headline):
    assert sched(headline) == {}
