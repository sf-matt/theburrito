import unittest
from unittest.mock import patch

from app import create_app


class AppTestCase(unittest.TestCase):
    def test_index(self):
        with patch.dict("os.environ", {}, clear=True):
            client = create_app().test_client()

            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(), {"message": "Hello from CloudSecBurrito!"}
        )

    def test_unknown_path_is_not_found(self):
        response = create_app().test_client().get("/unknown")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
