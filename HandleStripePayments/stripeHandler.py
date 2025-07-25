#! /usr/bin/env python3.6
# Python 3.6 or newer required.

###########################################################
# 🚨 WARNING: DEVELOPMENT SECRETS IN USE! DO NOT DEPLOY 🚨
# - Replace `stripe.api_key` with ENV variable
# - Replace `endpoint_secret` with ENV variable (THIS ONE IS ALREADY DONE)
# - Remove any hardcoded test keys
# ✅ Run through your pre-deploy checklist
###########################################################


import json
import os
import stripe
from flask import Flask
print("✅ stripeHandler.py loaded")

# This is your test secret API key.
stripe.api_key = 'sk_test_51Rmxzj078lI8NTECF8bbk7E4ZgasawwDQOLKa2tPgE7ipcjGSj5yAsj9m9UtjeBhf49TdOK2ayqRhxG6X03V076w006zlHzUp8'

# Replace this endpoint secret with your endpoint's unique secret
# If you are testing with the CLI, find the secret by running 'stripe listen'
# If you are using an endpoint defined with the API or dashboard, look in your webhook settings
# at https://dashboard.stripe.com/webhooks
endpoint_secret = 'whsec_x48q5L2woXndlXNVbuaAmKHlKGI1khsd'
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook(): 

    print('WEBHOOK IS IN BABY WOOOO')
    event = None
    payload = request.data

    try:
        event = json.loads(payload)
    except json.decoder.JSONDecodeError as e:
        print('⚠️  Webhook error while parsing basic request.' + str(e))
        return jsonify(success=False)
    if endpoint_secret:
        # Only verify the event if there is an endpoint secret defined
        # Otherwise use the basic event deserialized with json
        sig_header = request.headers.get('stripe-signature')
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except stripe.error.SignatureVerificationError as e:
            print('⚠️  Webhook signature verification failed.' + str(e))
            return jsonify(success=False)

    # Handle the event
    if event and event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']  # contains a stripe.PaymentIntent
        print('Payment for {} succeeded'.format(payment_intent['amount']))
        # Then define and call a method to handle the successful payment intent.
        # handle_payment_intent_succeeded(payment_intent)
    elif event['type'] == 'payment_method.attached':
        payment_method = event['data']['object']  # contains a stripe.PaymentMethod
        print('hello everything working?')
        # Then define and call a method to handle the successful attachment of a PaymentMethod.
        # handle_payment_method_attached(payment_method)
    else:
        # Unexpected event type
        print('Unhandled event type {}'.format(event['type']))

    verified = jsonify(success=True)
    return verified




