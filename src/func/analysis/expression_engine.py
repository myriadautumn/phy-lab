from __future__ import annotations

from dataclasses import dataclass
import ast
import re
from typing import Any

import numpy as np
import pandas as pd
import sympy as sp

from func.analysis.error_propagation import (
    PropagationError,
    PropagationResult,
    propagate_general,
)
from func.models.dataset import Dataset


@dataclass(frozen=True)
class ExpressionResult:
    """Result of evaluating a derived expression."""

    values: pd.Series
    errors: pd.Series | None = None


@dataclass(frozen=True)
class DerivedDatasetResult:
    """Container for a newly generated dataset from an expression."""

    dataset: Dataset
    value_column: str
    error_column: str | None = None


@dataclass(frozen=True)
class NormalizedExpression:
    """Normalized expression ready for evaluation.

    Attributes
    ----------
    original:
        User-entered expression.
    normalized:
        Python-safe expression used internally.
    token_to_column:
        Mapping of generated safe tokens (e.g. COL_0) back to the original
        dataset column names wrapped in braces by the user.
    """

    original: str
    normalized: str
    token_to_column: dict[str, str]


class ExpressionEngineError(ValueError):
    """Raised when an expression cannot be parsed or evaluated."""


# Functions allowed in user expressions.
_ALLOWED_FUNCS: dict[str, Any] = {
    "sin": np.sin,
    "cos": np.cos,
    "tan": np.tan,
    "asin": np.arcsin,
    "acos": np.arccos,
    "atan": np.arctan,
    "sinh": np.sinh,
    "cosh": np.cosh,
    "tanh": np.tanh,
    "exp": np.exp,
    "log": np.log,
    "log10": np.log10,
    "sqrt": np.sqrt,
    "abs": np.abs,
}

_ALLOWED_CONSTS: dict[str, float] = {
    "pi": float(np.pi),
    "e": float(np.e),
}

_ALLOWED_SYMPY_FUNCS: dict[str, Any] = {
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "sinh": sp.sinh,
    "cosh": sp.cosh,
    "tanh": sp.tanh,
    "exp": sp.exp,
    "log": sp.log,
    "log10": lambda x: sp.log(x, 10),
    "sqrt": sp.sqrt,
    "abs": sp.Abs,
    "pi": sp.pi,
    "e": sp.E,
}

_ALLOWED_NODES = {
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Name,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.Constant,
    ast.Call,
}

_BRACE_REF_RE = re.compile(r"\{([^{}]+)\}")


def _normalize_math_notation(expr: str) -> str:
    """Normalize common user-friendly math notation into Python syntax.

    Supported conveniences:
    - `^` becomes `**`
    - unicode multiplication/division/minus/dot operators are normalized
    - simple implicit multiplication such as `2pi`, `2sin(x)`, or `2(x+1)`
      becomes explicit multiplication
    """
    normalized = expr.strip()
    normalized = normalized.replace("×", "*")
    normalized = normalized.replace("·", "*")
    normalized = normalized.replace("÷", "/")
    normalized = normalized.replace("−", "-")
    normalized = normalized.replace("^", "**")

    # Add explicit multiplication for common implicit cases.
    # Example: 2pi -> 2*pi, 2sin(x) -> 2*sin(x), 2(x+1) -> 2*(x+1)
    normalized = re.sub(r"(?<=\d)(?=[A-Za-z_(])", "*", normalized)
    normalized = re.sub(r"(?<=\))(?=[\dA-Za-z_(])", "*", normalized)
    return normalized


def normalize_expression(expr: str) -> NormalizedExpression:
    """Convert a user expression into a Python-safe internal expression.

    Column names containing spaces or symbols can be referenced using braces,
    for example:

        2*pi*{Angle (rad) Run #6}

    which is normalized internally to a safe tokenized expression.
    """
    if not expr or not expr.strip():
        raise ExpressionEngineError("Expression must not be empty.")

    token_to_column: dict[str, str] = {}

    def _replace_brace_ref(match: re.Match[str]) -> str:
        column_name = match.group(1).strip()
        if not column_name:
            raise ExpressionEngineError("Empty column reference {} is not allowed.")
        token = f"COL_{len(token_to_column)}"
        token_to_column[token] = column_name
        return token

    replaced = _BRACE_REF_RE.sub(_replace_brace_ref, expr)
    normalized = _normalize_math_notation(replaced)

    return NormalizedExpression(
        original=expr,
        normalized=normalized,
        token_to_column=token_to_column,
    )


