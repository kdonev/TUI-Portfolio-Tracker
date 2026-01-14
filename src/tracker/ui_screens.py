from textual.screen import Screen
from textual.widgets import Input, Button, Static, OptionList
from textual.widget import Widget
from textual.containers import Vertical
from textual.message import Message
from tracker.db import add_etf, get_etf_by_ticker, get_etf_by_id, list_etfs, add_transaction, delete_etf, update_etf

class AddETFScreen(Screen):
    BINDINGS = [("escape", "pop_screen", "Cancel")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.supports_fractions = True

    def compose(self):
        yield Static("Add ETF", id="title")
        yield Vertical(
            Input(placeholder="TICKER (e.g., VOO)", id="ticker"),
            Input(placeholder="TARGET % (e.g., 30)", id="target_pct"),
            Button("Fractions: Yes", id="fractions_toggle"),
            Button("Add", id="add_btn"),
            Button("Cancel", id="cancel_btn"),
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.app.pop_screen()
            return
        if event.button.id == "fractions_toggle":
            self.supports_fractions = not self.supports_fractions
            label = "Fractions: Yes" if self.supports_fractions else "Fractions: No"
            self.query_one("#fractions_toggle", Button).label = label
            return
        ticker = self.query_one("#ticker", Input).value.strip().upper()
        target = self.query_one("#target_pct", Input).value.strip()
        try:
            target_pct = float(target)
        except Exception:
            self.app.pop_screen()
            return
        # ensure ticker not exists
        existing = get_etf_by_ticker(ticker)
        if existing:
            self.app.pop_screen()
            return
        add_etf(ticker, target_pct, self.supports_fractions)
        self.app.pop_screen()
        self.app.refresh_dashboard()

class AddTransactionScreen(Screen):
    BINDINGS = [("escape", "pop_screen", "Cancel")]

    def __init__(self, etf_id=None, **kwargs):
        super().__init__(**kwargs)
        self.etf_id = etf_id

    def compose(self):
        yield Static("Add Transaction", id="title")
        etf_id_placeholder = f"ETF ID ({self.etf_id})" if self.etf_id else "ETF ID (see dashboard)"
        # If ETF ID is pre-filled, show the ticker
        if self.etf_id:
            etf = get_etf_by_id(self.etf_id)
            ticker_display = f"[green]Ticker: {etf.ticker}[/green]" if etf else "[yellow]Ticker not found[/yellow]"
            yield Static(ticker_display, id="ticker_display")
        yield Vertical(
            Input(placeholder=etf_id_placeholder, id="etf_id"),
            Input(placeholder="Date (YYYY-MM-DD, optional)", id="date"),
            Input(placeholder="Shares (e.g., 1.5)", id="shares"),
            Input(placeholder="Total amount (price × shares)", id="total_amount"),
            Input(placeholder="Commission (optional, e.g., 0)", id="commission"),
            Input(placeholder="Price (per share)", id="price"),
            Button("Add", id="add_btn"),
            Button("Cancel", id="cancel_btn"),
        )

    def on_mount(self) -> None:
        """Set the ETF ID field if pre-filled and prefill date with today."""
        if self.etf_id:
            self.query_one("#etf_id", Input).value = str(self.etf_id)
        # Prefill date with today's date
        import datetime
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        self.query_one("#date", Input).value = today

    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.app.pop_screen()
            return
        try:
            etf_id = int(self.query_one("#etf_id", Input).value.strip())
            
            # Try to parse price, shares, and total_amount
            price_str = self.query_one("#price", Input).value.strip()
            shares_str = self.query_one("#shares", Input).value.strip()
            total_str = self.query_one("#total_amount", Input).value.strip()
            
            price = float(price_str) if price_str else None
            shares = float(shares_str) if shares_str else None
            total = float(total_str) if total_str else None
            
            # Calculate missing value if we have 2 of 3
            if price is not None and shares is not None and total is None:
                # Calculate total amount
                total = price * shares
            elif price is not None and shares is None and total is not None and price > 0:
                # Calculate shares
                shares = total / price
            elif price is None and shares is not None and total is not None and shares > 0:
                # Calculate price
                price = total / shares
            elif price is None or shares is None:
                # If we still don't have price and shares, we can't proceed
                self.app.pop_screen()
                return
            
            # Parse optional commission
            commission_str = self.query_one("#commission", Input).value.strip()
            commission = float(commission_str) if commission_str else 0.0
            
            # Parse optional date
            date_str = self.query_one("#date", Input).value.strip()
            date = None
            if date_str:
                import datetime as dt
                date = dt.datetime.strptime(date_str, "%Y-%m-%d")
                date = date.replace(tzinfo=dt.timezone.utc)
        except Exception:
            self.app.pop_screen()
            return
        add_transaction(etf_id, price, shares, commission=commission, date=date)
        self.app.pop_screen()
        self.app.refresh_dashboard()


class PlanScreen(Screen):
    BINDINGS = [("escape", "pop_screen", "Cancel")]

    def __init__(self, etf_id=None, **kwargs):
        super().__init__(**kwargs)
        self.mode = "rebalance"
        self.etf_id = etf_id

    def compose(self):
        yield Static("Buy Plan", id="title")
        # Amount at top, Buttons below
        yield Vertical(
            Input(placeholder="Amount to invest (e.g., 1000)", id="amount"),
            Vertical(
                Button("Plan", id="plan_btn"),
                Button("Cancel", id="cancel_btn"),
            ),
        )
        yield Static("", id="result")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.app.pop_screen()
            return
        if event.button.id == "plan_btn":
            # validate inputs
            try:
                amount = float(self.query_one("#amount", Input).value.strip())
                if amount < 0:
                    raise ValueError("Negative not allowed")
            except Exception:
                # show error
                self.query_one("#result", Static).update("Invalid input: ensure amount is a positive number.")
                return
            from tracker.planner import compute_plan
            plan = compute_plan(amount, mode="rebalance", precision=6)
            # Filter plan rows if a specific ETF is selected
            plan_rows = plan["rows"]
            if self.etf_id:
                plan_rows = [r for r in plan_rows if r["etf_id"] == self.etf_id]
                etf = get_etf_by_id(self.etf_id)
                title = f"Buy Plan for {etf.ticker if etf else 'ETF'} — invest {amount:.2f}"
            else:
                title = f"Rebalance Plan — invest {amount:.2f}"
            # render table
            from rich.table import Table
            from rich.console import Console
            from io import StringIO
            tbl = Table(title=title)
            tbl.add_column("Ticker")
            tbl.add_column("Target %")
            tbl.add_column("Current Value")
            tbl.add_column("Price")
            tbl.add_column("To Buy (amount)")
            tbl.add_column("To Buy (shares)")
            for r in plan_rows:
                # Determine precision for this ETF based on supports_fractions
                from tracker.db import get_etf_by_id
                etf = get_etf_by_id(r["etf_id"])
                etf_precision = 6 if (etf and etf.supports_fractions) else 0
                
                tbl.add_row(
                    r["ticker"],
                    f"{r['target_pct']:.2f}%",
                    f"{r['current_value']:.2f}",
                    f"{r['last_price']:.2f}" if r['last_price'] else "-",
                    f"{r['to_buy_amount']:.2f}",
                    f"{r['to_buy_shares']:.{etf_precision}f}" if r['to_buy_shares'] is not None else "-",
                )
            summary = f"\nPlanned spend: {plan['planned_spend']:.2f} | Leftover: {plan['leftover']:.2f}"
            if plan.get("missing_prices"):
                summary += " | Missing prices: " + ", ".join(plan['missing_prices'])
            # combine table and summary into a single string
            console = Console(file=StringIO(), width=120)
            console.print(tbl)
            table_str = console.file.getvalue()
            combined = table_str + summary
            self.query_one("#result", Static).update(combined)
            self.app.action_refresh()


class DeleteETFScreen(Screen):
    BINDINGS = [("escape", "pop_screen", "Cancel")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.etf_list = []

    def compose(self):
        self.etf_list = list_etfs()
        yield Static("Delete ETF", id="title")
        if self.etf_list:
            option_list = OptionList(id="etf_list")
            for etf in self.etf_list:
                option_list.add_option(f"{etf.ticker} (target {etf.target_pct}%)")
            yield Vertical(
                option_list,
                Button("Delete", id="delete_btn"),
                Button("Cancel", id="cancel_btn"),
            )
        else:
            yield Static("No ETFs to delete")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.app.pop_screen()
            return
        if event.button.id == "delete_btn":
            try:
                option_list = self.query_one("#etf_list", OptionList)
                selected_idx = option_list.highlighted
                if selected_idx is None:
                    return
                # get the corresponding ETF from the list
                if selected_idx >= len(self.etf_list):
                    return
                etf = self.etf_list[selected_idx]
                # push confirmation screen
                self.app.push_screen(ConfirmDeleteScreen(etf.id, etf.ticker))
            except Exception:
                self.app.pop_screen()
                return


class ConfirmDeleteScreen(Screen):
    BINDINGS = [("escape", "pop_screen", "Cancel")]

    def __init__(self, etf_id: int, etf_name: str, **kwargs):
        super().__init__(**kwargs)
        self.etf_id = etf_id
        self.etf_name = etf_name

    def compose(self):
        yield Static(f"Confirm Delete {self.etf_name}", id="title")
        yield Vertical(
            Static(f"Are you sure you want to delete {self.etf_name}?\nThis will remove all associated transactions."),
            Button("Yes, Delete", id="confirm_btn", variant="error"),
            Button("Cancel", id="cancel_btn"),
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.app.pop_screen()
            return
        if event.button.id == "confirm_btn":
            # perform deletion
            delete_etf(self.etf_id)
            # pop confirmation screen and delete screen
            self.app.pop_screen()
            self.app.pop_screen()
            self.app.refresh_dashboard()


class EditETFScreen(Screen):
    BINDINGS = [("escape", "pop_screen", "Cancel")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.etf_list = []
        self.selected_etf = None

    def compose(self):
        self.etf_list = list_etfs()
        yield Static("Edit ETF", id="title")
        if self.etf_list:
            option_list = OptionList(id="etf_list")
            for etf in self.etf_list:
                option_list.add_option(f"{etf.ticker} (target {etf.target_pct}%)")
            yield Vertical(
                option_list,
                Button("Select", id="select_btn"),
                Button("Cancel", id="cancel_btn"),
            )
        else:
            yield Static("No ETFs to edit")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.app.pop_screen()
            return
        if event.button.id == "select_btn":
            try:
                option_list = self.query_one("#etf_list", OptionList)
                selected_idx = option_list.highlighted
                if selected_idx is None or selected_idx >= len(self.etf_list):
                    return
                self.selected_etf = self.etf_list[selected_idx]
                # push edit form screen
                self.app.push_screen(EditETFFormScreen(self.selected_etf))
            except Exception:
                self.app.pop_screen()
                return


class EditETFFormScreen(Screen):
    BINDINGS = [("escape", "pop_screen", "Cancel")]

    def __init__(self, etf, **kwargs):
        super().__init__(**kwargs)
        self.etf = etf
        self.supports_fractions = etf.supports_fractions

    def compose(self):
        yield Static(f"Edit {self.etf.ticker}", id="title")
        yield Vertical(
            Static(f"Target %: {self.etf.target_pct:.2f}"),
            Input(placeholder=f"New target % (e.g., {self.etf.target_pct:.2f})", id="target_pct"),
            Button(f"Fractions: {'Yes' if self.supports_fractions else 'No'}", id="fractions_toggle"),
            Button("Save", id="save_btn"),
            Button("Cancel", id="cancel_btn"),
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.app.pop_screen()
            return
        if event.button.id == "fractions_toggle":
            self.supports_fractions = not self.supports_fractions
            label = f"Fractions: {'Yes' if self.supports_fractions else 'No'}"
            self.query_one("#fractions_toggle", Button).label = label
            return
        if event.button.id == "save_btn":
            target_input = self.query_one("#target_pct", Input).value.strip()
            try:
                if target_input:
                    target_pct = float(target_input)
                else:
                    target_pct = self.etf.target_pct
                if target_pct < 0:
                    raise ValueError("Negative not allowed")
                update_etf(self.etf.id, target_pct=target_pct, supports_fractions=self.supports_fractions)
            except Exception:
                self.app.pop_screen()
                return
            # pop form and list screens
            self.app.pop_screen()
            self.app.pop_screen()
            self.app.refresh_dashboard()