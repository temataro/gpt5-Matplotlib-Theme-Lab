from __future__ import annotations

import io
import os
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib as mpl
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from cycler import cycler

from .figures import render_all
from .theming import Theme, make_theme_set, register_fonts
from .utils import ZipBuilder, b64_png, json_pretty, norm_hex, validate_hex_list

app = FastAPI(title="Matplotlib Theme Lab", version="1.0.1")

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure non-interactive backend for servers
mpl.use("agg", force=True)
register_fonts()


def _rc_serialize(rc: dict) -> dict:
    """Make rcParams JSON-serializable (notably axes.prop_cycle/Cycler)."""
    out: dict = {}
    for k, v in rc.items():
        if k == "axes.prop_cycle":
            try:
                by = v.by_key() if hasattr(v, "by_key") else None
            except Exception:
                by = None
            if by and len(by) == 1 and "color" in by:
                out[k] = {"key": "color", "values": list(by["color"])}
            elif by:
                # General case: multiple keys in the cycler
                n = len(next(iter(by.values())))
                out[k] = {
                    "multi": [{kk: vv[i] for kk, vv in by.items()} for i in range(n)]
                }
            else:
                out[k] = v  # hope it's already JSON-able
        else:
            out[k] = v
    return out


def _rc_deserialize(rc: dict) -> dict:
    """Rebuild Matplotlib-friendly rc dict from JSON (axes.prop_cycle special-case)."""
    out = dict(rc)
    pc = out.get("axes.prop_cycle")
    if isinstance(pc, dict):
        if "key" in pc and "values" in pc:
            out["axes.prop_cycle"] = cycler(pc["key"], pc["values"])
        elif "multi" in pc:
            cy = None
            for entry in pc["multi"]:
                c = None
                for kk, vv in entry.items():
                    c = cycler(kk, [vv]) if c is None else c + cycler(kk, [vv])
                cy = c if cy is None else cy + c
            out["axes.prop_cycle"] = cy
    return out


@app.post("/api/themes/generate")
async def api_generate_themes(
    fg: str = Form("#111111"),
    bg: str = Form("#FAFAF7"),  # off-white default
    accent: str = Form("#2E7FE8"),
    dpi: int = Form(200),
    seed: int = Form(42),
    palette: Optional[str] = Form(None),  # JSON array of HEX strings
    style: Optional[UploadFile] = File(None),
):
    """Generate 6 themes (3 light, 3 dark). Returns metadata only (no images yet)."""
    try:
        fg = norm_hex(fg)
        bg = norm_hex(bg)
        accent = norm_hex(accent)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=400, detail="Invalid HEX value for fg/bg/accent."
        )

    base_palette: Optional[List[str]] = None
    if palette:
        try:
            import json

            base_palette = validate_hex_list(json.loads(palette))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid palette JSON: {e}")

    style_bytes: Optional[bytes] = None
    if style is not None:
        if not style.filename.endswith(".mplstyle"):
            raise HTTPException(
                status_code=400, detail="Upload must be a .mplstyle file."
            )
        style_bytes = await style.read()

    themes = make_theme_set(
        fg=fg,
        bg=bg,
        accent=accent,
        base_palette=base_palette,
        dpi=dpi,
        user_style_bytes=style_bytes,
        seed=seed,
    )

    return JSONResponse(
        [
            {
                "slug": t.slug,
                "name": t.name,
                "mode": t.mode,
                "fg": t.fg,
                "bg": t.bg,
                "accent": t.accent,
                "palette": t.palette,
                "rc_global": _rc_serialize(t.rc_global),
                "seed": t.seed,
            }
            for t in themes
        ]
    )


