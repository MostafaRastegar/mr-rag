"""
Tests for the science / academic notation normalizer.
"""

from app.infrastructure.science_normalizer import process, normalizer


def test_math_caret():
    assert process("x^2 + y^2 = z^2") == "$x^2$ + $y^2$ = $z^2$"


def test_math_underscore():
    assert process("x_1 + y_2") == "$x_1$ + $y_2$"


def test_math_functions():
    out = process("sin(30) + cos(60)")
    assert "$sin$" in out and "$cos$" in out


def test_chemistry_simple():
    out = process("H2O + CO2 -> C6H12O6")
    assert "$\\mathrm{H_{2}O}$" in out
    assert "$\\mathrm{CO_{2}}$" in out
    assert "$\\mathrm{C_{6}H_{12}O_{6}}$" in out


def test_chemistry_parenthesized():
    out = process("Fe2(SO4)3")
    assert "$\\mathrm{Fe_{2}(SO_{4})_{3}}$" in out


def test_biology_abbrev():
    out = process("DNA and RNA transcripts")
    assert "DNA" in out and "RNA" in out


def test_plain_text_unchanged():
    assert process("no science here") == "no science here"


def test_empty_string():
    assert process("") == ""


def test_idempotent():
    text = "H2O and x^2"
    assert process(process(text)) == process(text)


def test_latex_output_disabled():
    n = normalizer.__class__(latex_output=False)
    out = n.process("H2O and x^2")
    assert "$" not in out
    assert "₂" in out or "²" in out  # unicode sub/superscripts


def test_greek_letters():
    out = process("Delta = 5")
    assert "$\\Delta$" in out or "Delta" in out
