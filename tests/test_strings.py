from strings import S

def test_both_languages_present():
    assert 'en' in S
    assert 'uk' in S

def test_all_keys_in_both_languages():
    en_keys = set(S['en'].keys())
    uk_keys = set(S['uk'].keys())
    missing_in_uk = en_keys - uk_keys
    missing_in_en = uk_keys - en_keys
    assert not missing_in_uk, f"Missing in UK: {missing_in_uk}"
    assert not missing_in_en, f"Missing in EN: {missing_in_en}"

def test_no_empty_strings():
    for lang in ('en', 'uk'):
        for key, val in S[lang].items():
            assert val.strip(), f"Empty string for [{lang}][{key}]"
