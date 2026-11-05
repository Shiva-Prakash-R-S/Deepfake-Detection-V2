import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    EqualTo,
    ValidationError
)


def validate_password_strength(form, field):
    password = field.data or ""
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Za-z]", password):
        raise ValidationError("Password must contain at least one letter.")
    if not re.search(r"\d", password):
        raise ValidationError("Password must contain at least one number.")


class RegisterForm(FlaskForm):
    full_name = StringField(
        "Full Name",
        validators=[
            DataRequired(message="Full name is required."),
            Length(min=2, max=100, message="Full name must be between 2 and 100 characters.")
        ],
        render_kw={"placeholder": "e.g. Shiva Prakash", "autocomplete": "name"}
    )
    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Email address is required."),
            Email(message="Please enter a valid email address."),
            Length(max=120, message="Email address is too long.")
        ],
        render_kw={"placeholder": "you@example.com", "autocomplete": "email"}
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            validate_password_strength
        ],
        render_kw={"placeholder": "Minimum 8 chars with letters & numbers", "autocomplete": "new-password"}
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Passwords must match.")
        ],
        render_kw={"placeholder": "Re-enter your password", "autocomplete": "new-password"}
    )
    submit = SubmitField("Create Account")


class LoginForm(FlaskForm):
    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Email address is required."),
            Email(message="Please enter a valid email address.")
        ],
        render_kw={"placeholder": "you@example.com", "autocomplete": "email"}
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required.")
        ],
        render_kw={"placeholder": "Enter your password", "autocomplete": "current-password"}
    )
    remember = BooleanField("Remember Me")
    submit = SubmitField("Sign In")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(
        "Current Password",
        validators=[
            DataRequired(message="Current password is required.")
        ],
        render_kw={"placeholder": "Enter your current password", "autocomplete": "current-password"}
    )
    new_password = PasswordField(
        "New Password",
        validators=[
            DataRequired(message="New password is required."),
            validate_password_strength
        ],
        render_kw={"placeholder": "Minimum 8 chars with letters & numbers", "autocomplete": "new-password"}
    )
    confirm_new_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(message="Please confirm your new password."),
            EqualTo("new_password", message="New passwords must match.")
        ],
        render_kw={"placeholder": "Re-enter new password", "autocomplete": "new-password"}
    )
    submit = SubmitField("Update Password")
