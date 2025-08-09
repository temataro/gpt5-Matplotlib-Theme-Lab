from __future__ import annotations

import json
import math
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib as mpl
from fastapi import HTTPException

from .utils import json_pretty, norm_hex, validate_hex_list

# -------------------------
# Font registration helpers
# -------------------------

ASSETS_DIR = Path(__file__).parent / 'assets'
FONTS_DIR = ASSETS_DIR / 'fonts'
DEFAULT_STYLE_PATH = ASSETS_DIR / 'computermodern.mplstyle'


def register_fonts() -> None:
    """Register Inter (if available) and ensure mathtext uses STIX."""
    try:
        from matplotlib import font_manager
        font_files = []
        if FONTS_DIR.exists():
            for ext in ("*.ttf", "*.otf"):
                font_files.extend(FONTS_DIR.rglob(ext))
        if font_files:
            for f in font_files:
                font_manager.fontManager.addfont(str(f))
        # Prefer Inter; fallback to DejaVu Sans
        mpl.rcParams.update({
            'font.family': ['cmr10', 'Inter',],
            'mathtext.fontset': 'stix',  # user choice
            'text.antialiased': True,
        })
    except Exception:
        pass
# helper near the palette code (add this small util):
def _rotate(xs: List[str], k: int) -> List[str]:
    k = k % len(xs) if xs else 0
    return xs[k:] + xs[:k]


# -------------------------
# OKLAB/OKLCH utilities (self-contained, no external deps)
# Based on Björn Ottosson's reference implementation.
# -------------------------

def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1/2.4)) - 0.055


def hex_to_rgb01(h: str) -> Tuple[float, float, float]:
    h = h.lstrip('#')
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return (r, g, b)


