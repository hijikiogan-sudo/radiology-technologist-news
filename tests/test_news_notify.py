"""要確認のメール通知のテスト (python -m pytest tests/test_news_notify.py)。実際には送信しない。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402

ITEM = {'headline': '医療安全情報 No.239：患者の体内に植込まれた医療機器等の不十分な確認（第２報）',
        'why': '自分の検査で同じ確認漏れが起きないか見直しましょう。', 'source': '日本医療機能評価機構',
        'url': 'https://www.med-safe.jp/pdf/med-safe_239.pdf', 'importance': '高'}


def test_not_configured_means_no_mail(monkeypatch):
    for k in ('GMAIL_USER', 'GMAIL_APP_PASSWORD', 'NOTIFY_TO'):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(u.smtplib, 'SMTP_SSL', lambda *a, **k: (_ for _ in ()).throw(AssertionError('should not connect')))
    assert u.notify_high([ITEM]) == 'not-configured'


def test_no_items_means_no_mail(monkeypatch):
    monkeypatch.setenv('GMAIL_USER', 'me@example.com')
    monkeypatch.setenv('GMAIL_APP_PASSWORD', 'x')
    assert u.notify_high([]) == 'no-items'


def test_mail_is_sent_to_self(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            sent['host'] = (host, port)
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def login(self, user, pw):
            sent['login'] = (user, pw)
        def send_message(self, msg):
            sent['to'], sent['subject'] = msg['To'], msg['Subject']
            sent['body'] = msg.get_payload(decode=True).decode('utf-8')
    monkeypatch.setenv('GMAIL_USER', 'me@example.com')
    monkeypatch.setenv('GMAIL_APP_PASSWORD', 'abcd efgh ijkl mnop')
    monkeypatch.delenv('NOTIFY_TO', raising=False)
    monkeypatch.setattr(u.smtplib, 'SMTP_SSL', FakeSMTP)
    assert u.notify_high([ITEM]) == 'sent'
    assert sent['host'] == ('smtp.gmail.com', 465)
    assert sent['login'] == ('me@example.com', 'abcdefghijklmnop')     # アプリパスワードの空白は除く
    assert sent['to'] == 'me@example.com'
    assert 'No.239' in sent['body'] and 'ポイント' in sent['body'] and u.SITE_URL in sent['body']


def test_send_failure_does_not_raise(monkeypatch):
    monkeypatch.setenv('GMAIL_USER', 'me@example.com')
    monkeypatch.setenv('GMAIL_APP_PASSWORD', 'x')
    monkeypatch.setattr(u.smtplib, 'SMTP_SSL', lambda *a, **k: (_ for _ in ()).throw(OSError('blocked')))
    assert u.notify_high([ITEM]) == 'error'
