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
from io import BytesIO
import pandas as pd

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
            if tools.is_col_allowed(col, request) is True]

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
                        if not col_name.startswith('NZ_') is True and col_name != 'training_data']:
        return HttpResponse(f'Collection "{col_name}" not found', status=404)

    # At least one group must be associated to the collection
    if tools.is_col_allowed(col_name, request) is False:
        return HttpResponse("No right to access this collection", status=403)

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
               'possible': {'match_type': 'possible_match'},
               'possible06': {'match_type': 'possible_match',
                              'max_match_score': {'$gt': 0.6}},
               'possible05': {'match_type': 'possible_match',
                              'max_match_score': {'$gt': 0.5}},
               'possible04': {'match_type': 'possible_match',
                              'max_match_score': {'$gt': 0.4}},
               'nomatch': {'match_type': 'no_match'},
               'match': {'match_type': 'match'},
               'duplicatematch': {'match_type': 'duplicate_match'},
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
            recids_query.update({'matched_record': {'$gte':rec['matched_record']}})

    if record_filter == 'duplicatematch':
        # Normal pipeline for other filters

        pipeline = [
            # 1. Match only documents marked as duplicate
            {"$match": recids_query},

            # 2. Group documents by matched_record
            {"$group": {
                "_id": "$matched_record",
                "documents": {"$push": "$$ROOT"}
            }},

            # 3. Assign a rank to each group to enable color alternation
            {
                "$setWindowFields": {
                    "sortBy": {"_id": 1},
                    "output": {
                        "groupRank": {"$rank": {}}
                    }
                }
            },

            # 4. Define color as True/False alternating by group rank
            {"$set": {
                "color": {"$eq": [{"$mod": ["$groupRank", 2]}, 0]}
            }},

            # 5. Unwind documents so each row is one document again
            {"$unwind": "$documents"},

            # 6. Set color field inside each document
            {"$set": {
                "documents.color": "$color"
            }},

            # 7. Replace root with each document
            {"$replaceRoot": {"newRoot": "$documents"}},

            # 8. Project only relevant fields
            {"$project": {
                "_id": False,
                "rec_id": True,
                "human_validated": True,
                "matched_record": True,
                "color": True,
                "match_type": True,
            }},

            # 9. Re-apply match filter if needed (e.g. for paging by rec_id)
            {"$match": recids_query},

            # 10. Sort by matched_record
            {"$sort": {"matched_record": 1}},

            # 11. Split results: total count and limited result page
            {"$facet": {
                "total": [{"$count": "total"}],
                "results": [{"$limit": 300}]
            }}
        ]
    else:
        # Workflow for all and no match and possible match filter
        pipeline = [
            {"$match": recids_query},
            {"$project": {
                "_id": False,
                "rec_id": True,
                "human_validated": True,
                "matched_record": True
            }},
            {"$facet": {  # split data
                "total": [  # Count nb documents
                    {"$count": "total"}
                ],
                "results": [
                    {"$limit": 300}
                ]
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
def get_local_rec(request, rec_id, col_name, jsonresponse=True):
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

    # Get the model used to calculate the similarity score
    selected_model = request.GET.get('selectedModel', 'mean')

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
                       'similarity_score': get_similarity_score(scores, method=selected_model),
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
    recids_to_check_for_duplicate_match = []

    orig_rec = mongo_db_dedup[col_name].find_one({'rec_id': rec_id},
                                                 {'_id': False,
                                                  'matched_record': True})
    if orig_rec is not None:
        recids_to_check_for_duplicate_match.append(orig_rec['matched_record'])

    # Case if button "cancel match" is clicked
    if matched_record is None or matched_record=='':
        matched_record = None

        _ = mongo_db_dedup[col_name].update_one({'rec_id': rec_id},
                                                {'$set': {'matched_record': matched_record,
                                                          'human_validated': True,
                                                          'match_type': 'no_match'}})
    else:
        recids_to_check_for_duplicate_match.append(matched_record)
        _ = mongo_db_dedup[col_name].update_one({'rec_id': rec_id},
                                                {'$set': {'matched_record': matched_record,
                                                          'human_validated': True,
                                                          'match_type': 'match'}})

    # We need to update 'match_type' field. If we add or remove a match count of matches could change
    for recid_to_check_for_duplicate_match in recids_to_check_for_duplicate_match:
        # Find recids of record that need to be updated
        # Cancel match: old matched record ID
        # Select match: current matched record ID
        recids = [r['rec_id'] for r in mongo_db_dedup[col_name].find({'matched_record': recid_to_check_for_duplicate_match},
                                      {'rec_id': True,
                                       '_id': False})]
        # Number of recids decide if we have a duplicate match or not
        if len(recids) > 1:
            _ = mongo_db_dedup[col_name].update_many({'rec_id': {'$in': recids}},
                                                      {'$set': {'match_type': 'duplicate_match'}})
        elif len(recids) == 1:
            recid = recids[0]
            _ = mongo_db_dedup[col_name].update_one({'rec_id': recid},
                                                    {'$set': {'match_type': 'match'}})

    return JsonResponse({'status': 'ok'})


@login_required
def add_to_training_data(request):
    """Add current records pair in training data set

    This view is an API that can be used to add a pair of records in the training data set.
    """
    # Get the data from the request, it contains the local record id, the NZ record, id and the decision of the user
    data = json.loads(request.body)

    # Get the model used to calculate the similarity score
    selected_model = data.get('selectedModel', 'mean')

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
    similarity_score = get_similarity_score(scores, method=selected_model)

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

@login_required
def get_matching_records(request, col_name=None):
    """Get matching records for a collection"""

    # possible matches
    query = {'possible_matches.0': {'$exists': 1}, 'matched_record': None}
    update = {"$set": {'match_type': 'possible_match'}}
    mongo_db_dedup[col_name].update_many(query, update)

    # No matches
    query = {'possible_matches.0': {'$exists': 0}, 'matched_record': None}
    update = {"$set": {'match_type': 'no_match'}}
    mongo_db_dedup[col_name].update_many(query, update)

    # matches and multi_matches
    query = {'matched_record': {'$ne': None}}
    project = {'matched_record': 1, '_id': 0}
    matched_ids = [recid['matched_record'] for recid in mongo_db_dedup[col_name].find(query, project)]

    matched_unique, matched_duplicate = tools.split_unique_and_duplicates(matched_ids)

    query = {"matched_record": {"$in": matched_unique}}
    update = {"$set": {'match_type': 'match'}}
    mongo_db_dedup[col_name].update_many(query, update)
    query = {"matched_record": {"$in": matched_duplicate}}
    update = {"$set": {'match_type': 'duplicate_match'}}
    mongo_db_dedup[col_name].update_many(query, update)

    matching_records = mongo_db_dedup[col_name].find({'match_type': {'$in': ['match', 'duplicate_match', 'possible_match']}},
                                                           {'_id': False,
                                                            'rec_id': True,
                                                            'matched_record': True,
                                                            'possible_matches': True,
                                                            'match_type': True})
    data = []
    for matching_record in matching_records:
        if matching_record['match_type'] in ['match', 'duplicate_match']:
            # Matched record
            data.append({'rec_id': matching_record['rec_id'],
                         'matched_record': matching_record['matched_record'],
                         'match_type': matching_record['match_type']})
        elif matching_record['match_type'] == 'possible_match':
            # No match but possible matches
            for possible_match in matching_record['possible_matches']:
                data.append({'rec_id': matching_record['rec_id'],
                             'matched_record': possible_match,
                             'match_type': matching_record['match_type']})

    if len(data) == 0:
        return collection(request, col_name)

    # create dataframe from the data
    df = pd.DataFrame(data)

    # Export data to Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)

    # Prepare response with the Excel file
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="export_{col_name}.xlsx"'

    return response

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
