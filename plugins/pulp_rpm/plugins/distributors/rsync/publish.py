# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software;
# if not, see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

from gettext import gettext as _
import logging
import os
import tempfile
import time
import functools

from pulp.common import dateutils
from pulp.server import config as pulp_config
from pulp.server.exceptions import PulpCodedException
from pulp.plugins.util.publish_step import UnitPublishStep, PublishStep, CopyDirectoryStep
from pulp.server.db.model.criteria import UnitAssociationCriteria
from pulp.server.db.model.repository import RepoPublishResult
from pulp.server.db.model import Distributor

import pulp_rpm.common.constants as constants

from . import configuration
from .utils import CopySelectedStep, Lazy, run, common_path

#import kobo.shortcuts

ASSOCIATED_UNIT_DATE_KEYWORD = "created"
LOG_PREFIX_NAME="pulp.plugins"

def getLogger(name):
    log_name = LOG_PREFIX_NAME + "." + name
    return logging.getLogger(log_name)

_LOG = getLogger(__name__)
STORAGE_PATH = storage_dir = pulp_config.config.get('server', 'storage_dir')

class UnknownRepositoryType(Exception):
    def __init__(self, repo_type):
       self.repo_type = repo_type

    def __str__(self):
        return "RSync distributor can't work with %s repo type" % self.repo_type


def get_unit_types(repo_type):
    if repo_type == "rpm-repo":
        return ["rpm", "srpm"]
    elif repo_type == "docker-repo":
        return ["docker_image"]


def get_unit_fields(repo_type):
    if repo_type == "rpm-repo":
        return ["relativepath", "cdn_path", "_storage_path", "name", "version",
                    "release", "epoch", "arch", "checksumtype", "checksum", "signature"]
    elif repo_type == "docker-repo":
        return ["relativepath", "_storage_path", "image_id", "digest"]


def get_extra_sync_data(repo, docker_version=None):
    if repo.notes["_repo-type"]  == "rpm-repo":
         return ["repodata"]
    elif repo.notes["_repo-type"]  == "docker-repo":
        if docker_version == "v2":
            return ["tags/list", "%s.json" % (repo.id)]
        else:
            return []


def get_exclude(repo_type):
    if repo_type == "rpm-repo":
        return [".*", "repodata.old"]
    elif repo_type == "docker-repo":
        return []


def get_origin_rel_path(unit, config):
    """
    return relative path of content unit in remote fs

    :param unit: Pulp content unit
    :type unit: Unit
    :param configuration: configuration of distributor
    :type configuration: dict
    """

    STORAGE_PATH = storage_dir = pulp_config.config.get('server', 'storage_dir')
    content_base = os.path.join(STORAGE_PATH, "content", unit.metadata["_content_type_id"])
    rel_unit_path = os.path.relpath(unit.storage_path, content_base)
    remote_content_base = configuration.get_remote_content_base(config)
    remote_base = os.path.join(remote_content_base, unit.metadata["_content_type_id"])
    return os.path.join(remote_base, rel_unit_path)


