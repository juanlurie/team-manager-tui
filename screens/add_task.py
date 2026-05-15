from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static
from textual.containers import Horizontal, Vertical

TYPES = [
    ("Task", "Task"),
    ("Bug", "Bug"),
    ("Dev", "Dev"),
    ("QA", "QA"),
    ("Analysis", "Analysis"),
    ("Design", "Design"),
    ("Release", "Release"),
]

STATUSES = [
    ("Planned", "Planned"),
    ("In Progress", "InProgress"),
]


class AddTaskModal(ModalScreen[dict | None]):
    """Modal form to create a work item. Dismisses with the payload dict or None on cancel."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    AddTaskModal {
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

    def __init__(self, members: list[dict]) -> None:
        super().__init__()
        self._members = members

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Add Task", id="dialog-title")
            yield Label("Title *", classes="field-label")
            yield Input(placeholder="Task title", id="title", max_length=200)
            yield Label("Assignee *", classes="field-label")
            yield Select([], id="assignee", prompt="Select a member")
            yield Label("Type *", classes="field-label")
            yield Select(TYPES, id="type", value="Task")
            yield Label("Status *", classes="field-label")
            yield Select(STATUSES, id="status", value="Planned")
            yield Label("Ticket ref", classes="field-label")
            yield Input(placeholder="e.g. PROJ-123", id="ref", max_length=50)
            yield Label("Est. points", classes="field-label")
            yield Input(placeholder="e.g. 3 (optional)", id="est-points", type="number")
            yield Static("", id="error-msg")
            with Horizontal(id="btn-row"):
                yield Button("Add", variant="primary", id="btn-add")
                yield Button("Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#title", Input).focus()
        options = [(m.get("fullName") or "?", m.get("sprintMemberId") or "") for m in self._members]
        select = self.query_one("#assignee", Select)
        select.set_options(options)
        if options:
            select.value = options[0][1]

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
        type_val = self.query_one("#type", Select).value
        status_val = self.query_one("#status", Select).value
        assignee_id = self.query_one("#assignee", Select).value
        est_str = self.query_one("#est-points", Input).value.strip()

        if not title:
            self.query_one("#error-msg", Static).update("Title is required.")
            self.query_one("#title", Input).focus()
            return

        if not assignee_id:
            self.query_one("#error-msg", Static).update("Assignee is required.")
            self.query_one("#assignee", Select).focus()
            return

        est_points: float | None = None
        if est_str:
            try:
                est_points = float(est_str)
                if est_points <= 0:
                    raise ValueError
            except ValueError:
                self.query_one("#error-msg", Static).update("Estimated points must be a positive number.")
                self.query_one("#est-points", Input).focus()
                return

        self.dismiss({
            "title": title,
            "externalTicketRef": ref,
            "type": str(type_val),
            "status": str(status_val),
            "sprintMemberId": str(assignee_id),
            "estimatedPoints": est_points,
        })

    def action_cancel(self) -> None:
        self.dismiss(None)
