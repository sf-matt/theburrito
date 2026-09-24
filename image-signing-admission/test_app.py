import unittest

from app import create_app


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_index(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "message": (
                    "Hello from the unsigned image-signing admission baseline!"
                )
            },
        )

    def test_unknown_path_is_not_found(self):
        response = self.client.get("/unknown")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
