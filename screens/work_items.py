from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static, TabbedContent, TabPane

import api

STATUS_GROUPS = {
    "Planned": ["Planned"],
    "In Progress": ["InProgress"],
    "Blocked": ["Blocked"],
    "Done": ["Completed", "ReadyForRelease", "Released"],
}


def _pts(val) -> str:
    if val is None:
        return "–"
    f = float(val)
    return str(int(f)) if f == int(f) else str(f)


class WorkItemsScreen(Screen):
    BINDINGS = [
        Binding("b", "go_back", "Back", show=True),
        Binding("escape", "go_back", "Back", show=False),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    DEFAULT_CSS = """
    WorkItemsScreen {
        background: $surface;
    }
    #wi-header {
        height: 1;
        padding: 0 1;
        background: $accent;
        color: $foreground;
        text-style: bold;
    }
    TabbedContent {
        height: 1fr;
    }
    TabPane {
        padding: 0 1;
    }
    """

    def __init__(self, member: dict, sprint_name: str) -> None:
        super().__init__()
        self._member = member
        self._sprint_name = sprint_name
        self._sprint_member_id: str = member.get("sprintMemberId") or ""
        self._member_name: str = member.get("fullName") or "Member"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            f"  {self._member_name}  –  {self._sprint_name}",
            id="wi-header",
        )
        with TabbedContent(id="tabs"):
            for group_name in STATUS_GROUPS:
                tab_id = _tab_id(group_name)
                tbl_id = _tbl_id(group_name)
                with TabPane(group_name, id=tab_id):
                    yield DataTable(id=tbl_id, cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Team Manager"
        for group_name in STATUS_GROUPS:
            tbl = self.query_one(f"#{_tbl_id(group_name)}", DataTable)
            if group_name == "Blocked":
                tbl.add_columns("Title", "Type", "Est", "Actual", "Ref", "Reason")
            else:
                tbl.add_columns("Title", "Type", "Est", "Actual", "Ref")
        self.run_worker(self._load_data(), exclusive=True)

    async def _load_data(self) -> None:
        try:
            work_items = await api.get_work_items(self._sprint_member_id)
        except Exception as exc:
            self.query_one("#wi-header", Static).update(
                f"  [red]Error: {exc}[/]"
            )
            return
        self._populate(work_items)

    def _populate(self, work_items: list[dict]) -> None:
        grouped: dict[str, list[dict]] = {g: [] for g in STATUS_GROUPS}
        for wi in work_items:
            status = wi.get("status") or "Planned"
            for group_name, statuses in STATUS_GROUPS.items():
                if status in statuses:
                    grouped[group_name].append(wi)
                    break

        tabs = self.query_one("#tabs", TabbedContent)

        for group_name, items in grouped.items():
            tbl = self.query_one(f"#{_tbl_id(group_name)}", DataTable)
            tbl.clear()
            count = len(items)

            for wi in items:
                title = wi.get("title") or "?"
                wi_type = wi.get("type") or "–"
                est = _pts(wi.get("estimatedPoints"))
                actual = _pts(wi.get("actualPoints"))
                ref = wi.get("externalTicketRef") or "–"
                if group_name == "Blocked":
                    reason = wi.get("blockedReason") or "–"
                    short = reason[:30] + "…" if len(reason) > 30 else reason
                    tbl.add_row(title, wi_type, est, actual, ref, short)
                else:
                    tbl.add_row(title, wi_type, est, actual, ref)

            # Update tab label with item count
            try:
                tab = tabs.get_tab(_tab_id(group_name))
                tab.label = f"{group_name} ({count})"
            except Exception:
                pass

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        self.query_one("#wi-header", Static).update(
            f"  {self._member_name}  –  {self._sprint_name}  [dim]Refreshing…[/]"
        )
        self.run_worker(self._load_data(), exclusive=True)

    def action_quit(self) -> None:
        self.app.exit()


def _tab_id(group_name: str) -> str:
    return f"tab-{group_name.replace(' ', '-').lower()}"


def _tbl_id(group_name: str) -> str:
    return f"tbl-{group_name.replace(' ', '-').lower()}"