def make_link_unit(repo_type, unit, extra_dst_path, working_dir,
                   remote_repo_path, remote_root, configuration):
    """
    This method creates symlink in working directory, pointing to remote
    content directory, so they can be sync to remote server

    :param repo_type: type of repository
    :type repo_type: str
    :param unit: Pulp content unit
    :type unit: Unit
    :param extra_dst_path: ending path for processes units
                          (for example 'Packages' for rpm)
    :type extra_dst_path: str
    :param working_dir: Working directory
    :type working_dir: str
    :param remote_repo_path: relative repo destination path on remote server
    :type remote_repo_path: str
    :param remote_root: remote destination root directory
    :type remote_root: str
    :param configuration: configuration of distributor
    :type configuration: dict
    """

    out_path = ""
    if unit.type_id == "rpm":
        filename =  unit.metadata["relativepath"]
        extra_src_path = [".relative"]
    elif unit.type_id == "docker_image":
        filename = unit.unit_key["image_id"]
        extra_src_path = [".relative"]
    elif unit.type_id == "docker_blob":
        filename = unit.unit_key["digest"]
        extra_src_path = [".relative", "blobs"]
        out_path = "blobs/"
    elif unit.type_id == "docker_manifest":
        filename = unit.unit_key["digest"]
        extra_src_path = [".relative", "manifests"]
        out_path = "manifests/"
    if not os.path.exists(os.path.join(working_dir, extra_dst_path, *extra_src_path)):
        os.makedirs(os.path.join(working_dir, extra_dst_path, *extra_src_path))

    origin_path = get_origin_rel_path(unit, configuration)

    dest = os.path.join(working_dir, *([extra_dst_path] + extra_src_path + [filename]))
    link_source = os.path.relpath(os.path.join(remote_root, origin_path),
                                  os.path.join(remote_root, remote_repo_path.lstrip("/"), out_path, extra_dst_path))

    _LOG.debug("LN %s -> %s " % (link_source, dest))
    if os.path.islink(dest):
        os.remove(dest)

    os.symlink(link_source, dest)
    return os.path.join(*([extra_dst_path] + extra_path + [filename]))


