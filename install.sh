#!/usr/bin/env bash
set -euo pipefail

# ── Team Manager TUI Installer ──────────────────────────────────────────────
# One-liner install:
#   curl -sSL https://raw.githubusercontent.com/juanlurie/team-manager-tui/main/install.sh | bash
#
# Or clone and run locally:
#   git clone git@github.com:juanlurie/team-manager-tui.git
#   cd team-manager-tui && bash install.sh --local
# ─────────────────────────────────────────────────────────────────────────────

REPO="juanlurie/team-manager-tui"
BRANCH="main"
INSTALL_DIR="${HOME}/.team-manager-tui"
BIN_DIR="${HOME}/.local/bin"
CLI_BIN="${BIN_DIR}/team-manager-tui"
USE_LOCAL=0

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}!${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1" >&2; }

# ── Parse args ──────────────────────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --local) USE_LOCAL=1 ;;
    esac
done

# ── Pre-flight checks ───────────────────────────────────────────────────────
command -v python3 >/dev/null 2>&1 || { error "python3 is required but not installed."; exit 1; }

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
MIN_VERSION="3.10"
if [ "$(printf '%s\n' "$MIN_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$MIN_VERSION" ]; then
    error "Python $MIN_VERSION or higher is required (found $PYTHON_VERSION)."
    exit 1
fi

echo ""
echo "  Team Manager TUI Installer"
echo "  ──────────────────────────"
echo ""

# ── Create directories ──────────────────────────────────────────────────────
mkdir -p "$INSTALL_DIR/screens"
mkdir -p "$BIN_DIR"

# ── Get source files ────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$USE_LOCAL" -eq 1 ]; then
    info "Installing from local source..."
    TUI_SRC="$SCRIPT_DIR"
    if [ ! -f "${TUI_SRC}/app.py" ]; then
        error "Cannot find app.py in ${TUI_SRC}. Run from the tui/ directory."
        exit 1
    fi
    cp "${TUI_SRC}/app.py" "${INSTALL_DIR}/app.py"
    cp "${TUI_SRC}/api.py" "${INSTALL_DIR}/api.py"
    cp "${TUI_SRC}/requirements.txt" "${INSTALL_DIR}/requirements.txt"
    cp "${TUI_SRC}/screens/"*.py "${INSTALL_DIR}/screens/"
else
    command -v git >/dev/null 2>&1  || { error "git is required but not installed."; exit 1; }

    info "Cloning TUI repository (shallow)..."
    TMP_DIR=$(mktemp -d)
    git clone --depth 1 --branch "$BRANCH" "https://github.com/${REPO}.git" "$TMP_DIR"

    TUI_SRC="$TMP_DIR"
    if [ ! -f "${TUI_SRC}/app.py" ]; then
        error "Could not find TUI source files after clone."
        rm -rf "$TMP_DIR"
        exit 1
    fi

    cp "${TUI_SRC}/app.py" "${INSTALL_DIR}/app.py"
    cp "${TUI_SRC}/api.py" "${INSTALL_DIR}/api.py"
    cp "${TUI_SRC}/requirements.txt" "${INSTALL_DIR}/requirements.txt"
    cp "${TUI_SRC}/screens/"*.py "${INSTALL_DIR}/screens/"
    rm -rf "$TMP_DIR"
fi

# ── Create/update venv ──────────────────────────────────────────────────────
if [ -d "${INSTALL_DIR}/venv" ]; then
    warn "Updating existing virtual environment..."
else
    info "Creating virtual environment..."
    python3 -m venv "${INSTALL_DIR}/venv"
fi

# ── Install dependencies ────────────────────────────────────────────────────
info "Installing dependencies..."
"${INSTALL_DIR}/venv/bin/pip" install --quiet --upgrade pip
"${INSTALL_DIR}/venv/bin/pip" install --quiet -r "${INSTALL_DIR}/requirements.txt"

# ── Create CLI wrapper ──────────────────────────────────────────────────────
info "Creating CLI wrapper at ${CLI_BIN}..."

cat > "${CLI_BIN}" << 'WRAPPER'
#!/usr/bin/env bash
# Team Manager TUI — auto-generated wrapper
INSTALL_DIR="${HOME}/.team-manager-tui"
export TEAM_MANAGER_API_URL="${TEAM_MANAGER_API_URL:-http://localhost:5000}"
cd "${INSTALL_DIR}"
exec "${INSTALL_DIR}/venv/bin/python3" "${INSTALL_DIR}/app.py" "$@"
WRAPPER

chmod +x "${CLI_BIN}"

# ── Ensure BIN_DIR is in PATH ───────────────────────────────────────────────
if ! echo "$PATH" | tr ':' '\n' | grep -qxF "$BIN_DIR"; then
    warn "Adding ${BIN_DIR} to your PATH..."
    SHELL_RC=""
    case "$SHELL" in
        */zsh)  SHELL_RC="${HOME}/.zshrc" ;;
        */bash) SHELL_RC="${HOME}/.bashrc" ;;
    esac
    if [ -n "$SHELL_RC" ]; then
        echo "" >> "$SHELL_RC"
        echo 'export PATH="${HOME}/.local/bin:${PATH}"' >> "$SHELL_RC"
        warn "Added to ${SHELL_RC}. Run 'source ${SHELL_RC}' or restart your terminal."
    fi
fi

# ── Done ────────────────────────────────────────────────────────────────────
echo ""
info "Installation complete!"
echo ""
echo "  Run the TUI with:"
echo "    team-manager-tui"
echo ""
echo "  Connect to a remote API:"
echo "    TEAM_MANAGER_API_URL=https://your-api.com team-manager-tui"
echo ""
echo "  Update to the latest version:"
echo "    curl -sSL https://raw.githubusercontent.com/${REPO}/${BRANCH}/install.sh | bash"
echo ""
