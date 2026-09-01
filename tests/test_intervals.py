"""Tests for interval and affine arithmetic primitives."""

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from certified_dose.intervals import AffineForm, Interval

# --- Unit Tests for Interval ---


def test_interval_initialization() -> None:
    i1 = Interval(1.0, 5.0)
    assert i1.lo == 1.0
    assert i1.hi == 5.0
    assert i1.midpoint == 3.0
    assert i1.width == 4.0
    assert i1.radius == 2.0

    # Degenerate interval
    i2 = Interval(3.5)
    assert i2.lo == 3.5
    assert i2.hi == 3.5
    assert i2.width == 0.0

    # Invalid intervals
    with pytest.raises(ValueError, match="lower bound .* > upper bound"):
        Interval(5.0, 2.0)

    with pytest.raises(ValueError, match="cannot be NaN"):
        Interval(float("nan"), 1.0)


def test_interval_containment_and_queries() -> None:
    i = Interval(2.0, 8.0)
    assert i.contains(2.0)
    assert i.contains(5.5)
    assert i.contains(8.0)
    assert not i.contains(1.99)
    assert not i.contains(8.01)

    sub = Interval(3.0, 6.0)
    assert i.contains_interval(sub)
    assert not sub.contains_interval(i)


def test_interval_widen() -> None:
    i = Interval(2.0, 5.0)
    widened = i.widen(0.5)
    assert widened.lo == 1.5
    assert widened.hi == 5.5

    with pytest.raises(ValueError, match="cannot be negative"):
        i.widen(-0.1)


def test_interval_hull_and_intersection() -> None:
    i1 = Interval(1.0, 4.0)
    i2 = Interval(3.0, 7.0)

    hull = i1.hull(i2)
    assert hull.lo == 1.0
    assert hull.hi == 7.0

    inter = i1.intersection(i2)
    assert inter is not None
    assert inter.lo == 3.0
    assert inter.hi == 4.0

    # Disjoint intervals
    i3 = Interval(5.0, 6.0)
    assert i1.intersection(i3) is None


def test_interval_addition_subtraction() -> None:
    i1 = Interval(1.0, 3.0)
    i2 = Interval(2.0, 5.0)

    # Addition
    add_int = i1 + i2
    assert add_int.lo == 3.0
    assert add_int.hi == 8.0

    add_scalar = i1 + 4.0
    assert add_scalar.lo == 5.0
    assert add_scalar.hi == 7.0

    radd_scalar = 4.0 + i1
    assert radd_scalar == add_scalar

    # Subtraction
    sub_int = i1 - i2
    assert sub_int.lo == 1.0 - 5.0
    assert sub_int.hi == 3.0 - 2.0

    sub_scalar = i1 - 1.0
    assert sub_scalar.lo == 0.0
    assert sub_scalar.hi == 2.0

    rsub_scalar = 5.0 - i1
    assert rsub_scalar.lo == 5.0 - 3.0
    assert rsub_scalar.hi == 5.0 - 1.0

    # Negation
    neg = -i1
    assert neg.lo == -3.0
    assert neg.hi == -1.0


def test_interval_multiplication_division() -> None:
    i1 = Interval(2.0, 4.0)
    i2 = Interval(-3.0, 5.0)

    # Multiplication
    mul = i1 * i2
    # products: -6, 10, -12, 20
    assert mul.lo == -12.0
    assert mul.hi == 20.0

    mul_scalar = i1 * -2.0
    assert mul_scalar.lo == -8.0
    assert mul_scalar.hi == -4.0

    # Division
    i3 = Interval(1.0, 2.0)
    div = i1 / i3
    assert div.lo == 1.0
    assert div.hi == 4.0

    # Division by interval containing zero
    with pytest.raises(ZeroDivisionError):
        _ = i1 / Interval(-1.0, 1.0)

    with pytest.raises(ZeroDivisionError):
        _ = i1 / 0.0

    with pytest.raises(ZeroDivisionError):
        _ = 5.0 / Interval(-1.0, 1.0)


