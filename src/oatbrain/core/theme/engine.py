from oatbrain.core.theme.models import ThemeData


def generate_gtk_css(theme: ThemeData) -> str:
    """Generate CSS: custom properties + GTK widget rules (SPEC §20.1)."""
    lines = [":root {"]
    for key, value in theme.tokens.items():
        lines.append(f"  --{key}: {value};")
    lines.append("}")

    # Widget rules — use var() so they always track the active token values.
    # Priority is APPLICATION+1, so these override Adwaita's defaults.
    lines.append("""
.oatbrain-filetree {
    background-color: var(--color-bg-alt);
    color: var(--color-fg);
}
.oatbrain-filetree row {
    background-color: var(--color-bg-alt);
    color: var(--color-fg);
}
.oatbrain-filetree row:selected {
    background-color: var(--color-selection);
    color: var(--color-fg);
}
.oatbrain-filetree row:hover:not(:selected) {
    background-color: var(--color-border);
}
""")

    return "\n".join(lines)
