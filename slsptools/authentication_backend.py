# auth_backends.py
from django.contrib.auth import get_user_model
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

User = get_user_model()

class EmailMatchesUsernameOIDCBackend(OIDCAuthenticationBackend):
    """
    Allows login only if the email (OIDC claim) exactly matches a Django user with username == email.
    """

    def filter_users_by_claims(self, claims):
        """
        Returns a queryset filtered for users where username == email_claim.
        If the email claim is missing, no user is returned.
        """
        email = claims.get("email")
        if not email:
            return User.objects.none()
        if not User.objects.filter(username=email):
            return User.objects.none()

        return User.objects.filter(username=email)
