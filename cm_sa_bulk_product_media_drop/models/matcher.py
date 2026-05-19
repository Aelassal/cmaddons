"""Pure-Python filename → product matching logic.

Kept in its own module (no ORM classes) so it can be unit-tested without
booting Odoo. The wizard in ../wizard/ calls into these helpers.
"""
import os
import re
from difflib import SequenceMatcher


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
_STRIP = re.compile(r"[^a-zA-Z0-9]+")


def is_image(filename):
    return os.path.splitext(filename)[1].lower() in _IMAGE_EXTS


def normalize(token):
    """Lowercase + strip non-alphanumerics, for loose comparisons."""
    return _STRIP.sub("", (token or "").lower())


def parse_filename(filename):
    """Split ``SKU123-red-L-2.jpg`` into (stem_parts, sequence_hint).

    Returns a dict with keys:
        ``stem``    — filename without extension
        ``parts``   — [sku_candidate, *modifiers]  (dash-split)
        ``position``— integer gallery position, or None
        ``is_thumb``— bool
    """
    stem, _ = os.path.splitext(os.path.basename(filename))
    parts = [p for p in re.split(r"[-_]", stem) if p]
    position = None
    is_thumb = False

    # Trailing numeric → gallery position
    if parts and parts[-1].isdigit():
        position = int(parts[-1])
        parts = parts[:-1]

    # Trailing 'thumb' or 'thumbnail' → thumbnail flag
    if parts and normalize(parts[-1]) in ("thumb", "thumbnail"):
        is_thumb = True
        parts = parts[:-1]

    return {
        "stem": stem,
        "parts": parts,
        "position": position,
        "is_thumb": is_thumb,
    }


def similarity(a, b):
    """0.0–1.0 loose match ratio."""
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def find_product(parsed, products_by_ref, products_by_barcode, all_templates,
                 fuzzy_threshold=0.85):
    """Resolve a parsed filename to a ``product.template`` candidate.

    ``products_by_ref``    — {normalized(default_code): template_id}
    ``products_by_barcode``— {normalized(barcode): template_id}
    ``all_templates``      — list of (template_id, default_code, name) tuples

    Returns a dict {template_id, modifiers, score} or None.
    """
    # Pass 0: try the full stem as an exact SKU/barcode. Covers products whose
    # reference itself contains dashes or trailing digits (e.g. "SKU-0123"),
    # which the modifier parser would otherwise carve apart.
    full = normalize(parsed["stem"])
    tid = products_by_ref.get(full) or products_by_barcode.get(full)
    if tid:
        return {"template_id": tid, "modifiers": [], "score": 1.0, "match_by": "stem"}

    if not parsed["parts"]:
        return None

    sku_candidate = parsed["parts"][0]
    modifiers = parsed["parts"][1:]
    norm = normalize(sku_candidate)

    # 1. Exact match on internal reference
    tid = products_by_ref.get(norm)
    if tid:
        return {"template_id": tid, "modifiers": modifiers, "score": 1.0, "match_by": "ref"}

    # 2. Exact match on barcode
    tid = products_by_barcode.get(norm)
    if tid:
        return {"template_id": tid, "modifiers": modifiers, "score": 1.0, "match_by": "barcode"}

    # 3. Fuzzy match against internal references (cheap — normalized keys only)
    best_score = 0.0
    best_tid = None
    for ref_norm, ref_tid in products_by_ref.items():
        score = similarity(norm, ref_norm)
        if score > best_score:
            best_score = score
            best_tid = ref_tid
    if best_tid and best_score >= fuzzy_threshold:
        return {
            "template_id": best_tid,
            "modifiers": modifiers,
            "score": best_score,
            "match_by": "fuzzy_ref",
        }

    # 4. Fuzzy against names — only if stem is reasonably long (avoid noise)
    if len(norm) >= 4:
        for tid, _ref, name in all_templates:
            score = similarity(parsed["stem"], name)
            if score > best_score:
                best_score = score
                best_tid = tid
        if best_tid and best_score >= fuzzy_threshold:
            return {
                "template_id": best_tid,
                "modifiers": modifiers,
                "score": best_score,
                "match_by": "fuzzy_name",
            }

    return None
