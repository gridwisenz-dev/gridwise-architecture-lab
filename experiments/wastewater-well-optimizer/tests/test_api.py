import json
import unittest
from pathlib import Path


class ApiTests(unittest.TestCase):
    def test_optimize_endpoint(self):
        try:
            from fastapi.testclient import TestClient
            from gridwise_optimizer.api import app
        except ModuleNotFoundError as exc:
            self.skipTest(f"API dependency not installed: {exc.name}")

        sample_path = Path(__file__).parents[1] / "samples" / "optimizer_request.json"
        client = TestClient(app)

        response = client.post("/optimize", json=json.loads(sample_path.read_text()))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["feasible"])
        self.assertEqual(len(body["plan"]), 12)


if __name__ == "__main__":
    unittest.main()

