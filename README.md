# TUI Portfolio Tracker

A terminal-based portfolio tracker with SQLite storage and price fetching via yfinance.

**Note**: This project was developed with AI assistance (GitHub Copilot / Claude Haiku 4.5).

Install (Poetry):

```bash
poetry install
poetry run tracker tui
```

Install Poetry via pipx (alternative):

```powershell
# Install pipx (if needed)
python -m pip install --user pipx
python -m pipx ensurepath
# Install Poetry via pipx
pipx install poetry
# Restart your terminal if needed, then verify
poetry --version
```

If you already have Poetry installed, you can skip the pipx steps.

Features:
- Track ETFs with target %
- Record purchases (transactions) with price, shares, amount, timestamp, commission
- Fetch prices with yfinance (refresh at start or manual)
- Rebalance planning: Calculate how much to buy of each ETF to reach target allocation
- Smart precision: Use 6 decimals for fractional ETFs, whole numbers for non-fractional
- Portfolio metrics: View total value, total invested, return amount and return rate
- TUI built with Textual
