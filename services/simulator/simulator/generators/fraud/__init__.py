from simulator.generators.fraud.account_takeover import account_takeover
from simulator.generators.fraud.context import Context
from simulator.generators.fraud.mule_account import mule_account
from simulator.generators.fraud.qr_scam import qr_scam
from simulator.generators.fraud.sim_swap import sim_swap
from simulator.generators.fraud.social_engineering import social_engineering

SCENARIOS = {
  "account_takeover": account_takeover,
  "sim_swap": sim_swap,
  "social_engineering": social_engineering,
  "qr_scam": qr_scam,
  "mule_account": mule_account,
}
FRAUD_TYPES = list(SCENARIOS)

__all__ = ["Context", "FRAUD_TYPES", "SCENARIOS"]
