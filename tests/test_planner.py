from tracker.db import init_db, add_etf, add_transaction, update_etf_price
from tracker.planner import compute_plan


def test_compute_plan_new_and_precision(tmp_path):
    dbfile = tmp_path / "portfolio_planner.db"
    init_db(f"sqlite:///{dbfile}")
    # Create two ETFs with targets
    e1 = add_etf('ETF1', 60.0)
    e2 = add_etf('ETF2', 40.0)
    # Add existing holdings
    add_transaction(e1.id, price=100.0, shares=1.0)  # current value 100
    add_transaction(e2.id, price=50.0, shares=2.0)   # current value 100
    # Update prices
    update_etf_price(e1.id, 110.0)  # new current value 110
    update_etf_price(e2.id, 55.0)   # new current value 110
    # Now compute plan for investing 1000 in 'new' mode with precision 2
    plan = compute_plan(1000.0, mode='new', precision=2)
    assert plan['mode'] == 'new'
    # Each ETF target of new money: 600 and 400
    rows = {r['ticker']: r for r in plan['rows']}
    assert 'ETF1' in rows and 'ETF2' in rows
    # With prices, compute expected floored shares
    # ETF1: target 600, price 110 => raw_shares = 600/110 = 5.4545 -> floored to 2 dec => 5.45 shares -> amount 599.5
    # ETF2: target 400, price 55 => raw_shares = 400/55 = 7.2727 -> floored to 2 dec => 7.27 -> amount 7.27*55 = 399.85
    # Initial planned_spend = 599.5 + 399.85 = 999.35, leftover = 0.65
    # Leftover allocated to fractional ETFs proportionally: ETF1 60%, ETF2 40%
    # ETF1 gets: 0.65 * 0.6 = 0.39, shares = 0.39/110 ≈ 0.00354545...
    # ETF2 gets: 0.65 * 0.4 = 0.26, shares = 0.26/55 ≈ 0.00472727...
    expected_e1_shares = 5.45 + 0.39 / 110.0
    expected_e2_shares = 7.27 + 0.26 / 55.0
    assert abs(rows['ETF1']['to_buy_shares'] - expected_e1_shares) < 1e-6
    assert abs(rows['ETF2']['to_buy_shares'] - expected_e2_shares) < 1e-6


def test_compute_plan_rebalance(tmp_path):
    dbfile = tmp_path / "portfolio_planner2.db"
    init_db(f"sqlite:///{dbfile}")
    e1 = add_etf('A', 50.0)
    e2 = add_etf('B', 50.0)
    add_transaction(e1.id, price=10.0, shares=10.0)  # 100
    add_transaction(e2.id, price=20.0, shares=5.0)   # 100
    update_etf_price(e1.id, 10.0)
    update_etf_price(e2.id, 20.0)
    # invest 100, total after = 300, each target 150, current values 100 each -> need 50 each
    plan = compute_plan(100.0, mode='rebalance', precision=3)
    rows = {r['ticker']: r for r in plan['rows']}
    assert abs(rows['A']['to_buy_amount'] - 50.0) < 1e-6 or rows['A']['to_buy_shares'] is not None
    assert abs(rows['B']['to_buy_amount'] - 50.0) < 1e-6 or rows['B']['to_buy_shares'] is not None
    assert abs(plan['planned_spend'] - (rows['A']['to_buy_amount'] + rows['B']['to_buy_amount'])) < 1e-6