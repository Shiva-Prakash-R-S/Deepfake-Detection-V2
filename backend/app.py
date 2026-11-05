import os
import sys
from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    send_from_directory,
    flash
)
from flask_cors import CORS
from flask_login import login_required, current_user

# ============================================================
# PROJECT ROOT CONFIGURATION
# ============================================================

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import io
from backend.config import Config
from backend.extensions import db, migrate, login_manager, csrf
from backend.db_models import User, PredictionHistory
from backend.auth import auth_bp
from backend.history import history_bp
from backend.storage import validate_and_save_image, remove_stored_image

try:
    from backend.predict import predict_image
except ImportError:
    from predict import predict_image

FRONTEND_DIST = os.path.join(PROJECT_ROOT, "frontend", "dist")
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "templates")


def create_app(config_class=Config):
    """Application factory for DeepFake Detection V2."""
    app = Flask(
        __name__,
        template_folder=TEMPLATES_DIR,
        static_folder=STATIC_DIR,
        static_url_path="/static"
    )
    app.config.from_object(config_class)

    # Initialize Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    CORS(app)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(history_bp)

    # Handle unauthorized access (JSON 401 for API, redirect to login for web)
    @login_manager.unauthorized_handler
    def unauthorized():
        if (
            request.path == "/predict"
            or request.path.startswith("/api/")
            or request.is_json
            or "application/json" in request.headers.get("Accept", "")
        ):
            return jsonify({
                "error": "Authentication required. Please log in to perform predictions."
            }), 401
        flash("Please log in to access this page.", "info")
        return redirect(url_for("auth.login", next=request.url))

    # ============================================================
    # ROUTES
    # ============================================================

    @app.route("/", methods=["GET"])
    def home():
        """Protected home / dashboard route."""
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        return render_template("dashboard.html")

    @app.route("/api/status", methods=["GET"])
    def api_status():
        """Public API health and model version status."""
        return jsonify({
            "message": "Deepfake Detection API Running",
            "version": "4.0",
            "model": "EfficientNet-B0 + FFT + Attention V4",
            "status": "ready"
        })

    @app.route("/predict", methods=["POST"])
    @login_required
    @csrf.exempt
    def predict():
        """
        Protected image inference route.
        Validates image, securely stores file, runs inference,
        and saves prediction record to PostgreSQL.
        """
        if "image" not in request.files:
            return jsonify({
                "error": "No image file provided. Field name must be 'image'."
            }), 400

        image_file = request.files["image"]

        if image_file.filename == "":
            return jsonify({
                "error": "No image selected."
            }), 400

        # 1. Validate image format and save to secure storage
        try:
            (
                stored_relative_path,
                sha256_hash,
                img_format,
                width,
                height,
                raw_bytes,
                safe_original_name
            ) = validate_and_save_image(image_file, current_user.id)
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except Exception as e:
            return jsonify({"error": f"Image processing failed: {str(e)}"}), 500

        # 2. Run inference on image bytes
        try:
            result = predict_image(io.BytesIO(raw_bytes))
        except Exception as e:
            remove_stored_image(stored_relative_path)
            return jsonify({
                "error": f"Prediction failed: {str(e)}"
            }), 500

        if "error" in result:
            remove_stored_image(stored_relative_path)
            return jsonify(result), 400

        # 3. Save prediction history to PostgreSQL
        try:
            predicted_label = result["prediction"].upper()
            prob_real = float(result["real_probability"])
            prob_fake = float(result["fake_probability"])
            conf = float(result["confidence"])
            threshold_used = 0.50
            inf_time_ms = round(float(result["inference_time"]) * 1000.0, 2)
            model_name = result.get("model", "EfficientNet-B0 + FFT + Attention V4")
            model_ver = "4.0"
            face_det = bool(result.get("face_detected", False))

            history_entry = PredictionHistory(
                user_id=current_user.id,
                original_filename=safe_original_name,
                stored_image_path=stored_relative_path,
                image_sha256=sha256_hash,
                image_format=img_format,
                image_width=width,
                image_height=height,
                predicted_label=predicted_label,
                probability_real=prob_real,
                probability_fake=prob_fake,
                confidence=conf,
                threshold_used=threshold_used,
                inference_time_ms=inf_time_ms,
                model_name=model_name,
                model_version=model_ver,
                face_detected=face_det
            )
            db.session.add(history_entry)
            db.session.commit()

            result["prediction_id"] = history_entry.id
            result["saved"] = True
            result["details_url"] = url_for("history.detail", prediction_id=history_entry.id)
            result["download_url"] = url_for("history.download_report", prediction_id=history_entry.id)
            result["image_url"] = url_for("history.serve_image", prediction_id=history_entry.id)
        except Exception as db_err:
            db.session.rollback()
            remove_stored_image(stored_relative_path)
            app.logger.error(f"Failed to record prediction in DB: {str(db_err)}")
            return jsonify({
                "error": "Failed to persist prediction history in database."
            }), 500

        return jsonify(result)

    # Serve static assets from frontend/dist if built
    @app.route("/assets/<path:path>", methods=["GET"])
    def serve_frontend_assets(path):
        assets_dir = os.path.join(FRONTEND_DIST, "assets")
        if os.path.exists(assets_dir):
            return send_from_directory(assets_dir, path)
        return jsonify({"error": "Asset not found"}), 404

    return app


# Default application instance
app = create_app()


# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("  [+] Deepfake Detection AI - Web Application")
    print("=" * 65)
    print("  * Login Page:          http://127.0.0.1:5000/login")
    print("  * Register Page:       http://127.0.0.1:5000/register")
    print("  * Dashboard Link:      http://127.0.0.1:5000/")
    print("=" * 65 + "\n")
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )