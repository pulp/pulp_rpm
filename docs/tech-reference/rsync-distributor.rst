=================
Rsync distributor
=================

Purpose:
========
Rsync distributor should be used for syncing already published files into remote
machine. That means, rsync distributor isn't designed to work as standalone
distributor.

How it works
============
Rsync distributor publishes in fast-forward mode by default. It selects
new content since last_published timestamp, however it also check predistributor
publish history if there weren't publishes that were non-fast-forward or
failed. In that case, cdn_distributor publishes everything from scratch.
Publish process is diveded into multiple steps:
unit query, origin publish, content publish, extra data publish

1. Unit query step fetchs units from database and creates realive symlinks to
units _storage_dir in <working_repo_dir>/<extra_dir>/.relative

2. origin publish syncs hard files from /var/lib/pulp/content/ to remote server
There can by multiple origin publish steps if there are more then one content
types to be synced.

3. content publish syncs files <working_repo_dir>/<extra_dir>/.relative to
remote server. Remote repo directory is calculated from ``remote_root`` and
relative_url.

4. extra data publish happens only if there are extra data to be synced. For
example extra data for rpm repo are repodata/* files.


Supported types
==============
For now, rsync distributor can sync any content from rpm and docker repositories

Requirements
============
To work proprely, your repository needs to have associated distributor that
procude data output. For docker repositories, docker_web_distributor is needed
and for rpm repositories, yum_distributor is needed. For now, cdn_distributor
will use configuration from first distributor with desired distributor_type
mentioned above.

Configuration
=============
Here's example of cdn_distributor configuration

{
    "handler_type": "rsync",
    "remote": {
        "auth_type": "publickey",
        "login": "rcm-cron",
        "key_path": "/etc/httpd/id_rsa",
        "ssh_login": "rcm-cron",
        "host": "pulp04.web.stage.ext.phx2.redhat.com",
        "remote_root": "/mnt/cdn/cdn-stage",
        "skip_repodata": false
    }
}

``handler_type``
  for now rsync is only supported handler

``auth_type``
  for now publickey is only supported

``login``
  ssh login to remote machine

``key_path``
  path to public key on pulp machine that will be used as identity file for ssh

``ssh_login``
  artifact from old ages, can be probably removed. Isn't used anymore

``host``
  remote hostname

``remote_root``
  remote root directory with all the data. (content + published_contnet)

Optional configuration
----------------------

``skip_fast_forward``
  if true, rsync distribtor will sync all content of repository.

``origin_only``
  if true, rsync distribtor will sync hard content (e.g. /var/lib/pulp/content)
