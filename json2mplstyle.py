#!/usr/bin/env python3
# json2mplstyle.py
# Convert a JSON theme into a .mplstyle / matplotlibrc file with grouped sections,
# concise per-section change summaries, and validation against your local Matplotlib (if available).

import argparse
import json
import math
import sys
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Tuple

# ---- Grouping & ordering -----------------------------------------------------

SECTION_SPECS = [
    ("figure", "Figures", ("figure.",)),
    ("axes", "Axes", ("axes.",)),
    ("lines", "Lines", ("lines.",)),
    ("ticks", "Ticks", ("xtick.", "ytick.")),
    ("grid", "Grid", ("grid.",)),
    ("legend", "Legend", ("legend.",)),
    ("fonts", "Fonts & Text", ("font.", "text.")),
    ("savefig", "Savefig", ("savefig.",)),
    (
        "image",
        "Images & Colormaps",
        ("image.", "cmap.", "colormap."),
    ),  # keep broad just in case
    (
        "patches",
        "Patches / Hatches / Markers",
        ("patch.", "hatch.", "markers.", "marker."),
    ),
    ("misc", "Other", ()),  # anything valid that doesn't hit the above
]

SECTION_ORDER = [k for k, _, _ in SECTION_SPECS]

# ---- Optional validation with Matplotlib -------------------------------------


def _matplotlib_context():
    try:
        import matplotlib as mpl  # noqa
        from matplotlib import rcParams, rcParamsDefault

        return True, rcParams, rcParamsDefault, mpl
    except Exception:
        return False, None, None, None


HAS_MPL, RCPARAMS, RCPARAMS_DEFAULT, MPL = _matplotlib_context()

# ---- Helpers -----------------------------------------------------------------


def _is_bool(x: Any) -> bool:
    return isinstance(x, bool)


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _format_bool(x: bool) -> str:
    # Matplotlib wants True/False capitalized
    return "True" if x else "False"


def _format_tuple_like(seq: Iterable[Any]) -> str:
    return "(" + ", ".join(_format_value(v) for v in seq) + ")"


def _format_list_for_csv(seq: Iterable[Any]) -> str:
    return ", ".join(_format_value(v) for v in seq)


def _format_value(v: Any, key: str = "") -> str:
    """
    Convert Python/JSON value into a matplotlibrc string.
    We keep strings as-is (unless they contain '#', then we quote them),
    booleans as True/False, tuples/lists as "(a, b, c)" by default.
    Special case: figure.figsize -> "w, h" (without parentheses).
    """
    # figsize special: prefer "w, h"
    if key == "figure.figsize":
        if (
            isinstance(v, (list, tuple))
            and len(v) == 2
            and all(_is_number(x) for x in v)
        ):
            return f"{v[0]}, {v[1]}"
        # if bad, fall back
    if _is_bool(v):
        return _format_bool(bool(v))
    if _is_number(v):
        # ints as ints, floats as plain floats
        return str(v)
    if isinstance(v, (list, tuple)):
        # for generic tuples/lists, use "(…)" which rc accepts
        return _format_tuple_like(v)
    if isinstance(v, str):
        # Quote strings that contain a comment char, so they aren't truncated.
        return f"'{v}'" if "#" in v else v
    # Fallback: JSON objects -> JSON string (commented key if not validated)
    try:
        return json.dumps(v, ensure_ascii=False)
    except Exception:
        return str(v)


def _flatten_grouped_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accept either:
      - flat: {"axes.facecolor": "#fff", "figure.dpi": 200}
      - grouped: {"axes": {"facecolor": "#fff"}, "figure": {"dpi": 200}}
    If a key contains dots, treat it as fully-qualified rcParam.
    If top-level key is a known prefix group, prefix subkeys with "group."
    """
    out = {}
    for k, v in data.items():
        if "." in k:
            out[k] = v
        elif isinstance(v, dict):
            # Grouped form
            for sk, sv in v.items():
                out[f"{k}.{sk}"] = sv
        else:
            # Unknown single token key; keep as-is (may validate later)
            out[k] = v
    return out


def _section_for_key(key: str) -> str:
    for sec_key, _, prefixes in SECTION_SPECS:
        if any(key.startswith(p) for p in prefixes if p):
            return sec_key
    return "misc"


def _summarize_changes(keys: List[str]) -> str:
    """
    Build a concise one-line bullet-ish list for a section comment.
    e.g., "Changed: facecolor, edgecolor, linewidth, linestyle (4 items)"
    """
    # Only the last token after the dot to keep it concise
    short = [k.split(".")[-1] for k in keys]
    if not short:
        return "No changes."
    # keep order but unique-ish
    seen = set()
    uniq = [x for x in short if not (x in seen or seen.add(x))]
    # Limit to a handful for readability
    if len(uniq) > 8:
        head = ", ".join(uniq[:8])
        return f"Changed: {head}, … ({len(uniq)} items)"
    return "Changed: " + ", ".join(uniq)


def _validate_rc_items(
    items: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Tuple[str, Any, str]]]:
    """
    If Matplotlib is available, validate by attempting to set into a fresh RcParams.
    Returns (valid_items, invalid_items_with_reason)
    """
    if not HAS_MPL:
        # Can’t validate without Matplotlib locally.
        return items, []

    # Create a shallow copy of defaults as a clean validator target
    from matplotlib import rcParams as live_rc
    from matplotlib import RcParams  # type: ignore

    test_rc = RcParams(live_rc)

    valid = {}
    invalid: List[Tuple[str, Any, str]] = []
    for k, v in items.items():
        try:
            # Attempt to assign; this will raise KeyError or ValueError if invalid.
            test_rc[k] = v
            valid[k] = v
        except KeyError as e:
            invalid.append((k, v, f"Unknown rcParam: {e}"))
        except ValueError as e:
            invalid.append((k, v, f"Invalid value: {e}"))
        except Exception as e:
            invalid.append((k, v, f"{type(e).__name__}: {e}"))
    return valid, invalid


def _normalize_axes_prop_cycle(value: Any) -> str | None:
    """
    If value is a list of colors, emit an rc-compatible cycler string:
      cycler('color', ['#a', '#b', ...])
    If it's already a string, return as-is. Otherwise None to let generic formatting handle it.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)) and all(
        isinstance(c, (str, list, tuple)) for c in value
    ):
        # Normalize nested tuples (e.g., RGB) into rc tuple strings or leave strings
        colors = []
        for c in value:
            if isinstance(c, str):
                colors.append(c)
            elif isinstance(c, (list, tuple)):
                colors.append(_format_tuple_like(c))
            else:
                colors.append(str(c))
        # Wrap tuple-strings in quotes only if they contain '#'? Usually not needed.
        colors_repr = ", ".join(
            (f"'{c}'" if isinstance(c, str) and "#" in c else f"{c}") for c in colors
        )
        return f"cycler('color', [{colors_repr}])"
    return None


