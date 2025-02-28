"""
This module contains the views of the deduplication application.
"""
# Django imports
from django.http import HttpResponse, JsonResponse, HttpRequest
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm

# Standard library imports
import pymongo
import os
import json

# Local imports
from . import tools

# Used for dedup tasks
# https://dedupmarcxml.readthedocs.io
from dedupmarcxml.evaluate import evaluate_records_similarity, get_similarity_score
from dedupmarcxml.briefrecord import RawBriefRec, JsonBriefRec

# Used only with DNB records
# from lxml import etree
# from almapiwrapper.record import XmlData
# import requests
# from almasru.briefrecord import BriefRecFactory, BriefRec
# from almasru import config_log

# Configure access to MongoDB databases

# Get the uri to connect to the MongoDB databases, it has all the required
# rights to use the following databases: records, dedup
mongo_uri = os.getenv('mongodb_dedup_uri')
mongo_client = pymongo.MongoClient(mongo_uri)

# We can already define the collection for the NZ records
mongo_db_nz = mongo_client[os.getenv('nz_db')]
mongo_col_nz = mongo_db_nz[os.getenv('nz_db_col')]

# As the collection is related the material type, we define globally only the database
# for each material type
mongo_db_dedup = mongo_client[os.getenv('dedup_db')]


def index(request: HttpRequest) -> HttpResponse:
    """
    Display the list of collections available in the dedup database

    This view is unprotected and can be accessed by anyone. It displays the
    list of collections. The application is able to dedup several collections
    without any hard coding. We display all collections of `dedup_db` except
    the ones starting with 'NZ_' and the training data collection.
    """
    # Fetch collections names from the database
    cols = [col for col in mongo_db_dedup.list_collection_names()
            if col.startswith('NZ_') is False and col != 'training_data']

    # Render the template with the list of collections
    return render(request, 'dedup/index.html', {"cols": cols})


@login_required
def collection(request: HttpRequest, col_name: str) -> HttpResponse:
    """Display the first records of a collection

    This view is protected and can only be accessed by authenticated users.
    It displays the first records of a collection.
    It's the main view of the deduplication process.
    """

    # We check that the collection name provided in url exists
    if col_name not in [col for col in mongo_db_dedup.list_collection_names()
                        if col.startswith('NZ_') is False]:
        return HttpResponse(f'Collection "{col_name}" not found')

    return render(request, 'dedup/collection.html', {"col_name": col_name})


