import stripe
import argparse
import json
from time import sleep
from datetime import datetime, UTC

def load_config(config_path):
    """Load configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            # Set default values if payment_settings is not present
            if 'payment_settings' not in config:
                config['payment_settings'] = {
                    'check_interval': 5,
                    'max_attempts': 6
                }
            return config
    except Exception as e:
        raise Exception(f"Error loading config file: {str(e)}")

def create_payment(amount=1000, currency="chf", card_number="4242424242424242", exp_month=12, exp_year=2025, cvc="123", config=None):
    """Create a payment intent and return its details"""
    if config is None:
        config = {'payment_settings': {'check_interval': 5, 'max_attempts': 6}}

    payment_settings = config['payment_settings']
    check_interval = payment_settings.get('check_interval', 5)
    max_attempts = payment_settings.get('max_attempts', 6)

    # Create PaymentIntent
    pi = stripe.PaymentIntent.create(
        amount=amount,
        currency=currency,
        payment_method_types=["card"],
        payment_method="pm_card_visa",
        confirm=True
    )
    initial_status = pi.status
    print(f"Payment Intent created: {pi.id}")
    print(f"Initial status: {initial_status}")

    # Wait for payment confirmation with status updates
    print("\nWaiting for payment confirmation...")
    attempts = 0
    while attempts < max_attempts:
        print(f"Attempt {attempts + 1}/{max_attempts} - Current status: {pi.status}")

        if pi.status in ['succeeded', 'failed', 'canceled']:
            break

        print(f"\nWaiting for {check_interval} seconds...")
        sleep(check_interval)
        attempts += 1
        pi = stripe.PaymentIntent.retrieve(pi.id)

    print(f"\nFinal status: {pi.status}")

    if pi.status != 'succeeded':
        print("Payment did not succeed")
        return pi

    # Wait for balance transaction to be available
    print("\nWaiting for balance transaction to be available...")
    attempts = 0
    while attempts < max_attempts:
        pi = stripe.PaymentIntent.retrieve(
            pi.id,
            expand=["latest_charge.balance_transaction"]
        )

        if pi.get("latest_charge") and pi["latest_charge"].get("balance_transaction"):
            ch = pi["latest_charge"]
            bt = ch["balance_transaction"]
            if isinstance(bt, dict) and bt.get("amount") is not None:
                break

        print(f"Attempt {attempts + 1}/{max_attempts} - Waiting for balance transaction...")
        sleep(check_interval)
        attempts += 1

    if not pi.get("latest_charge") or not isinstance(pi["latest_charge"].get("balance_transaction"), dict):
        print("No balance transaction available after waiting")
        return pi

    ch = pi["latest_charge"]
    bt = ch["balance_transaction"]
    print("\nTransaction Details:")
    print(f"Gross amount: {bt['amount']} {bt['currency']}")
    print(f"Stripe fee  : {bt['fee']} {bt['currency']}")
    print(f"Net to you  : {bt['net']} {bt['currency']}")
    print("\nFee details:")
    for f in bt["fee_details"]:
        print(f" - {f['type']:>12}  {f['amount']:>5} {f['currency']}  {f.get('description')}")

    return pi

def get_balance():
    """Retrieve and display the current Stripe balance"""
    bal = stripe.Balance.retrieve()
    print("\nCurrent Balance:")
    print("Pending :", [(x['currency'], x['amount']) for x in bal['pending']])
    print("Available:", [(x['currency'], x['amount']) for x in bal['available']])
    return bal

def list_payments(limit=5):
    """List recent payment intents"""
    payments = stripe.PaymentIntent.list(limit=limit)
    print("\nRecent Payments:")
    for payment in payments.data:
        print(f"ID: {payment.id}")
        print(f"Amount: {payment.amount} {payment.currency}")
        print(f"Status: {payment.status}")
        print("-" * 40)
    return payments

def create_customer(email, name, description=None):
    """Create a new Stripe customer"""
    customer = stripe.Customer.create(
        email=email,
        name=name,
        description=description
    )
    print("\nCustomer Created:")
    print(f"ID: {customer.id}")
    print(f"Name: {customer.name}")
    print(f"Email: {customer.email}")
    return customer

def create_refund(payment_intent_id):
    """Create a refund for a payment"""
    # First get the charge ID from the payment intent
    pi = stripe.PaymentIntent.retrieve(payment_intent_id)
    if not pi.latest_charge:
        print("No charge found for this payment intent")
        return None

    refund = stripe.Refund.create(
        charge=pi.latest_charge,
        reason='requested_by_customer'
    )
    print("\nRefund Created:")
    print(f"ID: {refund.id}")
    print(f"Amount: {refund.amount} {refund.currency}")
    print(f"Status: {refund.status}")
    return refund

def list_payment_methods():
    """List available payment method types for the account"""
    capabilities = stripe.Account.retrieve()
    payment_methods = stripe.PaymentMethod.list(
        limit=10,
        type="card"
    )
    print("\nAvailable Payment Methods:")
    for pm in payment_methods:
        if hasattr(pm, 'card'):
            print(f"ID: {pm.id}")
            print(f"Type: {pm.type}")
            print(f"Brand: {pm.card.brand}")
            print(f"Last 4: {pm.card.last4}")
            print("-" * 40)
    return payment_methods

def get_payment_details(payment_intent_id):
    """Get detailed information about a specific payment, including balance transaction"""
    try:
        pi = stripe.PaymentIntent.retrieve(
            payment_intent_id,
            expand=["latest_charge.balance_transaction"]
        )

        if not pi.get("latest_charge"):
            print("No charge found for this payment intent")
            return None

        ch = pi["latest_charge"]
        bt = ch["balance_transaction"]
        ts = bt["available_on"]
        created_ts = ch["created"]

        print("\nPayment Details:")
        print(f"Payment ID: {pi.id}")
        print(f"Status: {pi.status}")
        print(f"Amount: {pi.amount} {pi.currency}")
        print(f"Transaction Date: {datetime.fromtimestamp(created_ts, UTC)} (UTC)")
        print(f"Available on: {datetime.fromtimestamp(ts, UTC)} (UTC)")
        print(f"Balance Transaction Status: {bt['status']}")
        print(f"Gross amount: {bt['amount']} {bt['currency']}")
        print(f"Fee: {bt['fee']} {bt['currency']}")
        print(f"Net amount: {bt['net']} {bt['currency']}")

        return pi
    except stripe.error.StripeError as e:
        print(f"Error retrieving payment details: {str(e)}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Stripe operations')
    parser.add_argument('operation',
                       choices=['set', 'get', 'list-payments', 'create-customer',
                               'create-refund', 'list-methods', 'payment-details'],
                       help='Operation to perform: set (create payment), get (check balance), '
                            'list-payments, create-customer, create-refund, list-methods, or payment-details')
    parser.add_argument('--config', type=str, default='conf/config.json',
                       help='Path to configuration file (default: conf/config.json)')
    parser.add_argument('--amount', type=int, default=1000,
                       help='Amount for the payment in smallest currency unit (e.g., cents). Default: 1000')
    parser.add_argument('--currency', type=str, default='chf',
                       help='Currency for the payment (e.g., chf, usd). Default: chf')
    parser.add_argument('--email', type=str,
                       help='Customer email (required for create-customer)')
    parser.add_argument('--name', type=str,
                       help='Customer name (required for create-customer)')
    parser.add_argument('--payment-id', type=str,
                       help='Payment Intent ID (required for create-refund)')
    parser.add_argument('--limit', type=int, default=5,
                       help='Limit for listing operations. Default: 5')

    args = parser.parse_args()

    # Load configuration and initialize Stripe
    config = load_config(args.config)
    if not config.get('stripe_api_key'):
        parser.error("No Stripe API key found in configuration file")

    stripe.api_key = config['stripe_api_key']

    if args.operation == 'set':
        print(f"Creating a payment of {args.amount} {args.currency}...")
        pi = create_payment(amount=args.amount, currency=args.currency, config=config)
    elif args.operation == 'get':
        print("Retrieving current balance...")
        balance = get_balance()
    elif args.operation == 'list-payments':
        payments = list_payments(limit=args.limit)
    elif args.operation == 'create-customer':
        if not args.email or not args.name:
            parser.error("--email and --name are required for create-customer operation")
        customer = create_customer(args.email, args.name)
    elif args.operation == 'create-refund':
        if not args.payment_id:
            parser.error("--payment-id is required for create-refund operation")
        refund = create_refund(args.payment_id)
    elif args.operation == 'list-methods':
        payment_methods = list_payment_methods()
    elif args.operation == 'payment-details':
        if not args.payment_id:
            parser.error("--payment-id is required for payment-details operation")
        get_payment_details(args.payment_id)
