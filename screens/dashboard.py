from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static
from textual.containers import Horizontal, Vertical, ScrollableContainer


def _fmt_date(d: str | None) -> str:
    return d[:10] if d else "?"


def _sprint_progress(members: list[dict]) -> tuple[int, int]:
    done = 0.0
    total = 0.0
    done_statuses = {"Completed", "ReadyForRelease", "Released"}
    for m in members:
        for wi in m.get("workItems") or []:
            est = wi.get("estimatedPoints") or 0
            total += est
            if wi.get("status") in done_statuses:
                done += wi.get("actualPoints") or est
    return int(done), int(total)


def _build_feature_rows(
    features: list[dict],
    members: list[dict],
) -> list[tuple]:
    """
    Returns list of (feature_dict, assignee_names, done_items, total_items)
    Also appends a synthetic 'Unplanned' row for work items with no featureId.
    """
    done_statuses = {"Completed", "ReadyForRelease", "Released"}

    # Index work items by featureId
    feature_items: dict[str | None, list[dict]] = {}
    for m in members:
        for wi in m.get("workItems") or []:
            fid = wi.get("featureId")
            feature_items.setdefault(fid, []).append({**wi, "_memberName": m.get("fullName") or "?"})

    rows = []
    for f in features:
        fid = f.get("id")
        items = feature_items.get(fid) or []
        names = sorted({wi["_memberName"] for wi in items})
        done = sum(1 for wi in items if wi.get("status") in done_statuses)
        rows.append((f, names, done, len(items)))

    # Unplanned items (no featureId)
    unplanned = feature_items.get(None) or []
    if unplanned:
        names = sorted({wi["_memberName"] for wi in unplanned})
        done = sum(1 for wi in unplanned if wi.get("status") in done_statuses)
        synthetic = {"id": None, "title": "Unplanned", "status": "–", "externalTicketRef": None, "isUnplanned": True}
        rows.append((synthetic, names, done, len(unplanned)))

    return rows


