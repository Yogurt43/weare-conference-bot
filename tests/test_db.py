# tests/test_db.py
import pytest
from unittest.mock import MagicMock
import db  # conftest.py sets env vars before this import

@pytest.fixture
def mock_sb(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(db, 'sb', mock)
    return mock

def test_get_participant_returns_none_when_not_found(mock_sb):
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    result = db.get_participant(99999)
    assert result is None

def test_get_participant_returns_data(mock_sb):
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {'chat_id': 123, 'full_name': 'Test User', 'status': 'approved'}
    ]
    result = db.get_participant(123)
    assert result['chat_id'] == 123
    assert result['status'] == 'approved'

def test_upsert_participant(mock_sb):
    mock_sb.table.return_value.upsert.return_value.execute.return_value.data = [
        {'chat_id': 123, 'lang': 'uk'}
    ]
    result = db.upsert_participant({'chat_id': 123, 'lang': 'uk'})
    assert result['lang'] == 'uk'

def test_get_houses_for_gender(mock_sb):
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {'id': 'abc', 'name': 'Test House', 'gender': 'M', 'capacity': 12}
    ]
    result = db.get_houses_for_gender('M')
    assert len(result) == 1
    assert result[0]['gender'] == 'M'

def test_get_setting(mock_sb):
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {'key': 'schedule_text', 'value': 'Day 1: ...'}
    ]
    result = db.get_setting('schedule_text')
    assert result == 'Day 1: ...'

def test_get_setting_returns_empty_when_not_found(mock_sb):
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    result = db.get_setting('missing_key')
    assert result == ''
