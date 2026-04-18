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
:backdrop .oatbrain-headerbar,
:backdrop .oatbrain-filetree,
:backdrop .oatbrain-filetree row {
    background-color: var(--color-bg-alt-bd);
}
"""
    )

    return "\n".join(lines)
