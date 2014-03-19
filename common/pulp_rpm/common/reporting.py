# -*- coding: utf-8 -*-
"""
Contains methods related to formatting the progress reports sent back to Pulp
by RPM plugins.
"""
import traceback


def format_exception(e):
    """
    Formats the given exception to be included in the report.

    :return: string representation of the exception
    :rtype:  str
    """
    return str(e)


def format_traceback(tb):
    """
    Formats the given traceback to be included in the report.

    :return: string representation of the traceback
    :rtype:  str
    """
    if tb:
        return traceback.extract_tb(tb)
    else:
        return None
