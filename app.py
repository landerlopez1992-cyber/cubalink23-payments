#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
💳 CUBALINK23 PAYMENTS BACKEND - SOLO SQUARE
🔒 Backend dedicado exclusivamente para pagos con Square API
🌐 Listo para deploy en Render.com como cubalink23-payments
"""

import os
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from square.client import Square

app = Flask(__name__)
CORS(app)

# Configuración
PORT = int(os.environ.get('PORT', 10000))

# Square API Configuration
SQUARE_APPLICATION_ID = os.environ.get('SQUARE_APPLICATION_ID')
SQUARE_ACCESS_TOKEN = os.environ.get('SQUARE_ACCESS_TOKEN')
SQUARE_LOCATION_ID = os.environ.get('SQUARE_LOCATION_ID')
SQUARE_ENVIRONMENT = os.environ.get('SQUARE_ENVIRONMENT', 'sandbox')  # 'sandbox' o 'production'

print("💳 CUBALINK23 PAYMENTS BACKEND - SOLO SQUARE v1.1")
print(f"🔧 Puerto: {PORT}")
print(f"🔑 Square App ID: {'✅ Configurada' if SQUARE_APPLICATION_ID else '❌ No configurada'}")
print(f"🔑 Square Access Token: {'✅ Configurada' if SQUARE_ACCESS_TOKEN else '❌ No configurada'}")
print(f"🔑 Square Location ID: {'✅ Configurada' if SQUARE_LOCATION_ID else '❌ No configurada'}")
print(f"🌍 Entorno: {SQUARE_ENVIRONMENT.upper()}")

# Inicializar cliente Square
square_client = None
if SQUARE_APPLICATION_ID and SQUARE_ACCESS_TOKEN and SQUARE_LOCATION_ID:
    try:
        square_client = Square(
            access_token=SQUARE_ACCESS_TOKEN,
            environment=SQUARE_ENVIRONMENT
        )
        print("✅ Cliente Square inicializado correctamente")
    except Exception as e:
        print(f"❌ Error inicializando Square: {e}")
        square_client = None
else:
    print("⚠️ Credenciales de Square no configuradas")

@app.route('/')
def home():
    """🏠 Página principal"""
    return jsonify({
        "message": "CubaLink23 Payments Backend - Solo Square",
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "version": "SQUARE_ONLY",
        "environment": SQUARE_ENVIRONMENT,
        "endpoints": [
            "/api/health",
            "/api/payments/process",
            "/api/payments/cards/save",
            "/api/payments/cards/charge"
        ]
    })

@app.route('/api/health')
def health_check():
    """💚 Health check"""
    return jsonify({
        "status": "healthy",
        "message": "CubaLink23 Payments Backend - Solo Square funcionando",
        "timestamp": datetime.now().isoformat(),
        "version": "SQUARE_ONLY",
        "environment": SQUARE_ENVIRONMENT,
        "square_configured": bool(square_client)
    })

@app.route('/api/payments/process', methods=['POST'])
def process_payment():
    """💳 Procesar pago con Square"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No se recibieron datos"}), 400

        card_token = data.get('card_token')
        amount = data.get('amount')
        currency = data.get('currency', 'USD')
        idempotency_key = data.get('idempotency_key', str(uuid.uuid4()))

        print(f"💳 Procesando pago:")
        print(f"   💰 Monto: {amount} {currency}")
        print(f"   🔑 Token: {card_token[:20]}..." if card_token else "   🔑 Token: None")
        print(f"   🆔 Idempotency: {idempotency_key}")

        if not square_client:
            return jsonify({"error": "Square no configurado"}), 500

        if not card_token or not amount:
            return jsonify({"error": "card_token y amount son requeridos"}), 400

        # Crear pago con Square
        payments_api = square_client.payments
        body = {
            "source_id": card_token,
            "idempotency_key": idempotency_key,
            "amount_money": {
                "amount": int(float(amount) * 100),  # Convertir a centavos
                "currency": currency
            },
            "location_id": SQUARE_LOCATION_ID
        }

        print(f"📤 Enviando a Square API: {json.dumps(body, indent=2)}")

        response = payments_api.create_payment(body)

        if response.is_success():
            payment_data = response.body['payment']
            print(f"✅ Pago exitoso: {payment_data['id']}")
            
            return jsonify({
                "success": True,
                "payment_id": payment_data['id'],
                "status": payment_data['status'],
                "amount": payment_data['amount_money']['amount'],
                "currency": payment_data['amount_money']['currency'],
                "created_at": payment_data['created_at'],
                "message": "Pago procesado exitosamente"
            })
        else:
            errors = response.errors
            print(f"❌ Error en pago: {errors}")
            
            return jsonify({
                "success": False,
                "error": "Error procesando pago",
                "details": errors,
                "message": "No se pudo procesar el pago"
            }), 400

    except Exception as e:
        print(f"💥 Error general: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Error interno: {str(e)}",
            "message": "Error interno del servidor"
        }), 500

