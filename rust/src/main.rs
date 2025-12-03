use chrono::{DateTime, TimeZone, Utc};
use clap::{Parser, Subcommand};
use colored::*;
use serde::Deserialize;
use serde_json::Value;
use std::{fs, path::PathBuf};

#[derive(Debug, Deserialize)]
struct PaymentSettings {
    #[serde(default = "default_check_interval")]
    check_interval: u64,
    #[serde(default = "default_max_attempts")]
    max_attempts: u32,
}
fn default_check_interval() -> u64 {
    5
}
fn default_max_attempts() -> u32 {
    6
}

#[derive(Debug, Deserialize)]
struct Config {
    stripe_api_key: String,
    #[serde(default)]
    payment_settings: Option<PaymentSettings>,
}

#[derive(Parser, Debug)]
#[command(name = "stripe-testbed")]
#[command(about = "Stripe operations testbed (Rust)")]
struct Cli {
    /// Path to configuration file (default: conf/config.json)
    #[arg(long, default_value = "conf/config.json")]
    config: PathBuf,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Create a payment (PaymentIntent)
    Set {
        /// Amount in smallest currency unit (e.g., cents)
        #[arg(long, default_value_t = 1000)]
        amount: i64,
        /// Currency code e.g., chf, usd
        #[arg(long, default_value = "chf")]
        currency: String,
    },
    /// Retrieve current balance
    Get,
    /// List recent payment intents
    ListPayments {
        /// Max number of items
        #[arg(long, default_value_t = 5)]
        limit: u32,
    },
    /// Create a new customer
    CreateCustomer {
        #[arg(long)]
        email: String,
        #[arg(long)]
        name: String,
        #[arg(long)]
        description: Option<String>,
    },
    /// Create a refund for a payment intent
    CreateRefund {
        #[arg(long, value_name = "pi_...")]
        payment_id: String,
    },
    /// List available card payment methods (may require a customer on some accounts)
    ListMethods,
    /// Show details for a specific payment
    PaymentDetails {
        #[arg(long, value_name = "pi_...")]
        payment_id: String,
    },
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();
    let config = load_config(&cli.config)?;
    let key = config.stripe_api_key;
    let settings = config.payment_settings.unwrap_or(PaymentSettings {
        check_interval: default_check_interval(),
        max_attempts: default_max_attempts(),
    });

    match cli.command {
        Commands::Set { amount, currency } => {
            println!(
                "{}",
                format!("Creating a payment of {} {}...", amount, currency).bold()
            );
            let pi = create_payment(&key, amount, &currency, &settings).await?;
            print_disclaimer();
            if let Some(id) = pi.get("id").and_then(|v| v.as_str()) {
                println!("\nPayment Intent id: {}", id);
            }
        }
        Commands::Get => {
            println!("Retrieving current balance...");
            get_balance(&key).await?;
            print_disclaimer();
        }
        Commands::ListPayments { limit } => {
            list_payments(&key, limit).await?;
            print_disclaimer();
        }
        Commands::CreateCustomer {
            email,
            name,
            description,
        } => {
            create_customer(&key, &email, &name, description.as_deref()).await?;
            print_disclaimer();
        }
        Commands::CreateRefund { payment_id } => {
            create_refund(&key, &payment_id).await?;
            print_disclaimer();
        }
        Commands::ListMethods => {
            list_payment_methods(&key).await?;
            print_disclaimer();
        }
        Commands::PaymentDetails { payment_id } => {
            payment_details(&key, &payment_id).await?;
            print_disclaimer();
        }
    }

    Ok(())
}

fn load_config(path: &PathBuf) -> anyhow::Result<Config> {
    let s = fs::read_to_string(path)?;
    let mut cfg: Value = serde_json::from_str(&s)?;

    // Backward-compat: ensure payment_settings default exists for deserialization
    if !cfg.get("payment_settings").is_some() {
        cfg["payment_settings"] = serde_json::json!({
            "check_interval": 5,
            "max_attempts": 6
        });
    }

    let cfg: Config = serde_json::from_value(cfg)?;
    Ok(cfg)
}

fn client(_key: &str) -> reqwest::Client {
    reqwest::Client::builder()
        .user_agent("stripe-testbed-rust/0.1")
        .build()
        .expect("client")
}

