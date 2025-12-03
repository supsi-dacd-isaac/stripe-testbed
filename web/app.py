from __future__ import annotations

import ast
import re
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from flask import Flask, flash, redirect, render_template, request, url_for

from .runner import CommandResult, RustStripeRunner

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_STR = str(PROJECT_ROOT)
if PROJECT_STR not in sys.path:
    sys.path.insert(0, PROJECT_STR)
pythonpath = os.environ.get("PYTHONPATH")
if pythonpath:
    if PROJECT_STR not in pythonpath.split(":"):
        os.environ["PYTHONPATH"] = f"{PROJECT_STR}:{pythonpath}"
else:
    os.environ["PYTHONPATH"] = PROJECT_STR

RUST_DIR = PROJECT_ROOT / "rust"
CONFIG_PATH = (RUST_DIR / "conf" / "config.json").resolve()
BRAND_NAME = "FEDECOM Stripe Demo"

USER_PROFILE = {
    "name": os.environ.get("DEMO_USER_NAME", "SUPSI demo user"),
    "role": os.environ.get("DEMO_USER_ROLE", "Test Merchant"),
    "config_path": str(CONFIG_PATH),
}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret")

runner = RustStripeRunner(RUST_DIR)
LAST_CONSOLE: dict[str, dict[str, str | int | list[str]]] = {}


class CommandExecutionError(RuntimeError):
    """Raised when the Rust CLI command cannot complete successfully."""


@dataclass
class BalanceRow:
    currency: str
    amount_minor: int
    amount_major: float


@dataclass
class PaymentRow:
    payment_id: str
    amount_major: float
    currency: str
    status: str
    created_at: str
    fee_major: float | None = None


@dataclass
class PaymentDetail:
    payment_id: str
    status: str
    amount_major: float
    currency: str
    transaction_date: str
    available_on: str
    balance_status: str
    gross_major: float
    fee_major: float
    net_major: float


def cents_to_units(amount: int | float) -> float:
    return round(int(amount) / 100.0, 2)


def format_currency(value: float) -> str:
    return f"{value:,.2f}"


app.jinja_env.filters["currency"] = format_currency


@app.context_processor
def inject_globals() -> dict[str, Any]:
    return {
        "brand_name": BRAND_NAME,
        "user_profile": USER_PROFILE,
    }


def execute_cli(
    command: str,
    *,
    extra: Sequence[str] | None = None,
    record_console: bool = True,
    context: str | None = None,
    label: str | None = None,
) -> CommandResult:
    result = runner.run(
        command,
        extra_args=extra,
        config_path=CONFIG_PATH,
    )
    global LAST_CONSOLE
    if record_console and context:
        LAST_CONSOLE[context] = {
            "command": result.command_line,
            "label": label or command,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "stdout": result.stdout.splitlines(),
            "stderr": result.stderr.splitlines(),
            "returncode": result.returncode,
        }
    if result.error:
        raise CommandExecutionError(result.error)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise CommandExecutionError(stderr or f"{command} exited with code {result.returncode}")
    return result


def parse_amount_list(raw: str) -> list[BalanceRow]:
    raw = raw.strip()
    if not raw:
        return []
    rows: list[BalanceRow] = []

    # First try to read literal JSON-like structures (older fallback)
    try:
        parsed = ast.literal_eval(raw)
        iterable = (
            parsed if isinstance(parsed, (list, tuple)) else [parsed]  # type: ignore[list-item]
        )
        for entry in iterable:
            if isinstance(entry, (list, tuple)) and len(entry) == 2:
                currency, amount = entry
                rows.append(
                    BalanceRow(
                        currency=str(currency).upper(),
                        amount_minor=int(amount),
                        amount_major=cents_to_units(int(amount)),
                    )
                )
    except (ValueError, SyntaxError, TypeError):
        rows = []

    if rows:
        return rows

    # Fallback: parse CLI tuples like "(chf,123), (usd,0)"
    pattern = re.compile(r"\(([a-zA-Z0-9_]+)\s*,\s*(-?\d+)\)")
    matches = pattern.findall(raw)
    for currency, amount in matches:
        rows.append(
            BalanceRow(
                currency=currency.upper(),
                amount_minor=int(amount),
                amount_major=cents_to_units(int(amount)),
            )
        )
    return rows