@app.route('/api/payments/cards/save', methods=['POST'])
def save_card():
    """💳 Guardar tarjeta para uso futuro"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No se recibieron datos"}), 400

        card_token = data.get('card_token')
        customer_id = data.get('customer_id')

        print(f"💳 Guardando tarjeta:")
        print(f"   🔑 Token: {card_token[:20]}..." if card_token else "   🔑 Token: None")
        print(f"   👤 Customer: {customer_id}")

        if not square_client:
            return jsonify({"error": "Square no configurado"}), 500

        if not card_token:
            return jsonify({"error": "card_token es requerido"}), 400

        # Crear customer si no existe
        if not customer_id:
            customers_api = square_client.customers
            customer_body = {
                "given_name": "Cliente",
                "family_name": "CubaLink23"
            }
            
            customer_response = customers_api.create_customer(customer_body)
            if customer_response.is_success():
                customer_id = customer_response.body['customer']['id']
                print(f"✅ Cliente creado: {customer_id}")
            else:
                return jsonify({"error": "Error creando cliente"}), 500

        # Crear card
        cards_api = square_client.cards
        card_body = {
            "source_id": card_token,
            "card": {
                "customer_id": customer_id
            }
        }

        response = cards_api.create_card(card_body)

        if response.is_success():
            card_data = response.body['card']
            print(f"✅ Tarjeta guardada: {card_data['id']}")
            
            return jsonify({
                "success": True,
                "card_id": card_data['id'],
                "customer_id": customer_id,
                "last_4": card_data['last_4'],
                "card_brand": card_data['card_brand'],
                "exp_month": card_data['exp_month'],
                "exp_year": card_data['exp_year'],
                "message": "Tarjeta guardada exitosamente"
            })
        else:
            errors = response.errors
            print(f"❌ Error guardando tarjeta: {errors}")
            
            return jsonify({
                "success": False,
                "error": "Error guardando tarjeta",
                "details": errors,
                "message": "No se pudo guardar la tarjeta"
            }), 400

    except Exception as e:
        print(f"💥 Error general: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Error interno: {str(e)}",
            "message": "Error interno del servidor"
        }), 500

@app.route('/api/payments/cards/charge', methods=['POST'])
def charge_saved_card():
    """💳 Cobrar tarjeta guardada"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No se recibieron datos"}), 400

        card_id = data.get('card_id')
        amount = data.get('amount')
        currency = data.get('currency', 'USD')
        idempotency_key = data.get('idempotency_key', str(uuid.uuid4()))

        print(f"💳 Cobrando tarjeta guardada:")
        print(f"   💳 Card ID: {card_id}")
        print(f"   💰 Monto: {amount} {currency}")
        print(f"   🆔 Idempotency: {idempotency_key}")

        if not square_client:
            return jsonify({"error": "Square no configurado"}), 500

        if not card_id or not amount:
            return jsonify({"error": "card_id y amount son requeridos"}), 400

        # Crear pago con tarjeta guardada
        payments_api = square_client.payments
        body = {
            "source_id": f"cnon:{card_id}",
            "idempotency_key": idempotency_key,
            "amount_money": {
                "amount": int(float(amount) * 100),  # Convertir a centavos
                "currency": currency
            },
            "location_id": SQUARE_LOCATION_ID
        }

        print(f"📤 Enviando a Square API: {json.dumps(body, indent=2)}")

        response = payments_api.create_payment(body)

        if response.is_success():
            payment_data = response.body['payment']
            print(f"✅ Cobro exitoso: {payment_data['id']}")
            
            return jsonify({
                "success": True,
                "payment_id": payment_data['id'],
                "status": payment_data['status'],
                "amount": payment_data['amount_money']['amount'],
                "currency": payment_data['amount_money']['currency'],
                "created_at": payment_data['created_at'],
                "message": "Cobro procesado exitosamente"
            })
        else:
            errors = response.errors
            print(f"❌ Error en cobro: {errors}")
            
            return jsonify({
                "success": False,
                "error": "Error procesando cobro",
                "details": errors,
                "message": "No se pudo procesar el cobro"
            }), 400

    except Exception as e:
        print(f"💥 Error general: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Error interno: {str(e)}",
            "message": "Error interno del servidor"
        }), 500

if __name__ == '__main__':
    print(f"💳 INICIANDO BACKEND SQUARE EN PUERTO {PORT}")
    print("🌐 Listo para deploy en Render.com como cubalink23-payments")
    
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=False,
        threaded=True
    )