@app.post("/api/render")
async def api_render(
    theme_json: str = Form(...),  # serialized Theme minus base_style_text
):
    """Render 10 demo plots for a given theme rc.

    Accepts a JSON string containing: fg, bg, palette, rc_global, seed.
    Returns base64-encoded PNGs + rc diffs.
    """
    import json

    try:
        data = json.loads(theme_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    rc_global_in = data.get("rc_global")
    seed = int(data.get("seed", 42))
    if not isinstance(rc_global_in, dict):
        raise HTTPException(status_code=400, detail="rc_global must be a dict")

    rc_global = _rc_deserialize(rc_global_in)

    # Compute diffs versus Matplotlib defaults
    base = mpl.rcParamsDefault
    theme_diff = {k: v for k, v in rc_global.items() if k in base and base[k] != v}

    theme_diff = _rc_serialize(theme_diff)

    png_map = render_all(theme_rc=rc_global, seed=seed)

    result = {
        "images": [
            {"filename": fn, "b64png": b64_png(buf)}
            for fn, buf in sorted(png_map.items())
        ],
        "rc_diff_theme": theme_diff,
    }
    return JSONResponse(result)


@app.post("/api/download")
async def api_download(
    theme_json: str = Form(...),  # same as /api/render
):
    """Build a zip: 10 PNGs + index.html gallery + theme.json + per-figure repro scripts + theme .mplstyle."""
    import json

    data = json.loads(theme_json)

    rc_global_in = data["rc_global"]
    rc_global = _rc_deserialize(rc_global_in)

    seed = int(data.get("seed", 42))
    name = data.get("name", data.get("slug", "theme"))
    slug = data.get("slug", name.lower().replace(" ", "-"))

    png_map = render_all(theme_rc=rc_global, seed=seed)

    zb = ZipBuilder()
    # Write PNGs
    for fn, buf in sorted(png_map.items()):
        zb.write_bytes(f"figures/{fn}", buf)

    # theme.json (JSON-serializable rc)
    data_serial = dict(data)
    data_serial["rc_global"] = _rc_serialize(rc_global)
    zb.write_text("theme.json", json_pretty(data_serial))

    # theme .mplstyle
    lines = []
    # Serialize axes.prop_cycle as cycler('color', [...]) when possible
    for k, v in rc_global.items():
        if k == "axes.prop_cycle":
            try:
                by = v.by_key() if hasattr(v, "by_key") else None
            except Exception:
                by = None
            if by and "color" in by:
                cols = by["color"]
                cols_str = ", ".join(cols)
                lines.append(f"axes.prop_cycle: cycler('color', [{cols_str}])")
            else:
                lines.append(f"{k}: {v}")
        else:
            lines.append(f"{k}: {v}")
    zb.write_text(f"themes/{slug}.mplstyle", " ".join(lines) + " ")

    # index.html gallery (minimal responsive grid)
    thumbs = " ".join(
        [
            f'<figure><img src="figures/{fn}" alt="{fn}"><figcaption>{fn}</figcaption></figure>'
            for fn in sorted(png_map)
        ]
    )
    html = f"""
<!doctype html>
<html lang=\"en\">
<meta charset=\"utf-8\"/>
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>
<title>Theme Gallery — {name}</title>
<style>
body{{margin:0;padding:24px;font:14px/1.5 Inter,system-ui,sans-serif;background:{rc_global.get('figure.facecolor','#FAFAF7')};color:{rc_global.get('text.color','#111')}}}
.grid{{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));}}
figure{{margin:0;background:rgba(0,0,0,.03);padding:12px;border-radius:12px;}}
figcaption{{margin-top:8px;opacity:.7}}
img{{width:100%;height:auto;display:block;border-radius:8px}}
</style>
<h1>Theme Gallery — {name}</h1>
<div class="grid">{thumbs}</div>
</html>
"""
    zb.write_text("index.html", html)

    # Repro scripts (one per figure)
    for item in sorted(png_map):
        code = f"""
# Repro for {item}
import matplotlib as mpl, matplotlib.pyplot as plt, numpy as np
mpl.use('agg', force=True)
plt.rcParams.update({rc_global})
from datetime import datetime

# NOTE: This script prints your effective rcParams and saves one PNG.
print('Matplotlib version:', mpl.__version__)
print('Timestamp:', datetime.now())

# Example tiny plot to verify style
fig, ax = plt.subplots()
ax.plot([0,1,2],[0,1,0])
ax.set_title('Style smoke test')
fig.savefig('{item}', dpi={rc_global.get('savefig.dpi', 200)})
"""
        zb.write_text(f"repro/repro_{item.replace('.png','.py')}", code)

    data = zb.close()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{slug}_bundle.zip"'},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True
    )