class RSyncPublishStep(PublishStep):
    _CMD = "rsync"
    _AZQ = "-rtKOzi" # recursive, symlinks, timestamps, keep dir links, omit dir times, compress, itemize

    def __init__(self, step_type, file_list, src_prefix, dest_prefix,
                 working_dir=None, distributor_type=None, config=None,
                 fast_forward=None, exclude=[], delete=False, links=False):
        self.description = _('Rsync files to remote destination')
        super(PublishStep, self).__init__(step_type,working_dir=working_dir,
                                          #distributor_type=distributor_type,
                                          config=config)
        self.file_list = file_list
        self.fast_forward = fast_forward
        self.exclude = []
        self.delete = delete
        self.src_prefix = src_prefix
        self.dest_prefix = dest_prefix
        self.links = links

    def remote_mkdir(self, path):
        _LOG.debug("remote_mkdir: %s" % (path))
        remote = self.get_config().flatten()["remote"]
        if not path or path == '/':
            return (True, "path is empty")
        if remote['auth_type'] == 'local':
            # XXX
            return ()
        remote_root = remote['root'].rstrip("/")
        path = path.rstrip("/")

        if self.remote_dir_exists(path):
            return (True, "%s exists" % path)
        is_ok, output = self.remote_mkdir(os.path.dirname(path))
        if self.remote_dir_exists(path):
            return (True, "%s exists" % path)
        #_LOG.info("%s is_ok %s" % (path, is_ok))
        if not is_ok:
            return (is_ok, output)
        _LOG.info("Making directory on remote server: %s/%s" % (remote_root, path))
        args = self.make_ssh_cmd() + [remote["host"],'mkdir -vp %s/%s' % (remote_root, path)]
        is_ok, output = self.call(args)
        if not is_ok:
            # check for race condition
            if self.remote_dir_exists(path):
                return (True, "%s exists" % path)
        return (is_ok, output)

    def remote_dir_exists(self, path):
        remote = self.get_config().flatten()["remote"]
        if remote['auth_type'] == 'local':
            # XXX
            return ()
        remote_root = remote['root'].rstrip("/")
        if 'akamai' in remote['host']:
            args = self.make_ssh_cmd() + [remote["host"], 'ls %s/%s' % (remote_root, path)]
        else:
            args = self.make_ssh_cmd() + [remote["host"], 'stat -c "%%F" %s/%s' % (remote_root, path)]
        is_ok, output = self.call(args, include_args_in_output=False)
        output = [ line.strip() for line in output.splitlines() ]
        # Filter out expected warnings
        for substring in ("list of known hosts",
                          "Inappropriate ioctl for device",
                          "Shared connection to" ):
            output = [ line for line in output if substring not in line ]
        #_LOG.info("dir_exists path is_ok output: %s %s %s" % (path, is_ok, output))
        if is_ok and ("directory" in output or os.path.basename(path) in output):
            return True
        return False

    def make_ssh_cmd(self, args=None, for_rsync=False):
        user = self.get_config().flatten()["remote"]['ssh_login']
        key = self.get_config().flatten()["remote"]['key_path'] # must be an abs path

        # -e 'ssh -l l_name -i key_path'
        # use shared ssh connection for other threads
        cmd = ['ssh',
               '-l', user,
               '-i', key,
               '-o', 'StrictHostKeyChecking no',
               '-o', 'UserKnownHostsFile /dev/null',
               '-S', '/tmp/rsync_distributor-%r@%h:%p',
               '-o', 'ControlMaster auto',
               '-o', 'ControlPersist 10']
        if not for_rsync:
            # -t -t is necessary for Akamai
            cmd.extend(['-t'])
        if args:
            cmd += args
        return cmd

    def make_authentication(self):
        """
        Used when rsync uses SSH as the remote shell.

        :return: str. e.g., '-e ssh -l ssh_login_user -i /key_path'
        :rtype: str
        """
        if self.get_config().flatten()["remote"]['auth_type'] == 'local':
            return ()
        ssh_parts = []
        for arg in self.make_ssh_cmd(for_rsync=True):
            if " " in arg:
                ssh_parts.append('"%s"' % arg)
            else:
                ssh_parts.append(arg)

        return ['-e', " ".join(ssh_parts)]

    def make_full_path(self, relative_path):
        return os.path.join(self.get_config().flatten()["remote"]['root'],
                            relative_path)

    def make_destination(self, relative_path):
        """
        Parse from self.config information
        to make up a hostname and remote path used
        for rsync command.

        :return: str of the combination of user, host, and dir.
        :rtype:  str
        """
        if self.get_config().flatten()["remote"]['auth_type'] == 'local':
            return self.get_config().flatten()["remote"]['root']
        relative_path = relative_path.lstrip("/")

        user = self.get_config().flatten()["remote"]['login']
        host = self.get_config().flatten()["remote"]['host']
        remote_root = self.get_config().flatten()["remote"]['root']

        return '%s@%s:%s' % (user, host, os.path.join(remote_root, relative_path))

    def is_skipped(self):
        return False

    def call(self, args, include_args_in_output=True):
        """
        Basically a wrapper to call kobo.shortcuts.run.
        If ssh_exchange_identification or max-concurrent-connections
        exceptions are thrown by ssh, up to 10 retries follows.
        """

        for t in xrange(10):
            rv, out = run(cmd=args, can_fail=True)
            if not ( rv and ("ssh_exchange_identification:" in out or "max-concurrent-connections=25" in out) ):
                break
            _LOG.info("Connections limit reached, trying once again in thirty seconds.")
            time.sleep(30)
        if include_args_in_output:
            message = "%s\n%s" % (args, out)
        else:
            message = out
        return (rv == 0, message)

    def make_rsync_args(self, files_from, source_prefix, dest_prefix, exclude=None):
        args = [self._CMD, self._AZQ,
                "--files-from", files_from, "--relative"]
        if exclude:
            for x in exclude:
                args.extend(["--exclude", x])
        args.extend(self.make_authentication())
        if self.delete:
            args.append("--delete")
        if self.links:
            args.append("--links")
        else:
            args.append("--copy-links")
        args.append(source_prefix)
        args.append(self.make_destination(dest_prefix))
        return args

    def rsync(self, dest=None, include_repodata=False):
        if not self.file_list:
            return (True, "Nothing to sync")
        output = ""
        _, tmp_path1 = tempfile.mkstemp(prefix="tmp_rsync_distributor")
        open(tmp_path1, 'w').write("\n".join(sorted(self.file_list)))
        # copy files here, not symlinks
        exclude = self.exclude + get_exclude(self.parent.repo_type)

        (is_successful, this_output) = self.remote_mkdir(self.dest_prefix)
        if not is_successful:
            _LOG.error("Cannot create directory %s: %s" % (self.dest_prefix, this_output))
            return (is_successful, this_output)
        output += this_output
        rsync_args = self.make_rsync_args(tmp_path1, str(self.src_prefix),
                                          self.dest_prefix, exclude)

        (is_successful, this_output) =  self.call(rsync_args)
        _LOG.info(this_output)
        if not is_successful:
            _LOG.error(this_output)
            return (is_successful, this_output)
        output += this_output
        return (is_successful, output)

    def process_main(self):
        (successful, output) = self.rsync(include_repodata=configuration.get_include_repodata(self.parent.repo, self.config))
        if not successful:
            raise PulpCodedException(message=output)


