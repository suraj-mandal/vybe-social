import importlib
import logging
from typing import Protocol

from django.conf import settings

logger = logging.getLogger(__name__)


class BaseSMSBackend(Protocol):
    def send(self, phone_number: str, message: str) -> None: ...


class ConsoleSMSBackend:
    """
    Class responsible for simulating the sending of SMS messages through a console output.

    This class introduces a mechanism to log SMS messages intended for a specified recipient
    to the console in a formatted manner. It is useful for scenarios where direct interaction
    with an SMS gateway is not required or during development and testing phases where real
    messages are not sent.

    """

    def send(self, phone_number: str, message: str) -> None:
        """
        Send an SMS message to a specified phone number. This method logs a formatted
        representation of the SMS, including the recipient's phone number and the message
        contents.

        :param phone_number: The recipient's phone number.
        :type phone_number: str
        :param message: The text message to be delivered.
        :type message: str
        :return: None
        """
        logger.info(f"\n{'=' * 50}\nSMS to {phone_number}:\n{message}\n{'=' * 50}\n")


class TwilioSMSBackend:
    """
    Handles the sending of SMS messages using the Twilio service.

    This class provides a method to send text messages to specified phone numbers by
    interacting with the Twilio API. The Twilio service is utilized for reliable delivery
    of SMS messages. To use this class, the necessary Twilio configuration, such as the
    account SID, authentication token, and sender phone number, must be correctly set
    in the application settings.

    """

    def send(self, phone_number: str, message: str) -> None:
        """
        Sends an SMS message to the specified phone number using the Twilio service. The function
        authenticates with Twilio using the account SID and authentication token.

        :param phone_number: The recipient's phone number in E.164 format.
        :type phone_number: str
        :param message: The text message to be sent.
        :type message: str
        :return: None
        """
        from twilio.rest import Client

        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
        )

        client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number,
        )


def get_sms_backend() -> BaseSMSBackend:
    """
    Retrieve the SMS backend class based on the configuration.

    This function dynamically loads and returns the SMS backend class specified in the
    `settings.SMS_BACKEND` configuration. The backend path must be represented as a string
    in dot notation, such as `module.submodule.ClassName`. It uses Python's importlib to
    load the module and retrieve the class for further use in the application.

    :raises ImportError: If the module specified in the backend path cannot be imported.
    :raises AttributeError: If the backend class cannot be found in the loaded module.
    :raises ValueError: If the backend path is improperly formatted and does not contain
        both a module path and a class name.

    :return: The SMS backend class as specified in the settings.
    :rtype: BaseSMSBackend
    """
    backend_path = settings.SMS_BACKEND
    module_path, class_name = backend_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    backend_class = getattr(module, class_name)
    return backend_class()
