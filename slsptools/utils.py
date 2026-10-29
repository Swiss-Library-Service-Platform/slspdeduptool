from django.http import HttpRequest
from django.utils.http import url_has_allowed_host_and_scheme

def is_staff(user):
    """Check if the user is an admin user."""
    return user.is_staff

def safe_next_url(request: HttpRequest, fallback: str = '/') -> str:
    if request.path.startswith('/login/') or request.path.startswith('/oidc/'):
        return fallback

    next_url = request.get_full_path() or fallback
    if next_url.startswith('/login/') or next_url.startswith('/oidc/'):
        next_url = fallback

    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = fallback

    return next_url