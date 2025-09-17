# Stripe Testbed (Python and Rust)

This repository contains two small CLI applications to experiment with Stripe's API for testing and learning purposes:

- python/: A Python CLI covering common Stripe operations
- rust/: A Rust CLI that mirrors the Python tool's features

Both apps focus on safe test-mode workflows and should be used with Stripe test API keys only.

## What they do

- Create payments (PaymentIntents) with custom amount and currency
- Check account balance (pending and available)
- List recent payments
- Create customers
- Create refunds
- List card payment methods
- Show detailed payment information including the expanded latest charge and balance transaction (gross, fee, net, availability date)

## Configuration

Each app reads a JSON config file with your Stripe test API key and optional polling settings:

- Default location: conf/config.json (relative to each app folder)
- Example file: conf/config.json.example

Key fields:
- stripe_api_key: Your Stripe test secret key (sk_test_...)
- payment_settings.check_interval: Seconds between status checks (optional)
- payment_settings.max_attempts: Max polling attempts (optional)

## Quick start

Python app:
- cd python
- Install deps: pip install -r requirements.txt
- Run help: python stripe_testbed.py --help
- Example: python stripe_testbed.py get

Rust app:
- cd rust
- Build: cargo build --release
- Run help: cargo run -- --help
- Example: cargo run -- get

You can pass a custom config path with --config /path/to/config.json in both apps.

## Full usage

See detailed guides with examples in:
- python/README.md
- rust/README.md

## Notes

- Use Stripe test keys and test payment methods only (e.g., pm_card_visa).
- Amounts are integers in the smallest currency unit (e.g., CHF centimes, USD cents).
