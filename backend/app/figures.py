from __future__ import annotations

import io
import math
import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

FigureGenerator = Callable[[mpl.axes.Axes, np.random.Generator], None]


@dataclass
class FigureSpec:
    name: str
    filename: str
    rc_mod: Dict[str, object]
    generator: FigureGenerator


def _annotate(ax: mpl.axes.Axes, text: str, xy: Tuple[float, float], xytext: Tuple[float, float]) -> None:
    ax.annotate(
        text,
        xy=xy,
        xytext=xytext,
        textcoords='axes fraction',
        arrowprops=dict(arrowstyle='->', lw=0.8, alpha=0.8),
        bbox=dict(boxstyle='round,pad=0.3', fc=ax.figure.get_facecolor(), ec=ax.spines['left'].get_edgecolor(), alpha=0.85),
        ha='left', va='bottom'
    )


def _inline_label(ax: mpl.axes.Axes, line: mpl.lines.Line2D, label: str) -> None:
    x, y = line.get_data()
    idx = int(0.7 * len(x))
    ax.text(x[idx], y[idx], f" {label} ", va='center', ha='left', bbox=dict(fc=ax.figure.get_facecolor(), ec='none', alpha=0.7))


def _apply_ax_style(ax: mpl.axes.Axes) -> None:
    # Minimal spines look
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    ax.spines['left'].set_position(('outward', 4))
    ax.spines['bottom'].set_position(('outward', 4))
    ax.minorticks_on()
    ax.tick_params(which='minor', length=2.0, width=0.6)


# -------------------------
# Synthetic datasets
# -------------------------

def make_rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


# -------------------------
# Figure generators
# -------------------------

def fig_line(ax: mpl.axes.Axes, rng: np.random.Generator) -> None:
    x = np.linspace(0, 10, 300)
    for k in range(3):
        y = np.sin(x + k) + 0.15 * rng.standard_normal(size=x.size)
        ln, = ax.plot(x, y, label=f"Series {k+1}")
        if k == 0:
            _inline_label(ax, ln, "signal")
    ax.set_title("Line: noisy sin waves")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.legend(["Sig 1", "Sig 2", "Sig 3"])
    _apply_ax_style(ax)


def fig_scatter(ax: mpl.axes.Axes, rng: np.random.Generator) -> None:
    mean = np.array([0.0, 0.0])
    cov = np.array([[1.0, 0.75], [0.75, 1.5]])
    pts = rng.multivariate_normal(mean, cov, size=400)
    ax.scatter(pts[:, 0], pts[:, 1], s=18, alpha=0.8, edgecolor='none')
    ax.set_title("Scatter: correlated Gaussians")
    ax.set_xlabel("feature 1")
    ax.set_ylabel("feature 2")
    _apply_ax_style(ax)


def fig_bar(ax: mpl.axes.Axes, rng: np.random.Generator) -> None:
    cats = ['A', 'B', 'C', 'D']
    vals1 = rng.uniform(3, 8, size=4)
    vals2 = rng.uniform(3, 8, size=4)
    x = np.arange(len(cats))
    w = 0.38
    b1 = ax.bar(x - w/2, vals1, width=w, label='2019', alpha=0.95)
    b2 = ax.bar(x + w/2, vals2, width=w, label='2024', alpha=0.95)
    ax.bar_label(b2, fmt='%.1f', padding=2)
    ax.set_xticks(x, cats)
    ax.set_title("Bar: grouped with labels")
    ax.legend(loc='upper left')
    _apply_ax_style(ax)


def fig_hist(ax: mpl.axes.Axes, rng: np.random.Generator) -> None:
    a = rng.normal(loc=0.0, scale=1.0, size=1000)
    b = rng.normal(loc=1.5, scale=0.75, size=1000)
    ax.hist(a, bins=30, alpha=0.6, density=True)
    ax.hist(b, bins=30, alpha=0.6, density=True)
    ax.set_title("Histogram: two normals")
    ax.set_xlabel("value")
    _apply_ax_style(ax)


def fig_heatmap(ax: mpl.axes.Axes, rng: np.random.Generator) -> None:
    x = np.linspace(-3, 3, 200)
    y = np.linspace(-3, 3, 200)
    X, Y = np.meshgrid(x, y)
    Z = np.exp(-(X**2 + Y**2)) * np.cos(2*X) * np.sin(2*Y)
    im = ax.imshow(Z, origin='lower', extent=[x.min(), x.max(), y.min(), y.max()])
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.set_ylabel('intensity')
    ax.set_title("Heatmap: analytic surface")
    _apply_ax_style(ax)


