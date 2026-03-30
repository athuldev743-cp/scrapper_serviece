# ─────────────────────────────────────────────────────────────────────────────
# PATCH for llm.py  (your existing groq-based agent file)
# Apply these 3 changes — nothing else needs to touch.
# ─────────────────────────────────────────────────────────────────────────────

# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 1 — add this import at the top of llm.py
# ══════════════════════════════════════════════════════════════════════════════

from design_client import get_design_brief, inject_into_plan_system, inject_into_css_system


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 2 — replace your plan_project() function with this version
# The only addition is: fetch brief → inject into PLAN_SYSTEM before the call
# ══════════════════════════════════════════════════════════════════════════════

def plan_project(prompt: str) -> dict:
    # ── NEW: fetch design brief and inject into plan prompt ──
    brief = get_design_brief(prompt)
    plan_system = inject_into_plan_system(PLAN_SYSTEM, brief)
    # ────────────────────────────────────────────────────────

    # was: call_groq(PLAN_SYSTEM, ...)
    raw = call_groq(plan_system, f"Project:\n{prompt}", max_tokens=1000)
    raw = strip_fences(raw)
    plan = json.loads(raw)
    plan["run_commands"] = [
        re.sub(r'--port\s+\d+', '--port PORT_PLACEHOLDER', cmd)
        for cmd in plan.get("run_commands", [])
    ]
    plan["contract"] = extract_contract(plan)

    # ── NEW: attach brief to plan so generate_file() can use it ──
    plan["_design_brief"] = brief
    # ─────────────────────────────────────────────────────────────

    return plan


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 3 — replace your generate_file() function with this version
# The only addition: when generating a .css file, inject CSS tokens
# ══════════════════════════════════════════════════════════════════════════════

def generate_file(
    file_path: str,
    description: str,
    project_context: str,
    plan: dict = None
) -> str:
    port = plan.get("port", 8001) if plan else 8001

    sections_list = []
    if plan:
        for f in plan.get("files", []):
            if f["path"] == file_path:
                sections_list = f.get("sections", [])
                break

    if not sections_list:
        sections_list = [description]

    # ── NEW: for CSS files, patch SECTION_SYSTEM with design tokens ──
    brief = (plan or {}).get("_design_brief")
    if brief and file_path.endswith(".css"):
        import llm as _self                         # patch the module-level constant
        _original = _self.SECTION_SYSTEM
        _self.SECTION_SYSTEM = inject_into_css_system(_original, brief)

    try:
        if len(sections_list) == 1:
            return generate_section(file_path, sections_list[0], project_context, port, plan=plan)

        generated = []
        for section_desc in sections_list:
            prev = [generated[-1]] if generated else []
            code = generate_section(
                file_path, section_desc, project_context, port, prev, plan=plan)
            generated.append(code)

        return combine_sections(file_path, generated, project_context)

    finally:
        # ── NEW: restore SECTION_SYSTEM after CSS generation ──
        if brief and file_path.endswith(".css"):
            _self.SECTION_SYSTEM = _original


# ─────────────────────────────────────────────────────────────────────────────
# ALTERNATIVE (cleaner, avoids module self-import):
# If you prefer not to self-import, just pass section_system into
# generate_section() as a parameter. Here's the minimal version of that:
# ─────────────────────────────────────────────────────────────────────────────

def generate_section_v2(
    file_path: str,
    section_desc: str,
    project_context: str,
    port: int,
    previous_sections: list = None,
    plan: dict = None,
    section_system_override: str = None,   # ← NEW param
) -> str:
    system = section_system_override or SECTION_SYSTEM   # ← use override if provided

    prev = ""
    if previous_sections:
        joined = "\n\n".join(previous_sections)
        prev = f"\nAlready written above:\n{safe_truncate(joined, 300)}\n"

    contract = ""
    if plan and plan.get("contract"):
        contract = f"API field names (use EXACTLY these, never rename): {json.dumps(plan.get('contract'))}\n"

    user = (
        f"Project: {safe_truncate(project_context, 120)}\n"
        f"Port: {port}\n"
        f"{contract}"
        f"File: {file_path}\n"
        f"{prev}"
        f"Write ONLY this section: {section_desc}\n"
        f"Max 50 lines. Stop when section is complete."
    )
    result = call_groq(system, user)          # ← pass system explicitly
    return strip_fences(result)