@login_required
def get_local_record_ids(request: HttpRequest, col_name: str) -> JsonResponse:
    """
    Get the record ids for a collection with a filter.

    This view is an API returning the record ids for a collection with a filter.
    Sorting is according to the `_id` field and not `rec_id`.

    Treatment for duplicated matches is special with a distinct pipeline.

    Parameters:
    -----------
    request : HttpRequest
        The HTTP request object containing the filter parameters.
    col_name : str
        The name of the collection to query.

    Returns:
    --------
    JsonResponse
        A JSON response containing the record ids and the total number of records.
    """

    # Get the filter from the request, using parameters
    record_filter = request.GET.get('filter', 'all')
    next_record = request.GET.get('next', None)
    recid = request.GET.get('recid', None)

    # Define the queries for the different filters
    queries = {'all': {},
               'possible': {'possible_matches.1': {'$exists': 1},
                            # 'max_match_score': {'$gt': 0.7},
                            'matched_record': None},
               'nomatch': {'possible_matches.1': {'$exists': 0},
                           'matched_record': None},
               'match': {'matched_record': {'$nin': [None, '']}},
               'duplicatematch': {'matched_record': {'$nin': [None, '']}},
               }

    recids_query = queries.get(record_filter, queries['all'])

    # Used with next button
    if next_record is not None:
        rec = mongo_db_dedup[col_name].find_one({'rec_id': next_record},
                                                {'_id': True, 'matched_record': True})
        if record_filter != 'duplicatematch':
            # Need to find the _id of the record with rec_id
            if rec is not None:
                recids_query.update({'_id': {'$gt': rec['_id']}})

        else:
            if rec is not None and rec.get('matched_record') is not None:
                # Add filter for duplicated matches to get the next record
                recids_query.update({'matched_record': {'$gte': rec['matched_record']}})

    # Used with input field for recid
    if recid is not None:
        # Need to find the _id of the record with rec_id
        rec = mongo_db_dedup[col_name].find_one({'rec_id': recid},
                                                {'_id': True, 'matched_record': True})
        if rec is not None and record_filter != 'duplicatematch':
            recids_query.update({'_id': {'$gte': rec['_id']}})
        elif rec is not None and record_filter == 'duplicatematch':
            print(rec)
            recids_query.update({'matched_record': {'$gte':rec['matched_record']}})

    if record_filter != 'duplicatematch':
        # Spectial pipeline for duplicated matches
        pipeline = [
            {"$match": recids_query},  # Filtre les documents selon ta requête
            {"$project": {  # Sélectionne les champs souhaités
                "_id": False,
                "rec_id": True,
                "human_validated": True,
                "matched_record": True
            }},
            {"$facet": {  # split data
                "total": [  # Count nb documents
                    {"$count": "total"}
                ],
                "results": [  # limit results to 20
                    {"$limit": 300}
                ]
            }}
        ]

    else:
        # Normal pipeline for other filters
        pipeline = [

            # Step 0: Sort by matched_record
            {"$sort": {"matched_record": 1}},

            # Step 1: Filter documents where matched_record is neither None nor an empty string
            {"$match": recids_query},

            # Step 2: Group by matched_record and count occurrences
            {"$group": {
                "_id": "$matched_record",
                "count": {"$sum": 1},  # Count occurrences of each matched_record
                "documents": {"$push": "$$ROOT"}  # Store original documents in an array
            }},

            # Step 3: Filter groups where count > 1 (non-unique values)
            {"$match": {"count": {"$gt": 1}}},

            # Step 4: Unwind the documents array to restore one document per row
            {
                "$setWindowFields": {
                    "sortBy": {"_id": 1},  # Sort groups by _id (or another field)
                    "output": {
                        "groupRank": {
                            "$rank": {}  # Assign a rank to each group
                        }
                    }
                }
            },
            {
                "$set": {
                    "color": {
                        "$cond": {
                            "if": {"$eq": [{"$mod": ["$groupRank", 2]}, 0]},  # Check if rank is even
                            "then": True,  # If even, set to true
                            "else": False  # If odd, set to false
                        }
                    }
                }
            },

            # Step 3: Unwind the documents array to restore one document per row
            {"$unwind": "$documents"},

            # Step 4: Add the "groupRank" field to each document
            {
                "$set": {
                    "documents.color": "$color"  # Add the group rank to each document
                }
            },


            # Step 5: Project the desired fields
            {"$replaceRoot": {"newRoot": "$documents"}},  # Replace the root with the original document
            {"$project": {
                "_id": False,
                "rec_id": True,
                "human_validated": True,
                "matched_record": True,
                "color": True
            }},
            {"$match": recids_query},
            {"$sort": {"matched_record": 1}},


            # Step 6: Use $facet to split the results
            {"$facet": {
                "total": [{"$count": "total"}],  # Count the total number of filtered documents
                "results": [{"$limit": 300}]  # Limit the results to 20 documents
            }}
        ]

    # Execute the query
    result = list(mongo_db_dedup[col_name].aggregate(pipeline))
    recs = result[0]['results']
    nb_total_recs = result[0]['total'][0]['total'] if result[0]['total'] else 0
    return JsonResponse({'rec_ids': [{'rec_id': r['rec_id'],
                                      'human_validated': r.get('human_validated', False),
                                      'color': r.get('color', False),
                                      'matched_record': r.get('matched_record', None)} for r in recs],
                         'nb_total_recs': nb_total_recs})


@login_required
def local_rec(request, rec_id=None, col_name=None):
    """
    Entry point when making an action on a local record.

    This view is an API that can be used to get or post a local
    record. With a post request, the system will validate
    matching records or cancel the validation.

    Parameters
    ----------
    request : HttpRequest
        The HTTP request object.
    rec_id : str, optional
        The record ID of the local record.
    col_name : str, optional
        The name of the collection.

    Returns
    -------
    HttpResponse
        The HTTP response object.
    """
    if request.method == 'GET':
        return get_local_rec(request, rec_id, col_name)

    if request.method == 'POST':
        return post_local_rec(request, rec_id, col_name)


@login_required
def get_local_rec(_, rec_id, col_name, jsonresponse=True):
    """Get a local record with its possible matches

    Format of the response is:
        {
            "briefrec": "Brief record in a human-readable format",
            "fullrec": "Marc21",  # Full record in Marc21 format
            "matched_record": "Rec_id of the matched record",
            "possible_matches": [
                {
                    "briefrec": "Brief record in a human-readable format",
                    "fullrec": "Marc21",  # Full record in Marc21 format
                    "scores": {"titles": 0.8, "creators": 0.5, ...},  # Similarity scores
                    "similarity_score": 0.68,  # Overall similarity score
                    "rec_id": "Rec_id of the possible match"
                },
                ...
            ]
        }

    Idea is to iterate the possible matches and get the data from the database.
    """

    # Get the record from the database
    rec = mongo_db_dedup[col_name].find_one({'rec_id': rec_id}, {'_id': False})
    briefrec = RawBriefRec(rec['briefrec'])

    # Prepare the dict with matching and possible matching records
    rec_data = {'briefrec': tools.display_briefrec(briefrec),
                'fullrec': tools.json_to_marc(rec['fullrec']),
                'matched_record': '',
                'possible_matches': []}

    possible_matches = []
    if rec.get('possible_matches') is not None:
        possible_matches = rec['possible_matches']
    if rec.get('matched_record') is not None:
        rec_data['matched_record'] = rec['matched_record']

    # Get data of possible matches
    for possible_match in possible_matches:

        # if possible_match.startswith('(DNB)'):
        #     nz_ext_data = get_dnb_rec(request, possible_match)
        # else:

        # Get the NZ record from the database
        rec = mongo_col_nz.find_one({'mms_id': possible_match}, {'_id': False})
        if rec is None:
            continue

        # Prepare the dict with the data of the possible match
        rec = dict(rec)

        nz_briefrec = JsonBriefRec(rec)
        scores = evaluate_records_similarity(briefrec, nz_briefrec)
        nz_ext_data = {'briefrec': tools.display_briefrec(nz_briefrec),
                       'fullrec': tools.json_to_marc(rec),
                       'scores': scores,
                       'similarity_score': get_similarity_score(scores),
                       'rec_id': possible_match}
        rec_data['possible_matches'].append(nz_ext_data)

    return JsonResponse(rec_data) if jsonresponse is True else rec_data


