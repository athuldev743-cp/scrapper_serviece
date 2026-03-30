"""
design_client.py — calls the deployed scraper service and returns
a design_brief dict ready to inject into LLM prompts.

Usage:
    from design_client import get_design_brief
    brief = get_design_brief("todo app")
    css_hint  = brief["css_prompt_injection"]
    plan_hint = brief["plan_theme_injection"]
"""

import os
import re
import httpx

# ── Config ────────────────────────────────────────────────────────────────────
# Set DESIGN_SCRAPER_URL in your .env or environment.
# During local dev you can run the service with:
#   cd scraper_service && uvicorn main:app --port 8010
SCRAPER_URL = os.environ.get(
    "DESIGN_SCRAPER_URL",
    "http://localhost:8010",   # overridden by .env in prod
).rstrip("/")

TIMEOUT = 15.0

# ── Keyword extraction ────────────────────────────────────────────────────────

_STOP = {
    "a","an","the","for","with","using","build","make","create",
    "app","application","website","site","page","project","tool",
    "simple","basic","full","new","my","i","want","need",
}

def _extract_keyword(prompt: str, fallback: str = "saas dashboard") -> str:
    words = re.findall(r"[a-z]+", prompt.lower())
    candidates = [w for w in words if w not in _STOP and len(w) > 3]
    return candidates[0] if candidates else fallback

# ── Fallback brief (when scraper is unreachable) ──────────────────────────────

def _fallback_brief(keyword: str) -> dict:
    return {
        "keyword":         keyword,
        "sources_scraped": [],
        "color_palette":   [],
        "fonts":           [],
        "spacing_scale":   [],
        "border_radius":   [],
        "component_patterns": [],
        "animation_examples":  [],
        "transition_examples": [],
        "easing_functions":    [],
        "css_prompt_injection": (
            "Use a modern, clean UI with a neutral base (#f8fafc, #1e293b) "
            "and one vibrant accent. Typography: a geometric sans-serif via Google Fonts. "
            "Spacing: 8px grid. Border-radius: 8px. "
            "Add smooth transitions (200ms ease) on all interactive elements. "
            "Use CSS custom properties for all colors and spacing."
        ),
        "plan_theme_injection": (
            f"Modern {keyword} UI with clean minimal aesthetic, "
            "neutral palette with bold accent, smooth micro-animations."
        ),
        "_fallback": True,
    }

# ── Public API ────────────────────────────────────────────────────────────────

def get_design_brief(prompt: str) -> dict:
    """
    Derive a keyword from the user prompt, hit the scraper service,
    and return the design brief dict.
    Falls back gracefully if the service is down.
    """
    keyword = _extract_keyword(prompt)

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            r = client.get(
                f"{SCRAPER_URL}/design-brief",
                params={"keyword": keyword},
            )
            r.raise_for_status()
            brief = r.json()

        # Validate minimal shape
        if "css_prompt_injection" not in brief or "plan_theme_injection" not in brief:
            raise ValueError("Malformed brief response")

        return brief

    except Exception as e:
        print(f"[design_client] scraper unreachable ({e}), using fallback brief.")
        return _fallback_brief(keyword)


def inject_into_plan_system(base_system: str, brief: dict) -> str:
    """
    Appends the design brief's plan_theme_injection into the PLAN_SYSTEM prompt
    so plan_project() produces a grounded design_theme.
    """
    hint = brief.get("plan_theme_injection", "")
    if not hint:
        return base_system
    injection = (
        f"\n\nDESIGN BRIEF (scraped from Awwwards + Land-book):\n"
        f"Use this as the design_theme field and overall visual direction:\n"
        f"{hint}"
    )
    return base_system + injection


def inject_into_css_system(base_system: str, brief: dict) -> str:
    """
    Appends the design brief's css_prompt_injection into the SECTION_SYSTEM prompt
    so CSS file generation uses real scraped tokens.
    """
    hint = brief.get("css_prompt_injection", "")
    if not hint:
        return base_system
    injection = (
        f"\n\nDESIGN TOKENS (from live scrape — follow these exactly):\n"
        f"{hint}"
    )
    return base_system + injection