def _validate_expression(normalized_expr: str) -> ast.Expression:
    try:
        tree = ast.parse(normalized_expr, mode="eval")
    except SyntaxError as exc:
        raise ExpressionEngineError(f"Invalid expression syntax: {exc}") from exc

    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODES:
            raise ExpressionEngineError(
                f"Unsupported expression element: {type(node).__name__}"
            )
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
                raise ExpressionEngineError(
                    "Only a restricted set of math functions is allowed."
                )

    return tree


def extract_expression_variables(expr: str) -> list[str]:
    """Return sorted unique dataset-variable names used by the expression.

    This returns original dataset column names for brace-wrapped references and
    regular variable names for already-safe column names.
    """
    normalized = normalize_expression(expr)
    tree = _validate_expression(normalized.normalized)
    names = {
        normalized.token_to_column.get(node.id, node.id)
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and node.id not in _ALLOWED_FUNCS
        and node.id not in _ALLOWED_CONSTS
    }
    return sorted(names)


def _extract_normalized_variable_names(normalized: NormalizedExpression) -> list[str]:
    """Return sorted unique variable tokens/names from a normalized expression."""
    tree = _validate_expression(normalized.normalized)
    names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and node.id not in _ALLOWED_FUNCS
        and node.id not in _ALLOWED_CONSTS
    }
    return sorted(names)


def _resolve_dataset_column(var_name: str, token_to_column: dict[str, str]) -> str:
    return token_to_column.get(var_name, var_name)


def _build_eval_context(
    df: pd.DataFrame,
    normalized_variables: list[str],
    token_to_column: dict[str, str],
) -> dict[str, Any]:
    ctx: dict[str, Any] = {name: func for name, func in _ALLOWED_FUNCS.items()}
    ctx.update(_ALLOWED_CONSTS)

    missing: list[str] = []
    for var_name in normalized_variables:
        column_name = _resolve_dataset_column(var_name, token_to_column)
        if column_name not in df.columns:
            missing.append(column_name)

    if missing:
        raise ExpressionEngineError(
            f"Columns not found in dataset: {', '.join(sorted(set(missing)))}"
        )

    for var_name in normalized_variables:
        column_name = _resolve_dataset_column(var_name, token_to_column)
        ctx[var_name] = pd.to_numeric(df[column_name], errors="coerce").astype(float)
    return ctx


def evaluate_expression(expr: str, df: pd.DataFrame) -> pd.Series:
    """Evaluate a numeric expression against DataFrame columns.

    Supported examples:
        evaluate_expression("voltage / current", df)
        evaluate_expression("2*pi*{Angle (rad) Run #6}", df)
    """
    normalized = normalize_expression(expr)
    _validate_expression(normalized.normalized)
    variables = _extract_normalized_variable_names(normalized)
    ctx = _build_eval_context(df, variables, normalized.token_to_column)

    try:
        values = eval(
            compile(normalized.normalized, "<expression>", "eval"),
            {"__builtins__": {}},
            ctx,
        )
    except Exception as exc:
        raise ExpressionEngineError(f"Failed to evaluate expression: {exc}") from exc

    if isinstance(values, pd.Series):
        out = pd.to_numeric(values, errors="coerce")
    else:
        out = pd.Series(values)
        out = pd.to_numeric(out, errors="coerce")
    return out.astype(float)


