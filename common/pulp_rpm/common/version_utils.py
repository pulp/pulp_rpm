# -*- coding: utf-8 -*-
"""
Contains the encoding algorithm to support the correct comparison of RPM version
and release numbers.

The encoding algorithm is as follows:

* Each version is split apart by periods. We'll refer to each piece as a segment.
* If a segment only consists of numbers, it's transformed into the format ``dd-num``, where:

  * **dd**  - number of digits in the value, including leading zeroes if necessary
  * **num** - value of the int being encoded

* If a segment contains one or more letters, it is:

 * Split into multiple segments of continuous letters or numbers. For example, 12a3bc becomes
   12.a.3.bc
 * All of these number-only subsegments is encoded according to the rules above.
 * All letter subsegments are prefixed with a dollar sign ($).
 * Any non-alphanumeric characters are discarded.

Examples:

* 3.9    -> 01-3.01-9
* 3.10   -> 01-3.02-10
* 5.256  -> 01-5.03-256
* 1.1a   -> 01-1.01-1.$a
* 1.a+   -> 01-1.$a
* 12a3bc -> 02-12.$a.01-3.$bc
* 2xFg33.+f.5 -> 01-2.$xFg.02-33.$f.01-5

Resources:
* http://fedoraproject.org/wiki/Archive:Tools/RPM/VersionComparison
* http://rpm.org/api/4.4.2.2/rpmvercmp_8c-source.html
"""

import re

# Used to separate the digit count from the actual int value
NUMBER_DIVIDER = '-'

# Used to ensure letters are considered older than numbers
LETTERS_TEMPLATE = '$%s'  # substitute in segment

# From the Fedora link above:
# "digits" and "letters" are defined as ASCII digits ('0'-'9') and ASCII letters
# ('a'-'z' and 'A'-'Z'). Other Unicode digits and letters (like accented Latin letters)
# are not considered letters.
#
#  Each label is separated into a list of maximal alphabetic or numeric sections, with
#  separators (non-alphanumeric characters) ignored.
#
# This regex is used on a single character to determine if it should be included.
LETTER_REGEX = re.compile(r'[a-zA-Z]')
INT_REGEX = re.compile('^-?\d+$')

# Keys the encoded fields are stored under in the unit's metadata
VERSION_INDEX = 'version_sort_index'
RELEASE_INDEX = 'release_sort_index'


class TooManyDigits(ValueError):
    pass


def encode(field):
    """
    Translates a package version into a string representation that is sortable according
    to the rules for RPM versions.

    :param field: version or release string to encode
    :type  field: str

    :return: encoded value that should be used for comparison searches and sorting
    """
    if not isinstance(field, basestring):
        raise TypeError('field must be a non-empty string')

    if len(field) == 0:
        raise ValueError('field must be a non-empty string')

    try:
        all_segments = reduce(_split_segments, field).split('.')
        encoded_segments = map(_encode_segment, all_segments)
        encoded_field = '.'.join(encoded_segments)
    except TooManyDigits:
        raise ValueError('Cannot not encode %s; too many digits in the field' % field)

    return encoded_field


# -- private ------------------------------------------------------------------

def _split_segments(x, y):
    """
    Used in the reduce() on the original version to break apart any combined letters/numbers
    into separate segments.

    From the Fedora link above:
      Each label is separated into a list of maximal alphabetic or numeric sections, with
      separators (non-alphanumeric characters) ignored. So, '2.0.1' becomes ('2', '0', '1'),
      while ('2xFg33.+f.5') becomes ('2', 'xFg', '33', 'f', '5').

    :type x: str
    :type y: str
    """
    if _is_int(x[-1]) != _is_int(y) and y != '.' and x[-1] != '.':
        y = '.' + y
    return x + y


def _encode_segment(x):
    """
    Encodes a particular segment, taking into account if its contents are numbers
    or letters.

    :type x: str
    :rtype: str
    """
    if _is_int(x):
        return _encode_int(x)
    else:
        clean = filter(LETTER_REGEX.match, x)
        return LETTERS_TEMPLATE % clean


def _encode_int(segment):
    """
    Translates an segment that consists entirely of numbers into its munged format.

    :param segment: segment to translate
    :type  segment: str

    :raise TooManyDigits: if the int is too long to be encoded
    """

    # From the Fedora link above:
    #  All numbers are converted to their numeric value. So '10' becomes 10, '000230'
    #  becomes 230, and '00000' becomes 0.
    #
    # Convert from the int back into a string to remove leading zeroes.

    str_segment = str(int(segment))

    # See module-level docs for more information on the format
    if len(str_segment) > 99:
        raise TooManyDigits()

    digit_prefix = '%02d' % len(str_segment)

    return digit_prefix + NUMBER_DIVIDER + str_segment


def _is_int(x):
    """
    Returns whether or not the given value is an integer.
    :type x: str
    :rtype: bool
    """
    return INT_REGEX.match(x) is not None
