from tracker.db import init_db, add_etf, list_etfs, add_transaction, get_etf_holdings, update_etf_price, get_etf_by_id


def test_db_roundtrip(tmp_path):
    dbfile = tmp_path / "portfolio_test.db"
    init_db(f"sqlite:///{dbfile}")
    e = add_etf('VOO', 50.0)
    assert e.ticker == 'VOO'
    etfs = list_etfs()
    assert len(etfs) == 1
    tx = add_transaction(e.id, price=400.0, shares=1.5)
    assert tx.amount == 600.0
    # update price and check holdings
    update_etf_price(e.id, 410.0)
    shares, value = get_etf_holdings(e.id)
    assert shares == 1.5
    assert value == 1.5 * 410.0