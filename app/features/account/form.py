from flask import url_for
from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import ValidationError
from wtforms.fields import (
    BooleanField, PasswordField, StringField,
    SubmitField, EmailField, TextAreaField,
)
from wtforms.validators import Email, InputRequired, Length, Optional, Regexp, URL
from ...core.db_class.user import User


class LoginForm(FlaskForm):
    email       = EmailField('Email',    validators=[InputRequired(), Length(1, 128), Email()])
    password    = PasswordField('Password', validators=[InputRequired()])
    remember_me = BooleanField('Keep me logged in')
    submit      = SubmitField('Sign in')


class EditUserForm(FlaskForm):
    # ── Identity ──────────────────────────────────────────
    first_name = StringField('First name', validators=[InputRequired(), Length(1, 64)])
    last_name  = StringField('Last name',  validators=[InputRequired(), Length(1, 64)])
    email      = EmailField('Email',       validators=[InputRequired(), Length(1, 128), Email()])
    username_handle = StringField('Username', validators=[
        Optional(), Length(1, 32),
        Regexp(r'^[a-zA-Z0-9_\-\.]+$', message='Letters, digits, _ - . only'),
    ])

    # ── Security ──────────────────────────────────────────
    password = PasswordField('New password', validators=[
        Optional(),
        Length(min=8, max=64),
        Regexp(r'.*[A-Z].*', message='At least one uppercase letter'),
        Regexp(r'.*[a-z].*', message='At least one lowercase letter'),
        Regexp(r'.*\d.*',    message='At least one digit'),
    ])

    # ── Profile ───────────────────────────────────────────
    bio       = TextAreaField('Bio',       validators=[Optional(), Length(max=500)])
    phone     = StringField('Phone',       validators=[Optional(), Length(max=25)])
    job_title = StringField('Job title',   validators=[Optional(), Length(max=100)])
    company   = StringField('Company',     validators=[Optional(), Length(max=100)])
    location  = StringField('Location',    validators=[Optional(), Length(max=100)])

    # ── Social ────────────────────────────────────────────
    website        = StringField('Website',  validators=[Optional(), Length(max=200)])
    social_twitter = StringField('Twitter / X', validators=[Optional(), Length(max=50)])
    social_github  = StringField('GitHub',   validators=[Optional(), Length(max=50)])
    social_linkedin= StringField('LinkedIn', validators=[Optional(), Length(max=200)])

    submit = SubmitField('Save changes')

    def validate_email(self, field):
        if field.data != current_user.email:
            if User.query.filter_by(email=field.data).first():
                raise ValidationError('Email already in use')

    def validate_username_handle(self, field):
        if field.data:
            handle = field.data.lstrip('@')
            existing = User.query.filter_by(username=handle).first()
            if existing and existing.id != current_user.id:
                raise ValidationError('Username already taken')


class AddNewUserForm(FlaskForm):
    first_name = StringField('First name', validators=[InputRequired(), Length(1, 64)])
    last_name  = StringField('Last name',  validators=[InputRequired(), Length(1, 64)])
    email      = EmailField('Email',       validators=[InputRequired(), Length(1, 128), Email()])
    password   = PasswordField('Password', validators=[
        InputRequired(),
        Length(min=8, max=64),
        Regexp(r'.*[A-Z].*', message='At least one uppercase letter'),
        Regexp(r'.*[a-z].*', message='At least one lowercase letter'),
        Regexp(r'.*\d.*',    message='At least one digit'),
    ])
    submit = SubmitField('Create user')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered')
