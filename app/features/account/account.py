from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, jsonify, session as flask_session)
from flask_login import current_user, login_user, logout_user

from ...core.db_class.user import User
from ...core.utils.decorators import require_permission
from .form import AddNewUserForm, LoginForm, EditUserForm
from ..account import account_core as AccountCore
from ...core.utils.utils import form_to_dict
from ...core.utils.logger import log_action

account_blueprint = Blueprint('account', __name__)


# ── Profile ───────────────────────────────────────────────────────────────────

@account_blueprint.route('/')
@require_permission()
def index():
    return render_template('account/profile.html', user=current_user)


# ── Public profile ────────────────────────────────────────────────────────────

@account_blueprint.route('/profile/<int:uid>')
@require_permission()
def user_profile(uid):
    user = User.query.get_or_404(uid)
    return render_template('account/user_profile.html', user=user)


# ── Edit profile ──────────────────────────────────────────────────────────────

@account_blueprint.route('/edit', methods=['GET', 'POST'])
@require_permission()
def edit_user():
    form = EditUserForm()

    if form.validate_on_submit():
        form_dict = form_to_dict(form)
        user, message = AccountCore.edit_user_core(form_dict, current_user.id)
        if user and message == "email_change_pending":
            from ...core.utils.mailer import send_verification_email
            ok, mail_msg = send_verification_email(
                user.pending_email, user.first_name, user.pending_email_token
            )
            if not ok:
                log_action(
                    f"Email change verification send failed: {mail_msg}",
                    "email_error", category="system", level="warning",
                    object_type="user", object_id=user.id, is_public=False,
                )
            flash('Profile saved. Check your new email address for the verification code.', 'success')
            return redirect(url_for('account.verify_email_change'))
        flash(message, 'success' if user else 'danger')
        return redirect(url_for('account.index'))

    if request.method == 'GET':
        form.first_name.data     = current_user.first_name
        form.last_name.data      = current_user.last_name
        form.email.data          = current_user.email
        form.username_handle.data= current_user.username
        form.bio.data            = current_user.bio
        form.phone.data          = current_user.phone
        form.job_title.data      = current_user.job_title
        form.company.data        = current_user.company
        form.location.data       = current_user.location
        form.website.data        = current_user.website
        form.social_twitter.data = current_user.social_twitter
        form.social_github.data  = current_user.social_github
        form.social_linkedin.data= current_user.social_linkedin

    return render_template('account/edit.html', form=form)


# ── Avatar upload (JSON endpoint) ─────────────────────────────────────────────

@account_blueprint.route('/avatar', methods=['POST'])
@require_permission()
def upload_avatar():
    if 'avatar' not in request.files:
        return jsonify({'message': 'No file provided'}), 400
    f = request.files['avatar']
    if not f or f.filename == '':
        return jsonify({'message': 'No file selected'}), 400
    filename, msg = AccountCore.save_avatar_core(f, current_user.id)
    if filename:
        return jsonify({'message': msg, 'filename': filename}), 200
    return jsonify({'message': msg}), 400


@account_blueprint.route('/avatar', methods=['DELETE'])
@require_permission()
def delete_avatar():
    ok, msg = AccountCore.delete_avatar_core(current_user.id)
    return jsonify({'message': msg}), 200 if ok else 400


# ── Reload API key (JSON endpoint) ────────────────────────────────────────────

@account_blueprint.route('/reload-api-key', methods=['POST'])
@require_permission()
def reload_api_key():
    user, msg = AccountCore.reload_api_key_core(current_user.id)
    if user:
        return jsonify({'message': msg, 'api_key': user.api_key}), 200
    return jsonify({'message': msg}), 400


# ── Create user ───────────────────────────────────────────────────────────────

@account_blueprint.route('/register', methods=['GET', 'POST'])
def create_user():
    from ...core.db_class.site_config import get_site_bool
    if not get_site_bool('allow_registration', True):
        if not (current_user.is_authenticated and current_user.is_admin()):
            flash('Account registration is currently disabled.', 'warning')
            return redirect(url_for('account.login'))
    form = AddNewUserForm()
    if form.validate_on_submit():
        form_dict = form_to_dict(form)
        if not current_user.is_authenticated or not current_user.is_admin():
            form_dict['role_id'] = 3   # read-only for self-registration
        user, message = AccountCore.create_user_core(form_dict)
        if user:
            log_action(
                "User registered",
                "register",
                category="user",
                level="success",
                object_type="user",
                object_id=user.id,
                is_public=False,
                meta={"user_id": user.id},
            )
            if not user.is_verified:
                flask_session['pending_verification_user_id'] = user.id
                from ...core.utils.mailer import send_verification_email
                ok, mail_msg = send_verification_email(
                    user.email, user.first_name, user.verification_token
                )
                if not ok:
                    log_action(
                        f"Verification email failed: {mail_msg}",
                        "email_error",
                        category="system",
                        level="warning",
                        object_type="user",
                        object_id=user.id,
                        is_public=False,
                    )
                flash('Account created! Check your email for the verification code.', 'success')
                return redirect(url_for('account.verify'))
            flash(message, 'success')
            return redirect(url_for('account.index'))
        flash(message, 'danger')
    return render_template('account/create.html', form=form)


