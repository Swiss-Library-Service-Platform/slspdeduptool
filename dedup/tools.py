import re

from lxml import etree
from dedupmarcxml.evaluate import evaluate_records_similarity, get_similarity_score
from dedupmarcxml.briefrecord import RawBriefRec, XmlBriefRec, JsonBriefRec

def json_to_marc(rec):
    data = rec['marc'] if 'marc' in rec else rec
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

def display_briefrec(briefrec):
    """Transform a brief record to a displayable format"""
    data = dict()
    for bk in briefrec.data.keys():
        if type(briefrec.data[bk])==list:
            txts = []
            for bk2 in briefrec.data[bk]:
                if type(bk2) == dict:
                    sub_txt = []
                    for bk3 in bk2.keys():

                        # Editions are a list of dictionaries containing a list
                        if type(bk2[bk3])==list:
                            sub_txt.append(', '.join([str(e) for e in bk2[bk3]]))

                        # Titles are a list of dictionaries
                        else:
                            if len(bk2[bk3]) > 0:
                                sub_txt.append(bk2[bk3])
                    txts.append(': '.join(sub_txt))

                else:
                    txts.append(bk2)

            data[bk] = ' / '.join(txts)

        elif type(briefrec.data[bk])==dict:
            txts = []
            for bk2 in briefrec.data[bk].keys():
                if type(briefrec.data[bk][bk2])==list:
                    if len(briefrec.data[bk][bk2]) == 0:
                        continue
                    sep = ': ' if bk == 'titles' else ', '
                    txts.append(sep.join([str(e) for e in briefrec.data[bk][bk2]]))
                elif type(briefrec.data[bk][bk2])==bool:
                    if briefrec.data[bk][bk2] is True:
                        txts.append(bk2)
                else:
                    txts.append(str(briefrec.data[bk][bk2]))

            data[bk] = ' / '.join(txts)
        else:
            data[bk] = briefrec.data[bk]
    return data

# def get_full_local_rec(rec):
#     new_full_local_rec = dict()
#     # # BOOKS
#     # full_local_rec_fields = [
#     #     'rec_id',
#     #     'title',
#     #     'creators',
#     #     'isbn',
#     #     'publishers',
#     #     'city',
#     #     'year',
#     #     'editions',
#     #     'language',
#     #     'extent',
#     #     'parent',
#     #     'content',
#     #     'callnumber',
#     #     'keywords',
#     #     'review',
#     #     'status',
#     #     'format',
#     #     'permalink',
#     #     'category_2',
#     #     'category_1']
#
#     # DVD
#     # full_local_rec_fields = [
#     #     'rec_id',
#     #     'title',
#     #     'creators',
#     #     'std_identifer',
#     #     'publishers',
#     #     'city',
#     #     'year',
#     #     'editions',
#     #     'language',
#     #     'duration',
#     #     'parent',
#     #     'content',
#     #     'callnumber',
#     #     'keywords',
#     #     'review',
#     #     'status',
#     #     'format',
#     #     'permalink',
#     #     'category_2',
#     #     'category_1']
#
#     # JOURNALS
#     # full_local_rec_fields = [
#     #     'rec_id',
#     #     'title',
#     #     'creators',
#     #     'std_identifier',
#     #     'publishers',
#     #     'city',
#     #     'year',
#     #     'language',
#     #     'orig_title',
#     #     'nb_issues']
#
#     for f in full_local_rec_fields:
#         new_full_local_rec[f] = ' / '.join(rec[f]) if type(rec[f]) == list else rec[f]
#
#     return new_full_local_rec


# def evaluate_format(format1: str, format2: str) -> float:
#     """evaluate_format(format1: str, format2: str) -> float
#     Return the result of the evaluation of similarity of two formats
#
#     If format is the same it returns 1, 0 otherwise
#
#     :param format1: format to compare
#     :param format2: format to compare
#
#     :return: similarity score between two formats as float"""
#     format1 = format1.split('/')
#     format2 = format2.split('/')
#     leader1 = format1[0].strip()
#     leader2 = format2[0].strip()
#
#     # Compare leader => 0.4 max
#     score = 0.4 if leader1 == leader2 else 0
#
#     # Compare fields 33X => 0.6 max for the 3 fields
#     f33x_1 = format1[1].strip().split(';')
#     f33x_2 = format2[1].strip().split(';')
#     for i in range(len(f33x_1)):
#         if len(f33x_2) > i:
#             if f33x_1[i] == f33x_2[i]:
#                 score += 0.2
#             elif f33x_1[i].strip() == '' or f33x_2[i].strip() == '':
#                 score += 0.1
#     if score >= 0.4:
#         score = 1
#     if format2[2].strip() != 'p':
#         score = 0
#
#     return score
#
#
# def evaluate_similarity(rec1, rec2):
#     raw_scores = evaluate_records_similarity(rec1, rec2)
#     return get_similarity_score(raw_scores)

def remove_ns(data: etree.Element) -> etree.Element:
    """Remove namespace from XML data
    :param data: `etree.Element` object with xml data
    :return: `etree.Element` without namespace information
    :rtype:
    """
    temp_data = etree.tostring(data).decode()
    temp_data = re.sub(r'\s?xmlns="[^"]+"', '', temp_data).encode()
    return etree.fromstring(temp_data)