from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from backend.extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def set_password(self, password: str) -> None:
        """Hash and set the user password using Werkzeug."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify the password against the stored hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User id={self.id} email={self.email}>"


class PredictionHistory(db.Model):
    __tablename__ = "prediction_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    original_filename = db.Column(db.String(255), nullable=False)
    stored_image_path = db.Column(db.String(512), nullable=False)
    image_sha256 = db.Column(db.String(64), nullable=False, index=True)
    image_format = db.Column(db.String(20), nullable=False)
    image_width = db.Column(db.Integer, nullable=False)
    image_height = db.Column(db.Integer, nullable=False)
    predicted_label = db.Column(db.String(10), nullable=False)  # 'REAL' or 'FAKE'
    probability_real = db.Column(db.Float, nullable=False)
    probability_fake = db.Column(db.Float, nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    threshold_used = db.Column(db.Float, default=0.50, nullable=False)
    inference_time_ms = db.Column(db.Float, nullable=False)
    model_name = db.Column(db.String(120), nullable=False)
    model_version = db.Column(db.String(50), nullable=False)
    face_detected = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "predictions",
            lazy="dynamic",
            cascade="all, delete-orphan",
            order_by="PredictionHistory.created_at.desc()"
        )
    )

    def __repr__(self):
        return f"<PredictionHistory id={self.id} user_id={self.user_id} label={self.predicted_label}>"


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login user loader callback."""
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None
