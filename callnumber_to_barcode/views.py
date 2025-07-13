# Django imports
import http

from django.http import HttpResponse, JsonResponse, HttpRequest
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.urls import reverse
from almapiwrapper import ApiKeys
from almapiwrapper.inventory import Item

from django.http import HttpResponse
import pymongo
import os
import re
from lxml import etree

# Get the uri to connect to the MongoDB databases, it has all the required
# rights to use the following databases: records, dedup
mongo_uri = os.getenv('mongodb_dedup_uri')
mongo_client = pymongo.MongoClient(mongo_uri)

# As the collection is related the material type, we define globally only the database
# for each material type
mongo_db_callnumbers = mongo_client[os.getenv('callnumbers_db')]

def index(request: HttpRequest) -> HttpResponse:
    """
    Display the list of collections available in the dedup database

    This view is unprotected and can be accessed by anyone. It displays the
    list of collections. The application is able to dedup several collections
    without any hard coding. We display all collections of `dedup_db` except
    the ones starting with 'NZ_' and the training data collection.
    """
    # Fetch collections names from the database
    cols = [col for col in mongo_db_callnumbers.list_collection_names()
            if is_col_allowed(col, request) is True]

    # Render the template with the list of collections
    return render(request, 'callnumber_to_barcode/index.html', {"cols": cols})


def collection(request, col_name):

    # We check that the collection name provided in url exists
    if col_name not in mongo_db_callnumbers.list_collection_names():
        return HttpResponse(f'Collection "{col_name}" not found', status=404)
    col = mongo_db_callnumbers[col_name]

    callnumber_query = request.GET.get('callnumber', '')

    recs_1 = list(col.find({'callnumber': callnumber_query}))

    recs_2 = list(col.find({
        'callnumber': {
            '$regex': f'^{callnumber_query}',
        '$options': 'i'
    }
    }).limit(500))
    itemids = [rec['item_id'] for rec in recs_1]
    recs_2 = natural_sort([rec for rec in recs_2 if rec['item_id'] not in itemids])
    recs = recs_1 + recs_2
    recs = recs[:500]

    return render(request,
                  'callnumber_to_barcode/collection.html',
                  {'recs': recs, 'col_name': col_name})

def update(request, item_id=None, col_name=None):
    # We check that the collection name provided in url exists
    if col_name not in mongo_db_callnumbers.list_collection_names():
        return HttpResponse(f'Collection "{col_name}" not found', status=404)
    col = mongo_db_callnumbers[col_name]
    callnumber = request.GET.get('callnumber', '')
    new_barcode = request.POST.get('new_barcode', None)
    if new_barcode == '':
        new_barcode = None
    col.update_one({'item_id': item_id}, {'$set': {'new_barcode': new_barcode, 'error': False}})
    rec = col.find_one({'item_id': item_id})
    if rec is None:
        return redirect(f"{reverse('callnumber_to_barcode:collection', kwargs={'col_name': col_name})}?callnumber={callnumber}")
    zone = col_name.split('_')[0]
    item = Item(rec['mms_id'], rec['holding_id'], rec['item_id'], zone=zone, env='P')
    if item.error is True:
        col.update_one({'item_id': item_id}, {'$set': {'new_barcode': None, 'error': True}})
        return redirect(f"{reverse('callnumber_to_barcode:collection', kwargs={'col_name': col_name})}?callnumber={callnumber}")

    # We use the old barcode if the new one is empty, we add error flag
    if new_barcode is not None:
        item.data.find('item_data/barcode').text = new_barcode
    else:
        item.data.find('item_data/barcode').text = rec['barcode']
        col.update_one({'item_id': item_id}, {'$set': {'new_barcode': None, 'error': True}})
    item.update()
    if item.error is True:
        col.update_one({'item_id': item_id}, {'$set': {'new_barcode': None, 'error': True}})

    return redirect(f"{reverse('callnumber_to_barcode:collection', kwargs={'col_name': col_name})}?callnumber={callnumber}")


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
                return redirect('callnumber_to_barcode:index')

    return render(request, 'callnumber_to_barcode/login.html', {'form': AuthenticationForm()})


def logout_view(request):
    """Logout the user and redirect to the index page"""
    logout(request)
    return redirect('callnumber_to_barcode:index')


def is_col_allowed(col_name: str, request: HttpRequest) -> bool:
    """Check if the user has access to the collection
    This function checks if the user has access to the collection

    Parameters:
    -----------
    col_name : str
        The name of the collection to check.
    request : HttpRequest
        The request object containing user information.

    Returns:
    --------
    bool
        True if the user has access to the collection, False otherwise.
    """

    # At least one group must be associated to the collection
    user_groups = list(request.user.groups.values_list("name", flat=True))
    if any(col_name.startswith(user_group) for user_group in user_groups):
        return True
    return False


def natural_sort(items):
    def natural_key(item):

        text = item['callnumber']
        # Split the string into parts: digits are converted to integers, others stay as strings
        return [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', text)]

    return sorted(items, key=natural_key)