def rgb01_to_hex(rgb: Tuple[float, float, float]) -> str:
    r, g, b = [max(0, min(1, x)) for x in rgb]
    return '#%02X%02X%02X' % (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def srgb_to_oklab(r: float, g: float, b: float) -> Tuple[float, float, float]:
    # Convert to linear
    lr, lg, lb = _srgb_to_linear(r), _srgb_to_linear(g), _srgb_to_linear(b)
    # Linear sRGB to LMS
    l = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb
    m = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb
    s = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb
    l_, m_, s_ = l ** (1/3), m ** (1/3), s ** (1/3)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return (L, a, b)


def oklab_to_srgb(L: float, a: float, b: float) -> Tuple[float, float, float]:
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    lr = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    lg = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    lb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    r, g, b = _linear_to_srgb(lr), _linear_to_srgb(lg), _linear_to_srgb(lb)
    return (r, g, b)


def srgb_hex_to_oklch(hex_color: str) -> Tuple[float, float, float]:
    r, g, b = hex_to_rgb01(hex_color)
    L, a, b2 = srgb_to_oklab(r, g, b)
    C = math.sqrt(a * a + b2 * b2)
    h = (math.degrees(math.atan2(b2, a)) + 360.0) % 360.0
    return (L, C, h)


def oklch_to_srgb_hex(L: float, C: float, h: float) -> str:
    a = C * math.cos(math.radians(h))
    b = C * math.sin(math.radians(h))
    r, g, b = oklab_to_srgb(L, a, b)
    return rgb01_to_hex((r, g, b))


def clamp_palette_to_gamut(colors: List[Tuple[float, float, float]]) -> List[str]:
    """Convert OKLCH tuples to in-gamut sRGB hex, clamping/chroma-reducing when needed."""
    out: List[str] = []
    for (L, C, h) in colors:
        # Reduce chroma until all channels are inside [0,1]
        c = C
        for _ in range(20):
            hex_candidate = oklch_to_srgb_hex(L, c, h)
            r, g, b = hex_to_rgb01(hex_candidate)
            if 0 <= r <= 1 and 0 <= g <= 1 and 0 <= b <= 1:
                break
            c *= 0.9
        out.append(oklch_to_srgb_hex(L, c, h))
    return out


def oklab_delta_e(c1: Tuple[float, float, float], c2: Tuple[float, float, float]) -> float:
    # Simple Euclidean distance in Oklab
    L1, a1, b1 = c1
    L2, a2, b2 = c2
    return math.sqrt((L1 - L2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2)


# -------------------------
# Theme & palette
# -------------------------

@dataclass
class Theme:
    slug: str
    name: str
    mode: str  # 'light' | 'dark'
    fg: str
    bg: str
    accent: str
    palette: List[str]
    rc_global: Dict[str, object]
    base_style_name: str
    base_style_text: str
    seed: int

    def to_json(self) -> str:
        return json_pretty({
            'slug': self.slug,
            'name': self.name,
            'mode': self.mode,
            'fg': self.fg,
            'bg': self.bg,
            'accent': self.accent,
            'palette': self.palette,
            'rc_global': self.rc_global,
            'base_style_name': self.base_style_name,
            'seed': self.seed,
        })


THEME_NAMES_LIGHT = ["Porcelain", "Parchment", "Lumen"]
THEME_NAMES_DARK = ["Slate", "Obsidian", "Nebula"]

def _generate_cycle_from_accent(
    accent: str,
    n: int,
    mode: str,
    hue_offset_deg: float = 0.0,
    lightness_shift: float = 0.0,
    chroma_scale: float = 1.0,
) -> List[str]:
    L0, C0, h0 = srgb_hex_to_oklch(accent)

    # Base lightness differs by mode; apply per-theme shift
    if mode == 'light':
        L_base = min(0.82, max(0.58, L0))
    else:
        L_base = min(0.72, max(0.46, L0))
    L_base = max(0.2, min(0.95, L_base + lightness_shift))

    # Moderate chroma for print-like look
    C_base = min(0.15, max(0.06, C0)) * chroma_scale
    C_base = max(0.04, min(0.20, C_base))

    colors_oklch: List[Tuple[float, float, float]] = []
    for i in range(n):
        hue = (h0 + hue_offset_deg + 360.0 * i / n) % 360.0
        dL = ((i % 2) * 0.06) - 0.03
        L = max(0.2, min(0.95, L_base + dL))
        C = C_base * (1.0 - 0.05 * (i % 3))
        colors_oklch.append((L, C, hue))

    def to_oklab(t):
        L, C, h = t
        a = C * math.cos(math.radians(h))
        b = C * math.sin(math.radians(h))
        return (L, a, b)

    lab_list = [to_oklab(c) for c in colors_oklch]
    for i in range(1, len(lab_list)):
        while oklab_delta_e(lab_list[i - 1], lab_list[i]) < 0.12:
            L, C, h = colors_oklch[i]
            h = (h + 3.0) % 360.0
            colors_oklch[i] = (L, C, h)
            lab_list[i] = to_oklab(colors_oklch[i])

    return clamp_palette_to_gamut(colors_oklch)



def load_base_style_text(user_style_bytes: Optional[bytes]) -> Tuple[str, str]:
    """Return (style_name, style_text). Fallback to bundled computermodern.mplstyle."""
    if user_style_bytes:
        try:
            text = user_style_bytes.decode('utf-8')
            # Light sanity check: must contain at least one rc key pattern like `:`
            if ':' not in text:
                raise ValueError('File does not look like a .mplstyle')
            return ("user", text)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse .mplstyle: {e}")
    # Fallback to bundled
    return ("computermodern", DEFAULT_STYLE_PATH.read_text(encoding='utf-8'))


def build_global_rc(fg: str, bg: str, palette: List[str], dpi: int, mode: str) -> Dict[str, object]:
    """Construct global rcParams consistent with our aesthetic.

    Modern thin strokes, minimal spines, STIX mathtext, Inter UI font.
    """
    is_dark = (mode == 'dark')
    grid_color = '#FFFFFF' if is_dark else '#000000'
    grid_alpha = 0.10

    return {
        # Rendering & size
        'figure.dpi': dpi,
        'savefig.dpi': dpi,
        'figure.figsize': (14, 10),  # single-column default
        'figure.facecolor': bg,
        'axes.facecolor': bg,

        # Typography
        'font.family': ['cmr10', 'Inter',],
        'font.size': 11.0,
        'axes.titlesize': 12.0,
        'axes.labelsize': 10.0,
        'legend.fontsize': 9.0,
        'xtick.labelsize': 9.0,
        'ytick.labelsize': 9.0,
        'mathtext.fontset': 'stix',

        # Strokes
        'lines.linewidth': 1.2,
        'axes.linewidth': 0.8,
        'patch.linewidth': 0.8,
        'grid.linewidth': 0.6,
        'xtick.major.width': 0.8,
        'ytick.major.width': 0.8,
        'xtick.minor.width': 0.6,
        'ytick.minor.width': 0.6,
        'xtick.major.size': 3.5,
        'ytick.major.size': 3.5,
        'xtick.minor.size': 2.0,
        'ytick.minor.size': 2.0,

        # Colors
        'text.color': fg,
        'axes.labelcolor': fg,
        'axes.edgecolor': fg,
        'xtick.color': fg,
        'ytick.color': fg,
        'grid.color': grid_color,
        'grid.alpha': grid_alpha,
        'axes.prop_cycle': mpl.cycler(color=palette),

        # Grid & ticks
        'axes.grid': True,
        'axes.grid.axis': 'y',
        'axes.grid.which': 'major',
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.spines.bottom': True,
        'axes.spines.left': True,
        'xtick.direction': 'in',
        'ytick.direction': 'in',

        # Legends
        'legend.frameon': True,
        'legend.framealpha': 0.85,
        'legend.fancybox': True,
        'legend.edgecolor': fg,

        # Image defaults
        'image.cmap': 'viridis' if not is_dark else 'magma',
        'image.interpolation': 'nearest',

        # Savefig
        'savefig.bbox': 'tight',
        'savefig.facecolor': bg,
        'savefig.edgecolor': bg,
        'savefig.pad_inches': 0.02,
    }

def make_theme_set(
    fg: str,
    bg: str,
    accent: str,
    base_palette: Optional[List[str]],
    dpi: int,
    user_style_bytes: Optional[bytes],
    seed: int,
) -> List[Theme]:
    """
    Create 6 themes (3 light, 3 dark).
    If base_palette is provided (3–10), it overrides the generated palette for each theme.
    Otherwise, each theme receives a distinct palette derived from the same accent, using:
      - different hue offsets (golden-angle based),
      - different lightness/chroma scales,
      - and a per-theme rotation of the final list.
    """
    import random
    random.seed(seed)

    style_name, style_text = load_base_style_text(user_style_bytes)
    themes: List[Theme] = []

    # Deterministic but visually distinct knobs per theme
    GOLDEN = 137.50776405003785  # golden angle in degrees
    # (light, light, light, dark, dark, dark) variants
    VARIANTS = [
        dict(hue=0.0,       dL=+0.00, c=1.00, rotate=0),
        dict(hue=GOLDEN/2,  dL=+0.02, c=1.10, rotate=1),
        dict(hue=GOLDEN,    dL=-0.02, c=0.92, rotate=2),
        dict(hue=GOLDEN*1.5,dL=-0.01, c=1.06, rotate=1),
        dict(hue=GOLDEN*2.0,dL=+0.03, c=1.15, rotate=3),
        dict(hue=GOLDEN*2.5,dL=-0.03, c=0.88, rotate=2),
    ]

    names = THEME_NAMES_LIGHT + THEME_NAMES_DARK
    for i, name in enumerate(names):
        mode = 'light' if i < len(THEME_NAMES_LIGHT) else 'dark'
        n_colors = max(3, min(10, len(base_palette) if base_palette else 8))

        if base_palette:
            palette = validate_hex_list(base_palette)
        else:
            v = VARIANTS[i % len(VARIANTS)]
            # small deterministic jitter per index for extra diversity
            r = random.Random((seed << 8) + i)
            hue_off = v['hue'] + r.uniform(-8.0, 8.0)
            dL     = v['dL']  + r.uniform(-0.015, 0.015)
            cscale = max(0.80, min(1.25, v['c'] + r.uniform(-0.08, 0.08)))
            pal    = _generate_cycle_from_accent(
                        accent, n_colors, mode,
                        hue_offset_deg=hue_off,
                        lightness_shift=dL,
                        chroma_scale=cscale)
            palette = _rotate(pal, v['rotate'] + (i % max(1, n_colors-1)))

        rc_global = build_global_rc(
            fg=fg, bg=bg, palette=palette, dpi=dpi, mode=mode
        )
        rc_global.update({'grid.alpha': 0.12 if mode == 'light' else 0.16})

        theme = Theme(
            slug=f"{name.lower()}",
            name=name,
            mode=mode,
            fg=fg,
            bg=bg,
            accent=accent,
            palette=palette,
            rc_global=rc_global,
            base_style_name=style_name,
            base_style_text=style_text,
            seed=random.randint(0, 2**31 - 1),
        )
        themes.append(theme)

    return themes