class RSyncFastForwardUnitPublishStep(UnitPublishStep):

    def __init__(self, step_type, link_list, original_list,
                 unit_types=None, repo_type=None,
                 working_dir=None, distributor_type=None, config=None,
                 association_filters=None, relative_symlinks=None,
                 remote_repo_path=None):
        self.description = _('Filtering units')
        """
        Set the default parent, step_type and units_type for the the
        publish step.

        :param step_type: The id of the step this processes
        :type step_type: str
        :param link_list: share list object across publish steps which
         holds information of file links that will be synced
        :type link_list: list
        :param original_list: share list object across publish steps which
         holds information of link origins that will be synced
        :type original_list: list
        :param unit_type: The type of unit this step processes
        :type unit_type: str or list of str
        """

        self.link_list = link_list
        self.original_list = original_list
        self.cdn_list = []
        self.repo_type = repo_type
        self.remote_repo_path = remote_repo_path

        super(RSyncFastForwardUnitPublishStep, self).__init__(step_type,
                                                            association_filters=association_filters,
                                                            #config=config,
                                                            unit_type=unit_types)
        self.unit_fields = get_unit_fields(repo_type)
        self.content_types = set()

    def get_unit_generator(self):
        """
        This method returns a generator for the unit_type specified on the PublishStep.
        The units created by this generator will be iterated over by the process_unit method.

        :return: generator of units
        :rtype:  GeneratorTyp of Units
        """

        types_to_query = list(set(self.unit_type).difference(self.skip_list))
        criteria = UnitAssociationCriteria(type_ids=types_to_query,
                                           association_filters=self.association_filters,
                                           unit_fields=self.unit_fields)
        return self.get_conduit().get_units(criteria, as_generator=True)

    def is_skipped(self):
        return False

    def process_unit(self, unit):
        self.content_types.add(unit.metadata["_content_type_id"])
        # symlink
        self.link_list.append(make_link_unit(self.parent.repo_type, unit,
                                             #self.parent.remote_path,
                                             self.parent.extra_path,
                                             self.get_working_dir(),
                                             self.remote_repo_path,
                                             self.get_config().get("remote")["root"]),
                                             self.get_config())
        # cdn - rpm repos only
        if "cdn_path" in unit.metadata:
            self.cdn_list.append(unit.metadata["cdn_path"])
        # orignal file
        self.original_list.append(unit.storage_path)
        #_LOG.error("unit storage path %s" % (unit.storage_path,))

    def _process_block(self, item=None):
        """
        This block is called for the main processing loop
        """
        package_unit_generator = self.get_unit_generator()
        count = 0
        for package_unit in package_unit_generator:
            if self.canceled:
                return
            count += 1
            self.process_unit(package_unit)
            self.progress_successes += 1
            if count % 50 == 0:
                self.report_progress()

        all_content_types = self.get_config().get("content_types",[])
        all_content_types.extend(self.content_types)
        self.get_config().override_config["content_types"] = list(set(all_content_types))
        cdn_rel_prefix = common_path(self.cdn_list)
        self.get_config().override_config["cdn_rel_prefix"] = cdn_rel_prefix


