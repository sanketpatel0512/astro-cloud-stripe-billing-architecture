# AstroCompute Cloud: Stripe B2B SaaS Billing Architecture

## Overview
This project demonstrates a production-ready B2B SaaS billing architecture using **Stripe Checkout**, the **Stripe Customer Portal**, and **Stripe Webhooks**. It models a cloud computing platform ("AstroCompute") where users can subscribe to recurring monthly tiers for heavy deep-sky image processing.

This architecture showcases how to offload complex billing logic (like prorations, upgrades, and cancellations) directly to Stripe, allowing the platform backend to simply listen for state changes and provision access accordingly.

## Technical Stack
* **Backend:** Python / Flask
* **Frontend:** HTML / Vanilla JavaScript (Jinja2 Templating)
* **Stripe APIs Used:** * `stripe.checkout.Session` (Recurring Subscription vaulted billing)
  * `stripe.billing_portal.Session` (Self-serve upgrade/downgrade UI)
  * `stripe.Webhook` (Asynchronous lifecycle management)

## Business Value & Solution Strategy
1. **Environment-Specific Configuration:** Stripe Price IDs and Webhook Secrets are abstracted into `.env` variables, ensuring the codebase requires zero changes when migrating from Test to Live Production environments (CI/CD best practice).
2. **Zero-UI Billing Management:** Leverages the Stripe-hosted Customer Portal, saving hundreds of engineering hours by offloading the UI, security, and proration math required for users to manage their own subscriptions.
3. **Event-Driven Provisioning:** The backend acts strictly as a listener. It relies on Stripe's Webhooks (`checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`) as the single source of truth to provision, modify, or completely revoke software access.

## Project Structure
```text
/
├── .env                    # Environment variables (Stripe Keys & Price IDs)
├── SaaSApp.py              # Main Flask application and Webhook listener
└── templates/              
    ├── pricing.html        # Dynamic SaaS catalog and Checkout entry point
    └── success.html        # Mock SaaS dashboard and Portal entry point
```

## How to Run Locally

### 1. Prerequisites
* Python 3.x
* A [Stripe account](https://dashboard.stripe.com/register) (Test Mode)
* [Stripe CLI](https://stripe.com/docs/stripe-cli) installed

### 2. Install Dependencies
Clone this repository, navigate to the project folder, and run:
```powershell
pip install stripe flask python-dotenv
```

### 3. Configure the Dashboard & Products
1. Go to your Stripe Dashboard -> **Product Catalog**. Create two recurring products (e.g., a $15/mo Basic tier and a $49/mo Pro tier). Copy their `price_...` API IDs.
2. Go to Dashboard -> **Settings -> Customer portal**. Enable the portal and allow users to "Update" and "Cancel" their subscriptions. Add your two products to the allowed update list.

### 4. Configure Environment Variables
Rename the included `.env.example` file to `.env` (or create a new one) and populate it with your test keys and the Price IDs generated in Step 3:
```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
PRICE_NEBULA_BASIC=price_...
PRICE_GALAXY_PRO=price_...
```

### 5. Start the Server & Webhooks
Run the Flask server:
```powershell
python SaaSApp.py
```
In a separate terminal window, start the Stripe CLI to forward events to your local server:
```powershell
stripe listen --forward-to localhost:4242/webhook
```
*(Make sure to copy the `whsec_...` secret provided by the CLI into your `.env` file!)*

## Demo Walkthrough (The Gauntlet)

To see the automated lifecycle in action, monitor your Flask terminal while performing the following steps:
1. **Provision:** Go to `http://localhost:4242`, click "Start Free Trial", and checkout using the test card (`4242 4242 4242 4242`). The terminal will log `🚀 [PROVISION]` as the webhook fires.
2. **Update:** From the local dashboard, click "Manage Billing" to enter the Customer Portal. Upgrade your plan. The terminal will log `🔄 [UPDATE]` with your new `price_...` ID.
3. **Revoke:** Re-enter the Customer Portal and cancel your subscription. The terminal will log `❌ [REVOKE]`, signaling the backend to instantly cut off software access.