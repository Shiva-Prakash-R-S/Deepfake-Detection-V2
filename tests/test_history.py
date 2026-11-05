import os
import io
import shutil
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

from backend.app import create_app
from backend.extensions import db
from backend.db_models import User, PredictionHistory
from backend.storage import resolve_stored_image_path


class TestHistoryConfig:
    TESTING = True
    SECRET_KEY = "test-secret-key-history"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    SERVER_NAME = "localhost"


class PredictionHistoryTestCase(unittest.TestCase):
    def setUp(self):
        # Create a dedicated temp directory for uploads in tests
        self.temp_upload_dir = tempfile.mkdtemp()

        class CustomConfig(TestHistoryConfig):
            UPLOAD_FOLDER = self.temp_upload_dir

        self.app = create_app(CustomConfig)
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Create User A
        self.user_a = User(full_name="Alice Analyst", email="alice@example.com")
        self.user_a.set_password("Password123")
        db.session.add(self.user_a)

        # Create User B
        self.user_b = User(full_name="Bob Investigator", email="bob@example.com")
        self.user_b.set_password("Password456")
        db.session.add(self.user_b)

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        shutil.rmtree(self.temp_upload_dir, ignore_errors=True)

    def _login(self, email, password):
        return self.client.post("/login", data={
            "email": email,
            "password": password
        }, follow_redirects=True)

    def _create_sample_image(self, width=224, height=224, color="blue", fmt="JPEG"):
        buf = io.BytesIO()
        img = Image.new("RGB", (width, height), color=color)
        img.save(buf, format=fmt)
        buf.seek(0)
        return buf

    # 1. Successful prediction history insertion
    def test_01_prediction_history_insertion(self):
        self._login("alice@example.com", "Password123")

        img_buf = self._create_sample_image(250, 250, "red", "JPEG")
        response = self.client.post(
            "/predict",
            data={"image": (img_buf, "red_sample.jpg")},
            content_type="multipart/form-data"
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("saved"))
        self.assertIn("prediction_id", data)

        record = PredictionHistory.query.get(data["prediction_id"])
        self.assertIsNotNone(record)

    # 2. Correct user ID association
    def test_02_correct_user_id_association(self):
        self._login("alice@example.com", "Password123")

        img_buf = self._create_sample_image()
        response = self.client.post(
            "/predict",
            data={"image": (img_buf, "alice_photo.jpg")},
            content_type="multipart/form-data"
        )
        data = response.get_json()
        record = PredictionHistory.query.get(data["prediction_id"])

        self.assertEqual(record.user_id, self.user_a.id)
        self.assertNotEqual(record.user_id, self.user_b.id)

    # 3. Prediction details saved accurately
    def test_03_prediction_details_saved_accurately(self):
        self._login("alice@example.com", "Password123")

        img_buf = self._create_sample_image(300, 200, "green", "PNG")
        response = self.client.post(
            "/predict",
            data={"image": (img_buf, "green_leaf.png")},
            content_type="multipart/form-data"
        )
        data = response.get_json()
        record = PredictionHistory.query.get(data["prediction_id"])

        self.assertEqual(record.original_filename, "green_leaf.png")
        self.assertEqual(record.image_width, 300)
        self.assertEqual(record.image_height, 200)
        self.assertEqual(record.image_format, "PNG")
        self.assertEqual(record.predicted_label, data["prediction"].upper())
        self.assertAlmostEqual(record.confidence, data["confidence"], places=2)
        self.assertAlmostEqual(record.probability_fake, data["fake_probability"], places=2)
        self.assertAlmostEqual(record.probability_real, data["real_probability"], places=2)
        self.assertEqual(record.threshold_used, 0.50)
        self.assertGreater(record.inference_time_ms, 0)
        self.assertEqual(record.model_name, "EfficientNet-B0 + FFT + Attention V4")
        self.assertEqual(record.model_version, "4.0")

    # 4. Uploaded image successfully stored
    def test_04_uploaded_image_stored_securely(self):
        self._login("alice@example.com", "Password123")

        img_buf = self._create_sample_image(150, 150, "purple", "JPEG")
        response = self.client.post(
            "/predict",
            data={"image": (img_buf, "test_store.jpg")},
            content_type="multipart/form-data"
        )
        data = response.get_json()
        record = PredictionHistory.query.get(data["prediction_id"])

        # Check path exists on disk within temp upload dir
        abs_path = resolve_stored_image_path(record.stored_image_path)
        self.assertTrue(os.path.exists(abs_path))
        self.assertIn(f"user_{self.user_a.id}_", os.path.basename(abs_path))
        self.assertEqual(len(record.image_sha256), 64)

    # 5. History page displays only current user's records
    def test_05_history_page_displays_current_user_records(self):
        # Alice creates a record
        self._login("alice@example.com", "Password123")
        img_a = self._create_sample_image()
        res_a = self.client.post(
            "/predict",
            data={"image": (img_a, "alice_secret.jpg")},
            content_type="multipart/form-data"
        )
        self.client.get("/logout")

        # Bob creates a record
        self._login("bob@example.com", "Password456")
        img_b = self._create_sample_image()
        res_b = self.client.post(
            "/predict",
            data={"image": (img_b, "bob_secret.jpg")},
            content_type="multipart/form-data"
        )

        # Check Bob's history view
        resp_bob = self.client.get("/history")
        self.assertEqual(resp_bob.status_code, 200)
        self.assertIn(b"bob_secret.jpg", resp_bob.data)
        self.assertNotIn(b"alice_secret.jpg", resp_bob.data)

        # Check Alice's history view
        self.client.get("/logout")
        self._login("alice@example.com", "Password123")
        resp_alice = self.client.get("/history")
        self.assertEqual(resp_alice.status_code, 200)
        self.assertIn(b"alice_secret.jpg", resp_alice.data)
        self.assertNotIn(b"bob_secret.jpg", resp_alice.data)

    # 6. Unauthenticated history access is rejected
    def test_06_unauthenticated_history_access_rejected(self):
        response = self.client.get("/history", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

        resp_detail = self.client.get("/history/1", follow_redirects=False)
        self.assertEqual(resp_detail.status_code, 302)

    # 7. User A cannot view User B's prediction
    def test_07_user_a_cannot_view_user_b_prediction(self):
        # Bob creates a record
        self._login("bob@example.com", "Password456")
        img_b = self._create_sample_image()
        res = self.client.post(
            "/predict",
            data={"image": (img_b, "bob_classified.jpg")},
            content_type="multipart/form-data"
        )
        bob_pred_id = res.get_json()["prediction_id"]
        self.client.get("/logout")

        # Alice attempts to inspect Bob's prediction
        self._login("alice@example.com", "Password123")
        resp = self.client.get(f"/history/{bob_pred_id}")
        self.assertEqual(resp.status_code, 404)

    # 8. User A cannot download User B's report
    def test_08_user_a_cannot_download_user_b_report(self):
        # Bob creates a record
        self._login("bob@example.com", "Password456")
        img_b = self._create_sample_image()
        res = self.client.post(
            "/predict",
            data={"image": (img_b, "bob_report.jpg")},
            content_type="multipart/form-data"
        )
        bob_pred_id = res.get_json()["prediction_id"]
        self.client.get("/logout")

        # Alice attempts to download Bob's PDF
        self._login("alice@example.com", "Password123")
        resp = self.client.get(f"/history/{bob_pred_id}/download")
        self.assertEqual(resp.status_code, 404)

    # 9. User A cannot retrieve User B's uploaded image
    def test_09_user_a_cannot_retrieve_user_b_image(self):
        # Bob creates a record
        self._login("bob@example.com", "Password456")
        img_b = self._create_sample_image()
        res = self.client.post(
            "/predict",
            data={"image": (img_b, "bob_private.jpg")},
            content_type="multipart/form-data"
        )
        bob_pred_id = res.get_json()["prediction_id"]
        self.client.get("/logout")

        # Alice attempts to fetch Bob's image
        self._login("alice@example.com", "Password123")
        resp = self.client.get(f"/history/{bob_pred_id}/image")
        self.assertEqual(resp.status_code, 404)

    # 10. Correct PDF content and embedded image
    def test_10_pdf_report_content_and_embedded_image(self):
        self._login("alice@example.com", "Password123")
        img = self._create_sample_image()
        res = self.client.post(
            "/predict",
            data={"image": (img, "audit_image.jpg")},
            content_type="multipart/form-data"
        )
        pred_id = res.get_json()["prediction_id"]

        resp = self.client.get(f"/history/{pred_id}/download")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, "application/pdf")
        self.assertIn(f"attachment; filename=deepfake_report_{pred_id}.pdf", resp.headers.get("Content-Disposition", ""))
        self.assertTrue(resp.data.startswith(b"%PDF-"))
        self.assertGreater(len(resp.data), 1000)

    # 11. Failed database writes are handled safely
    def test_11_failed_db_write_handled_safely(self):
        self._login("alice@example.com", "Password123")
        img = self._create_sample_image()

        with patch.object(db.session, "commit", side_effect=Exception("Simulated DB Crash")):
            response = self.client.post(
                "/predict",
                data={"image": (img, "failure_test.jpg")},
                content_type="multipart/form-data"
            )
            self.assertEqual(response.status_code, 500)
            data = response.get_json()
            self.assertIn("Failed to persist", data["error"])

        # Confirm no orphan record was created
        record = PredictionHistory.query.filter_by(original_filename="failure_test.jpg").first()
        self.assertIsNone(record)

    # 12. Invalid image uploads are rejected
    def test_12_invalid_image_upload_rejected(self):
        self._login("alice@example.com", "Password123")

        # Send raw text instead of image
        fake_file = (io.BytesIO(b"This is a text file not an image"), "malicious.txt")
        response = self.client.post(
            "/predict",
            data={"image": fake_file},
            content_type="multipart/form-data"
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

        # Confirm nothing saved
        count = PredictionHistory.query.count()
        self.assertEqual(count, 0)

    # 13. Pagination works
    def test_13_pagination_works(self):
        self._login("alice@example.com", "Password123")

        # Create 12 prediction records directly
        for i in range(12):
            rec = PredictionHistory(
                user_id=self.user_a.id,
                original_filename=f"batch_img_{i}.jpg",
                stored_image_path=f"predictions/user_{self.user_a.id}_test_{i}.jpg",
                image_sha256="0" * 64,
                image_format="JPEG",
                image_width=224,
                image_height=224,
                predicted_label="REAL",
                probability_real=95.0,
                probability_fake=5.0,
                confidence=95.0,
                threshold_used=0.50,
                inference_time_ms=120.0,
                model_name="EfficientNet-B0 + FFT + Attention V4",
                model_version="4.0",
                face_detected=True
            )
            db.session.add(rec)
        db.session.commit()

        # Page 1 (per_page=10)
        resp_p1 = self.client.get("/history?page=1")
        self.assertEqual(resp_p1.status_code, 200)
        self.assertIn(b"batch_img_11.jpg", resp_p1.data)
        self.assertIn(b"Showing page 1 of 2", resp_p1.data)

        # Page 2
        resp_p2 = self.client.get("/history?page=2")
        self.assertEqual(resp_p2.status_code, 200)
        self.assertIn(b"Showing page 2 of 2", resp_p2.data)

    # 14. Existing login and detection flow pass
    def test_14_existing_login_and_detection_pass(self):
        # Direct check that user can log in and view dashboard
        login_resp = self.client.post("/login", data={
            "email": "alice@example.com",
            "password": "Password123"
        }, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)
        self.assertIn(b"Forensic Analysis Workbench", login_resp.data)


if __name__ == "__main__":
    unittest.main()
