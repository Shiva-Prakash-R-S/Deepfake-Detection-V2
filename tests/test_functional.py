import io
import pytest

from backend.app import create_app
from backend.extensions import db
from backend.db_models import User


# --------------------------------------------------
# TEST CONFIGURATION
# Uses SQLite instead of your development PostgreSQL DB
# --------------------------------------------------

class TestConfig:
    TESTING = True
    SECRET_KEY = "pytest-only-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False


# --------------------------------------------------
# FIXTURES
# --------------------------------------------------

@pytest.fixture()
def app(tmp_path):
    application = create_app(config_class=TestConfig)

    application.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")

    with application.app_context():
        db.create_all()

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def test_user(app):
    with app.app_context():
        user = User(
            full_name="Test User",
            email="testuser@example.com",
        )
        user.set_password("TestPass123")

        db.session.add(user)
        db.session.commit()

        return {
            "email": "testuser@example.com",
            "password": "TestPass123",
        }


def login(client, email, password):
    return client.post(
        "/login",
        data={
            "email": email,
            "password": password,
        },
        follow_redirects=True,
    )


# --------------------------------------------------
# 1. APPLICATION AND PUBLIC ROUTES
# --------------------------------------------------

def test_home_requires_login(client):
    response = client.get("/")
    assert response.status_code in (302, 401, 403)


def test_login_page_loads(client):
    response = client.get("/login")
    assert response.status_code == 200


def test_register_page_loads(client):
    response = client.get("/register")
    assert response.status_code == 200


def test_api_status(client):
    response = client.get("/api/status")

    assert response.status_code == 200

    data = response.get_json()
    assert data is not None
    assert data["status"] == "ready"
    assert "model" in data
    assert "version" in data


def test_unknown_route_returns_404(client):
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404


# --------------------------------------------------
# 2. REGISTRATION TESTS
# --------------------------------------------------

