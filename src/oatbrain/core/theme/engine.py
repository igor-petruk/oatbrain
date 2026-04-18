from oatbrain.core.theme.models import ThemeData


def generate_gtk_css(theme: ThemeData) -> str:
    """Generate a CSS :root block from theme tokens for GTK and WebKit (SPEC §20.1)."""
    lines = [":root {"]
    for key, value in theme.tokens.items():
        lines.append(f"  --{key}: {value};")
    lines.append("}")
    return "\n".join(lines)
