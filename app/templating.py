from pathlib import Path

from fastapi.templating import Jinja2Templates

from .config import get_settings

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _initials(name: str) -> str:
    if not name:
        return "?"
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _split_tags(tags: str | None):
    if not tags:
        return []
    return [t.strip() for t in tags.split(",") if t.strip()]


templates.env.filters["initials"] = _initials
templates.env.filters["split_tags"] = _split_tags
templates.env.globals["settings"] = get_settings()