class Publisher(PublishStep):
    """
    RSync publisher class that is responsible for the actual publishing
    of a yum repository to remote machine.
    """

    def create_date_range_filter(self, config):
        """
        Create a date filter based on start and end issue dates specified in the repo config. The returned
        filter is a dictionary which can be used directly in a mongo query.

        :param config: plugin configuration instance; the proposed repo configuration is found within
        :type  config: pulp.plugins.config.PluginCallConfiguration

        :return: date filter dict with issued date ranges in mongo query format
        :rtype:  {}
        """
        start_date = config.get(constants.START_DATE_KEYWORD)
        end_date = config.get(constants.END_DATE_KEYWORD)
        date_filter = None
        if start_date and not isinstance(start_date, basestring):
            start_date_str = dateutils.format_iso8601_datetime(start_date)
        else:
            start_date_str = start_date
        if end_date and not isinstance(end_date, basestring):
            end_date_str = dateutils.format_iso8601_datetime(end_date)
        else:
            end_date_str = end_date

        if start_date and end_date:
            date_filter = {ASSOCIATED_UNIT_DATE_KEYWORD: {"$gte": start_date_str,
                                                          "$lte": end_date_str}}
        elif start_date:
            date_filter = {ASSOCIATED_UNIT_DATE_KEYWORD: {"$gte": start_date_str}}
        elif end_date:
            date_filter = {ASSOCIATED_UNIT_DATE_KEYWORD: {"$lte": end_date_str}}
        return date_filter

    def _get_root_publish_dir(self):
        if self.repo_type == "rpm-repo":
            if self.predistributor["config"].get("https",False):
                return configuration.get_https_publish_dir(self.get_config())
            else:
                return configuration.get_http_publish_dir(self.get_config())

    def _get_extra_path(self):
        if self.repo_type == "rpm-repo":
            return self.predistributor["config"].get("relative_rpm_path", "")
        else:
            return ""

    def _get_predistributor(self):
        """ Returns distributor which repo has to be published in before
            publish in rsync distributor, content generator.
        """
        if self.repo_type == "rpm-repo":
            dist_type = "yum_distributor"
        elif self.repo_type == "docker-repo":
            dist_type =  "docker_distributor_web"
        else:
            raise UnknownRepositoryType(self.repo_type)
        #distributors = RepoDistributorManager().get_distributors(self.repo.id)
        dist = Distributor.objects.get_or_404(repo_id=self.repo.id,
                                              distributor_type_id=dist_type)
        return dist.distributor_id
        #for distributor in distributors:
        #    if distributor["distributor_type_id"] == dist_type:
        #        return distributor["distributor_id"]

    def get_repo_repo_path(self):
        if "relative_url" in self.repo.notes and self.repo.notes["relative_url"]:
            return self.repo.notes["relative_url"]
        else:
            return self.repo.id

    def get_repo_content_types(self, repo_type):
        if repo_type == "rpm-repo":
            return configuration.RPM_UNIT_TYPES
        elif repo_type == "docker-repo":
            types = configuration.DOCKER_V2_UNIT_TYPES[:]
            types.extend(configuration.DOCKER_UNIT_TYPES)
            return sorted(set(types))

    def get_master_dirs(self):
        dirs = []
        if self.repo_type == "rpm-repo":
            for x in self.get_repo_content_types(self.repo_type):
                repo_relative_path = configuration.get_repo_relative_path(self.repo, self.config)
                dirs.append(os.path.realpath(os.path.join(self._get_root_publish_dir(),
                                                          repo_relative_path)))
        elif self.repo_type == "docker-repo":
            for _type in self.get_repo_content_types(self.repo_type):
                if _type in configuration.DOCKER_V2_UNIT_TYPES:
                    docker_version = "v2"
                else:
                    docker_version = "v1"
                master_dir = configuration.get_docker_master_dir(self.config, docker_version, self.repo)
                dirs.append(master_dir) #os.path.realpath(os.path.join(self._get_root_publish_dir()
        return dirs

    def get_origin_dest_prefix(self):
        if self.get_config().get("cdn_rel_prefix"):
            origin_dest_prefix = self.get_config().get("cdn_rel_prefix")
        elif len(self.get_config().get("content_types")) >= 2:
            origin_dest_prefix = os.path.join("content", "origin", "units")
        else:
            origin_dest_prefix = os.path.join("content", "origin", "units", self.get_config().get("content_types")[0])
        return origin_dest_prefix

    def get_original_list(self):
        original_list = reduce(lambda x,y: x+y,  self.original_lists.values())[:]
        original_rel_prefix = common_path(original_list)
        for p in range(len(original_list)):
            original_list[p] = os.path.relpath(original_list[p], original_rel_prefix)
        return original_list

    def get_original_prefix(self):
        original_list = reduce(lambda x,y: x+y,  self.original_lists.values())
        return common_path(original_list)

    def get_link_list(self, master, docker_version):
        link_rel_prefix = common_path(self.link_lists[master])
        link_list = self.link_lists[master][:]
        for p in range(len(link_list)):
            link_list[p] = os.path.relpath(link_list[p], link_rel_prefix)
        return link_list

    def get_link_prefix(self, master_dir, docker_version):
        return common_path(self.link_lists[master_dir])

    def __init__(self, repo, publish_conduit, config, distributor_type,
                 association_filters=None, relative_path=None,
                 relative_symlinks=True, **kwargs):
        """
        :param repo: Pulp managed Yum repository
        :type  repo: pulp.plugins.model.Repository
        :param publish_conduit: Conduit providing access to relative Pulp functionality
        :type  publish_conduit: pulp.plugins.conduits.repo_publish.RepoPublishConduit
        :param config: Pulp configuration for the distributor
        :type  config: pulp.plugins.config.PluginCallConfiguration
        """

        super(Publisher, self).__init__("Repository publish", repo,
                                        publish_conduit, config,
                                        distributor_type=distributor_type,
                                        working_dir="",#os.path.join(repo.working_dir,
                                        )

        distributor = Distributor.objects.get_or_404(repo_id=self.repo.id,
                                                     distributor_id=publish_conduit.distributor_id)
        self.last_published = distributor["last_publish"]
        self.last_deleted = repo.last_unit_removed
        self.repo_type = repo.notes["_repo-type"]
        self.predistributor = Distributor.objects.get_or_404(repo_id=self.repo.id,
                                                             distributor_id=self._get_predistributor())
        if self.last_published and not isinstance(self.last_published, basestring):
             string_date = dateutils.format_iso8601_datetime(self.last_published)
        elif self.last_published:
            string_date = self.last_published
        else:
            string_date = None

        search_params = {'repo_id': repo.id,
                         'distributor_id': self.predistributor["id"],
                         'started' : {"$gte":string_date}}
        self.predist_history = RepoPublishResult.get_collection().find(search_params)
        self.remote_path = self.get_remote_repo_path()

        if not self.is_fastforward():
            date_filter = None
        else:
            range_criteria = {constants.START_DATE_KEYWORD: self.last_published,
                              constants.END_DATE_KEYWORD: self.predistributor["last_publish"]}
            date_filter = self.create_date_range_filter(range_criteria)

        self.extra_path = self._get_extra_path()
        self.original_lists = {}
        self.link_lists = {}
        remote_repo_path = configuration.get_repo_relative_path(self.repo, self.config,
                                                             docker_version="v2")
        if self.repo_type == "docker-repo":
            web_dir = configuration.get_docker_web_dir(self.config, "v2", self.repo)
            if os.path.exists(web_dir):
                self.add_child(CopyDirectoryStep(web_dir, self.get_working_dir()))
        for master_dir, ctypes in zip(self.get_master_dirs(),
                                      self.get_repo_content_types(self.repo_type)):
            self.original_lists.setdefault(master_dir, [])
            self.link_lists.setdefault(master_dir, [])
            gen_step = RSyncFastForwardUnitPublishStep("Unit query step (%s)" % ctypes,
                                                     self.link_lists[master_dir],
                                                     self.original_lists[master_dir],
                                                     repo_type=self.repo_type,
                                                     unit_types=ctypes,
                                                     distributor_type=distributor_type,
                                                     association_filters=date_filter,
                                                     working_dir=master_dir,
                                                     relative_symlinks=relative_symlinks,
                                                     remote_repo_path=remote_repo_path)
            self.add_child(gen_step)


        origin_dest_prefix = Lazy(str, self.get_origin_dest_prefix)
        self.original_list = Lazy(list, self.get_original_list)
        origin_src_prefix = Lazy(str, self.get_original_prefix)

        self.add_child(RSyncPublishStep("Rsync step (origin)", self.original_list,
                                        origin_src_prefix, origin_dest_prefix,
                                        fast_forward=self.is_fastforward(),
                                        distributor_type=distributor_type,
                                        #working_dir="",#working_dir,
                                        config=config))

        if self.repo_type == "rpm-repo":
            src_prefix = self.get_working_dir()
            dest_prefix = configuration.get_repo_relative_path(self.repo, self.config)
            master_dir = self.get_master_dirs()[0]
            self.add_child(CopySelectedStep(master_dir, self.get_working_dir()),
                                            globs=["repodata"])
            self.add_child(RSyncPublishStep("Rsync step (content)",
                                            Lazy(list, lambda: self.link_lists[master_dir] + get_extra_sync_data(self.repo)),
                                            src_prefix, dest_prefix,
                                            fast_forward=self.is_fastforward(),
                                            distributor_type=distributor_type,
                                            working_dir="",#working_dir,
                                            config=config, links=True,
                                            delete=not self.is_fastforward()))
        elif self.repo_type == "docker-repo":
            src_prefix = self.get_working_dir()
            for master_dir, ctypes in zip(self.get_master_dirs(),
                                          self.get_repo_content_types(self.repo_type)):
                if ctypes in configuration.DOCKER_V2_UNIT_TYPES:
                    docker_version = "v2"
                else:
                    docker_version = "v1"
                step = RSyncPublishStep("Rsync step (content)",
                                        Lazy(list, functools.partial(self.get_link_list, master_dir, docker_version)),
                                        Lazy(str, functools.partial(lambda src_p, master_d, docker_v: os.path.join(src_prefix, self.get_link_prefix(master_d, docker_v)),
                                                          src_prefix, master_dir, docker_version)),
                                        configuration.get_repo_relative_path(self.repo, self.config, docker_version=docker_version),
                                        fast_forward=self.is_fastforward(),
                                        distributor_type=distributor_type,
                                        config=config, links=True,
                                        delete=not self.is_fastforward())
                self.add_child(step)
                if get_extra_sync_data(self.repo, docker_version):
                    step = RSyncPublishStep("Rsync step (content)",
                                            Lazy(list, lambda:get_extra_sync_data(self.repo, docker_version) if self.link_lists[master_dir] else []),
                                            src_prefix,
                                            configuration.get_repo_relative_path(self.repo, self.config, docker_version=docker_version),
                                            fast_forward=self.is_fastforward(),
                                            distributor_type=distributor_type,
                                            config=config, links=True,
                                            delete=not self.is_fastforward())
                    self.add_child(step)

    def is_fastforward(self):
        skip_fast_forward = False
        for entry in self.predist_history:
            skip_fast_forward |= entry.get("distributor_config",{}).get("skip_fast_forward", False)
        if self.last_published:
            last_published = self.last_published #dateutils.parse_iso8601_datetime(self.last_published)
        else:
            last_published = None
        return last_published\
           and ((self.last_deleted and last_published > self.last_deleted) or not self.last_deleted)\
           and not (skip_fast_forward | self.get_config().get("skip_fast_forward", False))