def fig_polar(ax: mpl.axes.Axes, rng: np.random.Generator) -> None:
    # Convert to polar projection
    ax.remove()
    ax = plt.gcf().add_subplot(111, projection='polar')
    theta = np.linspace(0, 2*np.pi, 200)
    r = 1 + 0.3 * np.cos(5*theta) + 0.1 * np.sin(7*theta)
    ax.plot(theta, r)
    ax.set_title("Polar: rose curve", pad=12)
    ax.grid(True)


def fig_stacked_bar(ax: mpl.axes.Axes, rng: np.random.Generator) -> None:
    cats = [f'Q{i}' for i in range(1, 6)]
    x = np.arange(len(cats))
    base = rng.uniform(2.0, 5.0, size=len(cats))
    inc1 = rng.uniform(1.0, 3.0, size=len(cats))
    inc2 = rng.uniform(0.5, 2.0, size=len(cats))
    ax.bar(x, base, label='Base')
    ax.bar(x, inc1, bottom=base, label='Add-on 1')
    ax.bar(x, inc2, bottom=base+inc1, label='Add-on 2')
    ax.set_xticks(x, cats)
    ax.set_title("Stacked Bar: contributions")
    ax.legend(ncols=3, loc='upper center', bbox_to_anchor=(0.5, 1.05))
    _apply_ax_style(ax)


def fig_box(ax: mpl.axes.Axes, rng: np.random.Generator) -> None:
    data = [rng.normal(loc=m, scale=0.5 + 0.2*i, size=120) for i, m in enumerate([0.0, 0.2, 0.6, 1.0])]
    ax.boxplot(data, notch=True, vert=True, widths=0.65, patch_artist=True)
    ax.set_xticks([1, 2, 3, 4], ['S1', 'S2', 'S3', 'S4'])
    ax.set_title("Box: distributions")
    _apply_ax_style(ax)


def fig_timeseries(ax: mpl.axes.Axes, rng: np.random.Generator) -> None:
    t = np.arange('2020-01', '2022-01', dtype='datetime64[D]')
    y = np.cumsum(rng.normal(0, 1, size=t.size))
    ln, = ax.plot(t, y, lw=1.4)
    # Highlight a region using the first line color for coherence
    color = ln.get_color()
    ax.axvspan(t[int(0.25*len(t))], t[int(0.35*len(t))], color=color, alpha=0.08)
    ax.set_title("Time-series: random walk with highlight")
    ax.set_xlabel("date")
    _apply_ax_style(ax)


def fig_mixed_gridspec(ax: mpl.axes.Axes, rng: np.random.Generator) -> None:
    # Replace axes with a GridSpec of small multiples
    fig = ax.figure
    ax.remove()
    import matplotlib.gridspec as gridspec
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.3, wspace=0.3)
    for i in range(6):
        sub = fig.add_subplot(gs[i])
        x = np.linspace(0, 1, 100)
        y = np.sin(2*np.pi*(i+1)*x) + 0.1 * rng.standard_normal(size=x.size)
        sub.plot(x, y)
        sub.set_title(f"f={i+1}")
        for side in ('top', 'right'):
            sub.spines[side].set_visible(False)
    fig.suptitle("GridSpec: small multiples", y=0.98)


