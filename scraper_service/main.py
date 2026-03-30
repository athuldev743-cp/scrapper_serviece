import re
import os
import json
import asyncio
import httpx
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Design Scraper Service", version="2.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 6.0
ANIMATE_CSS_CDN = "https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"
GRADIENTS_JSON_URL = "https://raw.githubusercontent.com/ghosh/uiGradients/master/gradients.json"

CATEGORY_ANIMATIONS = {
    "todo":      ["fadeInUp", "fadeIn", "slideInLeft", "pulse"],
    "dashboard": ["fadeInUp", "fadeIn", "zoomIn", "slideInDown"],
    "saas":      ["fadeInUp", "zoomIn", "fadeIn", "slideInUp"],
    "ecommerce": ["fadeInUp", "slideInLeft", "pulse", "fadeIn"],
    "blog":      ["fadeIn", "fadeInUp", "slideInUp"],
    "chat":      ["fadeInUp", "slideInLeft", "slideInRight", "fadeIn"],
    "finance":   ["fadeInUp", "fadeIn", "zoomIn", "slideInDown"],
    "portfolio": ["fadeInUp", "zoomIn", "fadeIn", "slideInLeft"],
    "default":   ["fadeInUp", "fadeIn", "slideInUp", "pulse"],
}

ELEMENT_ANIMATION_MAP = {
    "card":    "animate__animated animate__fadeInUp",
    "hero":    "animate__animated animate__fadeIn",
    "navbar":  "animate__animated animate__slideInDown",
    "modal":   "animate__animated animate__zoomIn",
    "toast":   "animate__animated animate__slideInRight",
    "badge":   "animate__animated animate__pulse",
    "sidebar": "animate__animated animate__slideInLeft",
    "list":    "animate__animated animate__fadeInUp",
}

TRANSITION_RECIPES = {
    "smooth":     "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
    "spring":     "all 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
    "snappy":     "all 0.15s cubic-bezier(0.4, 0, 1, 1)",
    "bouncy":     "all 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)",
    "slow_fade":  "opacity 0.6s ease, transform 0.6s ease",
    "color_only": "color 0.2s ease, background-color 0.2s ease, border-color 0.2s ease",
    "lift":       "transform 0.2s ease, box-shadow 0.2s ease",
    "slide_up":   "transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease",
}

CATEGORY_TRANSITIONS = {
    "todo":      ["smooth", "snappy", "lift"],
    "dashboard": ["smooth", "slow_fade", "color_only"],
    "saas":      ["spring", "smooth", "lift"],
    "ecommerce": ["smooth", "lift", "snappy"],
    "blog":      ["slow_fade", "smooth", "color_only"],
    "chat":      ["snappy", "smooth", "slide_up"],
    "finance":   ["smooth", "color_only", "lift"],
    "portfolio": ["spring", "slow_fade", "lift"],
    "default":   ["smooth", "lift", "spring"],
}

GRADIENT_DB = {
    "todo":      [("Cosmic Fusion","linear-gradient(135deg,#0f172a 0%,#312e81 100%)","#f8fafc"),("Deep Space","linear-gradient(135deg,#0f0c29 0%,#302b63 50%,#24243e 100%)","#f8fafc")],
    "dashboard": [("Dark Ocean","linear-gradient(135deg,#0a0a0b 0%,#0f172a 100%)","#f0fdf4"),("Carbon","linear-gradient(135deg,#0a0a0b 0%,#1a1a2e 100%)","#e2e8f0")],
    "saas":      [("Violet Sky","linear-gradient(135deg,#030712 0%,#1e1b4b 100%)","#f9fafb"),("Predawn","linear-gradient(135deg,#030712 0%,#2d1b69 100%)","#e5e7eb")],
    "ecommerce": [("Autumn Warmth","linear-gradient(135deg,#1c1917 0%,#292524 100%)","#fef3c7"),("Ember","linear-gradient(135deg,#1c1917 0%,#451a03 100%)","#fed7aa")],
    "blog":      [("Dark Romance","linear-gradient(135deg,#1a1a2e 0%,#16213e 100%)","#f5f5f5"),("Editorial","linear-gradient(135deg,#1a1a2e 0%,#0f3460 50%,#16213e 100%)","#e2e8f0")],
    "chat":      [("Deep Twilight","linear-gradient(135deg,#0f172a 0%,#1e293b 100%)","#e2e8f0"),("Nebula","linear-gradient(135deg,#0f172a 0%,#1a0533 100%)","#c4b5fd")],
    "finance":   [("Matrix","linear-gradient(135deg,#0d1117 0%,#161b22 100%)","#00d084"),("Dark Terminal","linear-gradient(135deg,#0d1117 0%,#010409 100%)","#00d084")],
    "portfolio": [("Obsidian","linear-gradient(135deg,#09090b 0%,#18181b 100%)","#fafafa"),("Void","linear-gradient(135deg,#09090b 0%,#27272a 100%)","#a1a1aa")],
    "default":   [("Midnight","linear-gradient(135deg,#0f172a 0%,#1e293b 100%)","#f8fafc"),("Deep Blue","linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%)","#e2e8f0")],
}

