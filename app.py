#!/usr/bin/env python3
"""Team Manager TUI — read-only terminal dashboard for engineering managers."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Label

import api


class TeamManagerApp(App):
    TITLE = "Team Manager"
    CSS = """
    Screen {
        background: $surface;
    }
    #main-area {
        height: 1fr;
    }
    #left-panel {
        width: 2fr;
        border-right: solid $accent;
        padding: 0 1;
    }
    #right-panel {
        width: 1fr;
        padding: 0 1;
    }
    #members-label {
        height: 1;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #members-table {
        height: 1fr;
    }
    #right-content {
        height: auto;
    }
    #stats-bar {
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
        color: $text-muted;
    }
    #wi-header {
        height: 1;
        padding: 0 1;
        background: $accent;
        color: $text;
        text-style: bold;
    }
    TabbedContent {
        height: 1fr;
    }
    TabPane {
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._sprints: list[dict] = []
        self._sprint_index: int = 0

    def compose(self) -> ComposeResult:
        yield Label("  Loading sprints…", id="loading")

    def on_mount(self) -> None:
        self.run_worker(self._bootstrap(), exclusive=True)

    async def _bootstrap(self) -> None:
        try:
            sprints = await api.get_sprints()
        except Exception as exc:
            self.query_one("#loading", Label).update(
                f"[red]Cannot connect to API at {api.BASE_URL}\n{exc}[/]\n\n"
                "Make sure the Team Manager API is running.\n"
                "Set TEAM_MANAGER_API_URL to override the base URL.\n"
                "Set TEAM_MANAGER_API_KEY if your API requires authentication."
            )
            return

        if not sprints:
            self.query_one("#loading", Label).update("[yellow]No sprints found.[/]")
            return

        # Sort newest first — prefer active sprints, then by start date
        sprints.sort(key=lambda s: (not s.get("isActive", False), s.get("startDate", "") or ""), reverse=False)
        sprints.sort(key=lambda s: s.get("startDate", "") or "", reverse=True)

        self._sprints = sprints
        self._sprint_index = 0

        # Find the most recent active sprint
        for i, s in enumerate(sprints):
            if s.get("isActive"):
                self._sprint_index = i
                break

        await self._push_dashboard()

    async def _push_dashboard(self) -> None:
        from screens.dashboard import DashboardScreen
        sprint = self._sprints[self._sprint_index]
        # Replace current screen (don't stack indefinitely when cycling)
        if len(self.screen_stack) > 1:
            await self.pop_screen()
        await self.push_screen(DashboardScreen(sprint, self._sprints))

    def action_prev_sprint(self) -> None:
        if not self._sprints:
            return
        self._sprint_index = (self._sprint_index + 1) % len(self._sprints)
        self.run_worker(self._push_dashboard(), exclusive=True)

    def action_next_sprint(self) -> None:
        if not self._sprints:
            return
        self._sprint_index = (self._sprint_index - 1) % len(self._sprints)
        self.run_worker(self._push_dashboard(), exclusive=True)


if __name__ == "__main__":
    TeamManagerApp().run()
