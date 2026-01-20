from django.http import HttpResponse, JsonResponse, HttpRequest
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from almapiwrapper import ApiKeys
import requests
import os
from django.core.cache import cache


def index(request: HttpRequest) -> HttpResponse:
    """
    Display the list of apps

    This view is unprotected and can be accessed by anyone.
    """

    # Render the template with the list of collections
    return render(request, 'slsptools/index.html')

def login_view(request):
    """Manage login of the user

    It uses the AuthenticationForm to authenticate the user.
    If the user is authenticated, it will redirect to the index page.
    """
    # We check the method of the request, post is used to send the form
    # and get is used to display the form
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)

        # We collect the data from the form and check if it's valid
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)

            # Redirection to the index page if the user is authenticated
            if user is not None:
                login(request, user)
                return redirect('index')

    return render(request, 'slsptools/login.html', {'form': AuthenticationForm()})

def logout_view(request):
    """Logout the user and redirect to the index page"""
    logout(request)
    return redirect('index')

def get_current_api_threshold():
    """Check the current API usage and return the status."""

    # We first check if we have a cached status
    cached_status = cache.get('api_threshold_probe_status')
    cached_remaining_api_calls = cache.get('remaining_api_calls')

    if cached_status is not None and cached_remaining_api_calls is not None:
        # We have a cached status, we return it
        status = cached_status
        remaining_api_calls = cached_remaining_api_calls
    else:
        # No cached status, we perform the API call to check the remaining calls
        env = 'S' if os.getenv('django_env') == 'dev' else 'P'
        headers = {'content-type': 'application/json',
                   'accept': 'application/json',
                   'Authorization': 'apikey ' + ApiKeys().get_key('NZ', 'Conf', 'RW', env)}

        r = requests.get('https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/test', headers=headers)

        if not r.ok:
            # No response or error response from the API => error status
            status = 'critical'
            remaining_api_calls = 'unknown'
        elif 'X-Exl-Api-Remaining' in r.headers and int(r.headers["X-Exl-Api-Remaining"]) < 100000:
            # Critical threshold reached
            status = 'critical'
            remaining_api_calls = r.headers["X-Exl-Api-Remaining"]
        elif 'X-Exl-Api-Remaining' in r.headers and int(r.headers["X-Exl-Api-Remaining"]) < 500000:
            # Warning threshold reached
            status = 'warning'
            remaining_api_calls = r.headers["X-Exl-Api-Remaining"]
        else:
            # Everything is ok, thresholds are fine
            status = 'ok'
            remaining_api_calls = r.headers.get("X-Exl-Api-Remaining", 'unknown')

        # We save the status and remaining API calls in cache for 30 minutes
        cache.set('api_threshold_probe_status', status, 1800)
        cache.set('remaining_api_calls', remaining_api_calls, 1800)

    return {'status': status, 'remaining_api_calls': remaining_api_calls}

def api_threshold_probe(request):
    """API view to check the current API usage and return the status.

    This view is unprotected and can be accessed by anyone.
    It returns a JSON response with the status and remaining API calls.
    """

    api_threshold = get_current_api_threshold()

    status = ['ok', 'warning', 'critical'].index(api_threshold['status'])
    api_threshold_str = f'{status} "Alma api calls threshold" remaining_api_calls={api_threshold["remaining_api_calls"]} - State of remaining API calls in the NZ: {api_threshold['status'].upper()}'

    return HttpResponse(api_threshold_str)