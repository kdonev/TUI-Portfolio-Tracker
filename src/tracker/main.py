from typer import Typer
from tracker.app import PortfolioApp

cli = Typer()

@cli.command(name="tui")
def tui():
    """Run the TUI application"""
    PortfolioApp().run()

@cli.command(name="check")
def check():
    """Run non-interactive startup checks: init DB, fetch prices for saved ETFs and report status."""
    import logging
    from tracker import prices
    from tracker.db import init_db, list_etfs, update_etf_price

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("tracker.check")
    logger.info("Initializing DB...")
    init_db()
    etfs = list_etfs()
    if not etfs:
        logger.info("No ETFs in DB.")
        return
    tickers = [e.ticker for e in etfs]
    logger.info(f"Fetching prices for: {', '.join(tickers)}")
    fetched = prices.fetch_prices(tickers)
    for e in etfs:
        p = fetched.get(e.ticker)
        if p is None:
            logger.warning(f"Price missing for {e.ticker}")
        else:
            update_etf_price(e.id, p)
            logger.info(f"Updated {e.ticker}: {p}")

def app():
    """Compatibility entrypoint for console scripts: call the Typer CLI."""
    return cli()

if __name__ == "__main__":
    cli()