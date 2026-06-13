import json
import unittest
from pathlib import Path
from unittest.mock import patch


class ApiTests(unittest.TestCase):
    def test_healthz_endpoint(self):
        try:
            from fastapi.testclient import TestClient
            from gridwise_optimizer.api import app
        except ModuleNotFoundError as exc:
            self.skipTest(f"API dependency not installed: {exc.name}")

        client = TestClient(app)

        response = client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_optimize_endpoint(self):
        try:
            from fastapi.testclient import TestClient
            from gridwise_optimizer.api import app
        except ModuleNotFoundError as exc:
            self.skipTest(f"API dependency not installed: {exc.name}")

        sample_path = Path(__file__).parents[1] / "samples" / "optimizer_request.json"
        client = TestClient(app)

        for path in ("/optimize", "/optimise"):
            response = client.post(path, json=json.loads(sample_path.read_text()))

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body["feasible"])
            self.assertEqual(len(body["plan"]), body["horizon_ticks"])

    def test_optimize_requires_api_key_when_configured(self):
        try:
            from fastapi.testclient import TestClient
            from gridwise_optimizer.api import app
        except ModuleNotFoundError as exc:
            self.skipTest(f"API dependency not installed: {exc.name}")

        sample_path = Path(__file__).parents[1] / "samples" / "optimizer_request.json"
        client = TestClient(app)

        with patch.dict("os.environ", {"OPTIMISER_API_KEY": "secret"}):
            response = client.post("/optimise", json=json.loads(sample_path.read_text()))

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
