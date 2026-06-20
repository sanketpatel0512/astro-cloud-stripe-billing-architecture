import stripe
import os
from flask import Flask, jsonify, request, render_template, redirect
from dotenv import load_dotenv

load_dotenv()
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
app = Flask(__name__)

# ==========================================
# MOCK DATABASE: SaaS Pricing Tiers
# Pulling Price IDs from environment variables for CI/CD best practices
# ==========================================
SAAS_TIERS = {
    "nebula_basic": {
        "name": "Nebula Basic",
        "description": "Perfect for standard planetary and light deep-sky processing.",
        "price_monthly": 15,
        "stripe_price_id": os.environ.get('PRICE_NEBULA_BASIC'), 
        "features": ["100GB Cloud Storage", "Standard Siril Stacking Nodes", "1080p Export Quality", "Community Support"]
    },
    "galaxy_pro": {
        "name": "Galaxy Pro",
        "description": "Heavy compute power for massive .fit datasets and advanced AI processing.",
        "price_monthly": 49,
        "stripe_price_id": os.environ.get('PRICE_GALAXY_PRO'),
        "features": ["2TB NVMe Storage", "Priority GPU Compute Instances", "Automated AI Denoise & Deconvolution", "API Access"]
    }
}

@app.route('/')
def pricing_page():
    """Renders the main SaaS pricing page."""
    return render_template('pricing.html', tiers=SAAS_TIERS)

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """
    Creates a Stripe Checkout session for a subscription.
    """
    try:
        data = request.get_json()
        tier_id = data.get('tier_id')
        tier = SAAS_TIERS.get(tier_id)

        if not tier:
            return jsonify(error="Subscription tier not found"), 404

        # Notice the mode is 'subscription', not 'payment'!
        # This tells Stripe to vault the card and set up recurring billing.
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': tier['stripe_price_id'],
                'quantity': 1,
            }],
            mode='subscription',
            # We pass the session ID to the success URL so we can provision the account later
            success_url='http://localhost:4242/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='http://localhost:4242/',
        )
        return jsonify({'url': session.url})
    
    except Exception as e:
        print(f"\n--- STRIPE CHECKOUT ERROR --- \n{str(e)}\n--------------------\n")
        return jsonify(error=str(e)), 403

@app.route('/success')
def success():
    """
    Retrieves the Checkout Session to find the Stripe Customer ID, 
    then renders the user's dashboard.
    """
    session_id = request.args.get('session_id')
    if not session_id:
        return redirect('/')
        
    try:
        # Retrieve the session from Stripe to grab the newly created Customer ID
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        customer_id = checkout_session.customer
        
        # Pass the Customer ID to the HTML template
        return render_template('success.html', customer_id=customer_id)
    except Exception as e:
        print(f"\n--- STRIPE SESSION ERROR --- \n{str(e)}\n--------------------\n")
        return str(e), 400

@app.route('/create-portal-session', methods=['POST'])
def create_portal_session():
    """
    Generates a secure link to the Stripe-hosted Customer Portal 
    so the user can upgrade, downgrade, or cancel their SaaS tier.
    """
    try:
        data = request.get_json()
        customer_id = data.get('customer_id')

        # Generate the portal link and tell Stripe where to send them when they click 'Return'
        portalSession = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url='http://localhost:4242/'
        )
        return jsonify({'url': portalSession.url})
    
    except Exception as e:
        print(f"\n--- STRIPE PORTAL ERROR --- \n{str(e)}\n--------------------\n")
        return jsonify(error=str(e)), 403

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Listens for Stripe events to provision, modify, or revoke SaaS access.
    """
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400

    # 1. PROVISION ACCESS: User just signed up via Checkout
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # We only care about subscription signups here
        if session.get('mode') == 'subscription':
            customer_id = session.get('customer')
            subscription_id = session.get('subscription')
            print(f"\n🚀 [PROVISION]: New signup! Customer {customer_id} started sub {subscription_id}")
            # In production: UPDATE database SET status = 'active' WHERE customer_id = customer_id

    # 2. MODIFY ACCESS: User upgraded/downgraded via Customer Portal
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        status = subscription.get('status') # e.g., 'active', 'past_due'
        
        # Grab the exact Price ID they are currently on to know their tier
        current_price_id = subscription['items']['data'][0]['price']['id']
        
        print(f"\n🔄 [UPDATE]: Customer {customer_id} modified plan. Status: {status}. New Price ID: {current_price_id}")
        # In production: UPDATE database SET tier = current_price_id WHERE customer_id = customer_id

    # 3. REVOKE ACCESS: User cancelled via Customer Portal (or failed to pay)
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        
        print(f"\n❌ [REVOKE]: Customer {customer_id} cancelled. Shutting down their compute node.")
        # In production: UPDATE database SET status = 'cancelled' WHERE customer_id = customer_id

    return jsonify(success=True), 200

if __name__ == '__main__':
    app.run(port=4242)