# oatbrain

A single-window, local-first desktop app for a personal Markdown vault.

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
    xvfb
```

## Development

### Setup

```bash
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -e .
```

### Running the application

```bash
python3 -m oatbrain
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
