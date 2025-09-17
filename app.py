import os, requests
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

def fail(code, msg, http=422):
    return jsonify({"status":"FAILED","code":code,"message":msg}), http

@app.post("/api/payments")
def api_payments():
    if (k := require_key()): return k
    data = request.get_json() or {}
    print(f"🔥 DATOS RECIBIDOS: {data}")
    
    amount = data.get("amount_cents")
    currency = data.get("currency", "USD")
    note = data.get("note", "")
    source_id = data.get("source_id") or data.get("nonce")
    customer_id = data.get("customer_id")
    card_id = data.get("card_id")
    
    print(f"🎯 SOURCE_ID: '{source_id}' (tipo: {type(source_id)})")
    print(f"💰 AMOUNT: {amount}")
    print(f"👤 CUSTOMER_ID: {customer_id}")

    # 🔒 Validación fuerte de nonce en SANDBOX
    if not source_id and not card_id:
        return fail("MISSING_SOURCE", "source_id o card_id requerido")

    if source_id:
        # Solo rechazar placeholders obvios, permitir nonces reales
        if source_id == "[redacted]" or source_id == "fake-nonce" or len(source_id) < 10:
            return fail("MISSING_NONCE", "Nonce inválido o placeholder")

    # Validar y convertir amount
    try:
        amount = int(amount) if amount else 0
        if amount <= 0:
            return fail("BAD_AMOUNT", "Monto debe ser mayor a 0")
    except (ValueError, TypeError):
        return fail("BAD_AMOUNT", f"Monto inválido: {amount}")

    try:
        # Dos modos: Card on File o Nonce directo
        if card_id and customer_id:
            p = create_payment_with_card(customer_id, card_id, amount, currency, note)
        else:
            p = create_payment_with_nonce(source_id, amount, currency, note, customer_id=customer_id)
        
        # Si hay error en la respuesta
        if "error" in p:
            return jsonify({
                "status": "FAILED",
                "code": "SQUARE_ERROR",
                "message": str(p["error"])
            }), p.get("status_code", 400)
        
        # ✅ Devolver TODO el objeto payment de Square
        return jsonify({"payment": p}), 200
            
    except Exception as e:
        return fail("SERVER_ERROR", str(e), 500)

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

@app.route("/api/users/<user_id>/cards", methods=["GET"])
def get_user_cards(user_id):
    """Obtener tarjetas guardadas del usuario desde backend principal"""
    try:
        # Llamar al backend principal de Cubalink23
        response = requests.get(
            f"https://cubalink23-backend.onrender.com/api/users/{user_id}/payment-cards",
            timeout=10
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"cards": []}), 200
            
    except Exception as e:
        print(f"❌ Error obteniendo tarjetas: {e}")
        return jsonify({"cards": []}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))