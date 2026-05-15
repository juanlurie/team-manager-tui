from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static, TabbedContent, TabPane


def _pts(val) -> str:
    if val is None:
        return "–"
    f = float(val)
    return str(int(f)) if f == int(f) else str(f)


STATUS_GROUPS = {
    "Planned": ["Planned"],
    "In Progress": ["InProgress"],
    "Blocked": ["Blocked"],
    "Done": ["Completed", "ReadyForRelease", "Released"],
}


class FeatureDetailScreen(Screen):
    BINDINGS = [
        Binding("b", "go_back", "Back", show=True),
        Binding("escape", "go_back", "Back", show=False),
        Binding("a", "add_task", "Add task", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    DEFAULT_CSS = """
    FeatureDetailScreen { background: $surface; }
    #feature-header {
        height: 1;
        padding: 0 1;
        background: $accent;
        color: $foreground;
        text-style: bold;
    }
    TabbedContent { height: 1fr; }
    TabPane { padding: 0 1; }
    """

    def __init__(self, feature: dict, members: list[dict], sprint_id: str, sprint_name: str) -> None:
        super().__init__()
        self._feature = feature
        self._sprint_id = sprint_id
        self._sprint_name = sprint_name
        self._members = members
        self._title = feature.get("title") or "Unplanned"
        self._feature_id = feature.get("id")  # None for unplanned
        # Collect all work items that belong to this feature across all members
        self._work_items: list[dict] = []
        for m in members:
            for wi in m.get("workItems") or []:
                if wi.get("featureId") == self._feature_id:
                    self._work_items.append({**wi, "_memberName": m.get("fullName") or "?"})

    def compose(self) -> ComposeResult:
        yield Header()
        ref = self._feature.get("externalTicketRef") or ""
        ref_suffix = f"  [{ref}]" if ref else ""
        yield Static(
            f"  {self._title}{ref_suffix}  –  {self._sprint_name}",
            id="feature-header",
        )
        with TabbedContent(id="tabs"):
            for group_name in STATUS_GROUPS:
                tab_id = f"tab-{group_name.replace(' ', '-').lower()}"
                tbl_id = f"tbl-{group_name.replace(' ', '-').lower()}"
                with TabPane(group_name, id=tab_id):
                    yield DataTable(id=tbl_id, cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Team Manager"
        for group_name in STATUS_GROUPS:
            tbl_id = f"tbl-{group_name.replace(' ', '-').lower()}"
            tbl = self.query_one(f"#{tbl_id}", DataTable)
            if group_name == "Blocked":
                tbl.add_columns("Title", "Member", "Type", "Est", "Actual", "Ref", "Reason")
            else:
                tbl.add_columns("Title", "Member", "Type", "Est", "Actual", "Ref")
        self._populate()

    def _populate(self) -> None:
        grouped: dict[str, list[dict]] = {g: [] for g in STATUS_GROUPS}
        for wi in self._work_items:
            status = wi.get("status") or "Planned"
            for group_name, statuses in STATUS_GROUPS.items():
                if status in statuses:
                    grouped[group_name].append(wi)
                    break

        tabs = self.query_one("#tabs", TabbedContent)

        for group_name, items in grouped.items():
            tbl_id = f"tbl-{group_name.replace(' ', '-').lower()}"
            tab_id = f"tab-{group_name.replace(' ', '-').lower()}"
            tbl = self.query_one(f"#{tbl_id}", DataTable)
            tbl.clear()

            for wi in items:
                title = wi.get("title") or "?"
                member = wi.get("_memberName") or "?"
                wi_type = wi.get("type") or "–"
                est = _pts(wi.get("estimatedPoints"))
                actual = _pts(wi.get("actualPoints"))
                ref = wi.get("externalTicketRef") or "–"
                if group_name == "Blocked":
                    reason = wi.get("blockedReason") or "–"
                    short = reason[:28] + "…" if len(reason) > 28 else reason
                    tbl.add_row(title, member, wi_type, est, actual, ref, short)
                else:
                    tbl.add_row(title, member, wi_type, est, actual, ref)

            try:
                tabs.get_tab(tab_id).label = f"{group_name} ({len(items)})"
            except Exception:
                pass

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_add_task(self) -> None:
        from screens.add_task import AddTaskModal
        modal = AddTaskModal(self._members)

        def on_result(payload: dict | None) -> None:
            if not payload:
                return
            self.run_worker(self._create_task(payload), exclusive=False)

        self.app.push_screen(modal, callback=on_result)

    async def _create_task(self, payload: dict) -> None:
        import api
        sprint_member_id = payload.pop("sprintMemberId")
        payload["featureId"] = self._feature_id
        try:
            await api.create_work_item(sprint_member_id, payload)
        except Exception as exc:
            self.app.notify(str(exc), title="Failed to create task", severity="error", timeout=8)
            return
        self.app.notify("Task created", severity="information", timeout=3)
        self.action_refresh()

    def action_refresh(self) -> None:
        import api
        for group_name in STATUS_GROUPS:
            tbl_id = f"tbl-{group_name.replace(' ', '-').lower()}"
            tbl = self.query_one(f"#{tbl_id}", DataTable)
            tbl.clear()
        self._work_items = []
        self.query_one("#feature-header", Static).update(
            f"  {self._title}  –  {self._sprint_name}  [dim]Refreshing…[/]"
        )
        self.run_worker(self._reload_data(), exclusive=True)

    async def _reload_data(self) -> None:
        import api
        try:
            dashboard = await api.get_sprint_dashboard(self._sprint_id)
        except Exception as exc:
            self.query_one("#feature-header", Static).update(
                f"  [red]Error: {exc}[/]"
            )
            return
        members = dashboard.get("members") or []
        self._work_items = []
        for m in members:
            for wi in m.get("workItems") or []:
                if wi.get("featureId") == self._feature_id:
                    self._work_items.append({**wi, "_memberName": m.get("fullName") or "?"})
        self._populate()
        self.query_one("#feature-header", Static).update(
            f"  {self._title}  –  {self._sprint_name}"
        )

    def action_quit(self) -> None:
        self.app.exit()
