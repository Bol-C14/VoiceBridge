#!/usr/bin/env bash
set -euo pipefail

# VoiceBridge one-click local setup + run.
#
# Usage:
#   bash scripts/oneclick.sh setup
#   bash scripts/oneclick.sh daemon
#   bash scripts/oneclick.sh meeting
#   bash scripts/oneclick.sh test
#
# Environment overrides:
#   PYTHON=python3.11
#   VENV_DIR=/path/to/venv
#   VOICEBRIDGE_BIN_DIR=/usr/local/bin
#   CORE_EXTRAS=audio,vad,asr   (default)
#   NO_EXTRAS=1                (skip optional extras)

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT/.venv}"

CORE_EXTRAS="${CORE_EXTRAS:-audio,vad,asr}"
NO_EXTRAS="${NO_EXTRAS:-0}"

DAEMON_HOST="${DAEMON_HOST:-127.0.0.1}"
DAEMON_PORT="${DAEMON_PORT:-8765}"

function info() { echo "[voicebridge] $*"; }
function warn() { echo "[voicebridge][warn] $*" 1>&2; }
function die() { echo "[voicebridge][error] $*" 1>&2; exit 1; }

function ensure_python() {
  command -v "$PYTHON" >/dev/null 2>&1 || die "Python not found: $PYTHON"
}

function ensure_venv() {
  if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating venv at: $VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
  fi
}

function venv_python() {
  echo "$VENV_DIR/bin/python"
}

function ensure_pip_updated() {
  info "Upgrading pip..."
  # Pin setuptools for webrtcvad compatibility (needs pkg_resources).
  "$(venv_python)" -m pip install -q -U pip wheel "setuptools<81"
}

function install_packages() {
  info "Installing core/daemon/cli (editable)..."
  if [[ "$NO_EXTRAS" == "1" ]]; then
    "$(venv_python)" -m pip install -q -e "$ROOT/packages/voicebridge_core"
  else
    "$(venv_python)" -m pip install -q -e "$ROOT/packages/voicebridge_core[$CORE_EXTRAS]" || {
      warn "Failed installing audio extras ($CORE_EXTRAS)."
      warn "On macOS you may need: brew install portaudio"
      die "Dependency install failed."
    }
  fi

  "$(venv_python)" -m pip install -q -e "$ROOT/apps/daemon"
  "$(venv_python)" -m pip install -q -e "$ROOT/apps/cli"
}

function _py_has_module() {
  local mod="$1"
  "$(venv_python)" -c "import ${mod}" >/dev/null 2>&1
}

function ensure_runtime_deps() {
  # Detect and install missing runtime deps into the venv (idempotent).
  if [[ "$NO_EXTRAS" == "1" ]]; then
    return 0
  fi

  local need_extras=0

  # Meeting audio stack
  # Ensure pkg_resources exists for webrtcvad.
  _py_has_module "pkg_resources" || "$(venv_python)" -m pip install -q "setuptools<81" || true
  _py_has_module "webrtcvad" || need_extras=1
  _py_has_module "sounddevice" || need_extras=1
  _py_has_module "numpy" || need_extras=1
  _py_has_module "faster_whisper" || need_extras=1

  if [[ "$need_extras" == "1" ]]; then
    info "Installing missing meeting runtime deps: voicebridge-core[$CORE_EXTRAS]"
    "$(venv_python)" -m pip install -q -e "$ROOT/packages/voicebridge_core[$CORE_EXTRAS]" || {
      warn "Failed installing meeting runtime deps ($CORE_EXTRAS)."
      warn "If sounddevice fails on macOS, install PortAudio: brew install portaudio"
      die "Dependency install failed."
    }
  fi

  # Daemon WebSocket support (needed for the browser UI live stream)
  if ! _py_has_module "websockets"; then
    info "Installing WebSocket dependency: websockets"
    "$(venv_python)" -m pip install -q "websockets>=11,<14" || die "Failed to install websockets"
  fi
}

function in_path() {
  case ":$PATH:" in
    *":$1:"*) return 0 ;;
    *) return 1 ;;
  esac
}

