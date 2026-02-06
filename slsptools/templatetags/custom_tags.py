from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, '')

@register.filter
def map_attr(list_of_dicts, attr):
    return [d.get(attr, '') for d in list_of_dicts]