async fn post_form(key: &str, path: &str, form: &[(String, String)]) -> anyhow::Result<Value> {
    let url = format!("https://api.stripe.com/v1{}", path);
    let resp = client(key)
        .post(&url)
        .basic_auth(key, Some(""))
        .form(&form)
        .send()
        .await?;
    let status = resp.status();
    let text = resp.text().await?;
    if !status.is_success() {
        anyhow::bail!("Stripe error {}: {}", status, text);
    }
    let v: Value = serde_json::from_str(&text)?;
    Ok(v)
}

async fn get_query(key: &str, path: &str, query: &[(String, String)]) -> anyhow::Result<Value> {
    let url = format!("https://api.stripe.com/v1{}", path);
    let resp = client(key)
        .get(&url)
        .basic_auth(key, Some(""))
        .query(&query)
        .send()
        .await?;
    let status = resp.status();
    let text = resp.text().await?;
    if !status.is_success() {
        anyhow::bail!("Stripe error {}: {}", status, text);
    }
    let v: Value = serde_json::from_str(&text)?;
    Ok(v)
}

async fn retrieve(key: &str, path: &str, query: &[(String, String)]) -> anyhow::Result<Value> {
    get_query(key, path, query).await
}

async fn create_payment(
    key: &str,
    amount: i64,
    currency: &str,
    settings: &PaymentSettings,
) -> anyhow::Result<Value> {
    // Create PaymentIntent
    let mut form = vec![
        ("amount".to_string(), amount.to_string()),
        ("currency".to_string(), currency.to_string()),
        ("confirm".to_string(), "true".to_string()),
        ("payment_method".to_string(), "pm_card_visa".to_string()),
    ];
    // payment_method_types[]=card
    form.push(("payment_method_types[]".to_string(), "card".to_string()));

    let mut pi = post_form(key, "/payment_intents", &form).await?;

    let initial_status = pi
        .get("status")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown");
    let pi_id: String = pi
        .get("id")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    println!("Payment Intent created: {}", pi_id);
    println!("Initial status: {}", initial_status);

    println!("\nWaiting for payment confirmation...");
    let mut attempts = 0u32;
    while attempts < settings.max_attempts {
        let status = pi
            .get("status")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown");
        println!(
            "Attempt {}/{} - Current status: {}",
            attempts + 1,
            settings.max_attempts,
            status
        );
        if matches!(status, "succeeded" | "failed" | "canceled") {
            break;
        }
        println!("\nWaiting for {} seconds...", settings.check_interval);
        tokio::time::sleep(std::time::Duration::from_secs(settings.check_interval)).await;
        attempts += 1;
        pi = retrieve(key, &format!("/payment_intents/{}", pi_id), &[]).await?;
    }

    let final_status = pi
        .get("status")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown");
    println!("\nFinal status: {}", final_status);
    if final_status != "succeeded" {
        println!("Payment did not succeed");
        return Ok(pi);
    }

    // Wait for balance transaction to be available
    println!("\nWaiting for balance transaction to be available...");
    let mut attempts = 0u32;
    loop {
        let expanded = retrieve(
            key,
            &format!("/payment_intents/{}", pi_id),
            &[(
                "expand[]".to_string(),
                "latest_charge.balance_transaction".to_string(),
            )],
        )
        .await?;
        let latest_charge = expanded.get("latest_charge");
        let bt = latest_charge.and_then(|lc| lc.get("balance_transaction"));
        let ok = bt
            .and_then(|b| b.get("amount"))
            .and_then(|a| a.as_i64())
            .is_some();
        if ok {
            print_transaction_details(&expanded);
            break;
        }
        attempts += 1;
        if attempts >= settings.max_attempts {
            println!("No balance transaction available after waiting");
            break;
        }
        println!(
            "Attempt {}/{} - Waiting for balance transaction...",
            attempts, settings.max_attempts
        );
        tokio::time::sleep(std::time::Duration::from_secs(settings.check_interval)).await;
    }

    Ok(pi)
}

fn print_transaction_details(pi: &Value) {
    if let Some(ch) = pi.get("latest_charge") {
        if let Some(bt) = ch.get("balance_transaction") {
            let gross = bt.get("amount").and_then(|v| v.as_i64()).unwrap_or(0);
            let fee = bt.get("fee").and_then(|v| v.as_i64()).unwrap_or(0);
            let net = bt.get("net").and_then(|v| v.as_i64()).unwrap_or(0);
            let cur = bt.get("currency").and_then(|v| v.as_str()).unwrap_or("");
            println!("\nTransaction Details:");
            println!("Gross amount: {} {}", gross, cur);
            println!("Stripe fee  : {} {}", fee, cur);
            println!("Net to you  : {} {}", net, cur);
            if let Some(arr) = bt.get("fee_details").and_then(|v| v.as_array()) {
                println!("\nFee details:");
                for f in arr {
                    let t = f.get("type").and_then(|v| v.as_str()).unwrap_or("");
                    let a = f.get("amount").and_then(|v| v.as_i64()).unwrap_or(0);
                    let c = f.get("currency").and_then(|v| v.as_str()).unwrap_or("");
                    let d = f.get("description").and_then(|v| v.as_str()).unwrap_or("");
                    println!(" - {:>12}  {:>5} {}  {}", t, a, c, d);
                }
            }
        }
    }
}