def evaluate_expression_with_errors(
    expr: str,
    df: pd.DataFrame,
    error_columns: dict[str, str],
) -> PropagationResult:
    """Evaluate an expression and propagate uncertainty via Gaussian propagation.

    Parameters
    ----------
    expr:
        Expression using DataFrame column names, e.g. ``"distance / time"`` or
        ``"2*pi*{Angle (rad) Run #6}"``.
    df:
        Source DataFrame.
    error_columns:
        Mapping from value column name -> error column name.
        Example: ``{"distance": "distance_err", "time": "time_err"}``

    Returns
    -------
    PropagationResult
        Contains the derived values and propagated errors.
    """
    normalized = normalize_expression(expr)
    normalized_variables = _extract_normalized_variable_names(normalized)
    if not normalized_variables:
        raise ExpressionEngineError(
            "Expression must reference at least one dataset column."
        )

    original_variables = [
        _resolve_dataset_column(name, normalized.token_to_column)
        for name in normalized_variables
    ]

    missing_err = [name for name in original_variables if name not in error_columns]
    if missing_err:
        raise ExpressionEngineError(
            "Missing error-column mapping for: " + ", ".join(sorted(missing_err))
        )

    values = evaluate_expression(expr, df)

    try:
        symbols = {name: sp.Symbol(name) for name in normalized_variables}
        sym_expr = sp.sympify(
            normalized.normalized,
            locals={**symbols, **_ALLOWED_SYMPY_FUNCS},
        )
    except Exception as exc:
        raise ExpressionEngineError(
            f"Failed to parse symbolic expression: {exc}"
        ) from exc

    partials: list[pd.Series] = []
    val_series_list: list[pd.Series] = []
    err_series_list: list[pd.Series] = []

    value_map = {
        name: pd.to_numeric(
            df[_resolve_dataset_column(name, normalized.token_to_column)],
            errors="coerce",
        ).astype(float)
        for name in normalized_variables
    }

    for name in normalized_variables:
        original_name = _resolve_dataset_column(name, normalized.token_to_column)
        err_col = error_columns[original_name]
        if err_col not in df.columns:
            raise ExpressionEngineError(f"Error column not found in dataset: {err_col}")

        sigma = pd.to_numeric(df[err_col], errors="coerce").astype(float)
        derivative_expr = sp.diff(sym_expr, symbols[name])

        try:
            derivative_func = sp.lambdify(
                [symbols[var] for var in normalized_variables],
                derivative_expr,
                modules=[_ALLOWED_FUNCS | _ALLOWED_CONSTS, "numpy"],
            )
        except Exception as exc:
            raise ExpressionEngineError(
                f"Failed to build derivative for {original_name}: {exc}"
            ) from exc

        try:
            derivative_values = derivative_func(
                *[value_map[var] for var in normalized_variables]
            )
        except Exception as exc:
            raise ExpressionEngineError(
                f"Failed to evaluate derivative for {original_name}: {exc}"
            ) from exc

        partial_series = pd.Series(derivative_values, index=df.index)
        partial_series = pd.to_numeric(partial_series, errors="coerce").astype(float)

        partials.append(partial_series)
        val_series_list.append(value_map[name])
        err_series_list.append(sigma)

    try:
        propagated = propagate_general(val_series_list, err_series_list, partials)
    except PropagationError as exc:
        raise ExpressionEngineError(str(exc)) from exc

    return PropagationResult(values=values, errors=propagated)


def build_derived_dataset(
    source: Dataset,
    expr: str,
    result_name: str,
    *,
    value_column: str,
    error_columns: dict[str, str] | None = None,
    error_column_name: str | None = None,
) -> DerivedDatasetResult:
    """Create a new derived dataset from an expression.

    If ``error_columns`` is supplied, Gaussian uncertainty propagation is also
    computed and saved as a new error column.
    """
    if source.df is None:
        raise ExpressionEngineError("Source dataset has no DataFrame.")
    if not result_name.strip():
        raise ExpressionEngineError("result_name must not be empty.")
    if not value_column.strip():
        raise ExpressionEngineError("value_column must not be empty.")

    out_df = source.df.copy()

    if error_columns:
        prop = evaluate_expression_with_errors(expr, out_df, error_columns)
        out_df[value_column] = prop.values
        err_col_name = error_column_name or f"{value_column}_err"
        out_df[err_col_name] = prop.errors
        derived = Dataset(
            name=result_name,
            path=None,
            df=out_df,
            source_name=source.name,
            derived=True,
            x_col=source.x_col,
            y_col=value_column,
            y_err_col=err_col_name,
            metadata={
                "expression": expr,
                "normalized_expression": normalize_expression(expr).normalized,
                "source_dataset": source.name,
                "error_columns": dict(error_columns),
            },
        )
        return DerivedDatasetResult(
            dataset=derived,
            value_column=value_column,
            error_column=err_col_name,
        )

    values = evaluate_expression(expr, out_df)
    out_df[value_column] = values
    derived = Dataset(
        name=result_name,
        path=None,
        df=out_df,
        source_name=source.name,
        derived=True,
        x_col=source.x_col,
        y_col=value_column,
        metadata={
            "expression": expr,
            "normalized_expression": normalize_expression(expr).normalized,
            "source_dataset": source.name,
        },
    )
    return DerivedDatasetResult(
        dataset=derived,
        value_column=value_column,
        error_column=None,
    )