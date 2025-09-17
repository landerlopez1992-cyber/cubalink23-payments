import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from square_client import (
    ensure_config_ok, create_customer, create_card_on_file,
    create_payment_with_card, create_payment_with_nonce
)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

API_KEY = os.getenv("INTERNAL_API_KEY")  # opcional

def require_key():
    if API_KEY and request.headers.get("X-Api-Key") != API_KEY:
        return jsonify({"error":"unauthorized"}), 401

@app.get("/health")
def health():
    ok, meta = ensure_config_ok()
    return {"ok": True, "square_ready": ok, **meta}

@app.post("/api/customers")
def api_customers():
    if (k := require_key()): return k
    data = request.get_json() or {}
    c = create_customer(given_name=data.get("name"), email=data.get("email"), reference_id=data.get("reference_id"))
    return jsonify(c), 200

@app.post("/api/cards")
def api_cards():
    if (k := require_key()): return k
    data = request.get_json() or {}
    card = create_card_on_file(data["customer_id"], data["nonce"])  # nonce viene del cliente
    return jsonify(card), 200

@app.post("/api/payments")
def api_payments():
    if (k := require_key()): return k
    data = request.get_json() or {}
    amount = int(data["amount_cents"]); currency = data.get("currency", "USD"); note = data.get("note")
    if "card_id" in data and "customer_id" in data:
        p = create_payment_with_card(data["customer_id"], data["card_id"], amount, currency, note)
        return jsonify(p), 200
    if "nonce" in data:
        p = create_payment_with_nonce(data["nonce"], amount, currency, note, customer_id=data.get("customer_id"))
        if "error" in p:
            return jsonify(p), p.get("status_code", 400)
        return jsonify(p), 200
    return jsonify({"error":"Provide {customer_id,card_id} or {nonce}"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))