import os
from flask import (
    Blueprint,
    render_template,
    abort,
    send_file,
    request,
    flash,
    redirect,
    url_for,
    current_app
)
from flask_login import login_required, current_user

from backend.extensions import db
from backend.db_models import PredictionHistory
from backend.storage import resolve_stored_image_path
from backend.reports import generate_pdf_report

history_bp = Blueprint("history", __name__, url_prefix="/history")


@history_bp.route("", methods=["GET"])
@login_required
def list_history():
    """
    Paginated prediction history for the currently authenticated user only.
    Strictly isolated: never queries or displays records belonging to other users.
    """
    page = request.args.get("page", 1, type=int)
    per_page = 10

    pagination = (
        PredictionHistory.query
        .filter_by(user_id=current_user.id)
        .order_by(PredictionHistory.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return render_template(
        "history/list.html",
        predictions=pagination.items,
        pagination=pagination
    )


@history_bp.route("/<int:prediction_id>", methods=["GET"])
@login_required
def detail(prediction_id: int):
    """
    Detailed inspection report for a specific prediction.
    Strict ownership check: returns 404 if prediction doesn't exist or belongs to another user.
    """
    record = PredictionHistory.query.filter_by(
        id=prediction_id,
        user_id=current_user.id
    ).first()

    if record is None:
        abort(404)

    return render_template("history/detail.html", prediction=record)


@history_bp.route("/<int:prediction_id>/image", methods=["GET"])
@login_required
def serve_image(prediction_id: int):
    """
    Secure authenticated image-serving endpoint.
    Verifies ownership, guards against path traversal, and returns original image.
    """
    record = PredictionHistory.query.filter_by(
        id=prediction_id,
        user_id=current_user.id
    ).first()

    if record is None:
        abort(404)

    try:
        abs_path = resolve_stored_image_path(record.stored_image_path)
    except (FileNotFoundError, PermissionError, ValueError):
        abort(404)

    mime_types = {
        "JPEG": "image/jpeg",
        "JPG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "BMP": "image/bmp"
    }
    mimetype = mime_types.get(record.image_format.upper(), "image/jpeg")

    return send_file(abs_path, mimetype=mimetype)


@history_bp.route("/<int:prediction_id>/download", methods=["GET"])
@login_required
def download_report(prediction_id: int):
    """
    Generate and stream downloadable forensic PDF authenticity report.
    Generates report exclusively from stored database records for verified owner.
    """
    record = PredictionHistory.query.filter_by(
        id=prediction_id,
        user_id=current_user.id
    ).first()

    if record is None:
        abort(404)

    try:
        pdf_buffer = generate_pdf_report(record, current_user)
        filename = f"deepfake_report_{record.id}.pdf"
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        current_app.logger.error(f"Failed to generate PDF for prediction {prediction_id}: {str(e)}")
        flash("Unable to generate PDF report at this time. Please try again later.", "danger")
        return redirect(url_for("history.detail", prediction_id=prediction_id))
