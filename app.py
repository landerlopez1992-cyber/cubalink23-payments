import os
from flask import Flask, request, jsonify, render_template_string
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

@app.get("/sdk/card")
def sdk_card():
    """Servir HTML con Square Web Payments SDK para tokenización"""
    try:
        with open('templates/card.html', 'r') as f:
            html_content = f.read()
        return html_content, 200, {'Content-Type': 'text/html'}
    except FileNotFoundError:
        return jsonify({"error": "Card HTML not found"}), 404

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

@app.post("/api/cards/save")
def api_cards_save():
    """Guardar tarjeta con nonce desde WebView"""
    data = request.get_json() or {}
    source_id = data.get("source_id")
    customer_id = data.get("customer_id")
    
    if not source_id or not customer_id:
        return jsonify({"error": "source_id y customer_id requeridos"}), 400
    
    try:
        card = create_card_on_file(customer_id, source_id)
        return jsonify({
            "card_id": card["id"],
            "brand": card["card_brand"],
            "last4": card["last_4"],
            "exp_month": card["exp_month"],
            "exp_year": card["exp_year"]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

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

@app.post("/api/payments/charge-onfile")
def api_payments_charge_onfile():
    """Cobrar tarjeta guardada (Card on File)"""
    data = request.get_json() or {}
    customer_id = data.get("customer_id")
    card_id = data.get("card_id")
    amount_money = data.get("amount_money", {})
    note = data.get("note", "CubaLink23")
    
    if not customer_id or not card_id or not amount_money:
        return jsonify({"error": "customer_id, card_id y amount_money requeridos"}), 400
    
    try:
        amount_cents = amount_money.get("amount", 0)
        currency = amount_money.get("currency", "USD")
        
        payment = create_payment_with_card(customer_id, card_id, amount_cents, currency, note)
        
        return jsonify({
            "status": payment["status"],
            "payment_id": payment["id"],
            "receipt_url": payment.get("receipt_url"),
            "message": "Pago procesado exitosamente"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "FAILED",
            "code": "PAYMENT_ERROR", 
            "message": str(e)
        }), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))