import os
from pathlib import Path

import pandas as pd
import psycopg

DATA_DIR = Path(os.environ.get("CASE_DATA_DIR", "/data"))
TIMEZONE = "America/Bogota"

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
FRAUD_TYPES = {
  "toma_de_cuenta": "account_takeover",
  "sim_swapping": "sim_swap",
  "ingenieria_social": "social_engineering",
  "engano_qr": "qr_scam",
  "cuenta_mula": "mule_account",
}
EVENT_TYPES = {
  "inicio_sesion": "login",
  "registro_dispositivo": "device_registration",
  "cambio_clave": "password_change",
  "cambio_sim_detectado": "sim_change",
}
RESULTS = {"exitoso": "success", "fallido": "failed"}
CUSTOMER_TYPES = {"persona": "person", "microcomerciante": "microbusiness"}
ONBOARDING = {"app": "app", "corresponsal": "correspondent", "referido": "referral"}


def dsn() -> str:
  return (
    f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
    f"port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']} "
    f"dbname={os.environ['POSTGRES_DB']}"
  )


def read(name: str) -> pd.DataFrame:
  return pd.read_csv(DATA_DIR / name, encoding="utf-8-sig")


def local_time(series: pd.Series) -> pd.Series:
  return pd.to_datetime(series).dt.tz_localize(TIMEZONE)


def nullable(value):
  return None if pd.isna(value) else value


def copy_rows(cur, table: str, columns: list[str], rows) -> int:
  count = 0
  with cur.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as copy:
    for row in rows:
      copy.write_row([nullable(v) for v in row])
      count += 1
  return count


def main() -> None:
  customers = read("clientes.csv")
  events = read("eventos_app.csv")
  tx = read("transacciones.csv")
  rules = read("reglas_vigentes.csv")
  alerts = read("alertas.csv")

  customers["type"] = customers["tipo_cliente"].map(CUSTOMER_TYPES)
  customers["onboarding"] = customers["canal_vinculacion"].map(ONBOARDING)
  events["type"] = events["tipo_evento"].map(EVENT_TYPES)
  events["result"] = events["resultado"].map(RESULTS)
  events["ts"] = local_time(events["fecha_hora"])
  tx["ts"] = local_time(tx["fecha_hora"])
  tx["operation"] = tx["tipo_operacion"].map(OPERATION_TYPES)
  tx["channel_en"] = tx["canal"].map(CHANNELS)
  tx["destination"] = tx["tipo_destino"].map(DESTINATION_TYPES)
  tx["fraud"] = tx["modalidad_fraude"].map(FRAUD_TYPES)
  alerts["ts"] = local_time(alerts["fecha_hora_alerta"])

  with psycopg.connect(dsn()) as conn, conn.cursor() as cur:
    cur.execute(
      "TRUNCATE labels, alerts, baseline_decisions, decisions, legacy_alerts, legacy_rules, "
      "transactions, session_events, customers CASCADE"
    )
    n = copy_rows(
      cur, "customers",
      ["id", "type", "department", "age_range", "joined_on", "confirmed_mule", "onboarding_channel"],
      zip(customers.id_cliente, customers.type, customers.departamento, customers.rango_edad,
          customers.fecha_vinculacion, customers.cuenta_mula_confirmada.astype(bool),
          customers.onboarding),
    )
    print(f"customers: {n}")
    n = copy_rows(
      cur, "session_events",
      ["id", "customer_id", "type", "device_id", "os", "ip_department", "result", "occurred_at"],
      zip(events.id_evento, events.id_cliente, events.type, events.id_dispositivo,
          events.sistema_operativo, events.departamento_ip, events.result, events.ts),
    )
    print(f"session_events: {n}")
    n = copy_rows(
      cur, "transactions",
      ["id", "occurred_at", "customer_id", "operation_type", "channel", "amount", "balance_before",
       "destination_id", "destination_type", "new_destination", "device_id", "new_device",
       "password_change_24h", "sim_change_48h", "ip_department", "ip_department_mismatch",
       "account_age_days", "is_fraud", "fraud_type"],
      zip(tx.id_transaccion, tx.ts, tx.id_cliente, tx.operation, tx.channel_en, tx.monto_cop,
          tx.saldo_antes_cop, tx.id_destino, tx.destination, tx.destino_nuevo.astype(bool),
          tx.id_dispositivo, tx.dispositivo_nuevo.astype(bool), tx.cambio_clave_24h.astype(bool),
          tx.cambio_sim_48h.astype(bool), tx.departamento_ip,
          tx.ip_departamento_distinto.astype(bool), tx.antiguedad_cuenta_dias,
          tx.es_fraude.astype(bool), tx.fraud),
    )
    print(f"transactions: {n}")
    n = copy_rows(
      cur, "legacy_rules",
      ["id", "name", "description", "condition", "severity", "target_fraud", "last_modified"],
      zip(rules.id_regla, rules.nombre, rules.descripcion, rules.condicion, rules.severidad,
          rules.modalidad_objetivo, rules.ultima_modificacion),
    )
    print(f"legacy_rules: {n}")
    n = copy_rows(
      cur, "legacy_alerts",
      ["id", "transaction_id", "customer_id", "alerted_at", "rules_fired", "severity", "status",
       "review_minutes", "analyst_decision", "action"],
      zip(alerts.id_alerta, alerts.id_transaccion, alerts.id_cliente, alerts.ts,
          alerts.reglas_activadas, alerts.severidad, alerts.estado,
          alerts.minutos_hasta_revision.astype("Int64"), alerts.decision_analista, alerts.accion),
    )
    print(f"legacy_alerts: {n}")
    conn.commit()


if __name__ == "__main__":
  main()
