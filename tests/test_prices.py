from tracker.prices import _candidates_for


def test_candidates_for_known_market():
    # IBIS2 should return candidates including common suffixes
    c = _candidates_for('SXR8@IBIS2')
    assert any(x.startswith('SXR8') for x in c)
    assert any(x.endswith('.DE') or x.endswith('.MI') for x in c)


def test_candidates_for_plain_ticker():
    c = _candidates_for('VOO')
    assert c == ['VOO']


def test_candidates_for_custom_map(tmp_path, monkeypatch):
    # set env var to map FOOBAR to .ZZ
    import os
    os.environ['TRACKER_TICKER_MAP'] = '{"FOOBAR": [".ZZ"]}'
    from importlib import reload
    import tracker.prices as prices
    reload(prices)
    c = prices._candidates_for('ABC@FOOBAR')
    assert 'ABC.ZZ' in c
    del os.environ['TRACKER_TICKER_MAP']


def test_candidates_for_exact_mapping(tmp_path, monkeypatch):
    # built-in mapping should include NUKL@SBF -> NUKL.DE
    import tracker.prices as prices
    c = prices._candidates_for('NUKL@SBF')
    assert 'NUKL.DE' in c

    # and custom mapping should still work
    import os
    os.environ['TRACKER_TICKER_MAP'] = '{"NUKL@SBF": ["NUKL.DE"]}'
    from importlib import reload
    reload(prices)
    c2 = prices._candidates_for('NUKL@SBF')
    assert 'NUKL.DE' in c2
    del os.environ['TRACKER_TICKER_MAP']