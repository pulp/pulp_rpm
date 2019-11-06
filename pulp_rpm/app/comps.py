import hashlib


def strdict_to_dict(value):
    """
    Convert libcomps StrDict type object to standard dict.

    Args:
        value: a libcomps StrDict

    Returns:
        lang_dict: a dict

    """
    lang_dict = {}
    if len(value):
        for i, j in value.items():
            lang_dict[i] = j
    return lang_dict


def dict_digest(dict):
    """
    Calculate a hexdigest for a given dictionary.

    Args:
        dict: a dictionary

    Returns:
        A digest

    """
    prep_hash = list(dict.values())
    str_prep_hash = [str(i) for i in prep_hash]
    str_prep_hash.sort()
    return hashlib.sha256(''.join(str_prep_hash).encode('utf-8')).hexdigest()