# ── Email verification ────────────────────────────────────────────────────────

@account_blueprint.route('/verify', methods=['GET', 'POST'])
def verify():
    from datetime import datetime
    uid = flask_session.get('pending_verification_user_id')
    if not uid:
        flash('No pending verification. Please register first.', 'warning')
        return redirect(url_for('account.create_user'))

    user = User.query.get(uid)
    if not user:
        flask_session.pop('pending_verification_user_id', None)
        flash('Account not found. Please register again.', 'danger')
        return redirect(url_for('account.create_user'))

    if user.is_verified:
        flask_session.pop('pending_verification_user_id', None)
        return redirect(url_for('account.login'))

    # Lazy cleanup of expired token
    if user.verification_expires_at and datetime.utcnow() > user.verification_expires_at:
        AccountCore.delete_expired_user_core(user.id)
        flask_session.pop('pending_verification_user_id', None)
        log_action(
            "Unverified account deleted — code expired",
            "delete",
            category="user",
            level="warning",
            object_type="user",
            object_id=uid,
            is_public=False,
        )
        flash('Verification code expired. Please register again.', 'danger')
        return redirect(url_for('account.create_user'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        if code == user.verification_token:
            _, msg = AccountCore.verify_user_core(user.id)
            flask_session.pop('pending_verification_user_id', None)
            log_action(
                "Account verified via email code",
                "verify",
                category="user",
                level="success",
                object_type="user",
                object_id=user.id,
                actor_id=user.id,
                is_public=False,
            )
            login_user(user)
            flash('Account verified! Welcome.', 'success')
            return redirect(url_for('home.home'))
        flash('Invalid code. Please try again.', 'danger')

    return render_template(
        'account/verify.html',
        email=user.email,
        expires_at=user.verification_expires_at,
    )


# ── Email change verification ─────────────────────────────────────────────────

@account_blueprint.route('/verify-email', methods=['GET', 'POST'])
@require_permission()
def verify_email_change():
    from datetime import datetime
    user = current_user
    if not user.pending_email:
        flash('No pending email change.', 'info')
        return redirect(url_for('account.index'))

    if user.pending_email_expires_at and datetime.utcnow() > user.pending_email_expires_at:
        AccountCore.cancel_email_change_core(user.id)
        log_action(
            "Email change cancelled — code expired",
            "cancel", category="user", level="warning",
            object_type="user", object_id=user.id, is_public=False,
        )
        flash('Verification code expired. The email change has been cancelled.', 'danger')
        return redirect(url_for('account.edit_user'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        if code == user.pending_email_token:
            _, msg = AccountCore.confirm_email_change_core(user.id)
            log_action(
                "Email address changed via verification",
                "edit", category="user", level="success",
                object_type="user", object_id=user.id,
                actor_id=user.id, is_public=False,
            )
            flash('Email address updated successfully.', 'success')
            return redirect(url_for('account.index'))
        flash('Invalid code. Please try again.', 'danger')

    return render_template(
        'account/verify_email_change.html',
        new_email=user.pending_email,
        expires_at=user.pending_email_expires_at,
    )


@account_blueprint.route('/verify-email/resend', methods=['POST'])
@require_permission()
def resend_email_change_verification():
    user = current_user
    if not user.pending_email:
        flash('No pending email change.', 'warning')
        return redirect(url_for('account.index'))
    u, msg = AccountCore.resend_email_change_core(user.id)
    if not u:
        flash(msg, 'danger')
        return redirect(url_for('account.verify_email_change'))
    from ...core.utils.mailer import send_verification_email
    ok, mail_msg = send_verification_email(u.pending_email, u.first_name, u.pending_email_token)
    if ok:
        log_action(
            "Email change code resent",
            "verify_resend", category="user", level="info",
            object_type="user", object_id=u.id, is_public=False,
        )
        flash('A new code has been sent to your new email address.', 'success')
    else:
        flash(f'Could not send email: {mail_msg}', 'danger')
    return redirect(url_for('account.verify_email_change'))


@account_blueprint.route('/verify-email/cancel', methods=['POST'])
@require_permission()
def cancel_email_change():
    AccountCore.cancel_email_change_core(current_user.id)
    flash('Email change cancelled.', 'info')
    return redirect(url_for('account.edit_user'))


@account_blueprint.route('/verify/resend', methods=['POST'])
def resend_verification():
    uid = flask_session.get('pending_verification_user_id')
    if not uid:
        flash('No pending verification found. Please register first.', 'warning')
        return redirect(url_for('account.create_user'))

    user, msg = AccountCore.resend_verification_core(uid)
    if not user:
        flash(msg, 'danger')
        return redirect(url_for('account.verify'))

    from ...core.utils.mailer import send_verification_email
    ok, mail_msg = send_verification_email(user.email, user.first_name, user.verification_token)
    if ok:
        log_action(
            "Verification code resent",
            "verify_resend",
            category="user",
            level="info",
            object_type="user",
            object_id=user.id,
            is_public=False,
        )
        flash('A new code has been sent to your email.', 'success')
    else:
        flash(f'Could not send email: {mail_msg}', 'danger')

    return redirect(url_for('account.verify'))


# ── Auth ──────────────────────────────────────────────────────────────────────

@account_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    # public
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.password_hash and user.verify_password(form.password.data):
            if not user.is_verified:
                from datetime import datetime
                # Lazy cleanup: if token expired, delete the account
                if (user.verification_token
                        and user.verification_expires_at
                        and datetime.utcnow() > user.verification_expires_at):
                    AccountCore.delete_expired_user_core(user.id)
                    log_action(
                        "Unverified account deleted — code expired at login",
                        "delete",
                        category="user",
                        level="warning",
                        object_type="user",
                        object_id=user.id,
                        is_public=False,
                    )
                    flash('This account was deleted because the verification code expired. Please register again.', 'danger')
                    return render_template('account/login.html', form=form)
                flash('Your account is pending email verification.', 'warning')
                log_action(
                    "Login blocked — account not verified",
                    "login_blocked",
                    category="security",
                    level="warning",
                    object_type="user",
                    object_id=user.id,
                    actor_id=user.id,
                    is_public=False,
                    meta={"user_id": user.id},
                )
            elif not user.is_admin():
                from ...core.db_class.site_config import get_site_bool
                if not get_site_bool('allow_login', True):
                    flash('Login is currently restricted to administrators only.', 'warning')
                    log_action(
                        "Login blocked — login disabled",
                        "login_blocked",
                        category="security",
                        level="warning",
                        object_type="user",
                        object_id=user.id,
                        actor_id=user.id,
                        is_public=False,
                        meta={"user_id": user.id},
                    )
                else:
                    if user.force_logout:
                        from ... import db as _db
                        user.force_logout = False
                        _db.session.commit()
                    login_user(user, form.remember_me.data)
                    log_action(
                        "User logged in",
                        "login",
                        category="user",
                        level="success",
                        object_type="user",
                        object_id=user.id,
                        actor_id=user.id,
                        is_public=False,
                        meta={"user_id": user.id},
                    )
                    return redirect(request.args.get('next') or url_for('home.home'))
            else:
                # Admin always allowed
                if user.force_logout:
                    from ... import db as _db
                    user.force_logout = False
                    _db.session.commit()
                login_user(user, form.remember_me.data)
                log_action(
                    "User logged in",
                    "login",
                    category="user",
                    level="success",
                    object_type="user",
                    object_id=user.id,
                    actor_id=user.id,
                    is_public=False,
                    meta={"user_id": user.id},
                )
                return redirect(request.args.get('next') or url_for('home.home'))
        else:
            flash('Invalid email or password.', 'danger')
            log_action(
                "Login failed — invalid credentials",
                "login_failed",
                category="security",
                level="warning",
                object_type="user",
                object_id=None,
                actor_id=None,
                is_public=False,
                meta={"email": form.email.data},
            )
    return render_template('account/login.html', form=form)


@account_blueprint.route('/logout')
@require_permission()
def logout():
    log_action(
        "User logged out",
        "logout",
        category="user",
        level="info",
        object_type="user",
        object_id=current_user.id,
        actor_id=current_user.id,
        is_public=False,
        meta={"user_id": current_user.id},
    )
    logout_user()
    return redirect(url_for('account.login'))
