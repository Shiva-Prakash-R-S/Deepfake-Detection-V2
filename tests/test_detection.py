import os
import io
import unittest
from PIL import Image
from backend.app import create_app
from backend.extensions import db
from backend.db_models import User


class TestDetectionConfig:
    TESTING = True
    SECRET_KEY = "test-secret-key-detection"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False


class DetectionIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestDetectionConfig)
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Create user
        self.user = User(full_name="Forensic Analyst", email="analyst@example.com")
        self.user.set_password("Password123")
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_unauthenticated_predict_denied(self):
        # Create a dummy image
        img_byte_arr = io.BytesIO()
        Image.new("RGB", (224, 224), color="blue").save(img_byte_arr, format="JPEG")
        img_byte_arr.seek(0)

        data = {"image": (img_byte_arr, "test.jpg")}
        response = self.client.post("/predict", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 401)
        self.assertIn(b"Authentication required", response.data)

    def test_authenticated_predict_succeeds(self):
        # Log in
        self.client.post("/login", data={
            "email": "analyst@example.com",
            "password": "Password123"
        })

        # Send image to /predict
        img_byte_arr = io.BytesIO()
        Image.new("RGB", (224, 224), color="green").save(img_byte_arr, format="JPEG")
        img_byte_arr.seek(0)

        data = {"image": (img_byte_arr, "sample_test.jpg")}
        response = self.client.post("/predict", data=data, content_type="multipart/form-data")

        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIn("prediction", json_data)
        self.assertIn(json_data["prediction"], ["fake", "real"])
        self.assertIn("confidence", json_data)
        self.assertIn("fake_probability", json_data)
        self.assertIn("real_probability", json_data)
        self.assertIn("inference_time", json_data)
        self.assertEqual(json_data["model"], "EfficientNet-B0 + FFT + Attention V4")


if __name__ == "__main__":
    unittest.main()
