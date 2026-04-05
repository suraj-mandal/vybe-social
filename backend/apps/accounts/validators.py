import re

from pydantic import ValidationError


def validate_phone_number(phone_number: str) -> str:
    """
    Validate and clean a phone number input string.

    This function ensures the given phone number is properly formatted by removing
    any non-numeric characters, except for an optional leading '+' sign, and validates
    the resulting phone number against the expected format of 7 to 15 digits. If the
    validation fails, a `ValidationError` is raised.

    :param phone_number: The input phone number string to be validated and cleaned.
    :type phone_number: str
    :return: A cleaned and validated phone number string.
    :rtype: str
    :raises ValidationError: If the phone number does not match the required format.
    """
    cleaned_phone_number = re.sub(r"[^\d+]", "", phone_number)

    if not re.match(r"^\+?\d{7,15}$", cleaned_phone_number):
        raise ValidationError("Enter a valid phone number (7-15 digits, optionally starting with +).")

    return cleaned_phone_number
