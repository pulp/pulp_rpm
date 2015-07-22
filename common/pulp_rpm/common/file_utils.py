import hashlib

CHECKSUM_CHUNK_SIZE = 32 * 1024 * 1024


def calculate_checksum(file_handle):
    """
    Return the sha256 checksum of the given file-like object.

    :param file_handle: A handle to an open file-like object
    :type  file_handle: file-like object
    :return:            The file's checksum
    :rtype:             string
    """
    file_handle.seek(0)
    hasher = hashlib.sha256()
    bits = file_handle.read(CHECKSUM_CHUNK_SIZE)
    while bits:
        hasher.update(bits)
        bits = file_handle.read(CHECKSUM_CHUNK_SIZE)
    return hasher.hexdigest()


def calculate_size(file_handle):
    """
    Return the size of the given file-like object in Bytes.

    :param file_handle: A handle to an open file-like object
    :type  file_handle: file-like object
    :return:            The file's size, in Bytes
    :rtype:             int
    """
    # Calculate the size by seeking to the end to find the file size with tell()
    file_handle.seek(0, 2)
    size = file_handle.tell()
    return size
