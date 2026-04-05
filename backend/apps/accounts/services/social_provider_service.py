from typing import Protocol

import requests
from django.conf import settings
from pydantic import BaseModel


class SocialAuthUser(BaseModel):
    """
    Represents a user authenticated via a social authentication provider.

    This class is a data model intended to encapsulate details of a user
    authenticated using a social auth provider, such as Google, Facebook, or
    Twitter. It is typically used in scenarios where user information is
    retrieved from third-party authentication systems.

    :ivar email: The email address of the user.
    :type email: str
    :ivar first_name: The first name of the user.
    :type first_name: str
    :ivar last_name: The last name of the user.
    :type last_name: str
    :ivar provider_user_id: The unique identifier assigned to the user by the
      social authentication provider.
    :type provider_user_id: str
    """

    email: str
    first_name: str
    last_name: str
    provider_user_id: str


class SocialAuthService(Protocol):
    """
    Provides an interface for verifying social authentication tokens.

    This class is designed as a protocol to outline the method that must
    be implemented for verifying authentication tokens issued by social
    authentication providers. It defines a standard method for verifying
    tokens and retrieving user information associated with the token.

    :ivar token: The authentication token that will be verified.
    :type token: str
    """

    @classmethod
    def verify_token(cls, token: str) -> SocialAuthUser: ...


class GoogleAuthService:
    """
    Handles verification of Google ID tokens to validate their authenticity and extract user information.

    This class provides functionality to interact with Google's OAuth2 token verification endpoint
    and ensures that provided ID tokens are valid, issued for the correct application, and associated
    with a verified email address.

    :ivar TOKENINFO_URL: The URL endpoint for Google's token verification service.
    :type TOKENINFO_URL: str
    """

    TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"

    @classmethod
    def verify_token(cls, token: str) -> SocialAuthUser:
        """
        Verifies the validity of a Google ID token and extracts user information.

        This method sends a request to Google's token information endpoint to validate a provided
        ID token. If the token is invalid (e.g., incorrect audience, unverified email, or wrong format),
        it raises appropriate exceptions. On successful validation, the method returns a
        `SocialAuthUser` instance containing the user's details extracted from the Google ID token.

        :param token: A string representing the Google ID token to validate.
        :type token: str
        :raises ValueError: If the token is invalid, issued for another application, or the email
                            is unverified.
        :return: A `SocialAuthUser` instance containing basic user information such as email, first
                 name, last name, and the provider user ID from the verified token.
        :rtype: SocialAuthUser
        """
        response = requests.get(cls.TOKENINFO_URL, params={"id_token": token}, timeout=10)

        if response.status_code != 200:
            raise ValueError("Invalid Google token.")

        data = response.json()

        if data.get("aud") != settings.GOOGLE_CLIENT_ID:
            raise ValueError("Token was not issued for this application.")

        if data.get("email_verified") != "true":
            raise ValueError("Google email is not verified.")

        return SocialAuthUser.model_validate(
            {
                "email": data["email"],
                "first_name": data.get("given_name", ""),
                "last_name": data.get("family_name", ""),
                "provider_user_id": data["sub"],
            }
        )


class FacebookAuthService:
    """
    Handles authentication and token verification with the Facebook Graph API.

    This service is designed to verify the validity of Facebook OAuth tokens. It
    interacts with Facebook's Graph API to retrieve user information based on the
    provided token, ensuring secure and authenticated communication with the
    Facebook platform.

    :ivar GRAPH_API_URL: The base URL for Facebook's Graph API used to verify
        the access token and retrieve user information.
    :type GRAPH_API_URL: str
    """

    GRAPH_API_URL = f"https://graph.facebook.com/{settings.FACEBOOK_GRAPHQL_VERSION}/me"

    @classmethod
    def verify_token(cls, token: str) -> SocialAuthUser:
        """
        Verifies the validity of a provided Facebook OAuth token by making an API call to
        Facebook's Graph API. If the token is valid, it retrieves the associated user
        information, such as email, first name, last name, and provider user ID, from
        Facebook and returns it as a `SocialAuthUser` instance. If the token is invalid
        or does not grant email access, appropriate exceptions are raised.

        :param token: The Facebook OAuth access token to verify.
        :type token: str
        :raises ValueError: If the Facebook token is invalid or if email access is not granted.
        :return: A `SocialAuthUser` object populated with the user's email, first name,
            last name, and provider user ID retrieved from Facebook.
        :rtype: SocialAuthUser
        """
        response = requests.get(
            cls.GRAPH_API_URL, params={"fields": "id,email,first_name,last_name", "access_token": token}, timeout=10
        )

        if response.status_code != 200:
            raise ValueError("Invalid Facebook token.")

        data = response.json()

        if "email" not in data:
            raise ValueError("Email not available from Facebook. Please grant email permission.")

        return SocialAuthUser.model_validate(
            {
                "email": data["email"],
                "first_name": data.get("first_name", ""),
                "last_name": data.get("last_name", ""),
                "provider_user_id": data["id"],
            }
        )
