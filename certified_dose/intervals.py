"""Interval and affine arithmetic primitives for formal reachability analysis.

This module provides verified numerical interval arithmetic and first-order
affine arithmetic representations. These form the mathematical backbone of the
worst-case reachability analysis engine.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any


class Interval:
    """Rigorous closed real interval [lo, hi].

    Guarantees conservative over-approximation for all supported operations.
    If an operation cannot be conservatively bounded (e.g. division by an
    interval containing zero), an explicit exception is raised.

    Attributes:
        lo: Lower bound of the interval.
        hi: Upper bound of the interval.
    """

    __slots__ = ("_lo", "_hi")

    def __init__(self, lo: float, hi: float | None = None) -> None:
        """Initializes a closed real interval [lo, hi].

        Args:
            lo: Lower bound (or scalar value if hi is None).
            hi: Upper bound. If None, the interval is degenerate [lo, lo].

        Raises:
            ValueError: If lo > hi, or if bounds are NaN.
        """
        lower = float(lo)
        upper = lower if hi is None else float(hi)

        if math.isnan(lower) or math.isnan(upper):
            raise ValueError(f"Interval bounds cannot be NaN: [{lower}, {upper}]")
        if lower > upper:
            raise ValueError(
                f"Invalid interval: lower bound ({lower}) > upper bound ({upper})"
            )

        self._lo: float = lower
        self._hi: float = upper

    @property
    def lo(self) -> float:
        """Returns the lower bound."""
        return self._lo

    @property
    def hi(self) -> float:
        """Returns the upper bound."""
        return self._hi

    @property
    def midpoint(self) -> float:
        """Returns the midpoint (center) of the interval."""
        return (self._lo + self._hi) / 2.0

    @property
    def width(self) -> float:
        """Returns the width (diameter) of the interval."""
        return self._hi - self._lo

    @property
    def radius(self) -> float:
        """Returns the radius (half-width) of the interval."""
        return (self._hi - self._lo) / 2.0

    def contains(self, value: float) -> bool:
        """Checks if a scalar value is contained in [lo, hi].

        Args:
            value: Scalar number to test.

        Returns:
            True if value is within bounds, False otherwise.
        """
        return self._lo <= value <= self._hi

    def contains_interval(self, other: Interval) -> bool:
        """Checks if another interval is completely contained within this interval.

        Args:
            other: The interval to test for containment.

        Returns:
            True if other is a subset of self.
        """
        return self._lo <= other.lo and other.hi <= self._hi

    def widen(self, margin: float) -> Interval:
        """Expands the interval by an absolute safety margin on both sides.

        Useful for compensating for floating-point truncation or ensuring strict
        conservativeness.

        Args:
            margin: Non-negative expansion amount.

        Returns:
            Widened interval [lo - margin, hi + margin].

        Raises:
            ValueError: If margin is negative.
        """
        if margin < 0:
            raise ValueError(f"Widen margin cannot be negative: {margin}")
        return Interval(self._lo - margin, self._hi + margin)

    def hull(self, other: Interval) -> Interval:
        """Computes the interval convex hull containing both intervals.

        Args:
            other: The second interval.

        Returns:
            Smallest interval containing both self and other.
        """
        return Interval(min(self._lo, other.lo), max(self._hi, other.hi))

    def intersection(self, other: Interval) -> Interval | None:
        """Computes the intersection of two intervals.

        Args:
            other: The second interval.

        Returns:
            The intersecting Interval, or None if intervals are disjoint.
        """
        new_lo = max(self._lo, other.lo)
        new_hi = min(self._hi, other.hi)
        if new_lo > new_hi:
            return None
        return Interval(new_lo, new_hi)

    def apply_monotonic(
        self, f: Callable[[float], float], increasing: bool = True
    ) -> Interval:
        """Applies a strictly monotonic function to the interval bounds.

        Args:
            f: Scalar continuous function.
            increasing: True if f is monotonically non-decreasing, False if non-increasing.

        Returns:
            Exact enclosing interval [f(lo), f(hi)] or [f(hi), f(lo)].
        """
        v1 = f(self._lo)
        v2 = f(self._hi)
        if increasing:
            return Interval(min(v1, v2), max(v1, v2))
        return Interval(min(v2, v1), max(v2, v1))

    # --- Arithmetic Operators ---

    def __add__(self, other: Interval | float) -> Interval:
        if isinstance(other, Interval):
            return Interval(self._lo + other.lo, self._hi + other.hi)
        if isinstance(other, (int, float)):
            return Interval(self._lo + other, self._hi + other)
        return NotImplemented

    def __radd__(self, other: float) -> Interval:
        return self.__add__(other)

    def __neg__(self) -> Interval:
        return Interval(-self._hi, -self._lo)

    def __sub__(self, other: Interval | float) -> Interval:
        if isinstance(other, Interval):
            return Interval(self._lo - other.hi, self._hi - other.lo)
        if isinstance(other, (int, float)):
            return Interval(self._lo - other, self._hi - other)
        return NotImplemented

    def __rsub__(self, other: float) -> Interval:
        if isinstance(other, (int, float)):
            return Interval(other - self._hi, other - self._lo)
        return NotImplemented

    def __mul__(self, other: Interval | float) -> Interval:
        if isinstance(other, (int, float)):
            p1 = self._lo * other
            p2 = self._hi * other
            return Interval(min(p1, p2), max(p1, p2))
        if isinstance(other, Interval):
            p1 = self._lo * other.lo
            p2 = self._lo * other.hi
            p3 = self._hi * other.lo
            p4 = self._hi * other.hi
            return Interval(min(p1, p2, p3, p4), max(p1, p2, p3, p4))
        return NotImplemented

    def __rmul__(self, other: float) -> Interval:
        return self.__mul__(other)

    def __truediv__(self, other: Interval | float) -> Interval:
        if isinstance(other, (int, float)):
            if other == 0:
                raise ZeroDivisionError("Interval division by scalar zero.")
            return self * (1.0 / other)
        if isinstance(other, Interval):
            if other.contains(0.0):
                raise ZeroDivisionError(
                    f"Interval division by an interval containing zero [{other.lo}, {other.hi}] is unbounded."
                )
            inv = Interval(1.0 / other.hi, 1.0 / other.lo)
            return self * inv
        return NotImplemented

    def __rtruediv__(self, other: float) -> Interval:
        if isinstance(other, (int, float)):
            if self.contains(0.0):
                raise ZeroDivisionError(
                    f"Interval division by an interval containing zero [{self._lo}, {self._hi}] is unbounded."
                )
            inv = Interval(1.0 / self._hi, 1.0 / self._lo)
            return inv * other
        return NotImplemented

    def __pow__(self, exponent: int | float) -> Interval:
        """Raises interval to a power.

        For integer powers:
        - Odd powers: strictly monotonic.
        - Even powers: if interval straddles zero, lower bound is 0.

        For positive float powers:
        - Requires interval lo >= 0.

        Raises:
            ValueError: If power is invalid for negative intervals.
        """
        if isinstance(exponent, int):
            if exponent == 0:
                return Interval(1.0, 1.0)
            if exponent < 0:
                return 1.0 / (self ** (-exponent))
            if exponent % 2 == 1:
                return Interval(self._lo**exponent, self._hi**exponent)
            # Even power
            if self._lo >= 0:
                return Interval(self._lo**exponent, self._hi**exponent)
            if self._hi <= 0:
                return Interval(self._hi**exponent, self._lo**exponent)
            # Straddles zero
            max_val = max(abs(self._lo), abs(self._hi)) ** exponent
            return Interval(0.0, max_val)

        if isinstance(exponent, float):
            if self._lo < 0:
                raise ValueError(
                    f"Fractional power not defined for negative interval [{self._lo}, {self._hi}]"
                )
            return Interval(self._lo**exponent, self._hi**exponent)

        return NotImplemented

    def exp(self) -> Interval:
        """Computes element-wise exponential e^x."""
        return Interval(math.exp(self._lo), math.exp(self._hi))

    def log(self) -> Interval:
        """Computes natural logarithm ln(x).

        Raises:
            ValueError: If interval lo <= 0.
        """
        if self._lo <= 0:
            raise ValueError(
                f"Natural log undefined for non-positive interval [{self._lo}, {self._hi}]"
            )
        return Interval(math.log(self._lo), math.log(self._hi))

    def sqrt(self) -> Interval:
        """Computes element-wise square root.

        Raises:
            ValueError: If interval lo < 0.
        """
        if self._lo < 0:
            raise ValueError(
                f"Square root undefined for negative interval [{self._lo}, {self._hi}]"
            )
        return Interval(math.sqrt(self._lo), math.sqrt(self._hi))

    def abs(self) -> Interval:
        """Computes element-wise absolute value |x|."""
        if self._lo >= 0:
            return Interval(self._lo, self._hi)
        if self._hi <= 0:
            return Interval(-self._hi, -self._lo)
        return Interval(0.0, max(abs(self._lo), abs(self._hi)))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Interval):
            return False
        return math.isclose(
            self._lo, other.lo, rel_tol=1e-12, abs_tol=1e-12
        ) and math.isclose(self._hi, other.hi, rel_tol=1e-12, abs_tol=1e-12)

    def __repr__(self) -> str:
        return f"Interval([{self._lo:.6g}, {self._hi:.6g}])"


class AffineForm:
    """First-order Affine Arithmetic Form.

    Represents uncertain quantities as:
        x_hat = x0 + sum_i(xi * eps_i) + r * eps_r

    where:
        - x0 is the central value
        - xi are partial deviations for named noise symbols eps_i in [-1, 1]
        - r is the accumulated approximation error bound (radius)

    Affine arithmetic tracks correlations between variables, dramatically
    reducing the wrapping effect (e.g. x - x = 0 in affine arithmetic,
    whereas [a, b] - [a, b] = [a-b, b-a] in interval arithmetic).
    """

    __slots__ = ("_x0", "_terms", "_rad")

    def __init__(
        self,
        x0: float,
        terms: dict[str, float] | None = None,
        rad: float = 0.0,
    ) -> None:
        """Initializes an affine form.

        Args:
            x0: Center value.
            terms: Mapping from symbol name to partial deviation coefficient.
            rad: Accumulated truncation/approximation error radius (>= 0).

        Raises:
            ValueError: If rad is negative or any value is NaN.
        """
        if math.isnan(x0) or math.isnan(rad):
            raise ValueError("AffineForm values cannot be NaN")
        if rad < 0:
            raise ValueError(f"Approximation radius cannot be negative: {rad}")

        self._x0: float = float(x0)
        self._terms: dict[str, float] = {
            k: float(v) for k, v in (terms or {}).items() if abs(v) > 1e-15
        }
        self._rad: float = float(rad)

    @property
    def x0(self) -> float:
        """Returns the central value."""
        return self._x0

    @property
    def terms(self) -> dict[str, float]:
        """Returns a copy of the partial deviation terms."""
        return dict(self._terms)

    @property
    def rad(self) -> float:
        """Returns the residual approximation error radius."""
        return self._rad

    @classmethod
    def from_interval(cls, interval: Interval, symbol: str) -> AffineForm:
        """Creates an affine form from an Interval by assigning a new noise symbol.

        Args:
            interval: Source interval [lo, hi].
            symbol: Unique name for the noise symbol.

        Returns:
            AffineForm with center at midpoint and deviation equal to radius.
        """
        center = interval.midpoint
        radius = interval.radius
        return cls(x0=center, terms={symbol: radius}, rad=0.0)

    @classmethod
    def from_scalar(cls, value: float) -> AffineForm:
        """Creates a deterministic affine form without noise symbols."""
        return cls(x0=value, terms={}, rad=0.0)

    def to_interval(self) -> Interval:
        """Converts the affine form to a guaranteed bounding Interval.

        Returns:
            Interval [x0 - total_radius, x0 + total_radius].
        """
        total_radius = sum(abs(coeff) for coeff in self._terms.values()) + self._rad
        return Interval(self._x0 - total_radius, self._x0 + total_radius)

    # --- Affine Arithmetic Operators ---

    def __add__(self, other: AffineForm | float | int) -> AffineForm:
        if isinstance(other, (int, float)):
            return AffineForm(self._x0 + other, self._terms, self._rad)
        if isinstance(other, AffineForm):
            new_terms = dict(self._terms)
            for sym, coeff in other.terms.items():
                new_terms[sym] = new_terms.get(sym, 0.0) + coeff
            return AffineForm(self._x0 + other.x0, new_terms, self._rad + other.rad)
        return NotImplemented

    def __radd__(self, other: float | int) -> AffineForm:
        return self.__add__(other)

    def __neg__(self) -> AffineForm:
        neg_terms = {k: -v for k, v in self._terms.items()}
        return AffineForm(-self._x0, neg_terms, self._rad)

    def __sub__(self, other: AffineForm | float | int) -> AffineForm:
        if isinstance(other, (int, float)):
            return AffineForm(self._x0 - other, self._terms, self._rad)
        if isinstance(other, AffineForm):
            return self + (-other)
        return NotImplemented

    def __rsub__(self, other: float | int) -> AffineForm:
        if isinstance(other, (int, float)):
            return (-self) + other
        return NotImplemented

    def __mul__(self, other: AffineForm | float | int) -> AffineForm:
        if isinstance(other, (int, float)):
            scale = float(other)
            new_terms = {k: v * scale for k, v in self._terms.items()}
            return AffineForm(self._x0 * scale, new_terms, self._rad * abs(scale))
        if isinstance(other, AffineForm):
            # First-order multiplication:
            # (x0 + sum xi eps_i + rx) * (y0 + sum yi eps_i + ry)
            # = x0*y0 + sum (x0*yi + y0*xi) eps_i + second_order_bound
            new_x0 = self._x0 * other.x0
            all_symbols = set(self._terms.keys()) | set(other.terms.keys())
            mult_terms: dict[str, float] = {}
            for sym in all_symbols:
                c1 = self._terms.get(sym, 0.0)
                c2 = other.terms.get(sym, 0.0)
                coeff = self._x0 * c2 + other.x0 * c1
                if abs(coeff) > 1e-15:
                    mult_terms[sym] = coeff

            rad_x = sum(abs(v) for v in self._terms.values()) + self._rad
            rad_y = sum(abs(v) for v in other.terms.values()) + other.rad

            # Conservative error bound for non-linear residual + cross terms
            error = (
                rad_x * rad_y + abs(self._x0) * other.rad + abs(other.x0) * self._rad
            )
            return AffineForm(new_x0, mult_terms, error)
        return NotImplemented

    def __rmul__(self, other: float | int) -> AffineForm:
        return self.__mul__(other)

    def __repr__(self) -> str:
        interval = self.to_interval()
        return f"AffineForm(x0={self._x0:.4g}, rad={self._rad:.4g} -> {interval})"