DESIGN_DB = {
    "todo":      {"colors":["#0f172a","#1e293b","#f1f5f9","#e2e8f0","#6366f1","#22c55e"],"fonts":["Plus Jakarta Sans","DM Sans"],"spacing_scale":["4px","8px","16px","24px","48px"],"border_radius":["6px","12px","999px"],"component_patterns":["card","pill","input","toast","list"]},
    "dashboard": {"colors":["#0a0a0b","#18181b","#3b82f6","#06b6d4","#f0fdf4","#d1fae5"],"fonts":["Inter","JetBrains Mono"],"spacing_scale":["8px","16px","24px","32px","64px"],"border_radius":["4px","8px","16px"],"component_patterns":["card","sidebar","badge","navbar","grid"]},
    "saas":      {"colors":["#030712","#1e1b4b","#6366f1","#8b5cf6","#f9fafb","#fbbf24"],"fonts":["Sora","Inter"],"spacing_scale":["8px","16px","32px","64px","128px"],"border_radius":["8px","16px","24px"],"component_patterns":["hero","card","navbar","modal","badge"]},
    "ecommerce": {"colors":["#1c1917","#292524","#f97316","#fef3c7","#e7e5e4","#10b981"],"fonts":["Nunito","Lato"],"spacing_scale":["8px","12px","20px","32px","48px"],"border_radius":["4px","8px","20px"],"component_patterns":["card","badge","hero","grid","pill"]},
    "blog":      {"colors":["#1a1a2e","#16213e","#e94560","#f5f5f5","#ffffff","#0f3460"],"fonts":["Playfair Display","Source Serif 4"],"spacing_scale":["8px","16px","24px","40px","80px"],"border_radius":["2px","4px","8px"],"component_patterns":["card","hero","navbar","grid"]},
    "chat":      {"colors":["#0f172a","#1e293b","#38bdf8","#e2e8f0","#7c3aed","#f472b6"],"fonts":["Outfit","JetBrains Mono"],"spacing_scale":["4px","8px","12px","16px","24px"],"border_radius":["8px","16px","24px","999px"],"component_patterns":["card","pill","modal","sidebar"]},
    "finance":   {"colors":["#0d1117","#161b22","#00d084","#0075ff","#f0f6fc","#8b949e"],"fonts":["IBM Plex Sans","IBM Plex Mono"],"spacing_scale":["8px","16px","24px","32px","48px"],"border_radius":["4px","6px","12px"],"component_patterns":["card","badge","navbar","sidebar","grid"]},
    "portfolio": {"colors":["#09090b","#18181b","#a1a1aa","#fafafa","#e4e4e7","#6366f1"],"fonts":["Space Grotesk","Fraunces"],"spacing_scale":["8px","16px","32px","64px","120px"],"border_radius":["0px","4px","8px"],"component_patterns":["hero","grid","card","navbar"]},
    "default":   {"colors":["#0f172a","#1e293b","#6366f1","#f8fafc","#e2e8f0","#22c55e"],"fonts":["Plus Jakarta Sans","DM Sans"],"spacing_scale":["8px","16px","24px","48px"],"border_radius":["8px","12px"],"component_patterns":["card","hero","navbar","button"]},
}