async fn get_balance(key: &str) -> anyhow::Result<()> {
    let bal = retrieve(key, "/balance", &[]).await?;
    println!("\nCurrent Balance:");
    let pending = bal
        .get("pending")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let available = bal
        .get("available")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let p: Vec<String> = pending
        .iter()
        .map(|x| {
            format!(
                "({},{})",
                x.get("currency").and_then(|v| v.as_str()).unwrap_or(""),
                x.get("amount").and_then(|v| v.as_i64()).unwrap_or(0)
            )
        })
        .collect();
    let a: Vec<String> = available
        .iter()
        .map(|x| {
            format!(
                "({},{})",
                x.get("currency").and_then(|v| v.as_str()).unwrap_or(""),
                x.get("amount").and_then(|v| v.as_i64()).unwrap_or(0)
            )
        })
        .collect();
    println!("Pending : {}", p.join(", "));
    println!("Available: {}", a.join(", "));
    Ok(())
}

async fn list_payments(key: &str, limit: u32) -> anyhow::Result<()> {
    let res = retrieve(
        key,
        "/payment_intents",
        &[("limit".to_string(), limit.to_string())],
    )
    .await?;
    println!("\nRecent Payments:");
    if let Some(arr) = res.get("data").and_then(|v| v.as_array()) {
        for p in arr {
            let id = p.get("id").and_then(|v| v.as_str()).unwrap_or("");
            let amt = p.get("amount").and_then(|v| v.as_i64()).unwrap_or(0);
            let cur = p.get("currency").and_then(|v| v.as_str()).unwrap_or("");
            let st = p.get("status").and_then(|v| v.as_str()).unwrap_or("");
            let created_ts = p.get("created").and_then(|v| v.as_i64()).unwrap_or(0);
            let created_dt = Utc
                .timestamp_opt(created_ts, 0)
                .single()
                .unwrap_or_else(Utc::now);
            println!(
                "ID: {}\nAmount: {} {}\nStatus: {}\n{}",
                id,
                amt,
                cur,
                st,
                "-".repeat(40)
            );
            println!("Created: {}", created_dt.to_rfc3339());
        }
    }
    Ok(())
}

async fn create_customer(
    key: &str,
    email: &str,
    name: &str,
    description: Option<&str>,
) -> anyhow::Result<()> {
    let mut form = vec![
        ("email".to_string(), email.to_string()),
        ("name".to_string(), name.to_string()),
    ];
    if let Some(d) = description {
        form.push(("description".to_string(), d.to_string()));
    }
    let c = post_form(key, "/customers", &form).await?;
    println!("\nCustomer Created:");
    println!("ID: {}", c.get("id").and_then(|v| v.as_str()).unwrap_or(""));
    println!(
        "Name: {}",
        c.get("name").and_then(|v| v.as_str()).unwrap_or("")
    );
    println!(
        "Email: {}",
        c.get("email").and_then(|v| v.as_str()).unwrap_or("")
    );
    Ok(())
}

async fn create_refund(key: &str, payment_intent_id: &str) -> anyhow::Result<()> {
    // retrieve PI first
    let pi = retrieve(key, &format!("/payment_intents/{}", payment_intent_id), &[]).await?;
    let latest_charge = pi
        .get("latest_charge")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    if latest_charge.is_empty() {
        println!("No charge found for this payment intent");
        return Ok(());
    }
    let refund = post_form(
        key,
        "/refunds",
        &[
            ("charge".to_string(), latest_charge.to_string()),
            ("reason".to_string(), "requested_by_customer".to_string()),
        ],
    )
    .await?;
    println!("\nRefund Created:");
    println!(
        "ID: {}",
        refund.get("id").and_then(|v| v.as_str()).unwrap_or("")
    );
    println!(
        "Amount: {} {}",
        refund.get("amount").and_then(|v| v.as_i64()).unwrap_or(0),
        refund
            .get("currency")
            .and_then(|v| v.as_str())
            .unwrap_or("")
    );
    println!(
        "Status: {}",
        refund.get("status").and_then(|v| v.as_str()).unwrap_or("")
    );
    Ok(())
}