def test_interval_powers() -> None:
    # Odd integer power
    i_odd = Interval(-2.0, 3.0)
    p_odd = i_odd**3
    assert p_odd.lo == -8.0
    assert p_odd.hi == 27.0

    # Even integer power straddling zero
    i_even = Interval(-2.0, 3.0)
    p_even = i_even**2
    assert p_even.lo == 0.0
    assert p_even.hi == 9.0

    # Even integer power strictly positive
    i_pos = Interval(2.0, 4.0)
    p_pos = i_pos**2
    assert p_pos.lo == 4.0
    assert p_pos.hi == 16.0

    # Even integer power strictly negative
    i_neg = Interval(-4.0, -2.0)
    p_neg = i_neg**2
    assert p_neg.lo == 4.0
    assert p_neg.hi == 16.0

    # Power 0
    assert (i_pos**0).lo == 1.0
    assert (i_pos**0).hi == 1.0

    # Negative power
    inv = i_pos**-1
    assert math.isclose(inv.lo, 0.25)
    assert math.isclose(inv.hi, 0.50)

    # Float power
    p_float = i_pos**1.5
    assert math.isclose(p_float.lo, 2.0**1.5)
    assert math.isclose(p_float.hi, 4.0**1.5)

    with pytest.raises(ValueError, match="Fractional power not defined"):
        _ = Interval(-2.0, 2.0) ** 1.5

    # Regression test: negative fractional power
    neg_frac = Interval(4.0, 9.0) ** -0.5
    assert math.isclose(neg_frac.lo, 1.0 / 3.0)
    assert math.isclose(neg_frac.hi, 1.0 / 2.0)

    # Regression test: integer-valued float power on negative straddling interval
    even_float = Interval(-2.0, 3.0) ** 2.0
    assert even_float.lo == 0.0
    assert even_float.hi == 9.0

    # Negative power on interval containing zero
    with pytest.raises(ZeroDivisionError):
        _ = Interval(-1.0, 2.0) ** -0.5

    with pytest.raises(ZeroDivisionError):
        _ = Interval(0.0, 2.0) ** -2


def test_interval_math_functions() -> None:
    i = Interval(0.0, 2.0)
    exp_i = i.exp()
    assert math.isclose(exp_i.lo, 1.0)
    assert math.isclose(exp_i.hi, math.exp(2.0))

    pos_i = Interval(1.0, math.e)
    log_i = pos_i.log()
    assert math.isclose(log_i.lo, 0.0)
    assert math.isclose(log_i.hi, 1.0)

    with pytest.raises(ValueError, match="Natural log undefined"):
        Interval(-1.0, 2.0).log()

    sqrt_i = Interval(4.0, 9.0).sqrt()
    assert sqrt_i.lo == 2.0
    assert sqrt_i.hi == 3.0

    with pytest.raises(ValueError, match="Square root undefined"):
        Interval(-4.0, 4.0).sqrt()

    abs_straddle = Interval(-3.0, 2.0).abs()
    assert abs_straddle.lo == 0.0
    assert abs_straddle.hi == 3.0


# --- AffineForm Tests ---


def test_affine_form_basic() -> None:
    a1 = AffineForm.from_interval(Interval(10.0, 14.0), symbol="e1")
    assert a1.x0 == 12.0
    assert a1.terms["e1"] == 2.0

    int_a1 = a1.to_interval()
    assert int_a1.lo == 10.0
    assert int_a1.hi == 14.0

    # Self-cancellation in affine arithmetic (a - a = 0)
    zero_form = a1 - a1
    assert zero_form.to_interval().lo == 0.0
    assert zero_form.to_interval().hi == 0.0

    # Contrast with interval arithmetic where [10, 14] - [10, 14] = [-4, 4]
    int_diff = Interval(10.0, 14.0) - Interval(10.0, 14.0)
    assert int_diff.lo == -4.0
    assert int_diff.hi == 4.0


