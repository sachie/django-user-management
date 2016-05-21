from django.contrib.auth.password_validation import validate_password


def validate_password_strength(value):
    return validate_password(value)
