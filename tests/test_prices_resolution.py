from tracker.prices import fetch_prices_with_resolution


def test_fetch_resolution_for_nukl():
    # Ensure we can resolve NUKL@SBF to NUKL.DE which has data
    res = fetch_prices_with_resolution(['NUKL@SBF'])
    price, resolved = res['NUKL@SBF']
    assert resolved == 'NUKL.DE'
    assert price is None or isinstance(price, float)
