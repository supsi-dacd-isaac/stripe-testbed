# Stripe Testbed Integration Tool

A comprehensive Python tool for interacting with Stripe API, providing various operations for payment processing and account management.

## Features

- Create payments with custom amount and currency
- Check account balance (pending and available)
- List recent payments/transactions
- Create and manage customers
- Process refunds
- List available payment methods
- View detailed payment information including balance transactions

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
   - Add your Stripe API key and optional payment settings to the configuration file:
     ```json
     {
         "stripe_api_key": "your_stripe_api_key_here",
         "payment_settings": {
             "confirmation_wait_time": 30,
             "check_interval": 5,
             "max_attempts": 6
         }
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

### Get Payment Details
```bash
python stripe_testbed.py payment-details --payment-id pi_123456789
```
This will show detailed information about a specific payment, including:
- Payment status
- Amount and currency
- Available date (UTC)
- Balance transaction status
- Gross amount, fees, and net amount
- Detailed fee breakdown

## Arguments

- `operation`: Required. Choose from: set, get, list-payments, create-customer, create-refund, list-methods, payment-details
- `--amount`: Payment amount in smallest currency unit (e.g., cents). Default: 1000
- `--currency`: Currency code (e.g., chf, usd). Default: chf
- `--email`: Customer email (required for create-customer)
- `--name`: Customer name (required for create-customer)
- `--payment-id`: Payment Intent ID (required for create-refund)
- `--limit`: Number of items to list (for listing operations). Default: 5

## Configuration

### Payment Settings
The tool supports configurable retry settings for payment processing:

- `confirmation_wait_time`: Total time to wait for confirmation (default: 30 seconds)
- `check_interval`: Time between status checks (default: 5 seconds)
- `max_attempts`: Maximum number of retry attempts (default: 6)

These settings can be adjusted in your `config.json` file to optimize for your specific needs.

## Note

This is a testing tool. Make sure to use test API keys and not production keys.
