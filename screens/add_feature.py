from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static
from textual.containers import Horizontal, Vertical

STATUSES = [
    ("Planned", "Planned"),
    ("In Progress", "InProgress"),
]


class AddFeatureModal(ModalScreen[dict | None]):
    """Modal form to create a new feature. Dismisses with the payload dict or None on cancel."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    AddFeatureModal {
        align: center middle;
    }
    #dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: solid $accent;
    }
    #dialog-title {
        height: 1;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    .field-label {
        height: 1;
        margin-top: 1;
        color: $foreground;
    }
    Input {
        margin-bottom: 0;
    }
    Select {
        margin-bottom: 0;
    }
    #error-msg {
        height: 1;
        color: $error;
        margin-top: 1;
    }
    #btn-row {
        margin-top: 1;
        height: 3;
        align: right middle;
    }
    #btn-row Button {
        margin-left: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Add Feature", id="dialog-title")
            yield Label("Title *", classes="field-label")
            yield Input(placeholder="Feature title", id="title", max_length=200)
            yield Label("Ticket ref", classes="field-label")
            yield Input(placeholder="e.g. PROJ-123", id="ref", max_length=50)
            yield Label("Status *", classes="field-label")
            yield Select(STATUSES, id="status", value="Planned")
            yield Label("Estimated days", classes="field-label")
            yield Input(placeholder="e.g. 3.5 (optional)", id="est-days", type="number")
            yield Static("", id="error-msg")
            with Horizontal(id="btn-row"):
                yield Button("Add", variant="primary", id="btn-add")
                yield Button("Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#title", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
            return
        self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        title = self.query_one("#title", Input).value.strip()
        ref = self.query_one("#ref", Input).value.strip() or None
        status_val = self.query_one("#status", Select).value
        est_str = self.query_one("#est-days", Input).value.strip()

        if not title:
            self.query_one("#error-msg", Static).update("Title is required.")
            self.query_one("#title", Input).focus()
            return

        est_days: float | None = None
        if est_str:
            try:
                est_days = float(est_str)
                if est_days <= 0:
                    raise ValueError
            except ValueError:
                self.query_one("#error-msg", Static).update("Estimated days must be a positive number.")
                self.query_one("#est-days", Input).focus()
                return

        self.dismiss({
            "title": title,
            "externalTicketRef": ref,
            "status": str(status_val),
            "estimatedDays": est_days,
        })

    def action_cancel(self) -> None:
        self.dismiss(None)
