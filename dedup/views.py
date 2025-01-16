from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
import requests
import pymongo
import os
import json

from lxml import etree
from almapiwrapper.record import JsonData, XmlData
from . import tools

from almasru.client import SruClient, SruRecord, IzSruRecord, SruRequest
from almasru.utils import check_removable_records, analyse_records
from almasru import dedup
from almasru.briefrecord import BriefRecFactory, BriefRec
from almasru import config_log

from .tools import json_to_xml, json_to_marc

mongo_uri = os.getenv('mongodb_tir_uri')
mongo_client = pymongo.MongoClient(mongo_uri)

mongo_db_nz = mongo_client['records']
mongo_col_nz = mongo_db_nz['nz_records']
mongo_db_tir = mongo_client['tir']
mongo_col_tir = mongo_db_tir['books']
# mongo_col_tir = mongo_db_tir['dvd']
# mongo_col_tir = mongo_db_tir['journal_titles']


def index(request):
    mms_ids = mongo_col_tir.find({}, {'_id': False, 'rec_id': True})

    return render(request, 'dedup/index.html', {"mms_ids": mms_ids})

def get_local_record_ids(request):
    record_filter = request.GET.get('filter', 'all')
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

    recs = mongo_col_tir.find(recids_query, {'_id': False,
                                                   'rec_id': True,
                                                   'human_validated': True,
                                                   'matched_record': True})

    if record_filter != 'duplicatematch':
        return JsonResponse({'rec_ids': [{'rec_id': rec['rec_id'],
                                          'human_validated': rec['human_validated'] } for rec in recs]})
    else:
        matches = dict()
        recs_ids = [{
            'rec_id': rec['rec_id'],
            'human_validated': rec['human_validated'],
            'matched_record': rec['matched_record']
        } for rec in recs]
        for rec in recs_ids:
            if rec['matched_record'] in matches:
                matches[rec['matched_record']].append(rec['rec_id'])
            else:
                matches[rec['matched_record']] = [rec['rec_id']]
        duplicate_recids = []
        for match in matches:
            if len(matches[match]) > 1:
                duplicate_recids += matches[match]
        recs_ids = [rec for rec in recs_ids if rec['rec_id'] in duplicate_recids]
        rec_ids = sorted(recs_ids, key=lambda x: x['matched_record'])
        return JsonResponse({'rec_ids': rec_ids})

def get_nz_rec(request, mms_id):
    rec = mongo_col_nz.find_one({'mms_id': mms_id}, {'_id': False})
    if rec is None:
        return None
    xml_rec = json_to_xml(rec)

    data = {'brief_rec': BriefRec(xml_rec).data,
            'full_rec': json_to_marc(rec)}

    return JsonResponse(data)

def get_dnb_rec(request, rec_id):
    if rec_id.startswith('(DNB)'):
        rec_id = rec_id[5:]
    # Define the parameters for the search
    params = {
        "version": "1.1",
        "operation": "searchRetrieve",
        "query": f"identifier={rec_id}",
        "recordSchema": "MARC21-xml"
    }
    nsmap = {'srw': 'http://www.loc.gov/zing/srw/',
             'm': 'http://www.loc.gov/MARC21/slim',
             'diag': 'http://www.loc.gov/zing/srw/diagnostic/'}

    base_url = "https://services.dnb.de/sru/dnb"


    # Send the request
    response = requests.get(base_url, params=params)
    xml_rec = XmlData(response.content)

    records = [XmlData(etree.tostring(tools.remove_ns(r))) for r in xml_rec.content.findall('.//m:record', namespaces=nsmap)]

    rec = records[0] if len(records) > 0 else None

    data = {'brief_rec': BriefRec(xml_rec.content).data,
            'full_rec': tools.json_to_marc(tools.xml_to_json(rec.content))}

    return JsonResponse(data)


def local_rec(request, rec_id):
    if request.method == 'GET':
        return get_local_rec(request, rec_id)

    if request.method == 'POST':
        return post_local_rec(request, rec_id)


def get_local_rec(request, rec_id):
    rec = mongo_col_tir.find_one({'rec_id': rec_id}, {'_id': False})
    rec_data = {'brief_rec': dict(),
                'full_rec': '',
                'matched_record': '',
                'possible_matches': []}

    for bk in rec['brief_rec'].keys():
        if type(rec['brief_rec'][bk])==list:
            rec_data['brief_rec'][bk] = ' / '.join([str(e) for e in rec['brief_rec'][bk]])
        else:
            rec_data['brief_rec'][bk] = rec['brief_rec'][bk]

    possible_matches = []
    if rec.get('possible_matches') is not None:
        possible_matches  = rec['possible_matches']
    if rec.get('matched_record') is not None:
        rec_data['matched_record'] = rec['matched_record']

    rec_data['full_rec'] = tools.get_full_local_rec(rec)

    for possible_match in possible_matches:

        if possible_match.startswith('(DNB)'):
            nz_ext_rec = get_dnb_rec(request, possible_match)
        else:
            nz_ext_rec = get_nz_rec(request, possible_match)
        # if nz_ext_rec is None:
        #     continue
        nz_ext_rec = json.loads(nz_ext_rec.content)
        nz_ext_rec['scores'] = tools.evaluate_similarity(rec['brief_rec'], nz_ext_rec['brief_rec'])
        nz_ext_rec['similarity_score'] = tools.get_similarity_score(rec['brief_rec'], nz_ext_rec['brief_rec'])
        nz_ext_rec['rec_id'] = possible_match
        rec_data['possible_matches'].append(nz_ext_rec)

    return JsonResponse(rec_data)

def post_local_rec(request, rec_id):
    """Change selected matching record for a local record

    If the request body contains a JSON object with a key 'matched_record', it
    will update the record with the given rec_id to have the matched_record. It can also
    be used with an empty string to remove the matched record.
    """
    matched_record = json.loads(request.body)['matched_record']
    _ = mongo_col_tir.update_one({'rec_id': rec_id}, {'$set': {'matched_record': matched_record,
                                                                           'human_validated': True}})
    return JsonResponse({'status': 'ok'})

# def set_matched_record(request, rec_id, matched_record):
#     if request.method != 'POST':
#         return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
#     mongo_col_tir.update_one({'rec_id': rec_id}, {'$set': {'matched_record': matched_record}})
#     return JsonResponse({'status': 'ok'})