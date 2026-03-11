"""Curve fitting engine with 12 built-in models.

Uses scipy.optimize.curve_fit for non-linear models and
numpy.polyfit / numpy.polyval for polynomial models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

import numpy as np
from scipy.optimize import curve_fit

from func.models.fit_result import FitResult


# ---------------------------------------------------------------------------
# Fit model definition
# ---------------------------------------------------------------------------

@dataclass
class FitModel:
    """Specification for one fit model."""

    name: str
    category: str
    expression_str: str
    func: Callable  # (x, *params) -> y
    param_names: list[str] = field(default_factory=list)
    default_p0: list[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Model functions
# ---------------------------------------------------------------------------

def _linear(x, a, b):
    return a * x + b


def _poly2(x, a, b, c):
    return a * x**2 + b * x + c


def _poly3(x, a, b, c, d):
    return a * x**3 + b * x**2 + c * x + d


def _poly4(x, a, b, c, d, e):
    return a * x**4 + b * x**3 + c * x**2 + d * x + e


def _gaussian(x, A, mu, sigma, y0):
    return A * np.exp(-((x - mu) ** 2) / (2 * sigma**2)) + y0


def _lorentzian(x, A, x0, gamma, y0):
    return A * gamma**2 / ((x - x0) ** 2 + gamma**2) + y0


def _voigt_pseudo(x, A, x0, sigma, gamma, eta, y0):
    """Pseudo-Voigt: weighted sum of Gaussian and Lorentzian profiles."""
    gauss = np.exp(-((x - x0) ** 2) / (2 * sigma**2))
    lorentz = gamma**2 / ((x - x0) ** 2 + gamma**2)
    return A * (eta * lorentz + (1 - eta) * gauss) + y0


def _exp_growth(x, A, k, y0):
    return A * np.exp(k * x) + y0


def _exp_decay(x, A, k, y0):
    return A * np.exp(-k * x) + y0


def _boltzmann(x, A1, A2, x0, dx):
    return A2 + (A1 - A2) / (1 + np.exp((x - x0) / dx))


def _power_law(x, A, n):
    return A * np.power(np.abs(x), n)


def _sine_wave(x, A, omega, phi, y0):
    return A * np.sin(omega * x + phi) + y0


# ---------------------------------------------------------------------------
# Registry of built-in fit models
# ---------------------------------------------------------------------------

FIT_MODELS: dict[str, FitModel] = {}


def _register(model: FitModel) -> None:
    FIT_MODELS[model.name] = model


_register(FitModel(
    name="Linear",
    category="Linear",
    expression_str="y = a·x + b",
    func=_linear,
    param_names=["a", "b"],
    default_p0=[1.0, 0.0],
))

_register(FitModel(
    name="Polynomial (2)",
    category="Polynomial",
    expression_str="y = a·x² + b·x + c",
    func=_poly2,
    param_names=["a", "b", "c"],
    default_p0=[1.0, 1.0, 0.0],
))

_register(FitModel(
    name="Polynomial (3)",
    category="Polynomial",
    expression_str="y = a·x³ + b·x² + c·x + d",
    func=_poly3,
    param_names=["a", "b", "c", "d"],
    default_p0=[1.0, 1.0, 1.0, 0.0],
))

_register(FitModel(
    name="Polynomial (4)",
    category="Polynomial",
    expression_str="y = a·x⁴ + b·x³ + c·x² + d·x + e",
    func=_poly4,
    param_names=["a", "b", "c", "d", "e"],
    default_p0=[1.0, 1.0, 1.0, 1.0, 0.0],
))

_register(FitModel(
    name="Gaussian",
    category="Peak",
    expression_str="y = A·exp(-(x-μ)²/(2σ²)) + y₀",
    func=_gaussian,
    param_names=["A", "μ", "σ", "y₀"],
    default_p0=[1.0, 0.0, 1.0, 0.0],
))

_register(FitModel(
    name="Lorentzian",
    category="Peak",
    expression_str="y = A·γ² / ((x-x₀)² + γ²) + y₀",
    func=_lorentzian,
    param_names=["A", "x₀", "γ", "y₀"],
    default_p0=[1.0, 0.0, 1.0, 0.0],
))

_register(FitModel(
    name="Voigt (pseudo)",
    category="Peak",
    expression_str="y = A·[η·L(x) + (1-η)·G(x)] + y₀",
    func=_voigt_pseudo,
    param_names=["A", "x₀", "σ", "γ", "η", "y₀"],
    default_p0=[1.0, 0.0, 1.0, 1.0, 0.5, 0.0],
))

_register(FitModel(
    name="Exponential Growth",
    category="Growth/Decay",
    expression_str="y = A·exp(k·x) + y₀",
    func=_exp_growth,
    param_names=["A", "k", "y₀"],
    default_p0=[1.0, 0.1, 0.0],
))

_register(FitModel(
    name="Exponential Decay",
    category="Growth/Decay",
    expression_str="y = A·exp(-k·x) + y₀",
    func=_exp_decay,
    param_names=["A", "k", "y₀"],
    default_p0=[1.0, 0.1, 0.0],
))

_register(FitModel(
    name="Boltzmann Sigmoid",
    category="Growth/Decay",
    expression_str="y = A₂ + (A₁-A₂) / (1 + exp((x-x₀)/dx))",
    func=_boltzmann,
    param_names=["A₁", "A₂", "x₀", "dx"],
    default_p0=[0.0, 1.0, 0.0, 1.0],
))

_register(FitModel(
    name="Power Law",
    category="Power",
    expression_str="y = A·x^n",
    func=_power_law,
    param_names=["A", "n"],
    default_p0=[1.0, 1.0],
))

_register(FitModel(
    name="Sine Wave",
    category="Periodic",
    expression_str="y = A·sin(ω·x + φ) + y₀",
    func=_sine_wave,
    param_names=["A", "ω", "φ", "y₀"],
    default_p0=[1.0, 1.0, 0.0, 0.0],
))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _smart_initial_guess(model: FitModel, x: np.ndarray, y: np.ndarray) -> list[float]:
    """Generate data-aware initial guess for better convergence."""

    name = model.name

    if name == "Linear":
        # Use endpoints for slope/intercept
        if len(x) >= 2:
            a = (y[-1] - y[0]) / (x[-1] - x[0]) if (x[-1] != x[0]) else 1.0
            b = y[0] - a * x[0]
            return [a, b]
        return model.default_p0[:]

    if name.startswith("Polynomial"):
        return model.default_p0[:]

    if name == "Gaussian":
        A = float(np.max(y) - np.min(y))
        mu = float(x[np.argmax(y)])
        sigma = float((x[-1] - x[0]) / 6) if len(x) > 1 else 1.0
        y0 = float(np.min(y))
        return [A, mu, max(sigma, 1e-6), y0]

    if name == "Lorentzian":
        A = float(np.max(y) - np.min(y))
        x0 = float(x[np.argmax(y)])
        gamma = float((x[-1] - x[0]) / 6) if len(x) > 1 else 1.0
        y0 = float(np.min(y))
        return [A, x0, max(gamma, 1e-6), y0]

    if name == "Voigt (pseudo)":
        A = float(np.max(y) - np.min(y))
        x0 = float(x[np.argmax(y)])
        w = float((x[-1] - x[0]) / 6) if len(x) > 1 else 1.0
        y0 = float(np.min(y))
        return [A, x0, max(w, 1e-6), max(w, 1e-6), 0.5, y0]

    if name in ("Exponential Growth", "Exponential Decay"):
        A = float(y[0]) if len(y) > 0 else 1.0
        return [A if A != 0 else 1.0, 0.01, 0.0]

    if name == "Boltzmann Sigmoid":
        A1 = float(np.min(y))
        A2 = float(np.max(y))
        x0 = float(np.median(x))
        dx = float((x[-1] - x[0]) / 4) if len(x) > 1 else 1.0
        return [A1, A2, x0, max(dx, 1e-6)]

    if name == "Power Law":
        return [1.0, 1.0]

    if name == "Sine Wave":
        A = float((np.max(y) - np.min(y)) / 2)
        y0 = float(np.mean(y))
        return [max(A, 1e-6), 1.0, 0.0, y0]

    return model.default_p0[:]


def _compute_r_squared(y_data: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = np.sum((y_data - y_pred) ** 2)
    ss_tot = np.sum((y_data - np.mean(y_data)) ** 2)
    if ss_tot == 0:
        return 1.0 if ss_res == 0 else 0.0
    return float(1 - ss_res / ss_tot)


def _compute_chi_squared(y_data: np.ndarray, y_pred: np.ndarray) -> float:
    residuals = y_data - y_pred
    return float(np.sum(residuals**2))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_model_names() -> list[str]:
    """Return the list of available fit model names."""
    return list(FIT_MODELS.keys())


def perform_fit(
    x: np.ndarray,
    y: np.ndarray,
    model_name: str,
    p0: Optional[Sequence[float]] = None,
    num_points: int = 500,
) -> FitResult:
    """Fit data to a named model.

    Parameters
    ----------
    x, y : numpy arrays of data.
    model_name : key in FIT_MODELS.
    p0 : optional initial parameter guess (overrides smart guess).
    num_points : number of points in the smooth fitted curve.

    Returns
    -------
    FitResult with fitted parameters, errors, R², and smooth curve.
    """

    if model_name not in FIT_MODELS:
        return FitResult(
            model_name=model_name,
            expression_str="",
            success=False,
            message=f"Unknown fit model: {model_name}",
        )

    model = FIT_MODELS[model_name]

    # Use numpy polyfit for polynomial models (more stable)
    if model_name.startswith("Polynomial") or model_name == "Linear":
        return _fit_polynomial(x, y, model, num_points)

    # Initial guess
    if p0 is not None:
        initial = list(p0)
    else:
        initial = _smart_initial_guess(model, x, y)

    try:
        popt, pcov = curve_fit(
            model.func,
            x,
            y,
            p0=initial,
            maxfev=10000,
        )
    except Exception as e:
        return FitResult(
            model_name=model_name,
            expression_str=model.expression_str,
            success=False,
            message=f"Fit failed: {e}",
        )

    # Parameter errors from covariance diagonal
    perr = np.sqrt(np.diag(pcov)) if pcov is not None else np.zeros(len(popt))

    params = {name: float(val) for name, val in zip(model.param_names, popt)}
    param_errors = {name: float(val) for name, val in zip(model.param_names, perr)}

    # Predictions on original data for R²/χ²
    y_pred = model.func(x, *popt)
    r2 = _compute_r_squared(y, y_pred)
    chi2 = _compute_chi_squared(y, y_pred)

    # Generate smooth curve
    x_fit = np.linspace(float(np.min(x)), float(np.max(x)), num_points)
    y_fit = model.func(x_fit, *popt)

    return FitResult(
        model_name=model_name,
        expression_str=model.expression_str,
        params=params,
        param_errors=param_errors,
        r_squared=r2,
        chi_squared=chi2,
        x_fit=x_fit,
        y_fit=y_fit,
        success=True,
        message=f"Fit converged (R² = {r2:.6f})",
    )


def _fit_polynomial(
    x: np.ndarray,
    y: np.ndarray,
    model: FitModel,
    num_points: int,
) -> FitResult:
    """Use numpy.polyfit for polynomial/linear fits (more stable)."""

    degree = len(model.param_names) - 1  # Linear=1, Poly2=2, etc.

    try:
        coeffs, cov = np.polyfit(x, y, degree, cov=True)
    except Exception as e:
        return FitResult(
            model_name=model.name,
            expression_str=model.expression_str,
            success=False,
            message=f"Fit failed: {e}",
        )

    perr = np.sqrt(np.diag(cov))
    params = {name: float(val) for name, val in zip(model.param_names, coeffs)}
    param_errors = {name: float(val) for name, val in zip(model.param_names, perr)}

    y_pred = np.polyval(coeffs, x)
    r2 = _compute_r_squared(y, y_pred)
    chi2 = _compute_chi_squared(y, y_pred)

    x_fit = np.linspace(float(np.min(x)), float(np.max(x)), num_points)
    y_fit = np.polyval(coeffs, x_fit)

    return FitResult(
        model_name=model.name,
        expression_str=model.expression_str,
        params=params,
        param_errors=param_errors,
        r_squared=r2,
        chi_squared=chi2,
        x_fit=x_fit,
        y_fit=y_fit,
        success=True,
        message=f"Fit converged (R² = {r2:.6f})",
    )