async fn list_payment_methods(key: &str) -> anyhow::Result<()> {
    // Note: On many accounts, listing payment methods requires a customer parameter.
    // We'll attempt a global list for parity with the Python script.
    let res = retrieve(
        key,
        "/payment_methods",
        &[
            ("type".to_string(), "card".to_string()),
            ("limit".to_string(), "10".to_string()),
        ],
    )
    .await?;
    println!("\nAvailable Payment Methods:");
    if let Some(arr) = res.get("data").and_then(|v| v.as_array()) {
        for pm in arr {
            let id = pm.get("id").and_then(|v| v.as_str()).unwrap_or("");
            let typ = pm.get("type").and_then(|v| v.as_str()).unwrap_or("");
            let card = pm.get("card").cloned().unwrap_or(Value::Null);
            let brand = card.get("brand").and_then(|v| v.as_str()).unwrap_or("");
            let last4 = card.get("last4").and_then(|v| v.as_str()).unwrap_or("");
            println!(
                "ID: {}\nType: {}\nBrand: {}\nLast 4: {}\n{}",
                id,
                typ,
                brand,
                last4,
                "-".repeat(40)
            );
        }
    }
    Ok(())
}

async fn payment_details(key: &str, payment_intent_id: &str) -> anyhow::Result<()> {
    let pi = retrieve(
        key,
        &format!("/payment_intents/{}", payment_intent_id),
        &[(
            "expand[]".to_string(),
            "latest_charge.balance_transaction".to_string(),
        )],
    )
    .await?;

    let id = pi.get("id").and_then(|v| v.as_str()).unwrap_or("");
    let status = pi.get("status").and_then(|v| v.as_str()).unwrap_or("");
    let amount = pi.get("amount").and_then(|v| v.as_i64()).unwrap_or(0);
    let currency = pi.get("currency").and_then(|v| v.as_str()).unwrap_or("");
    let ch = pi.get("latest_charge").cloned().unwrap_or(Value::Null);
    if ch.is_null() {
        println!("No charge found for this payment intent");
        return Ok(());
    }

    let bt = ch
        .get("balance_transaction")
        .cloned()
        .unwrap_or(Value::Null);
    let available_on_ts = bt.get("available_on").and_then(|v| v.as_i64()).unwrap_or(0);
    let created_ts = ch.get("created").and_then(|v| v.as_i64()).unwrap_or(0);

    let created_dt: DateTime<Utc> = Utc
        .timestamp_opt(created_ts, 0)
        .single()
        .unwrap_or_else(Utc::now);
    let available_on_dt: DateTime<Utc> = Utc
        .timestamp_opt(available_on_ts, 0)
        .single()
        .unwrap_or_else(Utc::now);

    println!("\nPayment Details:");
    println!("Payment ID: {}", id);
    println!("Status: {}", status);
    println!("Amount: {} {}", amount, currency);
    println!("Transaction Date: {} (UTC)", created_dt.to_rfc3339());
    println!("Available on: {} (UTC)", available_on_dt.to_rfc3339());
    println!(
        "Balance Transaction Status: {}",
        bt.get("status").and_then(|v| v.as_str()).unwrap_or("")
    );
    println!(
        "Gross amount: {} {}",
        bt.get("amount").and_then(|v| v.as_i64()).unwrap_or(0),
        bt.get("currency").and_then(|v| v.as_str()).unwrap_or("")
    );
    println!(
        "Fee: {} {}",
        bt.get("fee").and_then(|v| v.as_i64()).unwrap_or(0),
        bt.get("currency").and_then(|v| v.as_str()).unwrap_or("")
    );
    println!(
        "Net amount: {} {}",
        bt.get("net").and_then(|v| v.as_i64()).unwrap_or(0),
        bt.get("currency").and_then(|v| v.as_str()).unwrap_or("")
    );

    Ok(())
}

fn print_disclaimer() {
    println!("\n*** IMPORTANT DISCLAIMER ***");
    println!("Conventionally, Stripe considers cents as the integer atomic unit for currency.");
    println!(
        "Thus, for example in the Swiss case 100 chf in Stripe correspond actually to real 1 CHF."
    );
}
