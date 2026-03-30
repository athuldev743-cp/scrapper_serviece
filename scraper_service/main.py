import re
import json
import asyncio
import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup

app = FastAPI(title="Design Scraper Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 12.0

# ─── Colour helpers ──────────────────────────────────────────────────────────

HEX_RE   = re.compile(r'#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b')
RGB_RE   = re.compile(r'rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})')
HSL_RE   = re.compile(r'hsla?\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%')

NOISE_COLORS = {
    "#ffffff", "#000000", "#fff", "#000",
    "#f0f0f0", "#e0e0e0", "#cccccc", "#333333",
}

def _hex3_to_6(h: str) -> str:
    return "".join(c * 2 for c in h)

def extract_colors_from_css(css_text: str) -> list[str]:
    colors: set[str] = set()
    for m in HEX_RE.finditer(css_text):
        h = m.group(1)
        full = ("#" + (_hex3_to_6(h) if len(h) == 3 else h)).lower()
        if full not in NOISE_COLORS:
            colors.add(full)
    for m in RGB_RE.finditer(css_text):
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        full = "#{:02x}{:02x}{:02x}".format(r, g, b)
        if full not in NOISE_COLORS:
            colors.add(full)
    return list(colors)[:12]

def extract_colors_from_soup(soup: BeautifulSoup) -> list[str]:
    colors: set[str] = set()
    for tag in soup.find_all(style=True):
        colors.update(extract_colors_from_css(tag["style"]))
    for style_tag in soup.find_all("style"):
        if style_tag.string:
            colors.update(extract_colors_from_css(style_tag.string))
    return list(colors)[:12]

# ─── Font helpers ─────────────────────────────────────────────────────────────

GFONT_RE   = re.compile(r'fonts\.googleapis\.com/css[^"\']*family=([^"\'&]+)')
FF_CSS_RE  = re.compile(r'font-family\s*:\s*([^;}{]+)')
FALLBACKS  = {"sans-serif","serif","monospace","inherit","initial","unset","var(--font)"}

def extract_fonts(soup: BeautifulSoup, css_text: str = "") -> list[str]:
    fonts: list[str] = []
    seen: set[str] = set()

    # Google Fonts links
    for m in GFONT_RE.finditer(str(soup)):
        for raw in m.group(1).replace("+", " ").split("|"):
            name = raw.split(":")[0].strip()
            if name and name not in seen:
                fonts.append(name); seen.add(name)

    # font-family rules in <style> or inline
    combined = css_text
    for tag in soup.find_all("style"):
        if tag.string:
            combined += tag.string
    for m in FF_CSS_RE.finditer(combined):
        for part in m.group(1).split(","):
            name = part.strip().strip("'\"")
            if name and name.lower() not in FALLBACKS and name not in seen:
                fonts.append(name); seen.add(name)

    return fonts[:6]

# ─── Spacing / layout helpers ─────────────────────────────────────────────────

SPACING_RE = re.compile(r'(?:padding|margin|gap|space)[^:]*:\s*([\d.]+(?:px|rem|em))')
RADIUS_RE  = re.compile(r'border-radius[^:]*:\s*([\d.]+(?:px|rem|em|%))')

def extract_spacing(css_text: str) -> dict:
    spacing_vals = SPACING_RE.findall(css_text)
    radius_vals  = RADIUS_RE.findall(css_text)
    return {
        "spacing_scale": list(dict.fromkeys(spacing_vals))[:6],
        "border_radius":  list(dict.fromkeys(radius_vals))[:4],
    }

# ─── Animation / transition helpers ──────────────────────────────────────────

ANIM_RE   = re.compile(r'animation\s*:[^;]+')
TRANS_RE  = re.compile(r'transition\s*:[^;]+')
EASING_RE = re.compile(r'(?:ease|cubic-bezier)[^;,)]*')

def extract_animations(css_text: str) -> dict:
    animations   = ANIM_RE.findall(css_text)[:4]
    transitions  = TRANS_RE.findall(css_text)[:4]
    easings      = list(dict.fromkeys(EASING_RE.findall(css_text)))[:4]
    return {
        "animation_examples": [a.strip() for a in animations],
        "transition_examples": [t.strip() for t in transitions],
        "easing_functions": easings,
    }

# ─── UI component patterns ────────────────────────────────────────────────────

COMPONENT_KEYWORDS = [
    "card", "hero", "navbar", "modal", "badge",
    "chip", "pill", "toast", "tooltip", "sidebar",
    "grid", "flex", "blur", "glass", "shadow",
]

def extract_component_patterns(soup: BeautifulSoup, css_text: str = "") -> list[str]:
    combined = (css_text + " " + " ".join(
        t.get("class", []) if isinstance(t.get("class", []), list)
        else [t.get("class", "")]
        for t in soup.find_all(True)
    )).lower()
    return [kw for kw in COMPONENT_KEYWORDS if kw in combined]

# ─── Scrapers ─────────────────────────────────────────────────────────────────

async def scrape_awwwards(client: httpx.AsyncClient, keyword: str) -> dict:
    url = f"https://www.awwwards.com/websites/search/?text={keyword}"
    try:
        r = await client.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
        soup = BeautifulSoup(r.text, "html.parser")
        css_text = r.text

        colors  = extract_colors_from_soup(soup)
        fonts   = extract_fonts(soup, css_text)
        spacing = extract_spacing(css_text)
        animations = extract_animations(css_text)
        components = extract_component_patterns(soup, css_text)

        # Try to pull a site name for context
        titles = [t.get_text(strip=True) for t in soup.select(".title")[:3]]

        return {
            "source": "awwwards",
            "keyword": keyword,
            "reference_sites": titles,
            "colors": colors,
            "fonts": fonts,
            **spacing,
            **animations,
            "component_patterns": components,
        }
    except Exception as e:
        return {"source": "awwwards", "error": str(e)}


async def scrape_landbook(client: httpx.AsyncClient, keyword: str) -> dict:
    url = f"https://land-book.com/?search={keyword}"
    try:
        r = await client.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
        soup = BeautifulSoup(r.text, "html.parser")
        css_text = r.text

        colors  = extract_colors_from_soup(soup)
        fonts   = extract_fonts(soup, css_text)
        spacing = extract_spacing(css_text)
        animations = extract_animations(css_text)
        components = extract_component_patterns(soup, css_text)

        return {
            "source": "land-book",
            "keyword": keyword,
            "colors": colors,
            "fonts": fonts,
            **spacing,
            **animations,
            "component_patterns": components,
        }
    except Exception as e:
        return {"source": "land-book", "error": str(e)}


# ─── Merge & score ────────────────────────────────────────────────────────────

def merge_results(results: list[dict]) -> dict:
    all_colors:     list[str] = []
    all_fonts:      list[str] = []
    all_spacing:    list[str] = []
    all_radii:      list[str] = []
    all_animations: list[str] = []
    all_transitions:list[str] = []
    all_easings:    list[str] = []
    all_components: list[str] = []
    sources:        list[str] = []

    for r in results:
        if "error" in r:
            continue
        sources.append(r.get("source", "?"))
        all_colors     += r.get("colors", [])
        all_fonts      += r.get("fonts", [])
        all_spacing    += r.get("spacing_scale", [])
        all_radii      += r.get("border_radius", [])
        all_animations += r.get("animation_examples", [])
        all_transitions+= r.get("transition_examples", [])
        all_easings    += r.get("easing_functions", [])
        all_components += r.get("component_patterns", [])

    def dedup(lst, limit=8):
        return list(dict.fromkeys(lst))[:limit]

    return {
        "sources_scraped": sources,
        "color_palette":   dedup(all_colors, 10),
        "fonts":           dedup(all_fonts, 5),
        "spacing_scale":   dedup(all_spacing, 6),
        "border_radius":   dedup(all_radii, 4),
        "animation_examples":  dedup(all_animations, 4),
        "transition_examples": dedup(all_transitions, 4),
        "easing_functions":    dedup(all_easings, 4),
        "component_patterns":  dedup(all_components),
    }


def build_design_brief(merged: dict, keyword: str) -> dict:
    palette = merged["color_palette"]
    fonts   = merged["fonts"]
    spacing = merged["spacing_scale"]
    radii   = merged["border_radius"]
    comps   = merged["component_patterns"]
    easings = merged["easing_functions"]

    # Compose natural-language prompt injections
    color_str   = ", ".join(palette[:5]) if palette else "use modern neutral tones with one bold accent"
    font_str    = " + ".join(fonts[:2])  if fonts   else "a clean geometric sans-serif"
    spacing_str = ", ".join(spacing[:3]) if spacing  else "8px, 16px, 24px, 48px"
    radius_str  = radii[0] if radii else "8px"
    comp_str    = ", ".join(comps[:6])   if comps   else "card, hero, navbar"
    easing_str  = easings[0] if easings else "cubic-bezier(0.4, 0, 0.2, 1)"

    css_prompt = (
        f"Use this exact color palette: {color_str}. "
        f"Typography: {font_str} via Google Fonts. "
        f"Spacing scale: {spacing_str}. "
        f"Border-radius: {radius_str}. "
        f"UI patterns detected: {comp_str}. "
        f"Easing: {easing_str}. "
        f"Add smooth transitions (200-400ms) on interactive elements. "
        f"Use CSS custom properties for all colors and spacing."
    )

    plan_theme = (
        f"Modern {keyword} UI — palette: {color_str}; "
        f"fonts: {font_str}; components: {comp_str}; "
        f"smooth micro-animations with {easing_str} easing."
    )

    return {
        "keyword":         keyword,
        "sources_scraped": merged["sources_scraped"],
        "color_palette":   palette,
        "fonts":           fonts,
        "spacing_scale":   spacing,
        "border_radius":   radii,
        "component_patterns": comps,
        "animation_examples":   merged["animation_examples"],
        "transition_examples":  merged["transition_examples"],
        "easing_functions":     merged["easing_functions"],
        # ── Ready-to-inject strings ──
        "css_prompt_injection":  css_prompt,
        "plan_theme_injection":  plan_theme,
    }


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/design-brief")
async def design_brief(keyword: str = Query(default="saas dashboard")):
    """
    Scrape Awwwards + Land-book for `keyword`, extract design tokens,
    and return a design brief JSON ready for LLM injection.
    """
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            scrape_awwwards(client, keyword),
            scrape_landbook(client, keyword),
        )

    merged = merge_results(list(results))
    brief  = build_design_brief(merged, keyword)
    return brief