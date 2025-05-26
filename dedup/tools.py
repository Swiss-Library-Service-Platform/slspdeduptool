"""
This module provides utility functions for handling MARC records and transforming them between JSON, XML, and HTML formats.

Functions:
- json_to_marc: Converts a JSON MARC record to an HTML string.
- json_to_xml: Transforms a JSON record into MarcXML format.
- xml_to_json: Converts an XML MARC record to a JSON format.
- display_briefrec: Transforms a brief record into a displayable format.
- remove_ns: Removes namespace information from an XML element.
"""

import re
from typing import Dict, Union

from lxml import etree
from dedupmarcxml import RawBriefRec, JsonBriefRec, XmlBriefRec
from django.http import HttpRequest


def json_to_marc(rec: Dict) -> str:
    """
    Transform a JSON MARC record to an HTML string.

    Parameters:
    -----------
    rec : dict
        The JSON MARC record to be transformed.

    Returns:
    --------
    str
        The HTML string representation of the MARC record.
    """
    # Get the data from the record, in NZ mongodb the full record
    # is stored in the 'marc' key. In dedup database the full record
    # is stored in the root of the record.
    data = rec['marc'] if 'marc' in rec else rec

    # We store the displayable data in a list
    new_data = list()
    new_data.append(f'<strong>LDR&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</strong>{data["leader"]}')
    for f_num in data:
        # Controlfields
        if f_num.startswith('00'):
            new_data.append(f'<strong>{f_num}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</strong> {data[f_num]}')

        # Datafields
        elif re.match(r'^\d{3}$', f_num):
            for field in data[f_num]:
                # Subfields
                subfields = ' '.join([[f'<strong>$${f}</strong> {subfield[f]}' for f in subfield][0] for subfield in field["sub"]])

                new_data.append(f'<strong>{f_num}&nbsp;{field["ind1"]}&nbsp;{field["ind2"]}&nbsp;</strong> {subfields}')

    # At the end we join the data and return it
    new_data = '<br>'.join(sorted(new_data, key=lambda k: 0 if k.startswith('<strong>LDR') else int(k[8:11])))
    return new_data.replace(' ', '&nbsp;')


def json_to_xml(data: dict) -> etree.Element('record'):
    """
    Transform a JSON record to MarcXML format.

    Parameters:
    -----------
    data : dict
        The JSON data of the record to transform into an XML
        record. It will only work with the format data used
        in MongoDB main records table.

    Returns:
    --------
    etree.Element
        An XML element containing the MarcXML record.
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


def xml_to_json(xml_data: etree.Element) -> Dict:
    """
    Convert an XML MARC record to a JSON format suitable for MongoDB.

    Parameters
    ----------
    xml_data : etree.Element
        The XML data of the MARC record to be converted.

    Returns
    -------
    dict
        A dictionary containing the JSON representation of the MARC record.
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


def display_briefrec(briefrec: Union[RawBriefRec, JsonBriefRec, XmlBriefRec]) -> dict:
    """
    Transform a brief record into a displayable format.

    This function takes a brief record and converts it into a dictionary
    where each key corresponds to a field in the brief record, and the value
    is a string representation of that field, suitable for display purposes.

    Parameters:
    -----------
    briefrec : Union[RawBriefRec, JsonBriefRec, XmlBriefRec]
        The brief record to be transformed.

    Returns:
    --------
    dict
        A dictionary where each key is a field from the brief record and the value
        is a string representation of that field.
    """
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


def remove_ns(data: etree.Element) -> etree.Element:
    """
    Remove namespace from XML data.

    Parameters:
    -----------
    data : etree.Element
        The XML element from which the namespace should be removed.

    Returns:
    --------
    etree.Element
        The XML element without namespace information.
    """
    temp_data = etree.tostring(data).decode()
    temp_data = re.sub(r'\s?xmlns="[^"]+"', '', temp_data).encode()
    return etree.fromstring(temp_data)


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

    # If the collection name starts with 'NZ_' or is 'training_data', access is denied
    if col_name.startswith('NZ_') is True or col_name == 'training_data':
        return False

    # At least one group must be associated to the collection
    user_groups = list(request.user.groups.values_list("name", flat=True))
    print(user_groups)
    if any(col_name.startswith(user_group) for user_group in user_groups):
        return True
    print('access denied')
    return False