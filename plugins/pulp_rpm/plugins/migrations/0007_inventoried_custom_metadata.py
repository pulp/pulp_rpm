import copy
import logging
import os
import pwd
import shutil
import uuid
from xml.etree import ElementTree

from pulp.plugins.types import  database as types_database
from pulp.server import config as pulp_config
from pulp.server.db.model.repository import Repo, RepoImporter, RepoContentUnit


_LOG = logging.getLogger('pulp')

_APACHE_USER = 'apache'

_TYPE_YUM_IMPORTER = 'yum_importer'
_TYPE_YUM_REPO_METADATA_FILE = 'yum_repo_metadata_file'

_REPODATA = 'repodata'
_REPOMD_FILE = 'repomd.xml'

_BASE_FTYPE_LIST = ('primary', 'primary_db', 'filelists_db', 'filelists', 'other',
                    'other_db', 'group', 'group_gz', 'updateinfo', 'updateinfo_db')

# -- migration entry point -----------------------------------------------------

def migrate(*args, **kwargs):
    inventory_custom_metadata()

# -- custom metadata migration -------------------------------------------------

def inventory_custom_metadata():

    repo_list = repositories_with_yum_importers()

    if not repo_list:
        _LOG.info('No yum repositories found to inventory custom metadata on')

    for repo in repo_list:
        migrate_repo(repo)
        remove_repodata_from_scratchpad(repo['id'])


def migrate_repo(repo):

    repo_id = repo['id']

    _LOG.info('Inventorying custom metadata for yum repository %s' % repo_id)

    scratch_pad = repo['scratchpad']

    if _REPODATA not in scratch_pad:
        _LOG.info('Yum repository %s has no custom metadata' % repo_id)
        return

    ftype_contents_dict = scratch_pad[_REPODATA]

    working_dir = importer_working_dir(_TYPE_YUM_IMPORTER, repo_id)
    repodata_dir = os.path.join(working_dir, repo_id, _REPODATA)
    repomd_file_path = os.path.join(repodata_dir, _REPOMD_FILE)

    if not os.path.exists(repomd_file_path):
        _LOG.info('Yum repository %s has no %s, cannot inventory custom metadata' % (repo_id, repomd_file_path))
        return

    ftype_dict = parse_repomd_xml(repomd_file_path, _BASE_FTYPE_LIST)

    for ftype, ftype_data in ftype_dict.items():

        if ftype not in ftype_contents_dict:
            # problematic, the custom metadata exists, but we don't have the contents
            _LOG.info('Skipping custom metadata %s on yum repository %s, contents not found' % (ftype, repo_id))
            continue

        ftype_data['repo_id'] = repo_id

        ftype_file_name = os.path.basename(ftype_data.pop('relative_path'))
        source_path = os.path.join(repodata_dir, ftype_file_name)
        relative_path = '%s/%s' % (repo_id, ftype_file_name)

        if not os.path.exists(source_path):
            _LOG.info('Skipping custom metadata %s on yum repository %s, source file not found' % (ftype, repo_id))
            continue

        content_unit = create_content_unit(ftype_data, relative_path)
        shutil.copyfile(source_path, content_unit['_storage_path'])
        fix_owner(content_unit['_storage_path'])
        add_content_unit_to_repo(repo_id, content_unit)

        _LOG.info('Successfully added custom metadata %s to yum repository %s' % (ftype, repo_id))

# -- pulp utilities ------------------------------------------------------------

def repositories_with_yum_importers():
    repo_importer_collection = RepoImporter.get_collection()
    repo_yum_importers = repo_importer_collection.find({'importer_type_id': _TYPE_YUM_IMPORTER}, fields=['repo_id'])
    yum_repo_ids = [i['repo_id'] for i in repo_yum_importers]
    repo_collection = Repo.get_collection()
    yum_repos = repo_collection.find({'id': {'$in': yum_repo_ids}}, fields=['id', 'scratchpad'])
    return list(yum_repos)


