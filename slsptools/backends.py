from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.contrib.auth import get_user_model

class WhitelistOIDCBackend(OIDCAuthenticationBackend):
    def filter_users_by_claims(self, claims):
        User = get_user_model()
        email = claims.get('email')
        if not email:
            return User.objects.none()
        return User.objects.filter(email__iexact=email)

    def create_user(self, claims):
        # Refuse automatic user creation
        return None

    def update_user(self, user, claims):
        # Refuse user updates
        return None
