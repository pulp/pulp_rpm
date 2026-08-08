import hashlib


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
    return hashlib.sha256("".join(str_prep_hash).encode("utf-8")).hexdigest()
