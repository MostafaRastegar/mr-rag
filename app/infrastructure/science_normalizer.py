"""
Science / academic notation normalizer for the RAG pipeline.

Detects and normalizes mathematical, chemical, and biological symbols in
retrieved context and generated answers so they can be rendered correctly
by the frontend (KaTeX / plain Unicode).

Design goals
------------
- Dependency-light: regex first, optional libraries (sympy / chemparse /
  biopython / unidecode) only for validation of complex expressions.
- Idempotent: running it twice produces the same result.
- Safe on arbitrary text: never raises for malformed input — falls back to
  the original string.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def _try_import(name: str) -> Optional[object]:
    try:
        module = __import__(name)
        return module
    except Exception:  # pragma: no cover - environment dependent
        logger.debug("Optional dependency %s not available", name)
        return None


_SUPERSCRIPT_MAP = str.maketrans(
    "0123456789+-=()abcdefghijklmnopqrstuvwxyz",
    "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖˠʳˢᵗᵘⱽʷˣʸᶻ",
)

_SUBSCRIPT_MAP = str.maketrans(
    "0123456789+-=()aehiklmnoprstuvx",
    "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢₖₗₘₙₒₚₛᵣₜᵤᵥₓ",
)

_LATEX_INLINE_RE = re.compile(r"\$[^$]+\$")
_LATEX_DISPLAY_RE = re.compile(r"\$\$[\s\S]*?\$\$")

_MATH_TOKEN_RE = re.compile(
    r"""
    (?:
        (?<=\W)
        |
        ^
    )
    (
        [αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ]
        |
        [A-Za-z]\^\d+
        |
        [A-Za-z]_\d+
        |
        \b(sin|cos|tan|log|ln|exp|sqrt)\b
        |
        [∫∑∏∂∇Δπ∞≤≥≠±×÷]
        |
        [A-Za-z0-9]\s*/\s*[A-Za-z0-9]
    )
    (?=\W|$)
    """,
    re.VERBOSE,
)
_CHEM_FORMULA_RE = re.compile(
    r"\b(?:[A-Z][a-z]?\d*)+(?:\((?:[A-Z][a-z]?\d*)+\)\d*)*\b"
)

_BIO_ABBREV_RE = re.compile(
    r"\b(DNA|RNA|mRNA|tRNA|rRNA|ATP|ADP|AMP|NAD|NADH|FAD|FADH2|"
    r"CoA|acetyl-CoA|glucose|glycolysis|mitosis|meiosis|"
    r"ribosome|mitochondrion|chloroplast|nucleus|cytoplasm|"
    r"enzyme|protein|amino acid|nucleotide|codon|antisense|"
    r"plasmid|vector|PCR|ELISA|CRISPR|siRNA|miRNA|lncRNA)\b",
    re.IGNORECASE,
)


class ScienceNormalizer:
    """Detects and normalizes science notation in text.

    Parameters
    ----------
    latex_output:
        If True, wrap detected expressions in LaTeX inline math delimiters
        (`$...$`) so the frontend can render them with KaTeX. If False,
        normalize to Unicode superscript/subscript instead.
    """

    def __init__(self, latex_output: bool = True) -> None:
        self.latex_output = latex_output
        self._sympy = _try_import("sympy")
        self._chemparse = _try_import("chemparse")
        self._periodictal = _try_import("periodictal")

    def process(self, text: str) -> str:
        """Normalize all science notation in *text*.

        Safe to call on any string; returns the input unchanged on error.
        """
        if not text:
            return text
        try:
            text = self._protect_latex(text)
            text = self.normalize_chemistry(text)   # chemistry FIRST
            text = self.normalize_math(text)        # then math
            text = self.normalize_biology(text)     # then biology (no-op)
            text = self._restore_latex(text)
            return text
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Science normalizer failed: %s", e)
            return text

    def normalize_math(self, text: str) -> str:
        """Detect math expressions and convert to LaTeX or Unicode."""
        if self.latex_output:
            return _MATH_TOKEN_RE.sub(lambda m: f"${m.group(0)}$", text)
        return _MATH_TOKEN_RE.sub(self._math_to_unicode, text)

    def normalize_chemistry(self, text: str) -> str:
        """Detect chemical formulas and render subscripts."""
        if not self._chemparse:
            return text

        def _replace(match: re.Match[str]) -> str:
            token = match.group(0)
            if len(token) == 1:
                return token
            try:
                parsed = self._chemparse.parse_formula(token)
                if not parsed:
                    return token
            except Exception:
                return token
            if self.latex_output:
                return f"$\\mathrm{{{self._formula_to_latex(token)}}}$"
            return self._formula_to_unicode(token)

        return _CHEM_FORMULA_RE.sub(_replace, text)

    def normalize_biology(self, text: str) -> str:
        """Keep biology abbreviations intact (frontend/LLM handles semantics)."""
        return _BIO_ABBREV_RE.sub(lambda m: m.group(0), text)

    def _protect_latex(self, text: str) -> str:
        self._latex_placeholders: list[str] = []

        def _store(match: re.Match[str]) -> str:
            self._latex_placeholders.append(match.group(0))
            return f"__LATEX_{len(self._latex_placeholders) - 1}__"

        text = _LATEX_DISPLAY_RE.sub(_store, text)
        text = _LATEX_INLINE_RE.sub(_store, text)
        return text

    def _restore_latex(self, text: str) -> str:
        for i, original in enumerate(getattr(self, "_latex_placeholders", [])):
            text = text.replace(f"__LATEX_{i}__", original)
        return text

    @staticmethod
    def _math_to_unicode(match: re.Match[str]) -> str:
        token = match.group(0)
        token = re.sub(
            r"\^(\d+)", lambda m: m.group(1).translate(_SUPERSCRIPT_MAP), token
        )
        token = re.sub(
            r"_(\d+)", lambda m: m.group(1).translate(_SUBSCRIPT_MAP), token
        )
        return token

    @staticmethod
    def _formula_to_latex(formula: str) -> str:
        return re.sub(r"(\d+)", r"_{\1}", formula)

    @staticmethod
    def _formula_to_unicode(formula: str) -> str:
        return re.sub(
            r"(\d+)", lambda m: m.group(1).translate(_SUBSCRIPT_MAP), formula
        )


normalizer = ScienceNormalizer(latex_output=True)


def process(text: str) -> str:
    return normalizer.process(text)

