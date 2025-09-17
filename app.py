import os, requests, uuid
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from square_client import (
    ensure_config_ok, create_customer, create_card_on_file,
    create_payment_with_card, create_payment_with_nonce
)
from supabase import create_client, Client

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

API_KEY = os.getenv("INTERNAL_API_KEY")  # opcional

# ====================== SUPABASE SETUP ======================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE") or os.getenv("SUPABASE_KEY")

supabase: Client = None
try:
    if SUPABASE_URL and SUPABASE_SERVICE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        print(f"✅ Supabase conectado: {SUPABASE_URL[:50]}...")
    else:
        print("⚠️ Supabase no configurado - algunos endpoints no funcionarán")
except Exception as e:
    print(f"❌ Error conectando Supabase: {e}")
    print("⚠️ Continuando sin Supabase - algunos endpoints no funcionarán")
    supabase = None

def require_key():
    if API_KEY and request.headers.get("X-Api-Key") != API_KEY:
        return jsonify({"error":"unauthorized"}), 401

@app.get("/health")
def health():
    ok, meta = ensure_config_ok()
    supabase_ready = supabase is not None
    return {"ok": True, "square_ready": ok, "supabase_ready": supabase_ready, **meta}

# ====================== ENDPOINTS CARD-ON-FILE SEGÚN AMIGO ======================

@app.post("/api/square/customers/ensure")
def ensure_square_customer():
    """1) Crear/obtener Customer en Square y vincular en Supabase"""
    if not supabase:
        return jsonify({"error": "Supabase no configurado"}), 500
        
    data = request.get_json() or {}
    user_id = data.get("user_id")
    email = data.get("email", "")
    name = data.get("name", "")
    
    if not user_id:
        return jsonify({"error": "user_id requerido"}), 400
    
    try:
        # Verificar si ya existe en Supabase
        result = supabase.table("user_square").select("square_customer_id").eq("user_id", user_id).execute()
        
        if result.data:
            # Ya existe
            square_customer_id = result.data[0]["square_customer_id"]
            print(f"✅ Customer existente: {square_customer_id}")
        else:
            # Crear nuevo customer en Square
            customer = create_customer(given_name=name, email=email, reference_id=user_id)
            square_customer_id = customer["id"]
            
            # Guardar en Supabase
            supabase.table("user_square").insert({
                "user_id": user_id,
                "square_customer_id": square_customer_id
            }).execute()
            
            print(f"🆕 Nuevo customer creado: {square_customer_id}")
        
        return jsonify({"square_customer_id": square_customer_id}), 200
        
    except Exception as e:
        print(f"❌ Error ensure customer: {e}")
        return jsonify({"error": str(e)}), 500

@app.post("/api/cards/create")
def create_card_with_metadata():
    """2) Guardar tarjeta (Card-on-File) con metadata en Supabase"""
    if not supabase:
        return jsonify({"error": "Supabase no configurado"}), 500
        
    data = request.get_json() or {}
    user_id = data.get("user_id")
    customer_id = data.get("customer_id")
    nonce = data.get("nonce")
    postal_code = data.get("postal_code", "12345")
    name = data.get("name", "")
    
    if not all([user_id, customer_id, nonce]):
        return jsonify({"error": "user_id, customer_id y nonce requeridos"}), 400
    
    try:
        # Crear tarjeta EN Square
        card = create_card_on_file(customer_id, nonce)
        
        if "error" in card:
            return jsonify({"error": card["error"]}), 400
        
        # Verificar si es la primera tarjeta del usuario
        existing_cards = supabase.table("payment_cards").select("id").eq("user_id", user_id).execute()
        is_default = len(existing_cards.data) == 0
        
        # Guardar metadata en Supabase
        card_data = {
            "user_id": user_id,
            "square_card_id": card["id"],  # ccof:...
            "square_customer_id": customer_id,
            "card_type": card.get("card_brand", "unknown"),
            "last4": card.get("last_4", "****"),
            "exp_month": card.get("exp_month"),
            "exp_year": card.get("exp_year"),
            "zip_code": postal_code,
            "holder_name": name,
            "is_default": is_default
        }
        
        result = supabase.table("payment_cards").insert(card_data).execute()
        
        return jsonify({
            "square_card_id": card["id"],
            "brand": card.get("card_brand"),
            "last4": card.get("last_4"),
            "exp_month": card.get("exp_month"),
            "exp_year": card.get("exp_year"),
            "is_default": is_default,
            "supabase_id": result.data[0]["id"] if result.data else None
        }), 200
        
    except Exception as e:
        print(f"❌ Error crear tarjeta: {e}")
        return jsonify({"error": str(e)}), 500

@app.get("/api/cards")
def list_user_cards():
    """3) Listar tarjetas para el perfil"""
    if not supabase:
        return jsonify({"error": "Supabase no configurado"}), 500
        
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id requerido"}), 400
    
    try:
        result = supabase.table("payment_cards").select(
            "id, square_card_id, card_type, last4, exp_month, exp_year, is_default, holder_name, created_at"
        ).eq("user_id", user_id).order("created_at", desc=True).execute()
        
        cards = []
        for card in result.data:
            cards.append({
                "id": card["id"],
                "square_card_id": card["square_card_id"],
                "brand": card["card_type"],
                "last4": card["last4"],
                "exp_month": card["exp_month"],
                "exp_year": card["exp_year"],
                "is_default": card["is_default"],
                "holder_name": card["holder_name"],
                "created_at": card["created_at"]
            })
        
        return jsonify({"cards": cards}), 200
        
    except Exception as e:
        print(f"❌ Error listar tarjetas: {e}")
        return jsonify({"error": str(e)}), 500

