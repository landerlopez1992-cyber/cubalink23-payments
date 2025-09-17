# 💳 CubaLink23 Payments Backend - Solo Square

## 🚨 **IMPORTANTE: BACKEND SEPARADO**

Este backend está **COMPLETAMENTE SEPARADO** del backend de Duffel para evitar conflictos.

- **`cubalink23-backend`** → Solo Duffel (CONGELADO)
- **`cubalink23-payments`** → Solo Square (ESTE)

## 🔧 **Configuración en Render**

### **Variables de Entorno Requeridas:**

```bash
SQUARE_APPLICATION_ID=sandbox-sq0idb-xxxxxxxxxxxxx
SQUARE_ACCESS_TOKEN=sandbox-sq0atb-xxxxxxxxxxxxx
SQUARE_LOCATION_ID=xxxxxxxxxxxxxxxxx
SQUARE_ENVIRONMENT=sandbox
```

### **Para Producción:**
```bash
SQUARE_ENVIRONMENT=production
# Y usar las credenciales de producción
```

## 📡 **Endpoints Disponibles:**

### **Health Check:**
```
GET /api/health
```

### **Procesar Pago:**
```
POST /api/payments/process
{
  "card_token": "cnon_xxxxxxxxxxxxx",
  "amount": "10.00",
  "currency": "USD",
  "idempotency_key": "unique-key-123"
}
```

### **Guardar Tarjeta:**
```
POST /api/payments/cards/save
{
  "card_token": "cnon_xxxxxxxxxxxxx",
  "customer_id": "optional-customer-id"
}
```

### **Cobrar Tarjeta Guardada:**
```
POST /api/payments/cards/charge
{
  "card_id": "card_xxxxxxxxxxxxx",
  "amount": "10.00",
  "currency": "USD",
  "idempotency_key": "unique-key-123"
}
```

## 🚀 **Deploy en Render:**

1. Crear nuevo servicio en Render
2. Nombre: `cubalink23-payments`
3. Conectar repositorio
4. Configurar variables de entorno
5. Deploy automático

## 🔒 **Seguridad:**

- Todas las claves se manejan via variables de entorno
- Idempotency keys para evitar cobros duplicados
- Validación de datos de entrada
- Logs detallados para debugging

## 📱 **Integración con Flutter:**

La app Flutter se conectará a este backend para:
- Tokenización de tarjetas
- Procesamiento de pagos
- Guardado de tarjetas
- Cobros futuros

**URL del backend:** `https://cubalink23-payments.onrender.com`
