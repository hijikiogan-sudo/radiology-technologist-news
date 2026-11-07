"""情報源の不調の記録と通知のテスト (python -m pytest tests/test_news_source_health.py)。実際には送信しない。"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402

TODAY = date(2026, 11, 3)


def test_ok_source_records_last_ok():
    status = {'日本核医学会': {'listed': 10, 'picked': 0}}
    assert u.track_source_health(status, {}, TODAY) == []
    assert status['日本核医学会']['last_ok'] == '2026-11-03'


def test_empty_but_normal_source_is_not_failing():
    status = {'PMDA回収クラスI': {'listed': 0, 'picked': 0, 'empty_ok': True},
              '日本乳癌検診学会誌': {'listed': 0, 'feed_entries': 0, 'added': 0, 'empty_ok': True}}
    assert u.track_source_health(status, {}, TODAY) == []
    assert all('failing_since' not in v for v in status.values())


def test_failure_is_counted_across_runs_and_alerted_once():
    prev = {'日本CT技術学会': {'error': 'HTTPError: 503', 'failing_since': '2026-11-01', 'last_ok': '2026-10-31'}}
    status = {'日本CT技術学会': {'error': 'HTTPError: 503'}}
    assert u.track_source_health(status, prev, TODAY) == ['日本CT技術学会']
    st = status['日本CT技術学会']
    assert st['failing_days'] == 3 and st['last_ok'] == '2026-10-31' and st['alerted']
    # 翌日も失敗していても、もう一度は知らせない
    again = {'日本CT技術学会': {'error': 'HTTPError: 503'}}
    assert u.track_source_health(again, status, date(2026, 11, 4)) == []
    assert again['日本CT技術学会']['failing_days'] == 4


def test_first_failure_is_not_alerted():
    status = {'厚生労働省': {'listed': 0, 'picked': 0}}
    assert u.track_source_health(status, {}, TODAY) == []
    assert status['厚生労働省']['failing_since'] == '2026-11-03'


def test_recovery_clears_failure():
    prev = {'厚生労働省': {'listed': 0, 'failing_since': '2026-10-30', 'alerted': True}}
    status = {'厚生労働省': {'listed': 120, 'picked': 1}}
    u.track_source_health(status, prev, TODAY)
    assert 'failing_since' not in status['厚生労働省'] and 'alerted' not in status['厚生労働省']


def test_health_mail_lists_sources(monkeypatch):
    sent = {}
    monkeypatch.setattr(u, 'send_mail', lambda subject, body: sent.update(subject=subject, body=body) or 'sent')
    monkeypatch.setattr(u, 'SOURCE_STATUS', {'日本CT技術学会': {'error': 'HTTPError: 503'}, 'メール通知': {'result': 'no-items'}})
    u.notify_source_health({'日本CT技術学会': {'error': 'x', 'failing_since': '2000-01-01'}})
    assert u.SOURCE_STATUS['不調の通知'] == {'result': 'sent', 'items': 1}
    assert '日本CT技術学会' in sent['subject'] and 'HTTPError: 503' in sent['body']
