from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, DataTable
from textual.screen import Screen
from rich.table import Table
import asyncio
import datetime
from tracker.db import init_db, list_etfs, add_etf, add_transaction, get_etf_by_id, update_etf_price, get_etf_holdings, get_etf_invested
from tracker import prices
from tracker.ui_screens import AddETFScreen, AddTransactionScreen, PlanScreen, DeleteETFScreen, EditETFScreen

class PortfolioApp(App):
    CSS_PATH = None

    BINDINGS = [
        ("a", "add_etf", "Add ETF"),
        ("e", "edit_etf", "Edit ETF"),
        ("t", "add_tx", "Add Transaction"),
        ("p", "plan", "Plan"),
        ("r", "refresh", "Refresh Prices"),
        ("d", "delete_etf", "Delete ETF"),
        ("q", "quit", "Quit"),
    ]

    def on_mount(self):
        # ensure DB exists
        init_db()
        # set reactive title after initialization to avoid overwriting the reactive descriptor
        self.title = "Portfolio Tracker"
        # add a status widget for progress messages
        # target the status Static by id to avoid ambiguous matches
        self.query_one("#status", Static).update("Loading...")
        # fetch prices once at start (run async in background so UI remains responsive)
        asyncio.create_task(self.update_prices_at_start())
        self.refresh_dashboard()

    def compose(self) -> ComposeResult:
        yield Header()
        dt = DataTable(id="main")
        dt.add_columns("Id", "Ticker", "Target %", "Shares", "Last Price", "Value", "Invested")
        yield dt
        yield Static("", id="summary")
        yield Static("", id="status")
        yield Footer()

    def refresh_dashboard(self):
        etfs = list_etfs()
        dt = self.query_one("#main", DataTable)
        dt.clear()
        
        total_value = 0.0
        total_invested = 0.0
        
        for e in etfs:
            shares, value = get_etf_holdings(e.id)
            invested = get_etf_invested(e.id)
            # Format shares with 6 decimals if fractions supported, else as whole number
            shares_str = f"{shares:.6f}" if e.supports_fractions else f"{shares:.0f}"
            dt.add_row(str(e.id), e.ticker, f"{e.target_pct:.2f}%", shares_str, f"{e.last_price:.2f}" if e.last_price else "-", f"{value:.2f}", f"{invested:.2f}")
            total_value += value
            total_invested += invested
        
        # Calculate return and return rate
        total_return = total_value - total_invested
        return_rate = (total_return / total_invested * 100) if total_invested > 0 else 0.0
        
        # Format summary
        summary_text = f"[bold]Portfolio Summary:[/bold] Value: €{total_value:.2f} | Invested: €{total_invested:.2f} | Return: €{total_return:.2f} ({return_rate:+.2f}%)"
        self.query_one("#summary", Static).update(summary_text)

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the dashboard table."""
        dt = self.query_one("#main", DataTable)
        row_key = event.row_key
        etf_id_str = dt.get_cell_at((row_key, 0))
        try:
            etf_id = int(etf_id_str)
            # Push AddTransactionScreen with pre-filled ETF ID
            self.push_screen(AddTransactionScreen(etf_id=etf_id))
        except (ValueError, IndexError):
            pass

    async def action_refresh(self):
        # run async refresh in background
        asyncio.create_task(self.update_prices_at_start())

    async def update_prices_at_start(self):
        etfs = list_etfs()
        n = len(etfs)
        if n == 0:
            self.query_one("#status", Static).update("No ETFs to refresh")
            return
        from tracker.db import update_etf_resolved_ticker
        for idx, e in enumerate(etfs, start=1):
            self.query_one("#status", Static).update(f"Refreshing prices: {idx}/{n} ({e.ticker})")
            # fetch price for single ticker in thread to avoid blocking
            fetched = await asyncio.to_thread(prices.fetch_prices_with_resolution, [e.ticker])
            p, resolved = fetched.get(e.ticker)
            if p is not None:
                update_etf_price(e.id, p)
                if resolved and resolved != e.ticker.upper():
                    update_etf_resolved_ticker(e.id, resolved)
                self.query_one("#status", Static).update(f"Updated {e.ticker} -> {p:.2f} (resolved {resolved}) ({idx}/{n})")
            else:
                self.query_one("#status", Static).update(f"Skipped {e.ticker} (no price) ({idx}/{n})")
            # yield control so UI can update
            await asyncio.sleep(0.05)
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.query_one("#status", Static).update(f"Prices refreshed at {ts}")
        self.refresh_dashboard()

    def action_add_etf(self):
        self.push_screen(AddETFScreen())

    def action_edit_etf(self):
        self.push_screen(EditETFScreen())

    def action_add_tx(self):
        # Get the currently selected row from the DataTable
        dt = self.query_one("#main", DataTable)
        if dt.cursor_row is not None:
            # Get the ETF ID from the first column of the selected row
            etf_id_str = dt.get_cell_at((dt.cursor_row, 0))
            try:
                etf_id = int(etf_id_str)
                self.push_screen(AddTransactionScreen(etf_id=etf_id))
                return
            except (ValueError, IndexError):
                pass
        # If no row selected, open without pre-filling
        self.push_screen(AddTransactionScreen())

    def action_plan(self):
        # Get the currently selected row from the DataTable
        dt = self.query_one("#main", DataTable)
        etf_id = None
        if dt.cursor_row is not None:
            # Get the ETF ID from the first column of the selected row
            etf_id_str = dt.get_cell_at((dt.cursor_row, 0))
            try:
                etf_id = int(etf_id_str)
            except (ValueError, IndexError):
                pass
        self.push_screen(PlanScreen(etf_id=etf_id))

    def action_delete_etf(self):
        self.push_screen(DeleteETFScreen())

    def action_quit(self):
        self.exit()