from django.test import TestCase


class HealthEndpointTests(TestCase):
    def test_liveness_returns_request_id(self):
        response = self.client.get("/healthz", HTTP_X_REQUEST_ID="test-request-123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response["X-Request-ID"], "test-request-123")

    def test_readiness_checks_database(self):
        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")
        self.assertTrue(response["X-Request-ID"])

    def test_versioned_api_alias_is_available(self):
        response = self.client.get("/api/v1/doctors/")
        self.assertEqual(response.status_code, 200)
