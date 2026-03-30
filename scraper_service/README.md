# Design Scraper Service

Tiny FastAPI microservice that scrapes **Awwwards** + **Land-book**,
extracts real design tokens, and returns a JSON brief your agent injects
into every LLM prompt — giving every generated UI real, modern aesthetics.

---

## What it extracts

| Token | Source |
|---|---|
| Color palette (hex) | CSS, inline styles |
| Font families | Google Fonts links, font-family rules |
| Spacing scale | padding/margin/gap values |
| Border radius | border-radius rules |
| Component patterns | CSS class names (card, hero, glass…) |
| Animation examples | animation: rules |
| Transition examples | transition: rules |
| Easing functions | cubic-bezier / ease values |

---

## Local dev

```bash
cd scraper_service
pip install -r requirements.txt
uvicorn main:app --port 8010 --reload

# Test it
curl "http://localhost:8010/design-brief?keyword=todo+app"
curl "http://localhost:8010/health"
```

---

## Deploy to Render (free)

1. Push this repo to GitHub
2. Go to https://render.com → New → Blueprint
3. Point it at your repo — Render reads `render.yaml` automatically
4. Service name: `design-scraper`
5. After deploy, copy the service URL e.g. `https://design-scraper.onrender.com`

---

## Connect your agent

Add to your `.env`:
```
DESIGN_SCRAPER_URL=https://design-scraper.onrender.com
```

Then apply the 3 changes in `llm_patch.py` to your `llm.py`.

---

## Flow

```
User prompt
    │
    ▼
design_client.get_design_brief(prompt)
    │  extracts keyword → calls /design-brief
    │
    ▼
Scraper hits Awwwards + Land-book in parallel
    │
    ▼
Returns design_brief {
    color_palette, fonts, spacing_scale,
    css_prompt_injection,   ← injected into SECTION_SYSTEM for .css files
    plan_theme_injection    ← injected into PLAN_SYSTEM for design_theme field
}
    │
    ├─► plan_project()  gets real design_theme
    │
    └─► generate_file("*.css")  gets exact hex codes + font names
```

---

## Fallback

If the scraper is unreachable (cold start, rate limited), `design_client.py`
returns a sensible hardcoded fallback brief automatically — your agent
never crashes, it just uses safe modern defaults.
```