def parse_balance(stdout: str) -> dict[str, Any]:
    pending: list[BalanceRow] = []
    available: list[BalanceRow] = []
    for line in stdout.splitlines():
        if line.startswith("Pending"):
            pending = parse_amount_list(line.split(":", 1)[1])
        elif line.startswith("Available"):
            available = parse_amount_list(line.split(":", 1)[1])

    combined: dict[str, dict[str, float]] = {}
    for row in pending:
        combined.setdefault(row.currency, {"pending": 0.0, "available": 0.0})
        combined[row.currency]["pending"] = row.amount_major
    for row in available:
        combined.setdefault(row.currency, {"pending": 0.0, "available": 0.0})
        combined[row.currency]["available"] = row.amount_major

    rows = [
        {
            "currency": currency,
            "pending": values["pending"],
            "available": values["available"],
        }
        for currency, values in combined.items()
    ]
    rows.sort(key=lambda item: item["currency"])

    return {
        "pending": pending,
        "available": available,
        "rows": rows,
        "pending_total": sum(row.amount_major for row in pending),
        "available_total": sum(row.amount_major for row in available),
    }


def parse_payments(stdout: str) -> list[PaymentRow]:
    payments: list[PaymentRow] = []
    current: dict[str, Any] = {}
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("ID:"):
            if current:
                payments.append(_build_payment_row(current))
                current = {}
            current["payment_id"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Amount:"):
            segment = stripped.split(":", 1)[1].strip()
            parts = segment.split()
            if len(parts) >= 2:
                current["amount_minor"] = parts[0]
                current["currency"] = parts[1]
        elif stripped.startswith("Status:"):
            current["status"] = stripped.split(":", 1)[1].strip()
        elif stripped.lower().startswith("created:"):
            current["created_at"] = stripped.split(":", 1)[1].strip()
    if current:
        payments.append(_build_payment_row(current))
    return [row for row in payments if row.payment_id]


def _build_payment_row(data: dict[str, Any]) -> PaymentRow:
    amount_minor = int(data.get("amount_minor", 0))
    return PaymentRow(
        payment_id=str(data.get("payment_id", "")),
        amount_major=cents_to_units(amount_minor),
        currency=str(data.get("currency", "CHF")).upper(),
        status=str(data.get("status", "unknown")).title(),
        created_at=str(data.get("created_at", "")),
    )


def parse_payment_details(stdout: str) -> PaymentDetail | None:
    values: dict[str, str] = {}
    for line in stdout.splitlines():
        stripped = line.strip()
        if ":" in stripped:
            key, val = stripped.split(":", 1)
            values[key.strip().lower()] = val.strip()
    if "payment id" not in values:
        return None
    amount_minor = _extract_minor(values.get("amount", "0"))
    gross_minor = _extract_minor(values.get("gross amount", "0"))
    fee_minor = _extract_minor(values.get("fee", "0"))
    net_minor = _extract_minor(values.get("net amount", "0"))

    def fmt(ts: str) -> str:
        return ts.replace("+00:00", "").replace("(UTC)", "").strip()

    return PaymentDetail(
        payment_id=values.get("payment id", ""),
        status=values.get("status", "").title(),
        amount_major=cents_to_units(amount_minor),
        currency=_extract_currency(values.get("amount", "")),
        transaction_date=fmt(values.get("transaction date", "")),
        available_on=fmt(values.get("available on", "")),
        balance_status=values.get("balance transaction status", "").title(),
        gross_major=cents_to_units(gross_minor),
        fee_major=cents_to_units(fee_minor),
        net_major=cents_to_units(net_minor),
    )


def _extract_minor(raw: str) -> int:
    token = raw.split()[0] if raw else "0"
    try:
        return int(token)
    except ValueError:
        return 0


def _extract_currency(raw: str, default: str = "CHF") -> str:
    if not raw:
        return default
    parts = raw.split()
    if len(parts) >= 2:
        return parts[-1].upper()
    return default


def parse_payment_creation(stdout: str) -> dict[str, str | None]:
    payment_id = None
    final_status = None
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("payment intent id"):
            payment_id = stripped.split(":", 1)[1].strip()
        elif stripped.lower().startswith("final status"):
            final_status = stripped.split(":", 1)[1].strip()
    return {"payment_id": payment_id, "final_status": final_status}


def dashboard_balance() -> tuple[dict[str, Any] | None, str | None, datetime]:
    requested_at = datetime.now(timezone.utc)
    try:
        result = execute_cli(
            "get",
            record_console=False,
        )
        return parse_balance(result.stdout), None, requested_at
    except CommandExecutionError as exc:
        return None, str(exc), requested_at


def hydrate_payment_metadata(payments: list[PaymentRow]) -> None:
    for payment in payments:
        detail, _ = payment_details(payment.payment_id)
        if detail:
            payment.created_at = payment.created_at or detail.transaction_date
            payment.fee_major = detail.fee_major


def recent_payments(
    limit: int = 8,
    *,
    record_console: bool = False,
) -> tuple[list[PaymentRow], str | None]:
    try:
        result = execute_cli(
            "list-payments",
            extra=["--limit", str(limit)],
            record_console=record_console,
            label="List payment intents" if record_console else None,
        )
        payments = parse_payments(result.stdout)
        hydrate_payment_metadata(payments)
        return payments, None
    except CommandExecutionError as exc:
        return [], str(exc)


def payment_details(payment_id: str) -> tuple[PaymentDetail | None, str | None]:
    try:
        result = execute_cli(
            "payment-details",
            extra=["--payment-id", payment_id],
            label=f"Payment details ({payment_id})",
            context="payments",
        )
        return parse_payment_details(result.stdout), None
    except CommandExecutionError as exc:
        return None, str(exc)


@app.route("/")
@app.route("/", methods=["GET", "POST"])
def dashboard() -> str:
    if request.method == "POST" and request.form.get("action") == "refresh-balance":
        try:
            execute_cli("get", context="dashboard", label="Refresh balance")
            flash("Balance refreshed.", "success")
        except CommandExecutionError as exc:
            flash(str(exc), "error")
        return redirect(url_for("dashboard"))

    balance, balance_error, balance_timestamp = dashboard_balance()
    payments, _ = recent_payments(limit=3, record_console=False)
    return render_template(
        "dashboard.html",
        active_nav="dashboard",
        balance=balance,
        balance_error=balance_error,
        spotlight_payments=payments,
        balance_timestamp=balance_timestamp,
        auto_refresh_seconds=15,
        console=LAST_CONSOLE.get("dashboard"),
    )


@app.route("/payments")
def payments_view() -> str:
    limit = request.args.get("limit", default=8, type=int)
    selected_id = request.args.get("payment_id")
    payments, list_error = recent_payments(limit=limit, record_console=False)
    detail, detail_error = (None, None)
    if selected_id:
        detail, detail_error = payment_details(selected_id)
        if detail is None and not detail_error:
            detail_error = "Unable to parse payment details."
    return render_template(
        "payments.html",
        active_nav="payments",
        payments=payments,
        list_error=list_error,
        detail=detail,
        detail_error=detail_error,
        console=LAST_CONSOLE.get("payments"),
    )


@app.post("/actions/create-payment")
def create_payment_action() -> str:
    amount_chf = request.form.get("amount_chf", "").replace(",", ".").strip()
    try:
        amount_major = float(amount_chf)
    except ValueError:
        flash("Enter a valid amount in CHF (e.g., 12.50).", "error")
        return redirect(url_for("dashboard"))

    if amount_major <= 0:
        flash("Amount must be greater than zero.", "error")
        return redirect(url_for("dashboard"))

    amount_minor = int(round(amount_major * 100))

    try:
        result = execute_cli(
            "set",
            extra=["--amount", str(amount_minor), "--currency", "chf"],
            label=f"Create payment ({amount_major:.2f} CHF)",
            context="dashboard",
        )
        summary = parse_payment_creation(result.stdout)
        if summary["payment_id"]:
            flash(
                (
                    f"Payment {summary['payment_id']} completed with status "
                    f"{summary['final_status'] or 'unknown'}"
                ),
                "success",
            )
        else:
            flash("Payment created via Rust CLI.", "success")
    except CommandExecutionError as exc:
        flash(str(exc), "error")
    return redirect(url_for("dashboard"))


@app.post("/actions/create-refund")
def create_refund_action() -> str:
    payment_id = request.form.get("payment_id", "").strip()
    if not payment_id:
        flash("Provide a payment intent id to refund.", "error")
        return redirect(url_for("dashboard"))
    try:
        result = execute_cli(
            "create-refund",
            extra=["--payment-id", payment_id],
            label=f"Create refund ({payment_id})",
            context="payments",
        )
        flash(f"Refund requested for {payment_id}.", "success")
    except CommandExecutionError as exc:
        flash(str(exc), "error")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)

