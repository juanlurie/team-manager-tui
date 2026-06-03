from __future__ import annotations

import asyncio
import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen, ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static
from textual.containers import Horizontal, Vertical


# ── Helpers ──────────────────────────────────────────────────────────────────

def _fmt_mins(mins: int) -> str:
    h, m = divmod(abs(mins), 60)
    if h and m:
        return f"{h}h {m}m"
    return f"{h}h" if h else f"{m}m"


def _date_key(d: datetime.date) -> str:
    return d.strftime("%Y-%m-%d")


def _week_start(d: datetime.date) -> datetime.date:
    return d - datetime.timedelta(days=d.weekday())


# ── Log Time Modal ────────────────────────────────────────────────────────────

class LogTimeModal(ModalScreen):
    """Keyboard-first entry modal. Press 1–9 for quick actions, C for custom."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("c", "custom_mode", "Custom"),
    ]

    DEFAULT_CSS = """
    LogTimeModal { align: center middle; }
    #dialog {
        width: 60;
        height: auto;
        max-height: 36;
        padding: 1 2;
        background: $surface;
        border: solid $accent;
    }
    #dlg-title { height: 1; text-style: bold; color: $accent; margin-bottom: 1; }
    .qa-row { height: 1; }
    .hint { height: 1; color: $text-muted; margin-top: 1; }
    .field-label { height: 1; margin-top: 1; color: $text-muted; }
    #dur-row { height: 3; align: left middle; margin-top: 0; }
    #dur-val { width: 10; height: 1; text-align: center; text-style: bold; }
    #sug-box { height: auto; max-height: 5; margin-top: 0; }
    .sug { height: 1; padding: 0 1; }
    .sug.sel { background: $accent; color: $foreground; }
    #err { height: 1; color: $error; margin-top: 1; }
    #btn-row { margin-top: 1; height: 3; align: right middle; }
    Button { margin-left: 1; }
    """

    def __init__(self, date_label: str, quick_actions: list[dict],
                 cat_map: dict[str, list[str]], location_options: list[str],
                 default_location: str) -> None:
        super().__init__()
        self._date_label = date_label
        self._quick_actions = quick_actions
        self._cat_map = cat_map
        self._location_options = location_options or ["Home", "Other", "Client", "Entelect"]
        self._default_location = default_location or "Home"
        self._custom = False
        self._dur_mins = 60
        self._proj: str | None = None
        self._cat: str | None = None
        self._sugs: list[tuple[str, str]] = []
        self._sug_idx = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(f"Log Time — {self._date_label}", id="dlg-title")
            with Vertical(id="qa-area"):
                if self._quick_actions:
                    for i, qa in enumerate(self._quick_actions[:9], 1):
                        label = qa.get("label") or qa.get("category", "?")
                        mins = qa.get("durationMins") or 60
                        yield Static(
                            f"  [bold]{i}[/]  {label:<30} [dim]{_fmt_mins(mins)}[/]",
                            classes="qa-row",
                        )
                else:
                    yield Static("  [dim]No quick actions configured[/]", classes="qa-row")
            yield Static("  [bold]C[/] Custom     [bold]Esc[/] Cancel", classes="hint", id="hint-line")
            with Vertical(id="custom-area"):
                pass
            yield Static("", id="err")

    def on_mount(self) -> None:
        self.query_one("#custom-area").display = False

    def on_key(self, event) -> None:
        if self._custom:
            return
        k = event.key
        if k.isdigit() and 0 < int(k) <= len(self._quick_actions):
            self._submit_quick(self._quick_actions[int(k) - 1])
            event.stop()

    def _submit_quick(self, qa: dict) -> None:
        mins = qa.get("durationMins") or 60
        self.dismiss({
            "project": qa["project"],
            "category": qa["category"],
            "hours": mins // 60,
            "minutes": mins % 60,
            "description": qa.get("note") or None,
            "workedFrom": qa.get("workedFrom") or self._default_location,
            "sentiment": "Neutral",
            "ticketNumber": None,
            "billable": False,
        })

    def action_custom_mode(self) -> None:
        if self._custom:
            return
        self._custom = True
        self.query_one("#qa-area").display = False
        self.query_one("#hint-line", Static).update("  [bold]↑↓[/] suggestions   [bold]Enter[/] select   [bold]Esc[/] cancel")
        self.query_one("#custom-area").display = True
        self.run_worker(self._mount_custom())

    async def _mount_custom(self) -> None:
        area = self.query_one("#custom-area")
        await area.mount(Label("Search category / project", classes="field-label"))
        await area.mount(Input(placeholder="e.g. standup, dev, meetings…", id="cat-inp"))
        await area.mount(Vertical(id="sug-box"))
        await area.mount(Label("Duration", classes="field-label"))
        await area.mount(
            Horizontal(
                Button("−", id="dur-min", variant="default"),
                Static(_fmt_mins(self._dur_mins), id="dur-val"),
                Button("+", id="dur-plus", variant="default"),
                id="dur-row",
            )
        )
        await area.mount(Label("Note (optional)", classes="field-label"))
        await area.mount(Input(placeholder="", id="note-inp"))
        await area.mount(
            Horizontal(Button("Add", variant="primary", id="btn-add"), Button("Cancel", id="btn-can"), id="btn-row")
        )
        self.query_one("#cat-inp", Input).focus()
        self._refresh_sugs("")

    def _refresh_sugs(self, q: str) -> None:
        q = q.lower().strip()
        self._sugs = []
        for proj, cats in self._cat_map.items():
            for cat in cats:
                if not q or q in cat.lower() or q in proj.lower():
                    self._sugs.append((proj, cat))
                if len(self._sugs) >= 7:
                    break
            if len(self._sugs) >= 7:
                break
        self._sug_idx = 0
        box = self.query_one("#sug-box", Vertical)
        for w in list(box.children):
            w.remove()
        for i, (proj, cat) in enumerate(self._sugs):
            box.mount(Static(
                f"  {'▶' if i == 0 else ' '} {cat:<22} [dim]{proj[:26]}[/]",
                classes=f"sug{'  sel' if i == 0 else ''}",
                id=f"s{i}",
            ))
        if self._sugs:
            self._proj, self._cat = self._sugs[0]

    def _move_sug(self, delta: int) -> None:
        if not self._sugs:
            return
        old = self._sug_idx
        self._sug_idx = max(0, min(len(self._sugs) - 1, self._sug_idx + delta))
        for i in range(len(self._sugs)):
            try:
                w = self.query_one(f"#s{i}", Static)
                proj, cat = self._sugs[i]
                sel = i == self._sug_idx
                w.update(f"  {'▶' if sel else ' '} {cat:<22} [dim]{proj[:26]}[/]")
                if sel:
                    w.add_class("sel")
                    self._proj, self._cat = proj, cat
                else:
                    w.remove_class("sel")
            except Exception:
                pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "cat-inp":
            self._refresh_sugs(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "cat-inp":
            if self._proj and self._cat:
                try:
                    self.query_one("#note-inp", Input).focus()
                except Exception:
                    pass
        elif event.input.id == "note-inp":
            self._submit_custom()

    def on_key_down_in_cat(self, event) -> None:
        pass  # handled globally below

    def watch_key(self, event) -> None:
        pass

    # Handle up/down in suggestions while cat-inp is focused
    def on_key(self, event) -> None:  # noqa: F811
        if self._custom:
            try:
                focused = self.focused
            except Exception:
                focused = None
            cat_inp = None
            try:
                cat_inp = self.query_one("#cat-inp", Input)
            except Exception:
                pass
            if focused is cat_inp:
                if event.key == "down":
                    self._move_sug(1)
                    event.stop()
                    return
                if event.key == "up":
                    self._move_sug(-1)
                    event.stop()
                    return
            return
        # quick-action number keys
        k = event.key
        if k.isdigit() and 0 < int(k) <= len(self._quick_actions):
            self._submit_quick(self._quick_actions[int(k) - 1])
            event.stop()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-can":
            self.dismiss(None)
        elif bid == "btn-add":
            self._submit_custom()
        elif bid == "dur-min":
            self._dur_mins = max(15, self._dur_mins - 15)
            self.query_one("#dur-val", Static).update(_fmt_mins(self._dur_mins))
        elif bid == "dur-plus":
            self._dur_mins += 15
            self.query_one("#dur-val", Static).update(_fmt_mins(self._dur_mins))

    def _submit_custom(self) -> None:
        if not self._proj or not self._cat:
            self.query_one("#err", Static).update("Select a category first (↓ to browse).")
            return
        try:
            note = self.query_one("#note-inp", Input).value.strip() or None
        except Exception:
            note = None
        self.dismiss({
            "project": self._proj,
            "category": self._cat,
            "hours": self._dur_mins // 60,
            "minutes": self._dur_mins % 60,
            "description": note,
            "workedFrom": self._default_location,
            "sentiment": "Neutral",
            "ticketNumber": None,
            "billable": False,
        })

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Timesheet Screen ──────────────────────────────────────────────────────────

class TimesheetScreen(Screen):
    BINDINGS = [
        Binding("[", "prev_day", "← Day"),
        Binding("]", "next_day", "Day →"),
        Binding("t", "today", "Today"),
        Binding("n", "add_entry", "Log time"),
        Binding("d", "delete_entry", "Delete"),
        Binding("plus", "nudge_up", "+15m"),
        Binding("minus", "nudge_down", "-15m"),
        Binding("r", "refresh", "Refresh"),
        Binding("escape", "go_back", "Back"),
    ]

    DEFAULT_CSS = """
    TimesheetScreen { background: $surface; }
    #banner {
        height: 1; padding: 0 1;
        background: $accent; color: $foreground; text-style: bold;
    }
    #day-strip { height: 3; }
    .day-cell {
        width: 1fr; height: 3; align: center middle; text-align: center;
        border-right: solid $surface-darken-2;
    }
    .day-cell.active { background: $accent; color: $foreground; text-style: bold; }
    .day-cell.today { color: $accent; text-style: bold; }
    #day-header {
        height: 1; padding: 0 1;
        color: $accent; text-style: bold; margin-top: 1;
    }
    #entries-table { height: 1fr; margin: 0 0; }
    #empty-msg {
        height: 3; text-align: center;
        padding: 1; color: $text-muted;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._member_id: str | None = None
        self._member_name = ""
        self._config: dict = {}
        self._entries: list[dict] = []
        self._today = datetime.date.today()
        self._selected = self._today
        self._wk_start = _week_start(self._today)

    @property
    def _week(self) -> list[datetime.date]:
        return [self._wk_start + datetime.timedelta(days=i) for i in range(5)]

    @property
    def _day_entries(self) -> list[dict]:
        key = _date_key(self._selected)
        return [e for e in self._entries if e.get("date", "")[:10] == key]

    def _total_for(self, d: datetime.date) -> int:
        key = _date_key(d)
        return sum(e.get("hours", 0) * 60 + e.get("minutes", 0)
                   for e in self._entries if e.get("date", "")[:10] == key)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("  Loading…", id="banner")
        with Horizontal(id="day-strip"):
            for i in range(5):
                yield Static("", classes="day-cell", id=f"dc{i}")
        yield Static("", id="day-header")
        yield DataTable(id="entries-table", cursor_type="row", zebra_stripes=True)
        yield Static("", id="empty-msg")
        yield Footer()

    def on_mount(self) -> None:
        tbl = self.query_one("#entries-table", DataTable)
        tbl.add_columns("Category", "Project", "Time", "Note", "Location")
        self.run_worker(self._load(), exclusive=True)

    # ── Data loading ──────────────────────────────────────────────────────────

    async def _load(self) -> None:
        import api
        try:
            me = await api.get_me()
            self._member_id = me["id"]
            self._member_name = f"{me.get('firstName', '')} {me.get('lastName', '')}".strip()
            months = {(d.year, d.month) for d in self._week}
            results = await asyncio.gather(
                api.get_timesheet_config(self._member_id),
                *[api.get_timesheets(self._member_id, y, m) for y, m in sorted(months)],
            )
            self._config = results[0]
            self._entries = []
            for r in results[1:]:
                self._entries.extend(r if isinstance(r, list) else [])
        except Exception as exc:
            self.query_one("#banner", Static).update(f"  [red]Error: {exc}[/]")
            return
        self._render()

    async def _reload_week(self) -> None:
        if not self._member_id:
            return
        import api
        months = {(d.year, d.month) for d in self._week}
        try:
            results = await asyncio.gather(
                *[api.get_timesheets(self._member_id, y, m) for y, m in sorted(months)]
            )
            # Drop cached entries for these months, replace with fresh data
            self._entries = [
                e for e in self._entries
                if (datetime.date.fromisoformat(e["date"][:10]).year,
                    datetime.date.fromisoformat(e["date"][:10]).month) not in months
            ]
            for r in results:
                self._entries.extend(r if isinstance(r, list) else [])
        except Exception as exc:
            self.app.notify(str(exc), severity="error", timeout=5)
        self._render()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render(self) -> None:
        week_total = sum(self._total_for(d) for d in self._week)
        self.query_one("#banner", Static).update(
            f"  {self._member_name}  ·  "
            f"Week {self._wk_start.strftime('%-d %b')}–"
            f"{(self._wk_start + datetime.timedelta(4)).strftime('%-d %b %Y')}"
            f"  [bold]Week total: {_fmt_mins(week_total)}[/]"
        )

        for i, d in enumerate(self._week):
            cell = self.query_one(f"#dc{i}", Static)
            total = self._total_for(d)
            is_active = d == self._selected
            is_today = d == self._today
            hrs = _fmt_mins(total) if total else "–"
            cell.update(f"{d.strftime('%a %-d')}\n{hrs}")
            classes = "day-cell"
            if is_active:
                classes += " active"
            elif is_today:
                classes += " today"
            cell.set_classes(classes)

        day_total = self._total_for(self._selected)
        total_str = f"  [dim]{_fmt_mins(day_total)}[/]" if day_total else ""
        self.query_one("#day-header", Static).update(
            f"  {self._selected.strftime('%A %-d %B %Y')}{total_str}"
        )

        entries = self._day_entries
        tbl = self.query_one("#entries-table", DataTable)
        tbl.clear()

        if entries:
            tbl.display = True
            self.query_one("#empty-msg", Static).update("")
            for e in entries:
                cat = e.get("category", "?")
                proj = e.get("project", "?")
                proj_s = (proj[:30] + "…") if len(proj) > 30 else proj
                mins = e.get("hours", 0) * 60 + e.get("minutes", 0)
                note = e.get("description") or "–"
                note_s = (note[:18] + "…") if len(note) > 18 else note
                loc = e.get("workedFrom") or "–"
                tbl.add_row(cat, proj_s, _fmt_mins(mins), note_s, loc, key=e["id"])
        else:
            tbl.display = False
            self.query_one("#empty-msg", Static).update(
                "[dim]No entries · press [bold]N[/] to log time[/]"
            )

    # ── Selected entry helper ─────────────────────────────────────────────────

    def _selected_entry(self) -> dict | None:
        tbl = self.query_one("#entries-table", DataTable)
        entries = self._day_entries
        if not tbl.display or not entries:
            return None
        row = tbl.cursor_row
        return entries[row] if 0 <= row < len(entries) else None

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_prev_day(self) -> None:
        self._selected -= datetime.timedelta(days=1)
        if self._selected < self._wk_start:
            self._wk_start -= datetime.timedelta(weeks=1)
            self.run_worker(self._reload_week(), exclusive=True)
        else:
            self._render()

    def action_next_day(self) -> None:
        self._selected += datetime.timedelta(days=1)
        if self._selected > self._wk_start + datetime.timedelta(days=4):
            self._wk_start += datetime.timedelta(weeks=1)
            self.run_worker(self._reload_week(), exclusive=True)
        else:
            self._render()

    def action_today(self) -> None:
        self._today = datetime.date.today()
        self._selected = self._today
        self._wk_start = _week_start(self._today)
        self.run_worker(self._reload_week(), exclusive=True)

    def action_refresh(self) -> None:
        self.run_worker(self._reload_week(), exclusive=True)

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_add_entry(self) -> None:
        if not self._member_id:
            return
        cfg = self._config
        ww = cfg.get("workWeek") or {}
        default_loc = ww.get(self._selected.strftime("%A"), "Home")
        loc_opts = cfg.get("workLocationOptions") or ["Home", "Other", "Client", "Entelect"]
        quick_actions = cfg.get("quickActions") or []
        merge = cfg.get("mergeEntriesEnabled", False)

        # Build cat_map from extra categories + entries seen this week
        cat_map: dict[str, list[str]] = {}
        for proj, cats in (cfg.get("extraCategories") or {}).items():
            cat_map[proj] = list(cats)
        for e in self._entries:
            p, c = e.get("project", ""), e.get("category", "")
            if p and c:
                cat_map.setdefault(p, [])
                if c not in cat_map[p]:
                    cat_map[p].append(c)

        date_label = self._selected.strftime("%a %-d %b")
        existing = self._day_entries

        def on_result(payload: dict | None) -> None:
            if payload is None:
                return
            payload["date"] = _date_key(self._selected)
            payload["billable"] = payload.get("project", "") in (cfg.get("billableProjects") or [])
            self.run_worker(self._create(payload, merge, existing))

        self.app.push_screen(
            LogTimeModal(date_label, quick_actions, cat_map, loc_opts, default_loc),
            callback=on_result,
        )

    async def _create(self, payload: dict, merge: bool, existing: list[dict]) -> None:
        import api
        try:
            if merge:
                match = next((
                    e for e in existing
                    if e.get("project") == payload.get("project")
                    and e.get("category") == payload.get("category")
                ), None)
                if match:
                    total = match["hours"] * 60 + match["minutes"] + payload["hours"] * 60 + payload["minutes"]
                    notes = [n for n in [match.get("description"), payload.get("description")] if n and n.strip()]
                    await api.update_timesheet_entry(self._member_id, match["id"], {
                        **payload,
                        "hours": total // 60,
                        "minutes": total % 60,
                        "description": "\n".join(notes) if len(notes) > 1 else (notes[0] if notes else None),
                        "workedFrom": match.get("workedFrom") or payload.get("workedFrom"),
                    })
                    self.app.notify("Entry merged", timeout=2)
                    await self._reload_week()
                    return
            await api.create_timesheet_entry(self._member_id, payload)
            self.app.notify("Logged ✓", timeout=2)
        except Exception as exc:
            self.app.notify(str(exc), title="Error", severity="error", timeout=8)
            return
        await self._reload_week()

    def action_delete_entry(self) -> None:
        e = self._selected_entry()
        if not e:
            return
        self.run_worker(self._delete(e["id"]))

    async def _delete(self, entry_id: str) -> None:
        import api
        try:
            await api.delete_timesheet_entry(self._member_id, entry_id)
            self.app.notify("Deleted", timeout=2)
        except Exception as exc:
            self.app.notify(str(exc), severity="error", timeout=8)
            return
        await self._reload_week()

    def action_nudge_up(self) -> None:
        e = self._selected_entry()
        if e:
            self.run_worker(self._nudge(e, e["hours"] * 60 + e["minutes"] + 15))

    def action_nudge_down(self) -> None:
        e = self._selected_entry()
        if e:
            self.run_worker(self._nudge(e, max(15, e["hours"] * 60 + e["minutes"] - 15)))

    async def _nudge(self, entry: dict, new_mins: int) -> None:
        import api
        try:
            await api.update_timesheet_entry(self._member_id, entry["id"], {
                **entry,
                "hours": new_mins // 60,
                "minutes": new_mins % 60,
            })
        except Exception as exc:
            self.app.notify(str(exc), severity="error", timeout=5)
            return
        await self._reload_week()
