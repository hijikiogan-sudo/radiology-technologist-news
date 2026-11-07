"""月別アーカイブのテスト (python -m pytest tests/test_news_archive.py)。"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update_news as u  # noqa: E402


def test_overflow_items_are_archived_by_month_without_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(u, 'ARCHIVE_DIR', tmp_path)
    a = {'date': '2026-09-03', 'headline': 'A', 'url': 'https://e/a'}
    b = {'date': '2026-09-20', 'headline': 'B', 'url': 'https://e/b'}
    c = {'date': '2026-08-31', 'headline': 'C', 'url': 'https://e/c'}
    u.archive_items([a, b, c])
    u.archive_items([a])                                    # 2回目でも重複しない
    sep = json.loads((tmp_path / '2026-09.json').read_text(encoding='utf-8'))
    assert [x['url'] for x in sep] == ['https://e/b', 'https://e/a']   # 新しい順
    idx = json.loads((tmp_path / 'index.json').read_text(encoding='utf-8'))
    assert idx['months'] == [{'month': '2026-09', 'count': 2}, {'month': '2026-08', 'count': 1}]


def test_nothing_happens_without_overflow(tmp_path, monkeypatch):
    monkeypatch.setattr(u, 'ARCHIVE_DIR', tmp_path / 'archive')
    u.archive_items([])
    assert not (tmp_path / 'archive').exists()


# --- 保存期間(1年) -----------------------------------------------------

def test_retention_cutoff_is_one_year_back():
    assert u.retention_cutoff(date(2027, 11, 5)) == '2026-11-05'


def test_expiry_keeps_the_boundary_day_and_undated_items():
    assert u.is_expired({'date': '2026-11-04'}, '2026-11-05')
    assert not u.is_expired({'date': '2026-11-05'}, '2026-11-05')
    assert not u.is_expired({'date': ''}, '2026-11-05')
    assert not u.is_expired({'headline': '日付なし'}, '2026-11-05')


def test_expiry_uses_the_date_shown_on_the_site():
    assert not u.is_expired({'date': '2026-01-01', 'featured_date': '2026-12-01'}, '2026-11-05')


def _write(path, items):
    path.write_text(json.dumps(items, ensure_ascii=False), encoding='utf-8')


def test_prune_removes_expired_articles_files_and_updates_index(tmp_path, monkeypatch):
    archive, html = tmp_path / 'archive', tmp_path / 'daily_html'
    archive.mkdir()
    html.mkdir()
    monkeypatch.setattr(u, 'ARCHIVE_DIR', archive)
    monkeypatch.setattr(u, 'HTML_DIR', html)
    _write(archive / '2026-09.json', [{'date': '2026-09-01', 'url': 'https://e/old'}])          # 全部期限切れ
    _write(archive / '2026-11.json', [{'date': '2026-11-20', 'url': 'https://e/new'},
                                      {'date': '2026-11-01', 'url': 'https://e/old2'}])         # 月の途中で分かれる
    _write(archive / '2027-01.json', [{'date': '2027-01-10', 'url': 'https://e/keep'}])
    for day in ('2026-11-04', '2026-11-05', '2027-01-01'):
        (html / f'放射線技師ニュース_{day}.html').write_text('x', encoding='utf-8')
    (html / 'メモ.html').write_text('x', encoding='utf-8')                                        # 形の違うファイルは触らない

    u.prune_old_data('2026-11-05')

    assert not (archive / '2026-09.json').exists()
    assert [x['url'] for x in json.loads((archive / '2026-11.json').read_text(encoding='utf-8'))] == ['https://e/new']
    idx = json.loads((archive / 'index.json').read_text(encoding='utf-8'))
    assert idx['months'] == [{'month': '2027-01', 'count': 1}, {'month': '2026-11', 'count': 1}]
    assert sorted(p.name for p in html.iterdir()) == sorted(['放射線技師ニュース_2026-11-05.html', '放射線技師ニュース_2027-01-01.html', 'メモ.html'])


def test_prune_leaves_broken_archive_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(u, 'ARCHIVE_DIR', tmp_path)
    monkeypatch.setattr(u, 'HTML_DIR', tmp_path / 'none')
    (tmp_path / '2020-01.json').write_text('{壊れた', encoding='utf-8')
    u.prune_old_data('2026-11-05')
    assert (tmp_path / '2020-01.json').exists()
