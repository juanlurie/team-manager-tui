# Team Manager TUI

A terminal dashboard for engineering managers using the [Team Manager](https://github.com/juanlurie/team-manager) platform. Built with [Textual](https://github.com/Textualize/textual).

## Quick Install

```bash
curl -sSL https://raw.githubusercontent.com/juanlurie/team-manager-tui/main/install.sh | bash
```

This installs the TUI to `~/.team-manager-tui` and creates a `team-manager-tui` command available from anywhere in your terminal.

## Usage

```bash
# Connect to local API (no auth)
team-manager-tui

# Connect to a remote API with an API key
TEAM_MANAGER_API_URL=https://your-api.com \
TEAM_MANAGER_API_KEY=your-key-here \
team-manager-tui
```

### Setting up an API Key

1. Log into the Team Manager web app
2. Go to **Profile** (sidebar) → **API Keys**
3. Click **Create Key** and copy the generated key
4. Use it with the `TEAM_MANAGER_API_KEY` env var

> You can also add `export TEAM_MANAGER_API_KEY=your-key` to your `~/.bashrc` or `~/.zshrc` so it's always available.

## Key Bindings

| Key | Action |
|-----|--------|
| `[` / `]` | Navigate between sprints |
| `n` | Add new feature |
| `Enter` | Open feature detail / work items |
| `r` | Refresh data |
| `b` / `Esc` | Go back |
| `q` | Quit |

## Screens

- **Dashboard** — Sprint overview with features, blockers, leave, and unallocated members
- **Feature Detail** — Work items grouped by status tabs (Planned, In Progress, Blocked, Done)
- **Work Items** — Individual member's work items with full filtering

## Requirements

- Python 3.10+
- A running Team Manager API instance

## Updating

Run the same install command again to pull the latest version:

```bash
curl -sSL https://raw.githubusercontent.com/juanlurie/team-manager-tui/main/install.sh | bash
```

## Manual Install

```bash
git clone git@github.com:juanlurie/team-manager-tui.git
cd team-manager-tui
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```
