# FEDECOM Stripe Demo — Web Interface

A Flask-based web interface that wraps the Rust Stripe CLI, providing a visual demonstration of Stripe payment operations without reimplementing the core logic in another language.

---

## Overview

This web application acts as a graphical bridge to the underlying Rust command-line tool. Every action you perform in the UI triggers the corresponding Rust CLI command, and the raw output is displayed in a dedicated **Rust console** panel on the right side of the screen.

---

## Features

### 1. Balance Page (`/`)

The main dashboard for monitoring and adjusting your Stripe test balance.

| Section | Description |
|---------|-------------|
| **Live Overview** | Displays current **Available** and **Pending** funds in CHF. Auto-refreshes every 15 seconds. Shows the timestamp of the last balance request. |
| **Refresh Balance** | Manual button to request the latest balance from Stripe. The corresponding CLI output appears in the Rust console. |
| **Collect Test Charge** | Create a new payment intent by entering an amount in CHF. Currency is fixed to CHF. |
| **Recent Payments** | A quick-glance table of the three most recent payment intents with ID, status, date, amount, and fee. Links to the full Payments page. |

### 2. Payments Page (`/payments`)

A dedicated view for browsing and inspecting payment intents.

| Section | Description |
|---------|-------------|
| **Ledger Log** | Paginated list of payment intents showing ID, status, and transaction date. Each row has a **Details** button. |
| **Payment Detail** | When a payment is selected, a card displays full metadata: status, amount, transaction date, availability date, gross/fee/net breakdown, and balance status. |

### 3. Rust Console Panel

A side panel visible on every page that displays:

- **Label** — A human-readable description of the last executed command (e.g., *Refresh balance*, *Create payment (10.00 CHF)*, *Payment details (pi_xxx)*).
- **Timestamp** — When the command was executed.
- **stdout** — The standard output from the Rust CLI.
- **stderr** — Any error output (shown only when present).

> **Note:** Automatic background refreshes (e.g., the 15-second balance update) do *not* overwrite the console. Only manual actions update the console panel.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Flask Web App                             │
│  ┌────────────────┐   ┌────────────────┐   ┌─────────────────┐  │
│  │  Templates     │   │  Routes        │   │  Runner         │  │
│  │  (Jinja2 HTML) │◄──│  (app.py)      │──►│  (runner.py)    │  │
│  └────────────────┘   └────────────────┘   └────────┬────────┘  │
│                                                      │           │
│                                                      ▼           │
│                                            ┌─────────────────┐  │
│                                            │  Rust CLI       │  │
│                                            │  (subprocess)   │  │
│                                            └─────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Key Components

| File | Purpose |
|------|---------|
| `app.py` | Flask application entry point. Defines routes, parses CLI output, and renders templates. |
| `runner.py` | `RustStripeRunner` class that locates the Rust binary (or falls back to `cargo run`) and executes commands via `subprocess`. |
| `templates/layout.html` | Base template with header, navigation, flash messages, and the console panel. |
| `templates/dashboard.html` | Balance page template. |
| `templates/payments.html` | Payments list and detail template. |
| `static/styles.css` | Custom CSS following the FEDECOM brand palette. |

---

## Configuration

The application reads configuration from environment variables and sensible defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_SECRET_KEY` | `dev-secret` | Secret key for Flask sessions and flash messages. |
| `DEMO_USER_NAME` | `SUPSI demo user` | Display name shown in the top-right user pill. |
| `DEMO_USER_ROLE` | `Test Merchant` | (Currently hidden) Role label. |
| `STRIPE_TESTBED_BIN` | *(auto-detect)* | Path to a pre-compiled Rust binary. If unset, the runner looks in `rust/target/release/` or `rust/target/debug/`, or falls back to `cargo run`. |

The Stripe API key and other Rust-side settings are read from `rust/conf/config.json`.

---

## Running the Application

### Prerequisites

- Python 3.10+
- Flask 3.0+ (install via `pip install -r ../python/requirements.txt`)
- Rust toolchain (if using `cargo run`) **or** a pre-compiled `stripe-testbed` binary

### Quick Start

```bash
# Activate virtual environment
source .venv/bin/activate

# Install Python dependencies
pip install -r python/requirements.txt

# Set PYTHONPATH to include the project root
export PYTHONPATH="$(pwd):$PYTHONPATH"

# Run the development server
python -m flask --app web.app run --debug
```

The server starts at **http://127.0.0.1:5000**.

---

## CLI Commands Exposed

The web interface wraps these Rust CLI commands:

| UI Action | CLI Command | Description |
|-----------|-------------|-------------|
| Refresh balance | `get` | Fetches current pending/available balance. |
| Create payment | `set --amount <cents> --currency chf` | Creates and confirms a PaymentIntent. |
| List payments | `list-payments --limit <n>` | Lists recent PaymentIntents. |
| Payment details | `payment-details --payment-id <id>` | Retrieves full metadata for a single PaymentIntent. |
| Create refund | `create-refund --payment-id <id>` | Initiates a refund (route exists but UI button removed). |

---

## Data Flow

1. **User clicks an action** (e.g., *Refresh balance*).
2. Flask route calls `execute_cli()` with the appropriate command and arguments.
3. `RustStripeRunner.run()` spawns the Rust CLI via `subprocess`.
4. CLI output is captured and parsed into Python dataclasses (`BalanceRow`, `PaymentRow`, `PaymentDetail`).
5. Parsed data is passed to Jinja2 templates for rendering.
6. Raw CLI output is stored in `LAST_CONSOLE` and displayed in the side panel.

---

## Styling

The UI follows the **FEDECOM brand palette** extracted from `demo_example_template.odp`:

- **Background:** Lavender (`#e6e6fa`)
- **Accent (primary):** Coral (`#ff6f61`)
- **Accent (secondary):** Purple (`#6a0dad`)
- **Text:** Near-black (`#1a1a2e`)
- **Font stack:** Century Gothic, Futura, sans-serif

Cards, buttons, and tables are styled with consistent padding, subtle shadows, and hover states to provide a clean, modern demo experience.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `No module named flask` | Activate the virtual environment and run `pip install -r python/requirements.txt`. |
| CLI times out | Increase `timeout` in `RustStripeRunner` or check Stripe API connectivity. |
| Balance shows 0 | Verify `rust/conf/config.json` contains valid Stripe test keys. |
| Console not updating | Ensure you're performing a *manual* action; background refreshes don't log to the console. |

---

## License

This demo is provided for internal testing and educational purposes. See the root `LICENSE` file for terms.

