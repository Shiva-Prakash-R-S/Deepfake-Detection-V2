import logging
from urllib.parse import urlparse, urljoin
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app
)
from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.extensions import db
from backend.db_models import User
from backend.forms import RegisterForm, LoginForm, ChangePasswordForm

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)


def is_safe_url(target: str) -> bool:
    """Verify that the target URL is safe for redirection and not an open redirect."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Handle new user registration."""
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    form = RegisterForm()
    if form.validate_on_submit():
        normalized_email = form.email.data.strip().lower()
        full_name = form.full_name.data.strip()
        password = form.password.data

        # Check for existing user with the same email
        existing_user = User.query.filter_by(email=normalized_email).first()
        if existing_user:
            flash("An account with this email address already exists. Please log in.", "danger")
            return render_template("auth/register.html", form=form)

        user = User(
            full_name=full_name,
            email=normalized_email
        )
        user.set_password(password)

        try:
            db.session.add(user)
            db.session.commit()
            flash("Account created successfully! You can now sign in.", "success")
            return redirect(url_for("auth.login"))
        except IntegrityError:
            db.session.rollback()
            flash("An account with this email address already exists.", "danger")
        except SQLAlchemyError as err:
            db.session.rollback()
            logger.error("Database error during registration: %s", err)
            flash("A database error occurred. Please try again later.", "danger")

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login with session management."""
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    form = LoginForm()
    if form.validate_on_submit():
        normalized_email = form.email.data.strip().lower()
        password = form.password.data

        user = User.query.filter_by(email=normalized_email).first()

        # Generic authentication failure message prevents user enumeration
        if not user or not user.check_password(password):
            flash("Invalid email address or password.", "danger")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember.data)
        flash(f"Welcome back, {user.full_name}!", "success")

        next_page = request.args.get("next")
        if next_page and is_safe_url(next_page):
            return redirect(next_page)
        return redirect(url_for("home"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    """Log out the current user and invalidate the session."""
    logout_user()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Allow an authenticated user to change their password."""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        current_password = form.current_password.data
        new_password = form.new_password.data

        # Verify current password
        if not current_user.check_password(current_password):
            flash("Incorrect current password.", "danger")
            return render_template("auth/change_password.html", form=form)

        # Reject reusing the current password
        if current_password == new_password:
            flash("New password cannot be identical to your current password.", "danger")
            return render_template("auth/change_password.html", form=form)

        current_user.set_password(new_password)

        try:
            db.session.commit()
            flash("Your password has been updated successfully.", "success")
            return redirect(url_for("home"))
        except SQLAlchemyError as err:
            db.session.rollback()
            logger.error("Database error during password change: %s", err)
            flash("Failed to update password. Please try again later.", "danger")

    return render_template("auth/change_password.html", form=form)