def build_figure_specs() -> List[FigureSpec]:
    """Create 10 FigureSpecs with per-figure rc modifications (>=7 keys each)."""
    specs: List[FigureSpec] = []

    # Base set of rc tweaks to ensure each figure feels distinct but within theme
    common_mod = {
        'axes.titleweight': 'bold',
        'axes.titlepad': 8.0,
        'axes.autolimit_mode': 'round_numbers',
        'axes.axisbelow': True,
        'legend.loc': 'best',
        'legend.borderaxespad': 0.6,
        'legend.borderpad': 0.4,
    }

    specs.append(FigureSpec(
        name='Line', filename='01_line.png', rc_mod={**common_mod, **{
            'axes.grid.which': 'both',
            'axes.grid.axis': 'both',
            'grid.alpha': 0.10,
            'grid.linestyle': '-',
            'lines.solid_capstyle': 'round',
            'lines.markersize': 0,
            'axes.xmargin': 0.02,
            'axes.ymargin': 0.05,
        }}, generator=fig_line))

    specs.append(FigureSpec(
        name='Scatter', filename='02_scatter.png', rc_mod={**common_mod, **{
            'axes.grid.axis': 'y',
            'grid.linestyle': ':',
            'grid.alpha': 0.12,
            'patch.force_edgecolor': False,
            'axes.xmargin': 0.05,
            'axes.ymargin': 0.05,
        }}, generator=fig_scatter))

    specs.append(FigureSpec(
        name='Bar', filename='03_bar.png', rc_mod={**common_mod, **{
            'axes.grid.axis': 'y',
            'grid.linestyle': '--',
            'grid.alpha': 0.10,
            'axes.xmargin': 0.03,
            'axes.ymargin': 0.05,
        }}, generator=fig_bar))

    specs.append(FigureSpec(
        name='Histogram', filename='04_hist.png', rc_mod={**common_mod, **{
            'axes.grid.axis': 'y',
            'grid.linestyle': '-',
            'grid.alpha': 0.10,
            'hist.bins': 30,
            'axes.xmargin': 0.03,
            'axes.ymargin': 0.05,
        }}, generator=fig_hist))

    specs.append(FigureSpec(
        name='Heatmap', filename='05_heatmap.png', rc_mod={**common_mod, **{
            'image.cmap': 'viridis',
            'image.interpolation': 'nearest',
            'axes.grid': False,
            'axes.edgecolor': 'none',
            'axes.xmargin': 0.0,
            'axes.ymargin': 0.0,
        }}, generator=fig_heatmap))

    specs.append(FigureSpec(
        name='Polar', filename='06_polar.png', rc_mod={**common_mod, **{
            'axes.grid.which': 'major',
            'grid.alpha': 0.12,
            'grid.linestyle': ':',
            'axes.titlepad': 14.0,
            'lines.linewidth': 1.4,
            'axes.xmargin': 0.0,
            'axes.ymargin': 0.0,
        }}, generator=fig_polar))

    specs.append(FigureSpec(
        name='Stacked Bar', filename='07_stacked_bar.png', rc_mod={**common_mod, **{
            'axes.grid.axis': 'y',
            'grid.alpha': 0.10,
            'grid.linestyle': '-',
            'axes.xmargin': 0.03,
            'axes.ymargin': 0.05,
        }}, generator=fig_stacked_bar))

    specs.append(FigureSpec(
        name='Box', filename='08_box.png', rc_mod={**common_mod, **{
            'boxplot.flierprops.marker': 'o',
            'boxplot.flierprops.markersize': 2.5,
            'boxplot.whiskerprops.linestyle': '-',
            'boxplot.boxprops.linewidth': 0.9,
            'boxplot.whiskerprops.linewidth': 0.9,
            'boxplot.capprops.linewidth': 0.9,
            'axes.grid.axis': 'y',
        }}, generator=fig_box))

    specs.append(FigureSpec(
        name='Time-series', filename='09_timeseries.png', rc_mod={**common_mod, **{
            'axes.grid.axis': 'y',
            'grid.linestyle': ':',
            'grid.alpha': 0.12,
            'lines.linewidth': 1.4,
            'axes.xmargin': 0.01,
        }}, generator=fig_timeseries))

    specs.append(FigureSpec(
        name='GridSpec', filename='10_gridspec.png', rc_mod={**common_mod, **{
            'axes.grid': False,
            'axes.spines.top': False,
            'axes.spines.right': False,
            'axes.titlepad': 6.0,
            'figure.figsize': (7.09, 3.54),
            'figure.constrained_layout.use': False,
            'figure.autolayout': True,
        }}, generator=fig_mixed_gridspec))

    return specs


def render_all(theme_rc: Dict[str, object], seed: int) -> Dict[str, bytes]:
    """Render all figures with given theme_rc, returning mapping filename->PNG bytes."""
    specs = build_figure_specs()
    rng = np.random.default_rng(seed)

    out: Dict[str, bytes] = {}
    for spec in specs:
        with mpl.rc_context(theme_rc | spec.rc_mod):
            fig, ax = plt.subplots()
            try:
                spec.generator(ax, rng)
                fig.canvas.draw()
                buf = io.BytesIO()
                fig.savefig(buf, format='png')
                out[spec.filename] = buf.getvalue()
            finally:
                plt.close(fig)
    return out
