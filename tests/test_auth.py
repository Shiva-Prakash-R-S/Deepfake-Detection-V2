import os
import unittest
from unittest.mock import patch
from werkzeug.security import check_password_hash
from sqlalchemy.exc import OperationalError

from backend.app import create_app
from backend.extensions import db
from backend.db_models import User


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret-key-12345"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    SERVER_NAME = "localhost"


class TestConfigWithCSRF(TestConfig):
    WTF_CSRF_ENABLED = True


class AuthenticationSystemTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # 1. Successful registration
    def test_01_successful_registration(self):
        response = self.client.post("/register", data={
            "full_name": "Test User",
            "email": "test@example.com",
            "password": "Password123",
            "confirm_password": "Password123"
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Account created successfully", response.data)

        user = User.query.filter_by(email="test@example.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.full_name, "Test User")

    # 2. Duplicate email rejection
    def test_02_duplicate_email_rejection(self):
        # Register first user
        self.client.post("/register", data={
            "full_name": "First User",
            "email": "duplicate@example.com",
            "password": "Password123",
            "confirm_password": "Password123"
        }, follow_redirects=True)

        # Attempt to register second user with same email (different case)
        response = self.client.post("/register", data={
            "full_name": "Second User",
            "email": "DUPLICATE@example.com",
            "password": "Password123",
            "confirm_password": "Password123"
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"already exists", response.data)
        users = User.query.filter_by(email="duplicate@example.com").all()
        self.assertEqual(len(users), 1)

    # 3. Password hashing
    def test_03_password_hashing(self):
        raw_password = "SecurePassword123"
        user = User(full_name="Hash Check", email="hash@example.com")
        user.set_password(raw_password)

        self.assertNotEqual(user.password_hash, raw_password)
        self.assertTrue(user.password_hash.startswith("scrypt:") or user.password_hash.startswith("pbkdf2:"))
        self.assertTrue(user.check_password(raw_password))
        self.assertFalse(user.check_password("WrongPassword123"))

    # 4. Successful login
    def test_04_successful_login(self):
        user = User(full_name="Login User", email="login@example.com")
        user.set_password("Password123")
        db.session.add(user)
        db.session.commit()

        response = self.client.post("/login", data={
            "email": "login@example.com",
            "password": "Password123"
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome back, Login User!", response.data)
        self.assertIn(b"Forensic Analysis Workbench", response.data)

    # 5. Invalid login
    def test_05_invalid_login(self):
        user = User(full_name="Valid User", email="valid@example.com")
        user.set_password("Password123")
        db.session.add(user)
        db.session.commit()

        # Wrong password
        response = self.client.post("/login", data={
            "email": "valid@example.com",
            "password": "IncorrectPassword123"
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid email address or password", response.data)

        # Non-existent email
        response = self.client.post("/login", data={
            "email": "nonexistent@example.com",
            "password": "Password123"
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid email address or password", response.data)

    # 6. Logout
    def test_06_logout(self):
        user = User(full_name="Logout User", email="logout@example.com")
        user.set_password("Password123")
        db.session.add(user)
        db.session.commit()

        # Log in first
        self.client.post("/login", data={
            "email": "logout@example.com",
            "password": "Password123"
        }, follow_redirects=True)

        # Log out
        response = self.client.post("/logout", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"successfully logged out", response.data)

        # Confirm session is cleared by checking protected route
        protected_response = self.client.get("/", follow_redirects=False)
        self.assertEqual(protected_response.status_code, 302)
        self.assertIn("/login", protected_response.location)

    # 7. Protected-route access
    def test_07_protected_route_access(self):
        # Unauthenticated access to root dashboard redirects to login
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

        # Unauthenticated access to /change-password redirects to login
        response = self.client.get("/change-password", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

        # Unauthenticated access to /predict returns 401 JSON
        api_response = self.client.post("/predict")
        self.assertEqual(api_response.status_code, 401)
        self.assertIn(b"Authentication required", api_response.data)

    # 8. Change password with correct current password
    def test_08_change_password_success(self):
        user = User(full_name="Change Pass User", email="changepass@example.com")
        user.set_password("OldPassword123")
        db.session.add(user)
        db.session.commit()

        self.client.post("/login", data={
            "email": "changepass@example.com",
            "password": "OldPassword123"
        }, follow_redirects=True)

        response = self.client.post("/change-password", data={
            "current_password": "OldPassword123",
            "new_password": "NewPassword456",
            "confirm_new_password": "NewPassword456"
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"password has been updated successfully", response.data)

        # Verify new password works
        updated_user = User.query.filter_by(email="changepass@example.com").first()
        self.assertTrue(updated_user.check_password("NewPassword456"))
        self.assertFalse(updated_user.check_password("OldPassword123"))

    # 9. Change password with wrong current password
    def test_09_change_password_wrong_current(self):
        user = User(full_name="Wrong Pass User", email="wrongcurr@example.com")
        user.set_password("OldPassword123")
        db.session.add(user)
        db.session.commit()

        self.client.post("/login", data={
            "email": "wrongcurr@example.com",
            "password": "OldPassword123"
        }, follow_redirects=True)

        response = self.client.post("/change-password", data={
            "current_password": "WrongCurrentPassword123",
            "new_password": "NewPassword456",
            "confirm_new_password": "NewPassword456"
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Incorrect current password", response.data)

    # 10. Password mismatch
    def test_10_password_mismatch(self):
        # Mismatch in registration
        response = self.client.post("/register", data={
            "full_name": "Mismatch User",
            "email": "mismatch@example.com",
            "password": "Password123",
            "confirm_password": "Password999"
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Passwords must match", response.data)

    # 11. Database error handling
    def test_11_database_error_handling(self):
        with patch.object(db.session, "commit", side_effect=OperationalError("Simulated DB Crash", None, None)):
            response = self.client.post("/register", data={
                "full_name": "Error User",
                "email": "error@example.com",
                "password": "Password123",
                "confirm_password": "Password123"
            }, follow_redirects=True)

            self.assertEqual(response.status_code, 200)
            self.assertIn(b"database error occurred", response.data)

    # 12. CSRF protection
    def test_12_csrf_protection(self):
        csrf_app = create_app(TestConfigWithCSRF)
        csrf_client = csrf_app.test_client()

        with csrf_app.app_context():
            db.create_all()
            # Attempt POST request without CSRF token
            response = csrf_client.post("/register", data={
                "full_name": "CSRF Attacker",
                "email": "csrf@example.com",
                "password": "Password123",
                "confirm_password": "Password123"
            })

            # Must be rejected with HTTP 400 Bad Request
            self.assertEqual(response.status_code, 400)
            db.drop_all()


if __name__ == "__main__":
    unittest.main()
