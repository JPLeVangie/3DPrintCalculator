import tempfile
import unittest
from pathlib import Path

import app as calculator


class AppTests(unittest.TestCase):
    def setUp(self):
        self.database = tempfile.TemporaryDirectory()
        calculator.DB_PATH = Path(self.database.name) / "test.sqlite"
        calculator.init_db()
        calculator.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = calculator.app.test_client()

    def tearDown(self):
        self.database.cleanup()

    def test_calculate_covers_cost_components_quantity_and_margins(self):
        result = calculator.calculate({
            "quantity": 2,
            "material_lines": [
                {"name": "PLA", "grams": 100, "cost_per_gram": 0.05},
                {"name": "Resin", "volume_ml": 10, "density": 1.1, "cost_per_gram": 0.10},
            ],
            "waste_rate": 10,
            "print_hours": 2,
            "print_minutes": 30,
            "power_watts": 120,
            "electricity_rate": 0.16,
            "printer_cost": 800,
            "printer_life_hours": 3000,
            "maintenance_rate": 0.05,
            "labor_hours": 1,
            "labor_minutes": 30,
            "labor_rate": 20,
            "hardware": 3,
            "packaging": 2,
            "setup_cost": 1.5,
            "overhead_rate": 15,
            "failure_rate": 20,
            "tax_rate": 8,
            "custom_margin": 50,
        })

        self.assertEqual(result["quantity"], 2)
        self.assertEqual(result["hours"], 2.5)
        self.assertEqual(result["weight"], 222.0)
        self.assertEqual(result["unit_weight"], 111.0)
        self.assertEqual(result["total"], 126.21)
        self.assertEqual(result["unit_cost"], 63.11)
        self.assertEqual(result["before_tax"], 116.86)
        self.assertEqual(result["tax"], 9.35)
        self.assertEqual(result["breakdown"], {
            "Material": 13.42,
            "Labor": 60.0,
            "Electricity": 0.1,
            "Depreciation": 1.33,
            "Maintenance": 0.25,
            "Failure reserve": 15.02,
            "Hardware": 6.0,
            "Packaging": 4.0,
            "Setup": 1.5,
            "Overhead": 15.24,
            "Tax": 9.35,
        })
        self.assertEqual(result["prices"], {
            "25": 84.14,
            "40": 105.18,
            "60": 157.76,
            "80": 315.53,
            "custom": 126.21,
        })

    def test_calculate_converts_resin_volume_to_grams(self):
        result = calculator.calculate({
            "material_lines": [{
                "name": "Resin",
                "volume_ml": 12.5,
                "density": 1.1,
                "cost_per_gram": 0.10,
            }]
        })

        self.assertEqual(result["weight"], 13.75)
        self.assertEqual(result["volume"], 12.5)
        self.assertEqual(result["lines"], [{"name": "Resin", "grams": 13.75, "cost": 1.38}])

    def test_api_calculate_returns_calculation(self):
        response = self.client.post("/api/calculate", json={"material_lines": [{"grams": 10, "cost_per_gram": 0.05}]})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["total"], 0.58)

    def test_api_calculate_rejects_invalid_json(self):
        response = self.client.post("/api/calculate", data="{not-json", content_type="application/json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "JSON object required."})

    def test_healthz(self):
        response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_anonymous_persistence_endpoints_require_authentication(self):
        endpoints = ("/api/preferences", "/api/material-presets", "/api/printer-profiles", "/api/quotes")
        for endpoint in endpoints:
            for method in ("get", "post"):
                with self.subTest(endpoint=endpoint, method=method):
                    response = getattr(self.client, method)(endpoint, json={"name": "anonymous"})
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.get_json(), {"error": "Sign in is required to save data."})


if __name__ == "__main__":
    unittest.main()