def test_register_valid_user(client, app):
    response = client.post(
        "/register",
        data={
            "full_name": "New Test User",
            "email": "newuser@example.com",
            "password": "StrongPass123",
            "confirm_password": "StrongPass123",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        user = User.query.filter_by(
            email="newuser@example.com"
        ).first()

        assert user is not None
        assert user.full_name == "New Test User"
        assert user.check_password("StrongPass123")



def test_register_normalizes_email(client, app):
    response = client.post(
        "/register",
        data={
            "full_name": "Email Test",
            "email": "NEWUSER@EXAMPLE.COM",
            "password": "StrongPass123",
            "confirm_password": "StrongPass123",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        user = User.query.filter_by(
            email="newuser@example.com"
        ).first()

        assert user is not None
        assert user.email == "newuser@example.com"


def test_register_rejects_duplicate_email(client, test_user, app):
    response = client.post(
        "/register",
        data={
            "full_name": "Duplicate User",
            "email": test_user["email"],
            "password": "AnotherPass123",
            "confirm_password": "AnotherPass123",
        },
    )

    assert response.status_code == 200

    with app.app_context():
        users = User.query.filter_by(
            email=test_user["email"]
        ).all()

        assert len(users) == 1


def test_register_rejects_weak_password(client, app):
    response = client.post(
        "/register",
        data={
            "full_name": "Weak Password User",
            "email": "weak@example.com",
            "password": "abc",
            "confirm_password": "abc",
        },
    )

    assert response.status_code == 200

    with app.app_context():
        user = User.query.filter_by(
            email="weak@example.com"
        ).first()

        assert user is None


def test_register_rejects_mismatched_passwords(client, app):
    response = client.post(
        "/register",
        data={
            "full_name": "Mismatch User",
            "email": "mismatch@example.com",
            "password": "StrongPass123",
            "confirm_password": "DifferentPass123",
        },
    )

    assert response.status_code == 200

    with app.app_context():
        user = User.query.filter_by(
            email="mismatch@example.com"
        ).first()

        assert user is None


# --------------------------------------------------
# 3. LOGIN TESTS
# --------------------------------------------------

def test_login_valid_credentials(client, test_user):
    response = login(
        client,
        test_user["email"],
        test_user["password"],
    )

    assert response.status_code == 200

    # Successful login should allow access to the dashboard.
    dashboard = client.get("/")
    assert dashboard.status_code == 200


def test_login_invalid_password(client, test_user):
    response = client.post(
        "/login",
        data={
            "email": test_user["email"],
            "password": "WrongPass123",
        },
    )

    assert response.status_code == 200
    assert b"Invalid email address or password" in response.data

    dashboard = client.get("/")
    assert dashboard.status_code in (302, 401, 403)


def test_login_unknown_email(client):
    response = client.post(
        "/login",
        data={
            "email": "unknown@example.com",
            "password": "SomePass123",
        },
    )

    assert response.status_code == 200
    assert b"Invalid email address or password" in response.data


def test_login_rejects_external_redirect(client, test_user):
    response = client.post(
        "/login?next=https://evil.example",
        data={
            "email": test_user["email"],
            "password": test_user["password"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "evil.example" not in response.headers.get("Location", "")


# --------------------------------------------------
# 4. LOGOUT AND SESSION PROTECTION
# --------------------------------------------------

def test_logout_ends_session(client, test_user):
    login(client, test_user["email"], test_user["password"])

    response = client.post("/logout", follow_redirects=True)
    assert response.status_code == 200

    dashboard = client.get("/")
    assert dashboard.status_code in (302, 401, 403)


def test_change_password_requires_login(client):
    response = client.get("/change-password")
    assert response.status_code in (302, 401, 403)


# --------------------------------------------------
# 5. CHANGE PASSWORD TESTS
# --------------------------------------------------

def test_change_password_success(client, app, test_user):
    login(client, test_user["email"], test_user["password"])

    response = client.post(
        "/change-password",
        data={
            "current_password": test_user["password"],
            "new_password": "UpdatedPass456",
            "confirm_new_password": "UpdatedPass456",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        user = User.query.filter_by(
            email=test_user["email"]
        ).first()

        assert user.check_password("UpdatedPass456")
        assert not user.check_password(test_user["password"])


def test_change_password_rejects_wrong_current_password(
    client, app, test_user
):
    login(client, test_user["email"], test_user["password"])

    response = client.post(
        "/change-password",
        data={
            "current_password": "IncorrectPass123",
            "new_password": "UpdatedPass456",
            "confirm_new_password": "UpdatedPass456",
        },
    )

    assert response.status_code == 200

    with app.app_context():
        user = User.query.filter_by(
            email=test_user["email"]
        ).first()

        assert user.check_password(test_user["password"])
        assert not user.check_password("UpdatedPass456")


def test_change_password_rejects_reusing_password(
    client, app, test_user
):
    login(client, test_user["email"], test_user["password"])

    response = client.post(
        "/change-password",
        data={
            "current_password": test_user["password"],
            "new_password": test_user["password"],
            "confirm_new_password": test_user["password"],
        },
    )

    assert response.status_code == 200

    with app.app_context():
        user = User.query.filter_by(
            email=test_user["email"]
        ).first()

        assert user.check_password(test_user["password"])


# --------------------------------------------------
# 6. PREDICTION ACCESS TESTS
# --------------------------------------------------

def test_prediction_requires_login(client):
    response = client.post("/predict")

    assert response.status_code == 401


def test_prediction_rejects_missing_image(client, test_user):
    login(client, test_user["email"], test_user["password"])

    response = client.post("/predict", data={})

    assert response.status_code == 400


def test_prediction_rejects_invalid_file(client, test_user):
    login(client, test_user["email"], test_user["password"])

    response = client.post(
        "/predict",
        data={
            "image": (
                io.BytesIO(b"This is not an image"),
                "not_an_image.txt",
            )
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400