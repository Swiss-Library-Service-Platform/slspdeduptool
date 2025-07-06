# Django imports
from django.http import HttpResponse, JsonResponse, HttpRequest
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.urls import reverse

from django.http import HttpResponse
import pymongo
import os

# Get the uri to connect to the MongoDB databases, it has all the required
# rights to use the following databases: records, dedup
mongo_uri = os.getenv('mongodb_dedup_uri')
mongo_client = pymongo.MongoClient(mongo_uri)

# As the collection is related the material type, we define globally only the database
# for each material type
mongo_db_callnumbers = mongo_client[os.getenv('callnumbers_db')]
col = mongo_db_callnumbers['cmg_hem']

def index(request):

    callnumber_query = request.GET.get('callnumber', '')

    recs_1 = list(col.find({'callnumber': callnumber_query}))

    recs_2 = list(col.find({
        'callnumber': {
            '$regex': f'^{callnumber_query}',
        '$options': 'i'
    }
    }).limit(20))
    itemids = [rec['item_id'] for rec in recs_1]
    recs_2 = [rec for rec in recs_2 if rec['item_id'] not in itemids]
    recs = recs_1 + recs_2
    recs = recs[:15]

    return render(request, 'callnumber_to_barcode/index.html', {'recs': recs})

def update(request, item_id=None):
    callnumber = request.GET.get('callnumber', '')
    new_barcode = request.POST.get('new_barcode', None)
    if new_barcode == '':
        new_barcode = None
    col.update_one({'item_id': item_id}, {'$set': {'new_barcode': new_barcode}})
    return redirect(f"{reverse('callnumber_to_barcode:index')}?callnumber={callnumber}")


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
    return redirect('dedup:index')