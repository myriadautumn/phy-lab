

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PropagationResult:
    """Result of an error-propagation calculation."""

    values: pd.Series
    errors: pd.Series


@dataclass(frozen=True)
class BinaryPropagationInput:
    """Input container for binary operations.

    Parameters are expected to be aligned pandas Series.
    """

    a: pd.Series
    sigma_a: pd.Series
    b: pd.Series
    sigma_b: pd.Series


class PropagationError(ValueError):
    """Raised when propagation inputs are invalid."""


def _to_numeric_series(series: pd.Series, name: str) -> pd.Series:
    """Return a float Series suitable for propagation math."""
    if series is None:
        raise PropagationError(f"{name} is required.")
    out = pd.to_numeric(series, errors="coerce").astype(float)
    return out


def _validate_binary(inp: BinaryPropagationInput) -> BinaryPropagationInput:
    """Validate and normalize binary propagation input."""
    a = _to_numeric_series(inp.a, "a")
    sigma_a = _to_numeric_series(inp.sigma_a, "sigma_a")
    b = _to_numeric_series(inp.b, "b")
    sigma_b = _to_numeric_series(inp.sigma_b, "sigma_b")

    n = len(a)
    if len(sigma_a) != n or len(b) != n or len(sigma_b) != n:
        raise PropagationError("Input series must have the same length.")

    return BinaryPropagationInput(a=a, sigma_a=sigma_a, b=b, sigma_b=sigma_b)


def _result(values: pd.Series, errors: pd.Series) -> PropagationResult:
    return PropagationResult(values=values.astype(float), errors=errors.astype(float))


def propagate_add(inp: BinaryPropagationInput) -> PropagationResult:
    """Gaussian propagation for Q = a + b.

    sigma_Q = sqrt(sigma_a^2 + sigma_b^2)
    """
    inp = _validate_binary(inp)
    values = inp.a + inp.b
    errors = np.sqrt(inp.sigma_a**2 + inp.sigma_b**2)
    return _result(values, errors)


def propagate_sub(inp: BinaryPropagationInput) -> PropagationResult:
    """Gaussian propagation for Q = a - b.

    sigma_Q = sqrt(sigma_a^2 + sigma_b^2)
    """
    inp = _validate_binary(inp)
    values = inp.a - inp.b
    errors = np.sqrt(inp.sigma_a**2 + inp.sigma_b**2)
    return _result(values, errors)


def propagate_mul(inp: BinaryPropagationInput) -> PropagationResult:
    """Gaussian propagation for Q = a * b.

    sigma_Q = sqrt((b*sigma_a)^2 + (a*sigma_b)^2)
    """
    inp = _validate_binary(inp)
    values = inp.a * inp.b
    errors = np.sqrt((inp.b * inp.sigma_a) ** 2 + (inp.a * inp.sigma_b) ** 2)
    return _result(values, errors)


def propagate_div(inp: BinaryPropagationInput) -> PropagationResult:
    """Gaussian propagation for Q = a / b.

    sigma_Q = sqrt((sigma_a / b)^2 + (a*sigma_b / b^2)^2)

    Division by zero results are converted to NaN.
    """
    inp = _validate_binary(inp)
    with np.errstate(divide="ignore", invalid="ignore"):
        values = inp.a / inp.b
        errors = np.sqrt((inp.sigma_a / inp.b) ** 2 + ((inp.a * inp.sigma_b) / (inp.b ** 2)) ** 2)

    values = values.replace([np.inf, -np.inf], np.nan)
    errors = errors.replace([np.inf, -np.inf], np.nan)
    return _result(values, errors)


def propagate_power(x: pd.Series, sigma_x: pd.Series, exponent: float) -> PropagationResult:
    """Gaussian propagation for Q = x^n.

    sigma_Q = |n * x^(n-1)| * sigma_x
    """
    x = _to_numeric_series(x, "x")
    sigma_x = _to_numeric_series(sigma_x, "sigma_x")
    if len(x) != len(sigma_x):
        raise PropagationError("x and sigma_x must have the same length.")

    with np.errstate(invalid="ignore"):
        values = x**exponent
        errors = np.abs(exponent * (x ** (exponent - 1.0))) * sigma_x

    values = values.replace([np.inf, -np.inf], np.nan)
    errors = errors.replace([np.inf, -np.inf], np.nan)
    return _result(values, errors)


def propagate_general(
    values: list[pd.Series],
    errors: list[pd.Series],
    partials: list[pd.Series],
) -> pd.Series:
    """General Gaussian propagation.

    sigma_f = sqrt(sum((df/dx_i * sigma_i)^2))

    This helper returns only the propagated error term because the caller is
    expected to compute the transformed values separately.
    """
    if not values or not errors or not partials:
        raise PropagationError("values, errors, and partials must not be empty.")
    if not (len(values) == len(errors) == len(partials)):
        raise PropagationError("values, errors, and partials must have the same length.")

    accum: pd.Series | None = None
    base_len: int | None = None

    for idx, (v, s, p) in enumerate(zip(values, errors, partials, strict=True), start=1):
        vv = _to_numeric_series(v, f"values[{idx}]")
        ss = _to_numeric_series(s, f"errors[{idx}]")
        pp = _to_numeric_series(p, f"partials[{idx}]")

        if base_len is None:
            base_len = len(vv)
        if len(vv) != base_len or len(ss) != base_len or len(pp) != base_len:
            raise PropagationError("All series in values/errors/partials must have the same length.")

        term = (pp * ss) ** 2
        accum = term if accum is None else (accum + term)

    assert accum is not None
    return np.sqrt(accum).astype(float)


def propagate_from_callable(
    func: Callable[..., pd.Series],
    args: list[pd.Series],
    arg_errors: list[pd.Series],
    partial_derivatives: list[pd.Series],
) -> PropagationResult:
    """Compute propagated uncertainty for an already-defined function.

    The caller supplies:
    - func: transformation producing the output values
    - args: input value series
    - arg_errors: uncertainty series for each input
    - partial_derivatives: evaluated partial derivative series for each input

    This keeps the module independent from any future expression parser.
    """
    if not args:
        raise PropagationError("args must not be empty.")
    if not (len(args) == len(arg_errors) == len(partial_derivatives)):
        raise PropagationError("args, arg_errors, and partial_derivatives must have the same length.")

    values = func(*args)
    if not isinstance(values, pd.Series):
        values = pd.Series(values)

    propagated = propagate_general(args, arg_errors, partial_derivatives)
    return _result(pd.to_numeric(values, errors="coerce"), propagated)