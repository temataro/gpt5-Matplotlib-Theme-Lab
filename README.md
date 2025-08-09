# GPT 5 -- Matplotlib Theme Lab

This app was vibecoded by GPT 5 so I can finally stop editing matplotlib figure
rcParams at work and get a sensible, pretty plot generator that I can plug any
random color palette into.
For ~2 hours of corralling and instructing, not too bad!
                                                            - Tem
![](Matplotlib-Themer-Demo.mp4)

# Matplotlib Theme Lab (React + FastAPI)

A highly interactive web app to evaluate and fine-tune Matplotlib themes for publication-quality figures.
```
Directory layout (monorepo)
 ├─ backend/
 │  ├─ app/
 │  │  ├─ __init__.py
 │  │  ├─ main.py
 │  │  ├─ theming.py
 │  │  ├─ figures.py
 │  │  ├─ utils.py
 │  │  └─ assets/
 │  │     ├─ computermodern.mplstyle
 │  │     └─ fonts/  # (place Inter *.ttf here if you want; optional)
 │  └─ requirements.txt
 ├─ frontend/
 │  ├─ index.html
 │  ├─ package.json
 │  ├─ postcss.config.js
 │  ├─ tailwind.config.ts
 │  ├─ vite.config.ts
 │  └─ src/
 │     ├─ main.tsx
 │     ├─ App.tsx
 │     ├─ styles.css
 │     ├─ utils/api.ts
 │     └─ components/
 │        ├─ ThemeCarousel.tsx
 │        ├─ RcEditor.tsx
 │        ├─ PaletteEditor.tsx
 │        └─ CompareSlider.tsx
 └─ README.md
```

## Features
- Upload `.mplstyle` or use bundled CM-inspired base.
- Provide 3–10 HEX colors or **build palette from a single Accent** (OKLCH-based).
- Generates **10 distinct demo plots** per theme with at least **7 rcParams** tweaks per figure.
- Shows **rcParams diff** (JSON) and lets you edit parameters live.
- **Theme carousel** (6 themes/refresh: 3 light, 3 dark) with modern aesthetic.
- **Download all**: 10 PNGs + gallery `index.html` + `theme.json` + per-figure repro scripts + saved `.mplstyle` for the theme.
- Typography: **Inter** + **mathtext=stix**. Thin, modern strokes at **180 DPI**. Avoids `cmr10` limitations.

## Backend (FastAPI)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Frontend (Vite + React + Tailwind)
```bash
# You do have to download node before this:
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash 
nvm install node
cd frontend
npm i
npm run dev
```
The dev server proxies `/api` to `http://localhost:8000`.

## Notes
- Matplotlib backend is forced to `Agg` for server rendering.
- If you want exact Inter shapes in plots, drop the Inter `.ttf` files in `backend/app/assets/fonts/` (optional). The app will auto-register them; otherwise it falls back to DejaVu Sans.
- Light themes default to **off-white** `#FAFAF7` per your glare preference.
- The palette generator uses **OKLCH** conversions (self-contained implementation) and aims for adjacent ΔE ≥ ~0.12 in Oklab space.

## Valid & modern Matplotlib code
- Targets **Matplotlib 3.9** and avoids deprecated APIs.
- Uses `with mpl.rc_context(rc_mod):` around each figure.
- Minimal spines; thin ticks; subtle grids; legends are lightweight.

## Edge cases
- HEX validation and palette length (3–10) with helpful errors.
- `.mplstyle` parsing failures surface as 400 errors.
- Missing fonts: gracefully fall back.
- If any figure fails, others still render (errors are isolated per figure in code).

## Production
- Consider Dockerizing, caching renders by `(theme-hash, seed)`, and adding a task queue for batch jobs.
- Add color-vision simulation overlays and WCAG AA contrast checks directly in the frontend with a canvas shader.

