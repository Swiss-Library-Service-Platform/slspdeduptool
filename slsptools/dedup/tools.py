import re

from lxml import etree
from almasru import dedup

def json_to_marc(rec):
    data = rec['marc']
    new_data = list()
    new_data.append(f'<strong>LDR&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</strong>{data["leader"]}')
    for f_num in data:
        if f_num.startswith('00'):
            new_data.append(f'<strong>{f_num}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</strong> {data[f_num]}')
        elif re.match(r'^\d{3}$', f_num):
            for field in data[f_num]:
                subfields = ' '.join([[f'<strong>$${f}</strong> {subfield[f]}' for f in subfield][0] for subfield in field["sub"]])

                new_data.append(f'<strong>{f_num}&nbsp;{field["ind1"]}&nbsp;{field["ind2"]}&nbsp;</strong> {subfields}')

    new_data = '<br>'.join(sorted(new_data, key=lambda k: 0 if k.startswith('<strong>LDR') else int(k[8:11])))
    return new_data.replace(' ', '&nbsp;')

def json_to_xml(data: dict) -> etree.Element('record'):
    """Transform json record to MarcXML version

    Parameter:
    ----------
    data: dictionary containing the json data of the record to transform
        into xml record. It will only work with the format data used in
        MongoDB main records table

    Returns:
    --------
    etree.Element containing the xml record
    """

    # Create the xml record
    record = etree.Element('record')

    # Iterate all fields
    for tag in data['marc']:

        # The field is the leader
        if tag == 'leader':
            leaderfield = etree.SubElement(record, 'leader')
            leaderfield.text = data['marc'][tag]

        # The field is a controlfield
        elif tag.startswith('00'):
            ctrlfield = etree.SubElement(record, 'controlfield', tag=tag)
            ctrlfield.text = data['marc'][tag]

        # The field is a datafield
        else:
            for field in data['marc'][tag]:

                # Create datafield with indicators
                datafield = etree.SubElement(record, 'datafield', tag=tag, ind1=field['ind1'], ind2=field['ind2'])

                # Create the subfields
                for subf in field['sub']:
                    code = next(iter(subf))
                    subfield = etree.SubElement(datafield, 'subfield', code=code)
                    subfield.text = subf[code]

    # Sort fields
    record[:] = sorted(record, key=lambda field_or_contr: field_or_contr.get('tag', '000'))
    return record

def xml_to_json(xml_data):
    """
    Convert to JSON record for MongoDB

    Returns
    -------
    JsonRecord
        JSON record
    """
    json_record = dict({'marc': dict()})

    # Get leader field
    leader = xml_data.find('leader')
    if leader is not None:
        json_record['marc']['leader'] = leader.text

    # Extract data from controlfields
    for controlfield in xml_data.findall('controlfield'):
        tag = controlfield.get('tag')
        json_record['marc'][tag] = controlfield.text

    # Extract data from datafields
    for datafield in xml_data.findall('datafield'):
        tag = datafield.get('tag')

        datafield_data = dict()

        datafield_data['ind1'] = datafield.get('ind1')
        datafield_data['ind2'] = datafield.get('ind2')
        subfields = datafield.findall('subfield')
        datafield_data['sub'] = [{subfield.get('code'): subfield.text} for subfield in
                                 subfields if subfield.text is not None]
        if tag not in json_record['marc']:
            json_record['marc'][tag] = list()

        json_record['marc'][tag].append(datafield_data)
    return json_record

def get_full_local_rec(rec):
    new_full_local_rec = dict()
    # BOOKS
    full_local_rec_fields = [
        'rec_id',
        'title',
        'creators',
        'isbn',
        'publishers',
        'city',
        'year',
        'editions',
        'language',
        'extent',
        'parent',
        'content',
        'callnumber',
        'keywords',
        'review',
        'status',
        'format',
        'permalink',
        'category_2',
        'category_1']

    # DVD
    # full_local_rec_fields = [
    #     'rec_id',
    #     'title',
    #     'creators',
    #     'std_identifer',
    #     'publishers',
    #     'city',
    #     'year',
    #     'editions',
    #     'language',
    #     'duration',
    #     'parent',
    #     'content',
    #     'callnumber',
    #     'keywords',
    #     'review',
    #     'status',
    #     'format',
    #     'permalink',
    #     'category_2',
    #     'category_1']
    for f in full_local_rec_fields:
        new_full_local_rec[f] = ' / '.join(rec[f]) if type(rec[f]) == list else rec[f]

    return new_full_local_rec


def evaluate_format(format1: str, format2: str) -> float:
    """evaluate_format(format1: str, format2: str) -> float
    Return the result of the evaluation of similarity of two formats

    If format is the same it returns 1, 0 otherwise

    :param format1: format to compare
    :param format2: format to compare

    :return: similarity score between two formats as float"""
    format1 = format1.split('/')
    format2 = format2.split('/')
    leader1 = format1[0].strip()
    leader2 = format2[0].strip()

    # Compare leader => 0.4 max
    score = 0.4 if leader1 == leader2 else 0

    # Compare fields 33X => 0.6 max for the 3 fields
    f33x_1 = format1[1].strip().split(';')
    f33x_2 = format2[1].strip().split(';')
    for i in range(len(f33x_1)):
        if len(f33x_2) > i:
            if f33x_1[i] == f33x_2[i]:
                score += 0.2
            elif f33x_1[i].strip() == '' or f33x_2[i].strip() == '':
                score += 0.1
    if score >= 0.4:
        score = 1
    if format2[2].strip() != 'p':
        score = 0

    return score


def evaluate_similarity(rec1, rec2):
    raw = dedup.evaluate_similarity(rec1, rec2)

    for e in ['date_2', 'parent', 'series', 'issns', 'other_std_num', 'sysnums', 'same_fields_existing',
              'are_analytical', 'are_series']:
        del raw[e]

    raw['format'] = evaluate_format(rec1['format'], rec2['format'])

    if rec2['corp_creators'] is None:
        del raw['corp_creators']
    elif rec2['creators'] is None:
        raw['creators'] = raw['corp_creators']
        del raw['corp_creators']
    else:
        raw['creators'] = (raw['creators'] + raw['corp_creators']) / 1.5
        if raw['creators'] > 1:
            raw['creators'] = 1
        del raw['corp_creators']

    for e in raw:
        if rec1[e] is None or rec2[e] is None:
            raw[e] = None
    return raw


def get_similarity_score(rec1, rec2):
    raw = evaluate_similarity(rec1, rec2)
    if raw['format'] == 0:
        return 0
    scores = []
    for e in raw:
        if e == 'creators' and raw[e] is None:
            scores.append(0.5)

        if raw[e] is not None:
            scores.append(raw[e])

            if e in ['isbns', 'short_title']:
                for n in range(2):
                    scores.append(raw[e] if raw[e] is not None else 0)

    return sum(scores) / len(scores) if len(scores) > 3 else 0


def remove_ns(data: etree.Element) -> etree.Element:
    """Remove namespace from XML data
    :param data: `etree.Element` object with xml data
    :return: `etree.Element` without namespace information
    :rtype:
    """
    temp_data = etree.tostring(data).decode()
    temp_data = re.sub(r'\s?xmlns="[^"]+"', '', temp_data).encode()
    return etree.fromstring(temp_data)