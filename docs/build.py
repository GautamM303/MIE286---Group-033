"""
build.py — Run whenever you update questions.xlsx OR add/change images.

HOW IT WORKS
------------
Every diagram in index_template.html has this structure:

    /*IMG:name*/
    /*FALLBACK:name*/
    ...coded HTML diagram (shown when no image exists)...
    /*END_FALLBACK:name*/

build.py reads both markers automatically. You never need to edit build.py
when you add a new question — just add the diagram entry to the template
with its own /*IMG:*/ and /*FALLBACK:*/ ... /*END_FALLBACK:*/ block.

IMAGE FILENAMES
---------------
The image filename is always the DiagramType value from questions.xlsx + .png
  DiagramType = "jugs"  -->  data/jugs.png

If data/<n>.png exists  -> image is embedded into index.html (self-contained)
If data/<n>.png missing -> the /*FALLBACK:n*/ HTML from the template is used

Supported formats: .png  .jpg / .jpeg  .gif  .webp

Usage:
    python build.py
"""

import base64, json, mimetypes, openpyxl, re, sys
from pathlib import Path

XLSX = Path("questions.xlsx")
TMPL = Path("index_template.html")
OUT  = Path("index.html")
DATA = Path("data")

# ── Validate files exist ──────────────────────────────────────────────────────
for fpath, label in [(XLSX, "questions.xlsx"), (TMPL, "index_template.html")]:
    if not fpath.exists():
        sys.exit(f"ERROR: {label} not found next to build.py")

# ── Load questions from Excel ─────────────────────────────────────────────────
wb      = openpyxl.load_workbook(XLSX, data_only=True)
ws      = wb["Questions"]
headers = [c.value for c in ws[1]]
questions = []
for row in ws.iter_rows(min_row=2, values_only=True):
    if not row[0]:
        continue
    r = dict(zip(headers, row))
    questions.append({
        "id":          str(r.get("QuestionID","")).strip(),
        "text":        str(r.get("QuestionText","")).strip(),
        "answer":      str(r.get("CorrectAnswer","")).strip().lower(),
        "answerType":  str(r.get("AnswerType","numeric")).strip().lower(),
        "textFeedback":str(r.get("TextFeedback","")).strip(),
        "diagramType": str(r.get("DiagramType","")).strip().lower(),
        "category":    str(r.get("Category","")).strip(),
    })

if len(questions) < 3:
    sys.exit(f"ERROR: only {len(questions)} question(s) found — need at least 3.")

# ── Load template ─────────────────────────────────────────────────────────────
template = TMPL.read_text(encoding="utf-8")

# ── Step 1: find image file for a given diagram name ──────────────────────────
def find_image(name):
    for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        p = DATA / f"{name}{ext}"
        if p.exists():
            return p
    return None

# ── Step 2: base64-encode an image into a self-contained <img> tag ────────────
def embed_image(path, alt=""):
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    b64  = base64.b64encode(path.read_bytes()).decode()
    kb   = path.stat().st_size / 1024
    return (
        f'<img src="data:{mime};base64,{b64}" alt="{alt}"\n'
        f'     style="width:100%;border-radius:10px;display:block;margin-bottom:10px"\n'
        f'     title="{path.name} ({kb:.1f} KB)">'
    )

# ── Step 3: replace /*IMG:name*/ + /*FALLBACK:name*/.../*END_FALLBACK:name*/ ──
#   Handled in ONE pass so an embedded image always suppresses the fallback HTML.
#     PNG found  -> <img> tag only, fallback HTML discarded
#     PNG missing -> fallback HTML kept, no <img> tag
embedded_log    = []
fallback_log    = []
no_fallback_log = []

combined_pattern = re.compile(
    r"/\*IMG:([^*]+)\*/"
    r"(\s*/\*FALLBACK:\1\*/(.*?)/\*END_FALLBACK:\1\*/)?",
    re.DOTALL
)

def replacer(m):
    name          = m.group(1)
    has_fallback  = m.group(2) is not None
    fallback_html = m.group(3) if has_fallback else None
    img           = find_image(name)
    if img:
        embedded_log.append(img)
        return embed_image(img, alt=f"Diagram: {name}")
    if has_fallback:
        fallback_log.append(name)
        return fallback_html
    no_fallback_log.append(name)
    return f'<p style="color:#ef4444;font-weight:700">⚠ No diagram found for "{name}" — add data/{name}.png</p>'

template = combined_pattern.sub(replacer, template)

# ── Step 5: inject question bank JSON ────────────────────────────────────────
json_str = json.dumps(questions, ensure_ascii=False, indent=2)
result   = re.sub(
    r"/\*QUESTION_BANK\*/.*?/\*END_QUESTION_BANK\*/",
    f"/*QUESTION_BANK*/\nconst ALL_QUESTIONS = {json_str};\n/*END_QUESTION_BANK*/",
    template, flags=re.DOTALL
)

# ── Write output ──────────────────────────────────────────────────────────────
OUT.write_text(result, encoding="utf-8")

# ── Print summary ─────────────────────────────────────────────────────────────
print(f"\n  Built {OUT}")
print(f"  {len(questions)} questions  |  {len(questions)//3} set(s) of 3\n")

used_types = sorted({q["diagramType"] for q in questions if q["diagramType"]})
for name in used_types:
    img = find_image(name)
    if img:
        kb = img.stat().st_size / 1024
        print(f"  [PNG]  {name:<14}  <--  {img.name}  ({kb:.1f} KB)")
    elif name in fallback_log:
        print(f"  [SVG]  {name:<14}  (add data/{name}.png to use a custom image instead)")
    else:
        print(f"  [!!!]  {name:<14}  NO image and NO fallback in template!")

if no_fallback_log:
    print()
    print("  ⚠ WARNING — these diagram types have no image AND no fallback block")
    print("    in index_template.html. They will show an error message in the experiment.")
    print()
    for name in no_fallback_log:
        print(f"    '{name}'")
        print(f"      Fix A (easiest): drop your image at  data/{name}.png")
        print(f"      Fix B: add a diagram entry to index_template.html with:")
        print(f"              /*IMG:{name}*/")
        print(f"              /*FALLBACK:{name}*/")
        print(f"              ...your coded HTML...")
        print(f"              /*END_FALLBACK:{name}*/")
        print()
else:
    print()
    print("  All diagrams accounted for. index.html is ready to share.")

print()