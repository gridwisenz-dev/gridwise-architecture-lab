import json
import unittest
from pathlib import Path

from gridwise_optimizer.models import OptimizeRequest, PumpDecision, WellConfig, WellState
from gridwise_optimizer.optimizer import optimize
from gridwise_optimizer.simulator import SimulationError, simulate_tick


class OptimizerTests(unittest.TestCase):
    def test_sample_request_returns_feasible_plan(self):
        sample_path = Path(__file__).parents[1] / "samples" / "optimizer_request.json"
        request = OptimizeRequest.model_validate(json.loads(sample_path.read_text()))

        response = optimize(request)

        self.assertTrue(response.feasible)
        self.assertEqual(len(response.plan), request.horizon_ticks)
        self.assertGreaterEqual(response.total_energy_cost, 0)

    def test_simulator_rejects_offline_pump_with_rate(self):
        config = WellConfig(
            capacity=100,
            low_water_mark=20,
            high_water_mark=80,
            pumps=[{"id": "p1", "allowed_rates": [0, 1]}],
        )
        state = WellState(
            time="t0",
            volume=50,
            pumps=[{"id": "p1", "status": "Online", "rate": 0}],
        )
        decisions = [
            PumpDecision(
                pump_id="p1",
                change_status="Offline",
                status="Offline",
                rate=1,
            )
        ]

        with self.assertRaises(SimulationError):
            simulate_tick(config, state, decisions, inflow=1, next_time="t1")


if __name__ == "__main__":
    unittest.main()