@login_required
def post_local_rec(request, rec_id=None, col_name=None):
    """Change selected matching record for a local record

    If the request body contains a JSON object with a key 'matched_record', it
    will update the record with the given rec_id to have the matched_record. It can also
    be used with an empty string to remove the matched record.
    """
    matched_record = json.loads(request.body)['matched_record']
    _ = mongo_db_dedup[col_name].update_one({'rec_id': rec_id}, {'$set': {'matched_record': matched_record,
                                                                          'human_validated': True}})
    return JsonResponse({'status': 'ok'})


@login_required
def add_to_training_data(request):
    """Add current records pair in training data set

    This view is an API that can be used to add a pair of records in the training data set.
    """
    # Get the data from the request, it contains the local record id, the NZ record, id and the decision of the user
    data = json.loads(request.body)

    # Get the local record from the database
    local_record = mongo_db_dedup[data['col_name']].find_one({'rec_id': data['local_recid']}, {'_id': False})
    briefrec = RawBriefRec(local_record['briefrec'])

    # Check if the nz fetched record is in the possible matches
    if data['ext_nz_recid'] not in local_record['possible_matches']:
        return JsonResponse({'status': 'error', 'message': 'External record not found in possible matches'})

    # Get the NZ record from the database
    nz_ext_rec = mongo_col_nz.find_one({'mms_id': data['ext_nz_recid']}, {'_id': False})
    nz_briefrec = JsonBriefRec(nz_ext_rec)

    # Calculate the similarity score
    scores = evaluate_records_similarity(briefrec, nz_briefrec)
    similarity_score = get_similarity_score(scores)

    # Preparation of the document with the training data
    # We use the json version of the full records
    training_entry = {'local_fullrec': local_record['fullrec'],
                      'ext_nz_fullrec': nz_ext_rec['marc'],
                      'similarity_score': similarity_score,
                      'is_match': data['is_match'],
                      'match_id': f'{local_record["rec_id"]}-{data["ext_nz_recid"]}',
                      'type': local_record['format']}

    # Update or insert a new record in the training data collection
    result = mongo_db_dedup[f'training_data'].replace_one({'match_id': training_entry['match_id']},
                                                          training_entry,
                                                              upsert=True)

    # Return the result of the operation in a message to display
    if result.modified_count == 0:
        return JsonResponse({'status': 'ok', 'message': 'New entry added to training data'})
    else:
        return JsonResponse({'status': 'ok', 'message': 'Entry updated in training data'})


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
                return redirect('dedup:index')

    return render(request, 'dedup/login.html', {'form': AuthenticationForm()})


@login_required
def logout_view(request):
    """Logout the user and redirect to the index page"""
    logout(request)
    return redirect('dedup:index')


# @login_required
# def get_dnb_rec(request, rec_id):
#     if rec_id.startswith('(DNB)'):
#         rec_id = rec_id[5:]
#     # Define the parameters for the search
#     params = {
#         "version": "1.1",
#         "operation": "searchRetrieve",
#         "query": f"identifier={rec_id}",
#         "recordSchema": "MARC21-xml"
#     }
#     nsmap = {'srw': 'http://www.loc.gov/zing/srw/',
#              'm': 'http://www.loc.gov/MARC21/slim',
#              'diag': 'http://www.loc.gov/zing/srw/diagnostic/'}
#
#     base_url = "https://services.dnb.de/sru/dnb"
#
#     # Send the request
#     response = requests.get(base_url, params=params)
#     xml_rec = XmlData(response.content)
#
#     records = [XmlData(etree.tostring(tools.remove_ns(r))) for r in
#                xml_rec.content.findall('.//m:record', namespaces=nsmap)]
#
#     rec = records[0] if len(records) > 0 else None
#
#     data = {'briefrec': BriefRec(xml_rec.content).data,
#             'fullrec': tools.json_to_marc(tools.xml_to_json(rec.content))}
#
#     return JsonResponse(data)
