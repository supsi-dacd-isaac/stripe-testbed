# Stripe Testbed (Rust)

A Rust CLI for interacting with the Stripe API, mirroring the Python testbed and supporting common payment operations for testing and exploration.

## Features

- Create payments (PaymentIntents) with configurable amount and currency
- Check current balance (pending and available)
- List recent payments
- Create customers
- Create refunds
- List card payment methods
- Retrieve detailed payment information (including balance transactions)

## Requirements

- Rust toolchain (stable) with Cargo
- Internet access
- Stripe test API key (starts with `sk_test_...`)

## Installation

1. Ensure Rust is installed:
   - https://www.rust-lang.org/tools/install
2. From the repo root, go to the Rust project:
   ```bash
   cd rust
   ```
3. Install dependencies and build:
   ```bash
   cargo build --release
   ```

## Configuration

1. Copy the example config and add your Stripe test API key:
   ```bash
   cp conf/config.json.example conf/config.json
   ```
2. Edit `conf/config.json`:
   ```json
   {
     "stripe_api_key": "sk_test_your_key_here",
     "payment_settings": {
       "check_interval": 5,
       "max_attempts": 6
     }
   }
   ```
3. Optional: You can adjust `payment_settings` to control polling intervals and retry attempts.

You can also pass a custom config path at runtime with `--config /path/to/config.json`.

## Usage

Run the CLI directly with Cargo during development:
```bash
cargo run -- --help
```

Common commands:

- Check balance:
  ```bash
  cargo run -- get
  ```
- List recent payments (limit N):
  ```bash
  cargo run -- list-payments --limit 5
  ```
- Create a payment (amount in smallest currency unit, e.g., cents):
  ```bash
  cargo run -- set --amount 1000 --currency chf
  ```
- Create a customer:
  ```bash
  cargo run -- create-customer --email "customer@example.com" --name "John Doe" --description "Test customer"
  ```
- Create a refund for a payment intent:
  ```bash
  cargo run -- create-refund --payment-id pi_123456789
  ```
- List card payment methods:
  ```bash
  cargo run -- list-methods
  ```
- Payment details:
  ```bash
  cargo run -- payment-details --payment-id pi_123456789
  ```

Use a custom configuration file:
```bash
cargo run -- --config conf/config.json get
```

## Running the compiled binary

After building with `cargo build --release`, you can run the binary directly:
```bash
./target/release/stripe-testbed --help
./target/release/stripe-testbed get
```

## Notes

- Use Stripe test keys and test payment methods only (e.g., automatically confirmed `pm_card_visa`).
- Amounts are in Stripe's smallest currency unit (e.g., CHF/centime, USD/cent) as integers.
- Some endpoints may require specific account setup or parameters (e.g., listing payment methods might require a customer on some accounts).

## Troubleshooting

- 401 Unauthorized / Invalid API Key: Verify the `stripe_api_key` in your config.
- Network/TLS errors: Check connectivity, system time, and firewall/proxy settings.
- 429 Rate Limited: Reduce request frequency or increase `check_interval`.
- Payment not moving to `succeeded`: Check account capabilities, payment method eligibility, and currency.

## License

See the repository's LICENSE file.

