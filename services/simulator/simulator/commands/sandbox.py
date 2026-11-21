import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from simulator.settings import API_URL, OUT_DIR, SANDBOX_URL

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
  "cuenta_yuma": "yuma_account", "otra_entidad": "other_bank", "comercio": "merchant",
  "corresponsal": "correspondent", "cajero": "atm", "servicio": "utility", "operador": "carrier",
}
DECISIONS = {"approve": "aprobar", "challenge": "desafiar", "hold": "retener", "reject": "rechazar"}


def to_score_request(tx: dict) -> dict:
  return {
    "transaction_id": tx["id_transaccion"],
    "occurred_at": tx["fecha_hora"].replace(" ", "T") + "-05:00",
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


def decide(api: httpx.Client, sandbox: httpx.Client, tx: dict) -> str:
  response = api.post("/score", json=to_score_request(tx))
  response.raise_for_status()
  body = response.json()
  sandbox.post(
    "/v1/decisiones",
    json={
      "id_transaccion": body["transaction_id"],
      "decision": DECISIONS[body["action"]],
      "puntaje": body["score"],
      "razones": [r["text"] for r in body["reasons"]],
    },
  ).raise_for_status()
  return body["action"]


def run_sandbox(args: argparse.Namespace) -> None:
  with httpx.Client(base_url=API_URL, timeout=10) as api, \
       httpx.Client(base_url=SANDBOX_URL, timeout=10) as sandbox, \
       ThreadPoolExecutor(args.workers) as pool:
    if args.reset:
      sandbox.post("/v1/reiniciar").raise_for_status()

    skipped = decided = 0
    actions: dict[str, int] = {}
    started = time.monotonic()
    while args.limit is None or decided < args.limit:
      batch = sandbox.get("/v1/transacciones/siguiente", params={"cantidad": args.workers}).json()
      if not batch["transacciones"]:
        break
      pending = [t for t in batch["transacciones"] if t["fecha_hora"] >= args.start]
      skipped += len(batch["transacciones"]) - len(pending)
      for action in pool.map(lambda t: decide(api, sandbox, t), pending):
        actions[action] = actions.get(action, 0) + 1
      decided += len(pending)
      if decided and decided % 1000 < len(pending):
        print(f"decided={decided} skipped={skipped} remaining={batch['restantes']}", flush=True)

    elapsed = time.monotonic() - started
    metrics = sandbox.get("/v1/metricas").json()

  report = {"start": args.start, "decided": decided, "skipped": skipped, "actions": actions,
            "elapsed_s": round(elapsed, 1), "sandbox_metrics": metrics}
  Path(OUT_DIR).mkdir(parents=True, exist_ok=True)
  (Path(OUT_DIR) / "sandbox_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
  print(json.dumps(report, indent=2, ensure_ascii=False))
