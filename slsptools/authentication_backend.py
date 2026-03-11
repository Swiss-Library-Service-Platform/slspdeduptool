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
        return User.objects.filter(username=email)


    def update_user(self, user, claims):
        """
        Synchronize some non-critical attributes.
        """
        changed = False

        # Optional: first/last name from SWITCH edu-ID
        given = claims.get("given_name")
        family = claims.get("family_name")
        if hasattr(user, "first_name") and given is not None and user.first_name != given:
            user.first_name = given
            changed = True
        if hasattr(user, "last_name") and family is not None and user.last_name != family:
            user.last_name = family
            changed = True

        if changed:
            user.save()

        return user

    def get_or_create_user(self, access_token, id_token, payload):
        """
        Returns (user, created) or (None, False) if no user matches the claims.
        This prevents exceptions and allows the OIDC error page to be shown.
        """
        users = self.filter_users_by_claims(payload)
        if not users.exists():
            return None, False
        user = users.first()
        return user, False
