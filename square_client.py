import os, uuid, requests

def _cfg():
    env = os.getenv("SQUARE_ENV", "sandbox").lower()
    base = "https://connect.squareup.com" if env == "production" else "https://connect.squareupsandbox.com"
    token = os.getenv("SQUARE_ACCESS_TOKEN", "")
    loc   = os.getenv("SQUARE_LOCATION_ID", "")
    return env, base, token, loc

def _headers(token:str):
    return {
        "Square-Version": "2024-08-21",  # requerido por Square
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def ensure_config_ok():
    env, base, token, loc = _cfg()
    ok = bool(token and loc)
    return ok, {"env": env, "has_token": bool(token), "has_location": bool(loc), "base": base}

def create_customer(given_name=None, email=None, reference_id=None):
    env, base, token, _ = _cfg()
    r = requests.post(
        f"{base}/v2/customers",
        headers=_headers(token),
        json={"idempotency_key": str(uuid.uuid4()), "given_name": given_name, "email_address": email, "reference_id": reference_id},
        timeout=30,
    )
    r.raise_for_status(); return r.json()["customer"]

def create_card_on_file(customer_id:str, nonce:str):
    # Cards API actual: POST /v2/cards  (no usar endpoint deprecated /customers/{id}/cards)
    env, base, token, _ = _cfg()
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "source_id": nonce,
        "card": { "customer_id": customer_id }
    }
    r = requests.post(f"{base}/v2/cards", headers=_headers(token), json=body, timeout=30)
    r.raise_for_status(); return r.json()["card"]

def create_payment_with_card(customer_id:str, card_id:str, amount_cents:int, currency="USD", note=None):
    env, base, token, loc = _cfg()
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "amount_money": {"amount": amount_cents, "currency": currency},
        "customer_id": customer_id,
        "card_id": card_id,
        "location_id": loc,
        "note": note
    }
    r = requests.post(f"{base}/v2/payments", headers=_headers(token), json=body, timeout=30)
    r.raise_for_status(); return r.json()["payment"]

def create_payment_with_nonce(nonce:str, amount_cents:int, currency="USD", note=None, customer_id=None):
    env, base, token, loc = _cfg()
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "amount_money": {"amount": amount_cents, "currency": currency},
        "source_id": nonce,
        "location_id": loc,
        "customer_id": customer_id,
        "note": note
    }
    r = requests.post(f"{base}/v2/payments", headers=_headers(token), json=body, timeout=30)
    r.raise_for_status(); return r.json()["payment"]
