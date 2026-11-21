OPERATION_TYPES = {
  "transferencia_inmediata": "instant_transfer",
  "pago_qr": "qr_payment",
  "pago_servicios": "bill_payment",
  "retiro_corresponsal": "correspondent_withdrawal",
  "retiro_cajero": "atm_withdrawal",
  "recarga_celular": "mobile_topup",
  "compra_tarjeta_virtual": "virtual_card_purchase",
}
CHANNELS = {"app": "app", "corresponsal": "correspondent", "cajero": "atm"}
DESTINATION_TYPES = {
  "cuenta_yuma": "yuma_account",
  "otra_entidad": "other_bank",
  "comercio": "merchant",
  "corresponsal": "correspondent",
  "cajero": "atm",
  "servicio": "utility",
  "operador": "carrier",
}
DECISIONS = {"approve": "aprobar", "challenge": "desafiar", "hold": "retener", "reject": "rechazar"}
BOGOTA_OFFSET = "-05:00"


def to_score_request(tx: dict) -> dict:
  return {
    "transaction_id": tx["id_transaccion"],
    "occurred_at": tx["fecha_hora"].replace(" ", "T") + BOGOTA_OFFSET,
    "customer_id": tx["id_cliente"],
    "operation_type": OPERATION_TYPES[tx["tipo_operacion"]],
    "channel": CHANNELS[tx["canal"]],
    "amount": tx["monto_cop"],
    "balance_before": tx["saldo_antes_cop"],
    "destination_id": tx["id_destino"],
    "destination_type": DESTINATION_TYPES[tx["tipo_destino"]],
    "new_destination": bool(tx["destino_nuevo"]),
    "device_id": tx["id_dispositivo"],
    "new_device": bool(tx["dispositivo_nuevo"]),
    "password_change_24h": bool(tx["cambio_clave_24h"]),
    "sim_change_48h": bool(tx["cambio_sim_48h"]),
    "ip_department": tx["departamento_ip"],
    "ip_department_mismatch": bool(tx["ip_departamento_distinto"]),
    "account_age_days": tx["antiguedad_cuenta_dias"],
  }


def to_sandbox_decision(response: dict) -> dict:
  return {
    "id_transaccion": response["transaction_id"],
    "decision": DECISIONS[response["action"]],
    "puntaje": response["score"],
    "razones": [r["text"] for r in response["reasons"]],
  }
