from oatbrain.core.theme.models import ThemeData


def generate_gtk_css(theme: ThemeData) -> str:
    """Generate CSS: custom properties + GTK widget rules (SPEC §20.1)."""
    lines = [":root {"]
    for key, value in theme.tokens.items():
        lines.append(f"  --{key}: {value};")
    lines.append("}")

    # Widget rules — use var() so they always track the active token values.
    # Priority is APPLICATION+1, so these override Adwaita's defaults.
    # color-bg-alt = panel/sidebar color (tree, terminal)
    # color-bg     = content/editor color (slightly lighter/brighter)
    lines.append(
        """
.oatbrain-filetree {
    background-color: var(--color-bg-alt);
    color: var(--color-tree-fg, var(--color-fg));
    font-family: var(--font-ui);
}
.oatbrain-filetree row {
    background-color: var(--color-bg-alt);
    color: var(--color-tree-fg, var(--color-fg));
}
.oatbrain-filetree row:selected {
    background-color: var(--color-selection);
    color: var(--color-tree-fg, var(--color-fg));
}
.oatbrain-filetree row:hover:not(:selected) {
    background-color: var(--color-border);
}
.oatbrain-editor {
    background-color: var(--color-bg);
    color: var(--color-fg);
    font-family: var(--font-mono);
}
.oatbrain-editor text {
    background-color: var(--color-bg);
    color: var(--color-fg);
}
.oatbrain-group-pane,
.oatbrain-group-pane notebook,
.oatbrain-group-pane stack {
    background-color: var(--color-bg);
}
textview.oatbrain-editor border,
textview.oatbrain-editor gutter {
    background-color: var(--color-gutter-bg, var(--color-bg));
    color: var(--color-gutter-fg, var(--color-fg-muted));
}
.oatbrain-headerbar {
    background-color: var(--color-bg-alt);
    color: var(--color-fg);
    box-shadow: none;
    border: none;
}
.oatbrain-statusbar {
    background-color: var(--color-bg-alt);
    color: var(--color-fg-muted, var(--color-fg));
    border: none;
    box-shadow: none;
    padding: 6px 12px;
}
/* Hide separators and ensure toolbarview bars match background */
toolbarview > separator {
    opacity: 0;
    min-height: 0;
    min-width: 0;
}
toolbarview header,
toolbarview footer,
toolbarview .top-bar,
toolbarview .bottom-bar {
    background-color: var(--color-bg-alt);
    border: none;
    box-shadow: none;
}
paned > separator {
    background-color: var(--color-border);
    min-width: 1px;
    min-height: 1px;
}
:backdrop .oatbrain-headerbar,
:backdrop .oatbrain-statusbar,
:backdrop .oatbrain-filetree,
:backdrop .oatbrain-filetree row {
    background-color: var(--color-bg-alt-bd);
}
"""
    )

    return "\n".join(lines)