def importer_working_dir(importer_type_id, repo_id):
    storage_dir = pulp_config.config.get('server', 'storage_dir')
    working_dir = os.path.join(storage_dir, 'working', 'repos', repo_id, 'importers', importer_type_id)
    return working_dir


def create_content_unit(unit_data, relative_path=None):
    collection = types_database.type_units_collection(_TYPE_YUM_REPO_METADATA_FILE)
    unit_data['_id'] = str(uuid.uuid4())
    unit_data['_content_type_id'] = _TYPE_YUM_REPO_METADATA_FILE
    unit_data['_storage_path'] = get_content_storage_path(relative_path)
    collection.insert(unit_data, safe=True)
    return unit_data


def get_content_storage_path(relative_path):
    if relative_path is None:
        return None
    if relative_path.startswith('/'):
        relative_path = relative_path[1:]
    storage_dir = pulp_config.config.get('server', 'storage_dir')
    content_storage_path = os.path.join(storage_dir, 'content', _TYPE_YUM_REPO_METADATA_FILE, relative_path)
    content_storage_dir = os.path.dirname(content_storage_path)
    if not os.path.exists(content_storage_dir):
        os.makedirs(content_storage_dir)
        fix_owner(storage_dir)
    return content_storage_path


def fix_owner(start_path):
    apache_user_info = pwd.getpwnam(_APACHE_USER)
    apache_uid = apache_user_info.pw_uid
    apache_gid = apache_user_info.pw_gid

    def _recursive_fix_owner(path):

        os.chown(path, apache_uid, apache_gid)

        if os.path.isdir(path):
            contents = os.listdir(path)
            for c in contents:
                _recursive_fix_owner(os.path.join(path, c))

    _recursive_fix_owner(start_path)


def add_content_unit_to_repo(repo_id, content_unit):
    associated_unit = RepoContentUnit(repo_id, content_unit['_id'], _TYPE_YUM_REPO_METADATA_FILE,
                                      RepoContentUnit.OWNER_TYPE_IMPORTER, _TYPE_YUM_IMPORTER)
    collection = RepoContentUnit.get_collection()
    collection.insert(associated_unit, safe=True)


def remove_repodata_from_scratchpad(repo_id):
    repo_collection = Repo.get_collection()
    repo = repo_collection.find_one({'id': repo_id}, fields=['scratchpad'])
    repo['scratchpad'].pop('repodata', None)
    repo_collection.update({'id': repo_id}, {'$set': {'scratchpad': repo['scratchpad']}}, safe=True)

# -- repodata.xml parsing ------------------------------------------------------

_SPEC_URL = 'http://linux.duke.edu/metadata/repo'

_DATA_TAG = '{%s}data' % _SPEC_URL
_LOCATION_TAG = '{%s}location' % _SPEC_URL
_CHECKSUM_TAG = '{%s}checksum' % _SPEC_URL

_DATA_SKEL = {'data_type': None,
              'relative_path': None,
              'checksum_type': None,
              'checksum': None}


def parse_repomd_xml(repomd_file_path, skip_data_types=None):
    skip_data_types = skip_data_types or []

    if not os.access(repomd_file_path, os.F_OK | os.R_OK):
        return {}

    xml_parser = ElementTree.iterparse(repomd_file_path, events=('end',))
    xml_iterator = iter(xml_parser)

    data_type_dict = {}

    for event, element in xml_iterator:
        if element.tag != _DATA_TAG:
            continue

        if element.attrib['type'] in skip_data_types:
            continue

        data_type = copy.deepcopy(_DATA_SKEL)

        data_type['data_type'] = element.attrib['type']

        location_element = element.find(_LOCATION_TAG)
        if location_element is not None:
            data_type['relative_path'] = location_element.attrib['href']

        checksum_element = element.find(_CHECKSUM_TAG)
        if checksum_element is not None:
            data_type['checksum_type'] = checksum_element.attrib['type']
            data_type['checksum'] = checksum_element.text

        data_type_dict[data_type['data_type']] = data_type

    return data_type_dict