KEYWORD_MAP = {
    "todo":      ["todo","task","list","checklist","habit","planner"],
    "dashboard": ["dashboard","analytics","admin","monitor","stats","metric"],
    "saas":      ["saas","landing","startup","product","service","platform"],
    "ecommerce": ["shop","store","ecommerce","cart","product","buy","sell"],
    "blog":      ["blog","article","news","magazine","post","write"],
    "chat":      ["chat","message","messenger","discord","slack","talk"],
    "finance":   ["finance","budget","money","expense","invoice","bank","crypto"],
    "portfolio": ["portfolio","resume","cv","personal","showcase"],
}

KEYFRAME_RE = re.compile(r'(@keyframes\s+([\w]+)\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', re.DOTALL)

def match_design_category(keyword: str) -> str:
    kw = keyword.lower()
    for category, terms in KEYWORD_MAP.items():
        if any(t in kw for t in terms):
            return category
    return "default"

async def fetch_animate_css_keyframes(client, category):
    wanted = set(CATEGORY_ANIMATIONS.get(category, CATEGORY_ANIMATIONS["default"]))
    try:
        r = await client.get(ANIMATE_CSS_CDN, headers=HEADERS, timeout=TIMEOUT)
        extracted = {name: block.strip() for block, name in KEYFRAME_RE.findall(r.text) if name in wanted}
        return {"source": "animate.css", "keyframes": extracted, "animation_names": list(extracted.keys())}
    except Exception:
        return {"source": "animate.css-fallback", "keyframes": {
            "fadeInUp": "@keyframes fadeInUp{from{opacity:0;transform:translate3d(0,20px,0)}to{opacity:1;transform:translate3d(0,0,0)}}",
            "fadeIn":   "@keyframes fadeIn{from{opacity:0}to{opacity:1}}",
            "zoomIn":   "@keyframes zoomIn{from{opacity:0;transform:scale3d(.8,.8,.8)}to{opacity:1;transform:scale3d(1,1,1)}}",
        }, "animation_names": ["fadeInUp","fadeIn","zoomIn"]}

