from simulator.generators.fraud.account_takeover import account_takeover
from simulator.generators.fraud.context import Context
from simulator.generators.fraud.fake_qr import fake_qr
from simulator.generators.fraud.mule_account import mule_account
from simulator.generators.fraud.sim_swap import sim_swap

FRAUD_TYPES = ["account_takeover", "sim_swap", "mule_account", "fake_qr"]
SCENARIO_WEIGHTS = [0.40, 0.35, 0.15, 0.10]
AVG_FRAUD_TX_PER_SCENARIO = 7.8

SCENARIOS = {
  "account_takeover": account_takeover,
  "sim_swap": sim_swap,
  "mule_account": mule_account,
  "fake_qr": fake_qr,
}

__all__ = [
  "AVG_FRAUD_TX_PER_SCENARIO",
  "Context",
  "FRAUD_TYPES",
  "SCENARIOS",
  "SCENARIO_WEIGHTS",
]
