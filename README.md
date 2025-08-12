# Stripe Testbed Integration Tool

A comprehensive Python tool for interacting with Stripe API, providing various operations for payment processing and account management.

## Features

- Create payments with custom amount and currency
- Check account balance (pending and available)
- List recent payments/transactions
- Create and manage customers
- Process refunds
- List available payment methods

## Requirements

- Python 3.x
- stripe
- argparse

See `requirements.txt` for specific versions.

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your configuration:
   - Copy `conf/config.json.example` to `conf/config.json` (if not exists)
   - Add your Stripe API key to the configuration file:
     ```json
     {
         "stripe_api_key": "your_stripe_api_key_here"
     }
     ```

## Usage

The script supports various operations through command-line arguments:

### Configuration
You can specify a custom configuration file path:
```bash
python stripe_testbed.py get --config /path/to/your/config.json
```

### Create a Payment
```bash
python stripe_testbed.py set --amount 1000 --currency chf
```

### Check Balance
```bash
python stripe_testbed.py get
```

### List Recent Payments
```bash
python stripe_testbed.py list-payments --limit 5
```

### Create a Customer
```bash
python stripe_testbed.py create-customer --email "customer@example.com" --name "John Doe"
```

### Create a Refund
```bash
python stripe_testbed.py create-refund --payment-id pi_123456789
```

### List Payment Methods
```bash
python stripe_testbed.py list-methods
```

## Arguments

- `operation`: Required. Choose from: set, get, list-payments, create-customer, create-refund, list-methods
- `--amount`: Payment amount in smallest currency unit (e.g., cents). Default: 1000
- `--currency`: Currency code (e.g., chf, usd). Default: chf
- `--email`: Customer email (required for create-customer)
- `--name`: Customer name (required for create-customer)
- `--payment-id`: Payment Intent ID (required for create-refund)
- `--limit`: Number of items to list (for listing operations). Default: 5

## Note

This is a testing tool. Make sure to use test API keys and not production keys.