def test_affine_form_multiplication() -> None:
    a1 = AffineForm.from_interval(Interval(2.0, 4.0), symbol="e1")
    a2 = AffineForm.from_interval(Interval(3.0, 5.0), symbol="e2")

    prod = a1 * a2
    inter = prod.to_interval()
    # True multiplication range of [2, 4] * [3, 5] is [6, 20]
    assert inter.lo <= 6.0
    assert inter.hi >= 20.0


def test_interval_apply_monotonic() -> None:
    i = Interval(1.0, 4.0)
    # Increasing
    inc = i.apply_monotonic(lambda x: x * 2.0, increasing=True)
    assert inc.lo == 2.0
    assert inc.hi == 8.0

    # Decreasing
    dec = i.apply_monotonic(lambda x: 10.0 - x, increasing=False)
    assert dec.lo == 6.0
    assert dec.hi == 9.0


def test_interval_repr_and_eq() -> None:
    i = Interval(1.234567, 8.9)
    assert "Interval" in repr(i)
    assert i == Interval(1.234567, 8.9)
    assert i != "not an interval"
    assert i != Interval(1.0, 8.9)


def test_interval_reverse_operators() -> None:
    i = Interval(2.0, 5.0)
    assert (10.0 - i) == Interval(5.0, 8.0)
    assert (20.0 / i) == Interval(4.0, 10.0)
    assert (3.0 * i) == Interval(6.0, 15.0)
    assert (4.0 + i) == Interval(6.0, 9.0)


def test_affine_form_scalar_operations_and_repr() -> None:
    a = AffineForm.from_scalar(10.0)
    assert a.x0 == 10.0
    assert a.rad == 0.0
    assert len(a.terms) == 0

    a_affine = AffineForm.from_interval(Interval(8.0, 12.0), symbol="eps")
    assert "AffineForm" in repr(a_affine)

    # Scalar addition
    add1 = a_affine + 5.0
    assert add1.x0 == 15.0
    add2 = 5.0 + a_affine
    assert add2.x0 == 15.0

    # Scalar subtraction
    sub1 = a_affine - 2.0
    assert sub1.x0 == 8.0
    sub2 = 20.0 - a_affine
    assert sub2.x0 == 10.0

    # Scalar multiplication
    mul1 = a_affine * 3.0
    assert mul1.x0 == 30.0
    mul2 = 3.0 * a_affine
    assert mul2.x0 == 30.0

    # Negation
    neg = -a_affine
    assert neg.x0 == -10.0


# --- Hypothesis Property-Based Tests for Interval Arithmetic ---


@given(
    st.floats(
        min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False
    ),
    st.floats(
        min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False
    ),
    st.floats(
        min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False
    ),
    st.floats(
        min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False
    ),
)
def test_hypothesis_interval_addition_soundness(
    a1: float, a2: float, b1: float, b2: float
) -> None:
    """Tests inclusion monotonicity for addition: x in A and y in B => x+y in A+B."""
    A = Interval(min(a1, a2), max(a1, a2))
    B = Interval(min(b1, b2), max(b1, b2))

    C = A + B
    # Sample center points
    x = A.midpoint
    y = B.midpoint
    assert C.contains(x + y)
    # Commutativity
    assert (A + B) == (B + A)


@given(
    st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
)
def test_hypothesis_interval_multiplication_soundness(
    a1: float, a2: float, b1: float, b2: float
) -> None:
    """Tests inclusion monotonicity for multiplication."""
    A = Interval(min(a1, a2), max(a1, a2))
    B = Interval(min(b1, b2), max(b1, b2))

    C = A * B
    x = A.midpoint
    y = B.midpoint
    assert C.contains(x * y)
    assert (A * B) == (B * A)
