from django.http import HttpResponse, JsonResponse, HttpRequest
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import user_passes_test
from almapiwrapper import ApiKeys
import requests
import os
from django.core.cache import cache
from pymongo import MongoClient, DESCENDING
from datetime import date, timedelta, datetime

def is_staff(user):
    """Check if the user is an admin user."""
    return user.is_staff

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
                   'Authorization': 'apikey ' + ApiKeys().get_key('NZ', 'Conf', 'R', env)}

        r = requests.get('https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/test', headers=headers)

        if not r.ok:
            # No response or error response from the API => error status
            status = 'CRITICAL'
            remaining_api_calls = 'unknown'
        elif 'X-Exl-Api-Remaining' in r.headers and int(r.headers["X-Exl-Api-Remaining"]) < 100000:
            # Critical threshold reached
            status = 'CRITICAL'
            remaining_api_calls = r.headers["X-Exl-Api-Remaining"]
        elif 'X-Exl-Api-Remaining' in r.headers and int(r.headers["X-Exl-Api-Remaining"]) < 500000:
            # Warning threshold reached
            status = 'WARNING'
            remaining_api_calls = r.headers["X-Exl-Api-Remaining"]
        else:
            # Everything is ok, thresholds are fine
            status = 'OK'
            remaining_api_calls = r.headers.get("X-Exl-Api-Remaining", 'unknown')

        # We save the status and remaining API calls in cache for 30 minutes
        cache.set('api_threshold_probe_status', status, 1800)
        cache.set('remaining_api_calls', remaining_api_calls, 1800)

    return {'status': status, 'remaining_api_calls': remaining_api_calls}

# def api_threshold_probe(request):
#     """API view to check the current API usage and return the status.

#     This view is unprotected and can be accessed by anyone.
#     It returns a JSON response with the status and remaining API calls.
#     """

#     api_threshold = get_current_api_threshold()

#     status = ['ok', 'warning', 'critical'].index(api_threshold['status'])
#     api_threshold_str = f'{status} "Alma api calls threshold" remaining_api_calls={api_threshold["remaining_api_calls"]} - State of remaining API calls in the NZ: {api_threshold["status"].upper()}'

#     return HttpResponse(api_threshold_str)

def get_job_status(task: dict, col: str) -> str:
    """Get the status of a job based on its last run date.

    Args:
        task (dict): The task document from the database, containing at least a 'TIMESTAMP' field.
        last_date (datetime): The date of the last run of the job.

    Returns:
        str: The status of the job ('OK', 'WARNING', 'CRITICAL', 'NO DATA').
    """
    now = datetime.now()

    task_timestamp = task.get('TIMESTAMP', None)
    if col == 'NZ_external_database':
        task_timestamp = task.get('end_time', None)
        if task_timestamp:
            if now - task_timestamp > timedelta(days=8, hours=12, minutes=0, seconds=0):
                return 'CRITICAL'
        else:
            task_timestamp = task.get('start_time', None)
            if now - task_timestamp > timedelta(days=2, hours=0, minutes=0, seconds=0):
                return 'CRITICAL'
        return 'OK'


    if task_timestamp is None:
        return 'NO DATA'



    if col in ['zbs_cug']:
        threshold = timedelta(days=7, minutes=30, seconds=0)
    elif col in ['VKSS_Einlagerung']:
        threshold = timedelta(days=7, hours=2, minutes=30, seconds=0)
    else:
        threshold = timedelta(days=1, minutes=30, seconds=0)

    if now - task_timestamp > threshold:
        return 'CRITICAL'

    if 'FAILED' in task and task['FAILED'] > 0:
        return 'WARNING'

    return 'OK'

def get_success(task: dict, col: str) -> int:
    """Check if the task was successful based on its 'FAILED' field.

    Args:
        task (dict): The task document from the database, containing at least a 'FAILED' field.
    Returns:
        int: number of successful operations.
    """
    if 'SUCCESS' in task:
        return task['SUCCESS']
    elif col == 'abn_cug_mediotheken':
        return task['nb_users_updated']
    elif col == 'reminders':
        return task['nb_copied_in_the_IZ']
    elif col == 'NZ_external_database':
        return task['nb_records_at_end_time']
    return 0

@user_passes_test(is_staff)
def services_status(request: HttpRequest) -> HttpResponse:
    """Display the status of the services used by the application.

    This view is unprotected and can be accessed by anyone.
    It displays the status of the services used by the application.
    """
    client = MongoClient(os.getenv('monogodb_automation_uri'))
    db = client[os.getenv('automation_db')]
    cols = sorted(db.list_collection_names(), key=lambda x: x.casefold())

    data = []
    for col in cols:
        collection = db[col]

        if col == 'NZ_external_database':
            history = list(collection.find({'start_time': {'$exists': True}}, {'_id': 0, 'chunk_directory': 0, 'critical_error_messages': 0 }).sort('start_time', DESCENDING).limit(7))
            for hist in history:
                hist['FAILED'] = len(hist.get('data_error_messages', []))
                del hist['data_error_messages']
                hist['TIMESTAMP'] = hist.get('start_time', None)
        else:
            history = list(collection.find({'TIMESTAMP': {'$exists': True}}, {'_id': 0, 'DATE': 0, 'TASKS': 0}).sort("TIMESTAMP", DESCENDING).limit(7))

        if len(history) == 0:
            data.append({'history': [],
                         'status': 'NO DATA',
                         'name': col,
                         'task_timestamp': None})
        else:
            if col == 'NZ_external_database':
                task_timestamp = history[0].get('start_time', None)
            else:
                task_timestamp = history[0].get('TIMESTAMP', None)

            status = get_job_status(history[0], col)
            nb_success = get_success(history[0], col)

            nb_failed = history[0].get('FAILED', 0)

            # We keep only the keys that are common to all documents to be able to create a nice table
            history_keys = history[0].keys()
            for hist in history:
                keys_to_remove = [key for key in hist.keys() if key not in history_keys]
                for key in keys_to_remove:
                    del hist[key]

            data.append({'history': history,
                         'status': status,
                         'name': col,
                         'nb_success': nb_success,
                         'nb_failed': nb_failed,
                         'task_timestamp': task_timestamp})

    api_threshold = get_current_api_threshold()
    print(api_threshold)
    context = {'data': data, 'cols': cols, 'api_threshold': api_threshold}
        # 'api_threshold_status': api_threshold['status'],
        # 'remaining_api_calls': api_threshold['remaining_api_calls'],


    return render(request, 'slsptools/services_status.html', context)
