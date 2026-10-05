"""Template loading and rendering utilities for versioned prompts."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "files"


def load_prompt_template(filename: str) -> str:
    """Load prompt template text from file."""
    filepath = PROMPTS_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Prompt template file not found: {filename}")
    return filepath.read_text(encoding="utf-8")


def render_template(template_text: str, variables: dict) -> str:
    """Simple mustache-style template renderer replacing {{variable_name}}."""
    rendered = template_text
    for key, value in variables.items():
        placeholder = f"{{{{{key}}}}}"
        rendered = rendered.replace(placeholder, str(value))
    return rendered