async def fetch_gradients(client, category):
    db = GRADIENT_DB.get(category, GRADIENT_DB["default"])
    kw_map = {"todo":["midnight","cosmic","deep"],"dashboard":["dark","carbon","ocean"],"saas":["violet","purple","deep"],"ecommerce":["warm","autumn","ember"],"blog":["dark","romance","ink"],"chat":["twilight","nebula","dark"],"finance":["dark","matrix","carbon"],"portfolio":["obsidian","void","dark"],"default":["midnight","dark"]}
    try:
        r = await client.get(GRADIENTS_JSON_URL, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        kws = kw_map.get(category, ["midnight","dark"])
        matched = []
        for g in data:
            name = g.get("name","").lower()
            colors = g.get("colors",[])
            if len(colors) >= 2 and any(k in name for k in kws):
                matched.append((g["name"], f"linear-gradient(135deg,{colors[0]} 0%,{colors[-1]} 100%)", "#f8fafc"))
            if len(matched) >= 2:
                break
        return {"source": "uigradients", "gradients": matched or db}
    except Exception:
        return {"source": "gradient-db", "gradients": db}

async def fetch_google_fonts(client, category):
    try:
        r = await client.get("https://fonts.google.com/metadata/fonts", headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
        data = json.loads(r.text.lstrip(")]}'\n"))
        families = data.get("familyMetadataList", [])
        preferred = {"blog":["Serif"],"portfolio":["Serif","Display"]}.get(category, ["Sans Serif"])
        picked = [f["family"] for f in families if f.get("category") in preferred][:2]
        return picked or [f["family"] for f in families[:2]]
    except Exception:
        return []

def get_transition_recipes(category):
    names = CATEGORY_TRANSITIONS.get(category, CATEGORY_TRANSITIONS["default"])
    return {"source":"transition-recipes","recipes":{n:TRANSITION_RECIPES[n] for n in names if n in TRANSITION_RECIPES},"primary":TRANSITION_RECIPES.get(names[0], TRANSITION_RECIPES["smooth"])}

async def scrape_design_db(client, keyword):
    cat = match_design_category(keyword)
    db = DESIGN_DB[cat]
    return {"source":f"design-db:{cat}","keyword":keyword,"colors":db["colors"],"fonts":db["fonts"],"spacing_scale":db["spacing_scale"],"border_radius":db["border_radius"],"component_patterns":db["component_patterns"],"animation_examples":[],"transition_examples":[],"easing_functions":[]}

def merge_results(results):
    all_colors,all_fonts,all_spacing,all_radii,all_comps,sources = [],[],[],[],[],[]
    for r in results:
        if "error" in r: continue
        sources.append(r.get("source","?"))
        all_colors+=r.get("colors",[]); all_fonts+=r.get("fonts",[]); all_spacing+=r.get("spacing_scale",[])
        all_radii+=r.get("border_radius",[]); all_comps+=r.get("component_patterns",[])
    def dedup(lst,n=8): return list(dict.fromkeys(lst))[:n]
    return {"sources_scraped":sources,"color_palette":dedup(all_colors,10),"fonts":dedup(all_fonts,5),"spacing_scale":dedup(all_spacing,6),"border_radius":dedup(all_radii,4),"component_patterns":dedup(all_comps)}

def build_design_brief(merged, keyword, category, anim_data, gradient_data, transition_data, extra_fonts):
    palette=merged["color_palette"]; fonts=list(dict.fromkeys(merged["fonts"]+extra_fonts))[:4]
    spacing=merged["spacing_scale"]; radii=merged["border_radius"]; comps=merged["component_patterns"]

    bg=palette[0] if len(palette)>0 else "#0f172a"; surf=palette[1] if len(palette)>1 else "#1e293b"
    light=palette[2] if len(palette)>2 else "#f8fafc"; muted=palette[3] if len(palette)>3 else "#e2e8f0"
    acc=palette[4] if len(palette)>4 else "#6366f1"; pos=palette[5] if len(palette)>5 else "#22c55e"
    r0=radii[0] if radii else "8px"; r1=radii[1] if len(radii)>1 else "16px"
    sp2=spacing[2] if len(spacing)>2 else "24px"; f0=fonts[0] if fonts else "Plus Jakarta Sans"; f1=fonts[1] if len(fonts)>1 else "DM Sans"

    gradients=gradient_data.get("gradients",[])
    hero_grad=gradients[0][1] if gradients else f"linear-gradient(135deg,{bg} 0%,{surf} 100%)"
    card_grad=gradients[1][1] if len(gradients)>1 else f"linear-gradient(135deg,{surf} 0%,{bg} 100%)"

    primary_trans=transition_data.get("primary","all 0.2s cubic-bezier(0.4,0,0.2,1)")
    recipes=transition_data.get("recipes",{})
    lift_trans=recipes.get("lift","transform 0.2s ease, box-shadow 0.2s ease")
    color_trans=recipes.get("color_only","color 0.2s ease, background-color 0.2s ease")

    keyframes=anim_data.get("keyframes",{}); anim_names=anim_data.get("animation_names",["fadeInUp","fadeIn"])
    keyframes_css="\n\n".join(keyframes.values())

    comp_class_hints=[f'{c} elements: add class "{ELEMENT_ANIMATION_MAP[c]}"' for c in comps if c in ELEMENT_ANIMATION_MAP]
    stagger="Apply staggered animation-delay: 1st child 0ms, 2nd 80ms, 3rd 160ms, 4th 240ms"

    f0q=f0.replace(" ","+"); f1q=f1.replace(" ","+")

    css_prompt=(
        "MANDATORY DESIGN SYSTEM - follow every rule exactly:\n\n"
        "1. GOOGLE FONTS IMPORT (top of CSS):\n"
        f"   @import url('https://fonts.googleapis.com/css2?family={f0q}:wght@400;500;600;700&family={f1q}:wght@400;500;600&display=swap');\n\n"
        "2. ANIMATE.CSS CDN (in HTML <head>):\n"
        "   <link rel=\"stylesheet\" href=\"https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css\"/>\n\n"
        "3. :root CSS VARIABLES:\n"
        f"   --bg:{bg}; --surface:{surf}; --surface-2:color-mix(in srgb,{surf} 80%,{light} 20%);\n"
        f"   --text:{light}; --text-muted:{muted}; --accent:{acc}; --positive:{pos};\n"
        f"   --radius:{r0}; --radius-lg:{r1};\n"
        f"   --transition:{primary_trans};\n"
        f"   --transition-lift:{lift_trans};\n"
        f"   --transition-color:{color_trans};\n"
        f"   --gradient-hero:{hero_grad};\n"
        f"   --gradient-card:{card_grad};\n\n"
        f"4. TYPOGRAPHY: body font-family:'{f0}',sans-serif; headings font-weight:700 letter-spacing:-0.02em; mono:'{f1}';\n\n"
        f"5. LAYOUT: .container max-width:1200px margin:0 auto padding:0 24px; sections gap:{sp2};\n\n"
        "6. COMPONENTS:\n"
        "   cards: background:var(--gradient-card); border-radius:var(--radius-lg); padding:24px;\n"
        "          border:1px solid rgba(255,255,255,0.06); box-shadow:0 4px 24px rgba(0,0,0,0.3); transition:var(--transition-lift);\n"
        "   cards:hover: transform:translateY(-2px); box-shadow:0 8px 40px rgba(0,0,0,0.4);\n"
        "   hero: background:var(--gradient-hero); padding:64px 24px;\n"
        "   navbar: background:var(--surface); border-bottom:1px solid rgba(255,255,255,0.06); padding:16px 24px; backdrop-filter:blur(12px);\n"
        "   buttons: background:var(--accent); color:#fff; padding:10px 20px; border-radius:var(--radius); font-weight:600; border:none; transition:var(--transition);\n"
        "   buttons:hover: filter:brightness(1.12); transform:translateY(-1px);\n"
        "   inputs: background:var(--surface-2); border:1px solid rgba(255,255,255,0.08); color:var(--text); border-radius:var(--radius); padding:10px 14px; transition:var(--transition-color);\n"
        "   inputs:focus: border-color:var(--accent); outline:none; box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 20%,transparent);\n"
        "   badges: background:color-mix(in srgb,var(--accent) 15%,transparent); color:var(--accent); padding:4px 10px; border-radius:999px; font-size:0.75rem;\n"
        "   positive values: color:var(--positive);\n"
        "   list rows: border-bottom:1px solid rgba(255,255,255,0.05); padding:12px 0;\n\n"
        f"7. KEYFRAMES (paste into CSS):\n{keyframes_css}\n\n"
        "8. ANIMATION RULES:\n"
        "   Cards: animation:fadeInUp 0.4s cubic-bezier(0.4,0,0.2,1) both;\n"
        f"   {stagger}\n"
        "   Interactive elements: transition:var(--transition);\n"
        "   Hover: use transform + box-shadow only (GPU accelerated)\n"
    )

    html_prompt=(
        "ANIMATE.CSS INTEGRATION:\n"
        "1. Add in <head>: <link rel=\"stylesheet\" href=\"https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css\"/>\n"
        "2. Element classes:\n"+"\n".join(f"   - {h}" for h in comp_class_hints)+"\n"
        f"3. {stagger}\n"
        f"4. Available animations: {', '.join(anim_names)}\n"
    )

    plan_theme=(
        f"Modern {keyword} UI - dark {category} theme; hero:{hero_grad[:40]}...; "
        f"accent {acc}; {f0}+{f1}; animate.css entrances with stagger; components:{','.join(comps[:5])}."
    )

    return {
        "keyword":keyword,"category":category,
        "sources_scraped":merged["sources_scraped"]+[anim_data["source"],gradient_data["source"]],
        "color_palette":palette,"fonts":fonts,"spacing_scale":spacing,"border_radius":radii,"component_patterns":comps,
        "gradients":[{"name":g[0],"css":g[1]} for g in gradients],
        "keyframes":list(keyframes.keys()),"transition_recipes":recipes,
        "css_prompt_injection":css_prompt,
        "html_prompt_injection":html_prompt,
        "plan_theme_injection":plan_theme,
    }

@app.get("/")
async def root():
    return {"status":"running","version":"2.0.0"}

@app.get("/health")
async def health():
    return {"status":"ok"}

@app.get("/design-brief")
async def design_brief(keyword: str = Query(default="saas dashboard")):
    category = match_design_category(keyword)
    async with httpx.AsyncClient(timeout=TIMEOUT, limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)) as client:
        db_result, anim_data, gradient_data, extra_fonts = await asyncio.wait_for(
            asyncio.gather(scrape_design_db(client,keyword), fetch_animate_css_keyframes(client,category), fetch_gradients(client,category), fetch_google_fonts(client,category)),
            timeout=8
        )
    transition_data = get_transition_recipes(category)
    merged = merge_results([db_result])
    brief = build_design_brief(merged,keyword,category,anim_data,gradient_data,transition_data,extra_fonts)
    return brief

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("scraper_service.main:app", host="0.0.0.0", port=port)