# oatbrain

A single-window, local-first desktop app for a personal Markdown vault. It allows you to build an AI-assisted "second brain" to organize large amounts of information efficiently.

## Vision

oatbrain is a single-window, local-first desktop app for a personal Markdown vault. It presents three panes:
1. A **file tree** rooted at the vault directory.
2. An **editor / preview** pane that flips between source-markdown editing and a rendered read mode.
3. A **terminal** emulator — a first-class peer of the editor.

## Installation

Currently in early development (Phase 1). Requires Python 3.12+ and GTK 4 / libadwaita.

### Debian/Ubuntu Dependencies

```bash
sudo apt-get update
sudo apt-get install -y \
    python3-gi \
    gir1.2-gtk-4.0 \
    gir1.2-adw-1 \
    gir1.2-vte-3.91 \
    gir1.2-webkit-6.0 \
    gir1.2-gtksource-5 \
    python3-markdown-it \
    python3-mdit-py-plugins \
    python3-yaml \
    fzf \
    python3-pyfzf \
    ripgrep \
    python3-pytest \
    python3-mypy \
    python3-ruff \
    xvfb
```

## Development

### Setup

No virtual environment or `pip` is required if system dependencies are installed.

### Running the application

You can run oatbrain directly using Python. Pass an optional path to a vault directory.

```bash
# Run using the module
PYTHONPATH=src python3 -m oatbrain [/path/to/your/vault]
```

### Linting and Testing

The project uses `ruff`, `mypy`, `tach`, and `pytest`.

```bash
# Run all linters
make lint

# Run unit tests
make test

# Run tests with xvfb (headless)
xvfb-run make test
```

## Architecture

oatbrain follows a hexagonal (Ports & Adapters) architecture.
- `core/`: Pure domain logic and Protocols (Ports).
- `adapters/`: Concrete implementations of ports.
- `ui/`: GTK 4 widgets.
- `app/`: Composition root.

Enforced by `tach`. See `SPEC.md` for details.