@app.delete("/api/cards/<square_card_id>")
def delete_user_card(square_card_id):
    """4) Eliminar tarjeta"""
    if not supabase:
        return jsonify({"error": "Supabase no configurado"}), 500
        
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id requerido"}), 400
    
    try:
        # TODO: Llamar a Square API para deshabilitar tarjeta
        # requests.post(f"{base_url}/v2/cards/{square_card_id}/disable", headers=headers)
        
        # Eliminar de Supabase
        result = supabase.table("payment_cards").delete().eq("square_card_id", square_card_id).eq("user_id", user_id).execute()
        
        if not result.data:
            return jsonify({"error": "Tarjeta no encontrada"}), 404
        
        return jsonify({"message": "Tarjeta eliminada exitosamente"}), 200
        
    except Exception as e:
        print(f"❌ Error eliminar tarjeta: {e}")
        return jsonify({"error": str(e)}), 500

@app.post("/api/payments/charge")
def charge_saved_card():
    """5) Pagar con card-on-file (checkout 1 toque)"""
    data = request.get_json() or {}
    user_id = data.get("user_id")
    amount = data.get("amount")  # centavos
    currency = data.get("currency", "USD")
    square_card_id = data.get("square_card_id")
    customer_id = data.get("customer_id")  # square customer id
    note = data.get("note", "Recarga Cubalink23")
    
    if not all([user_id, amount, square_card_id, customer_id]):
        return jsonify({"error": "user_id, amount, square_card_id y customer_id requeridos"}), 400
    
    try:
        # Validar que la tarjeta pertenece al usuario
        if supabase:
            card_check = supabase.table("payment_cards").select("id").eq("square_card_id", square_card_id).eq("user_id", user_id).execute()
            if not card_check.data:
                return jsonify({"error": "Tarjeta no encontrada o no autorizada"}), 403
        
        # Procesar pago con Square
        payment = create_payment_with_card(customer_id, square_card_id, int(amount), currency, note)
        
        if "error" in payment:
            return jsonify({
                "status": "FAILED",
                "error": payment["error"],
                "status_code": payment.get("status_code", 400)
            }), payment.get("status_code", 400)
        
        status = payment.get("status")
        success = status == "COMPLETED"
        
        return jsonify({
            "status": status,
            "payment_id": payment.get("id"),
            "receipt_url": payment.get("receipt_url"),
            "success": success,
            "amount": amount,
            "currency": currency
        }), (200 if success else 400)
        
    except Exception as e:
        print(f"❌ Error pago card-on-file: {e}")
        return jsonify({
            "status": "FAILED",
            "error": str(e)
        }), 500

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

@app.route("/api/payments/charge-card-on-file", methods=["POST"])
def charge_card_on_file():
    """Cobrar tarjeta guardada (Card on File) - SIN FORMULARIO"""
    try:
        data = request.get_json(force=True)
        print(f"🔥 COBRO CARD ON FILE: {data}")
        
        amount = int(data["amount"])
        currency = data.get("currency", "USD")
        customer_id = data["customer_id"]
        card_id = data["card_id"]
        note = data.get("note", "")
        
        # ✅ Obtener ZIP code de Supabase para la tarjeta
        try:
            # Llamar al backend system para obtener info de la tarjeta
            card_response = requests.get(
                f"https://cubalink23-system.onrender.com/api/users/{customer_id}/cards/{card_id}",
                timeout=5
            )
            zip_code = "12345"  # Por defecto
            if card_response.status_code == 200:
                card_data = card_response.json()
                zip_code = card_data.get("zip_code", "12345")
                print(f"📮 ZIP code obtenido: {zip_code}")
        except:
            zip_code = "12345"  # Fallback
        
        # ✅ Usar función existente con ZIP code
        payment = create_payment_with_card(customer_id, card_id, amount, currency, note)
        
        if "error" in payment:
            return jsonify({
                "ok": False,
                "status_code": payment.get("status_code", 400),
                "square": payment["error"]
            }), payment.get("status_code", 400)
        
        # Verificar status
        status = payment.get("status")
        ok = status == "COMPLETED"
        
        return jsonify({
            "ok": ok,
            "status_code": 200 if ok else 400,
            "square": {"payment": payment}
        }), (200 if ok else 400)
        
    except Exception as e:
        print(f"❌ Error en Card on File: {e}")
        return jsonify({
            "ok": False,
            "status_code": 500,
            "square": {"error": str(e)}
        }), 500

@app.route("/api/cards/create", methods=["POST"])
def create_card():
    """Crear tarjeta EN Square y devolver card.id real"""
    try:
        data = request.get_json(force=True)
        print(f"🔥 CREAR TARJETA EN SQUARE: {data}")
        
        nonce = data["nonce"]
        customer_id = data["customer_id"]
        name = data.get("name", "")
        zip_code = data.get("zip", "12345")
        
        # ✅ Crear tarjeta EN Square usando función existente
        card = create_card_on_file(customer_id, nonce)
        
        if "error" in card:
            return jsonify({
                "ok": False,
                "square": card["error"]
            }), card.get("status_code", 400)
        
        # ✅ Devolver card.id REAL de Square
        return jsonify({
            "ok": True,
            "square_card_id": card["id"],  # Este es el ccof:... real
            "card": card
        }), 200
        
    except Exception as e:
        print(f"❌ Error creando tarjeta: {e}")
        return jsonify({
            "ok": False,
            "square": {"error": str(e)}
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))