function choose_bin_dir() {
  if [[ -n "${VOICEBRIDGE_BIN_DIR:-}" ]]; then
    echo "$VOICEBRIDGE_BIN_DIR"
    return 0
  fi

  # Prefer writable dirs that are already on PATH.
  local candidates=(
    "/usr/local/bin"
    "/opt/homebrew/bin"
    "$HOME/.local/bin"
    "$HOME/bin"
  )

  local d
  for d in "${candidates[@]}"; do
    mkdir -p "$d" 2>/dev/null || true
    if [[ -d "$d" && -w "$d" && "$(cd "$d" && pwd)" != "$(cd "$VENV_DIR/bin" && pwd)" ]]; then
      if in_path "$d"; then
        echo "$d"
        return 0
      fi
    fi
  done

  # Fallback: writable even if not on PATH.
  for d in "${candidates[@]}"; do
    mkdir -p "$d" 2>/dev/null || true
    if [[ -d "$d" && -w "$d" && "$(cd "$d" && pwd)" != "$(cd "$VENV_DIR/bin" && pwd)" ]]; then
      echo "$d"
      return 0
    fi
  done

  echo ""
}

function install_wrappers() {
  local bin_dir
  bin_dir="$(choose_bin_dir)"
  if [[ -z "$bin_dir" ]]; then
    warn "No writable bin dir found; skipping PATH install."
    return 0
  fi

  info "Installing PATH wrappers into: $bin_dir"
  local vb="$bin_dir/voicebridge"
  local vbd="$bin_dir/voicebridge-daemon"

  _write_wrapper "$vb" "voicebridge_cli" "$ROOT"
  _write_wrapper "$vbd" "voicebridge_daemon" "$ROOT"

  if ! in_path "$bin_dir"; then
    warn "Bin dir is not on PATH: $bin_dir"
    warn "Add to PATH (zsh): echo 'export PATH=\"$bin_dir:$PATH\"' >> ~/.zshrc && source ~/.zshrc"
  fi
}

function _write_wrapper() {
  local path="$1"
  local module="$2"
  local root="$3"

  if [[ -e "$path" && ! -L "$path" ]]; then
    warn "Not overwriting existing file: $path"
    return 0
  fi
  if [[ -L "$path" ]]; then
    rm -f "$path" || true
  fi

  cat >"$path" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export VOICEBRIDGE_CONFIG_DIR="${root}/config"
exec "${VENV_DIR}/bin/python" -m ${module} "\$@"
EOF
  chmod +x "$path" || true
}

function setup() {
  ensure_python
  ensure_venv
  ensure_pip_updated
  install_packages
  ensure_runtime_deps
  install_wrappers
  info "Setup complete."
  info "Try:"
  info "  voicebridge-daemon --host ${DAEMON_HOST} --port ${DAEMON_PORT}"
  info "  voicebridge meeting --profile Meeting"
}

function run_daemon() {
  setup
  info "Starting daemon at http://${DAEMON_HOST}:${DAEMON_PORT}/"
  exec "${VENV_DIR}/bin/python" -m voicebridge_daemon --host "${DAEMON_HOST}" --port "${DAEMON_PORT}"
}

function run_meeting() {
  setup
  info "Starting meeting CLI (Ctrl+C to stop)."
  exec "${VENV_DIR}/bin/python" -m voicebridge_cli meeting --profile Meeting
}

function run_tests() {
  setup
  "${VENV_DIR}/bin/python" -m pip install -q -e "$ROOT/packages/voicebridge_core[dev]"
  info "Running tests..."
  PYTHONPATH="$ROOT/packages/voicebridge_core" "${VENV_DIR}/bin/python" -m pytest -q "$ROOT/packages/voicebridge_core/tests"
}

cmd="${1:-daemon}"
case "$cmd" in
  setup) setup ;;
  daemon) run_daemon ;;
  meeting) run_meeting ;;
  test|tests) run_tests ;;
  *)
    echo "Usage: bash scripts/oneclick.sh [setup|daemon|meeting|test]"
    exit 2
    ;;
esac