class DashboardScreen(Screen):
    BINDINGS = [
        Binding("[", "prev_sprint", "Prev sprint", show=True),
        Binding("]", "next_sprint", "Next sprint", show=True),
        Binding("n", "add_feature", "New feature", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("enter", "open_feature", "Work items", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    DEFAULT_CSS = """
    DashboardScreen { background: $surface; }
    #sprint-banner {
        height: 1;
        padding: 0 1;
        background: $accent;
        color: $foreground;
        text-style: bold;
    }
    #stats-bar {
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
    }
    #main-area { height: 1fr; }
    #left-panel {
        width: 2fr;
        border-right: solid $accent;
        padding: 0 1;
    }
    #features-title {
        height: 1;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #features-table { height: 1fr; }
    #right-panel { width: 1fr; padding: 0 1; }
    #right-content { height: auto; }
    """

    def __init__(self, sprint: dict, sprints: list[dict]) -> None:
        super().__init__()
        self._sprint = sprint
        self._sprints = sprints
        self._dashboard: dict = {}
        self._blockers: list[dict] = []
        self._leave_summary: dict | None = None
        self._feature_rows: list[tuple] = []   # (feature_dict, names, done, total)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("  Loading…", id="sprint-banner")
        yield Static("  Loading…", id="stats-bar")
        with Horizontal(id="main-area"):
            with Vertical(id="left-panel"):
                yield Static("FEATURES", id="features-title")
                yield DataTable(id="features-table", cursor_type="row", zebra_stripes=True)
            with ScrollableContainer(id="right-panel"):
                yield Static("Loading…", id="right-content")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Team Manager"
        sprint = self._sprint
        name = sprint.get("name", "?")
        pi = sprint.get("piName") or ""
        start = _fmt_date(sprint.get("startDate"))
        end = _fmt_date(sprint.get("endDate"))
        prefix = f"{pi} – " if pi else ""
        self.query_one("#sprint-banner", Static).update(f"  {prefix}{name}   {start} → {end}")

        tbl = self.query_one("#features-table", DataTable)
        tbl.add_columns("Feature", "Status", "Ref", "Members", "Done")
        self.run_worker(self._load_data(), exclusive=True)

    async def _load_data(self) -> None:
        import api
        try:
            dashboard, blockers, leave_summary = await api.load_dashboard_data(self._sprint["id"])
        except Exception as exc:
            self.query_one("#stats-bar", Static).update(f"  [red]Error: {exc}[/]")
            return
        self._dashboard = dashboard
        self._blockers = blockers
        self._leave_summary = leave_summary
        self._populate()

    def _populate(self) -> None:
        members: list[dict] = self._dashboard.get("members") or []
        features: list[dict] = self._dashboard.get("features") or []

        done_pts, total_pts = _sprint_progress(members)
        pct = int(done_pts / total_pts * 100) if total_pts else 0
        bar_filled = "█" * (pct // 5)
        bar_empty = "░" * (20 - pct // 5)

        leave_members: list[dict] = []
        if self._leave_summary:
            leave_members = self._leave_summary.get("members") or []

        blocked_count = len(self._blockers)
        total_features = len(features)

        self.query_one("#stats-bar", Static).update(
            f"  [green]{bar_filled}[/][dim]{bar_empty}[/]  [bold]{pct}%[/]"
            f"   [bold]{total_features}[/] features"
            f"   [bold]{len(members)}[/] members"
            f"   [red bold]{blocked_count}[/] blocked"
            f"   [yellow]{len(leave_members)}[/] on leave"
        )

        # Build and render features table
        self._feature_rows = _build_feature_rows(features, members)
        tbl = self.query_one("#features-table", DataTable)
        tbl.clear()

        done_statuses = {"Completed", "ReadyForRelease", "Released"}

        for feature, assignee_names, done_items, total_items in self._feature_rows:
            title = feature.get("title") or "?"
            status = feature.get("status") or "–"
            ref = feature.get("externalTicketRef") or "–"
            members_str = ", ".join(assignee_names[:3])
            if len(assignee_names) > 3:
                members_str += f" +{len(assignee_names) - 3}"
            if not assignee_names:
                members_str = "[dim]unassigned[/]"
            progress = f"{done_items}/{total_items}" if total_items else "–"
            tbl.add_row(title, status, ref, members_str, progress, key=feature.get("id") or "__unplanned__")

        if not self._feature_rows:
            tbl.add_row("[dim]No features this sprint[/]", "", "", "", "")

        # Right panel: blockers + leave + unallocated
        unallocated = [m for m in members if not (m.get("workItems") or [])]

        lines: list[str] = ["[bold]BLOCKERS[/]"]
        if self._blockers:
            for b in self._blockers:
                member_name = b.get("memberName") or "?"
                title = b.get("title") or ""
                days = b.get("daysBlocked") or 0
                short_title = title[:28] + "…" if len(title) > 28 else title
                lines.append(f"  [red]●[/] {member_name}  {days}d")
                if short_title:
                    lines.append(f"    [dim]{short_title}[/]")
        else:
            lines.append("  [dim]None[/]")

        lines += ["", "[bold]LEAVE[/]"]
        if leave_members:
            for lm in leave_members:
                lname = lm.get("memberName") or "?"
                days = lm.get("totalWorkingDays") or 0
                lines.append(f"  [yellow]●[/] {lname}  ({days}d)")
        else:
            lines.append("  [dim]None[/]")

        lines += ["", f"[bold]UNALLOCATED[/] [dim]({len(unallocated)})[/]"]
        if unallocated:
            for m in unallocated:
                name = m.get("fullName") or "?"
                squads = ", ".join(m.get("squadNames") or []) or "–"
                lines.append(f"  [dim]●[/] {name}  [dim]{squads}[/]")
        else:
            lines.append("  [dim]All members have work items[/]")

        self.query_one("#right-content", Static).update("\n".join(lines))

    def action_add_feature(self) -> None:
        from screens.add_feature import AddFeatureModal
        sprint_id = self._sprint["id"]

        def on_result(payload: dict | None) -> None:
            if not payload:
                return
            self.run_worker(self._create_feature(sprint_id, payload), exclusive=False)

        self.app.push_screen(AddFeatureModal(), callback=on_result)

    async def _create_feature(self, sprint_id: str, payload: dict) -> None:
        import api
        try:
            await api.create_feature(sprint_id, payload)
        except Exception as exc:
            self.app.notify(str(exc), title="Failed to create feature", severity="error", timeout=8)
            return
        self.action_refresh()

    def action_open_feature(self) -> None:
        tbl = self.query_one("#features-table", DataTable)
        if not self._feature_rows or tbl.cursor_row < 0 or tbl.cursor_row >= len(self._feature_rows):
            return
        feature, assignee_names, done_items, total_items = self._feature_rows[tbl.cursor_row]
        if not feature.get("id") and not feature.get("isUnplanned"):
            return
        members: list[dict] = self._dashboard.get("members") or []
        sprint_name = self._sprint.get("name", "Sprint")
        from screens.feature_detail import FeatureDetailScreen
        self.app.push_screen(FeatureDetailScreen(feature, members, sprint_name))

    def action_refresh(self) -> None:
        tbl = self.query_one("#features-table", DataTable)
        tbl.clear()
        self._feature_rows = []
        self.query_one("#stats-bar", Static).update("  Refreshing…")
        self.run_worker(self._load_data(), exclusive=True)

    def action_prev_sprint(self) -> None:
        self.app.action_prev_sprint()

    def action_next_sprint(self) -> None:
        self.app.action_next_sprint()

    def action_quit(self) -> None:
        self.app.exit()
