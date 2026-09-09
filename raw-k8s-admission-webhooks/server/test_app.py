import unittest

from app import app


def admission_review(name: str, uid: str = "test-uid") -> dict:
    return {
        "request": {
            "uid": uid,
            "object": {
                "metadata": {
                    "name": name,
                }
            },
        }
    }


class AdmissionWebhookTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_denies_badpod_name(self):
        response = self.client.post("/validate", json=admission_review("badpod-test"))

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["response"]["uid"], "test-uid")
        self.assertFalse(body["response"]["allowed"])

    def test_allows_other_name(self):
        response = self.client.post("/validate", json=admission_review("goodpod"))

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["response"]["uid"], "test-uid")
        self.assertTrue(body["response"]["allowed"])


if __name__ == "__main__":
    unittest.main()
