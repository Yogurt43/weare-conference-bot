# tests/test_utils.py
from utils import validate_age, format_house_button, get_lang, is_admin

def test_validate_age_valid():
    assert validate_age('25') == 25
    assert validate_age('10') == 10
    assert validate_age('99') == 99

def test_validate_age_invalid():
    assert validate_age('abc') is None
    assert validate_age('9') is None
    assert validate_age('100') is None
    assert validate_age('') is None
    assert validate_age('-1') is None

def test_format_house_button_available():
    house = {'name': 'Дім Сонця', 'capacity': 12}
    label = format_house_button(house, taken=4)
    assert 'Дім Сонця' in label
    assert '4/12' in label

def test_format_house_button_full():
    house = {'name': 'Дім Сонця', 'capacity': 12}
    label = format_house_button(house, taken=12)
    assert 'FULL' in label or 'ЗАЙНЯТИЙ' in label or label.endswith('— 12/12 spots taken')

def test_get_lang_defaults_to_en():
    participant = {'lang': None}
    assert get_lang(participant) == 'en'

def test_get_lang_returns_stored():
    participant = {'lang': 'uk'}
    assert get_lang(participant) == 'uk'

def test_is_admin_owner():
    assert is_admin(479515546) is True

def test_is_admin_known_admin():
    assert is_admin(426569764) is True

def test_is_admin_random_user():
    assert is_admin(99999999) is False
