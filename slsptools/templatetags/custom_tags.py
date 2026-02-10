from django import template
from datetime import datetime

register = template.Library()

@register.filter
def get_item(dictionary, key):
    temp = dictionary.get(key, '')
    if type(temp) is datetime:
        return temp.strftime("%d.%m.%Y %H:%M")
    else:
        return dictionary.get(key, '')

@register.filter
def map_attr(list_of_dicts, attr):
    return [d.get(attr, '') for d in list_of_dicts]