# ---- Main conversion ---------------------------------------------------------


def convert_json_to_mplstyle(
        data: Dict[str, Any], write_unknown_as_comments: bool = True
) -> Tuple[str, List[str]]:
    """
    Returns (mplstyle_text, warnings_list)
    """
    flat = _flatten_grouped_json(data)

    # Special-case normalization hooks (add more as needed)
    special_overrides = {}
    if "axes.prop_cycle" in flat:
        cyc = _normalize_axes_prop_cycle(flat["axes.prop_cycle"])
        if cyc is not None:
            special_overrides["axes.prop_cycle"] = cyc

    # Format values for file output (strings, tuples, booleans, etc.)
    formatted: Dict[str, str] = {}
    for k, v in flat.items():
        if k in special_overrides:
            formatted[k] = special_overrides[k]
        else:
            formatted[k] = _format_value(v, key=k)

    # Validate against Matplotlib (if available)
    to_check = {k: v for k, v in flat.items()}
    valid_items, invalid_items = _validate_rc_items(to_check)

    # Split into sections using only the valid keys
    sections: Dict[str, Dict[str, str]] = defaultdict(dict)
    for k in valid_items:
        sec = _section_for_key(k)
        sections[sec][k] = formatted[k]

    # Build output text
    lines: List[str] = []
    lines.append("# Generated by json2mplstyle.py\n#   github.com/temataro/gpt5-Matplotlib-Theme-Lab\n")
    if HAS_MPL:
        lines.append(
            "# Validation: Matplotlib detected; invalid keys/values were omitted and listed below."
        )
    else:
        lines.append(
            "# Validation: Matplotlib not detected; emitted keys were not runtime-validated."
        )

    # Emit sections in fixed order
    for sec_key, sec_title, _ in SECTION_SPECS:
        kv = sections.get(sec_key, {})
        if not kv:
            continue
        # Per-section concise summary
        section_keys_sorted = sorted(kv.keys())
        summary = _summarize_changes(section_keys_sorted)
        lines.append("")
        lines.append(f"# ===== {sec_title} =====")
        lines.append(f"# {summary}")
        # Emit key: value lines
        for k in section_keys_sorted:
            lines.append(f"{k}: {kv[k]}")

    # Any valid keys that didn't match a known section are already placed into "misc"

    # Optionally write invalids as commented block
    warnings = []
    if invalid_items:
        lines.append("")
        lines.append("# ===== Invalid / Skipped =====")
        for k, v, reason in invalid_items:
            warnings.append(f"{k} -> {v!r} :: {reason}")
            fv = _format_value(v, key=k)
            lines.append(f"# {k}: {fv}")
            lines.append(f"#   ^ {reason}")

    # Unknown-but-valid section note: already handled via validation
    return "\n".join(lines).rstrip() + "\n", warnings


# ---- CLI ---------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Convert a JSON theme to a .mplstyle (matplotlibrc) with validation and grouped sections."
    )
    parser.add_argument("-i", "--input", help="Path to input JSON file.")
    parser.add_argument(
        "-o",
        "--output",
        default="",
        help="Path to output .mplstyle file (default: stdout).",
    )
    parser.add_argument(
        "--no-write-invalid-comments",
        action="store_true",
        help="Do not write invalid/skipped keys as commented lines in the output.",
    )
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
            data = data["rc_global"]
    except Exception as e:
        print(f"Error reading JSON: {e}", file=sys.stderr)
        sys.exit(1)

    text, warnings = convert_json_to_mplstyle(
        data, write_unknown_as_comments=not args.no_write_invalid_comments
    )

    if args.output != "":
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            print(f"Error writing output: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(text, end="")

    if warnings:
        print(f"\n[Validation warnings: {len(warnings)}]", file=sys.stderr)
        for w in warnings:
            print(f"- {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
