.. _troubleshooting:

***************
Troubleshooting
***************

CA Certificate is Incorrect or Missing
======================================

Due to `#887039 <https://bugzilla.redhat.com/show_bug.cgi?id=887039>`_, if you
do not pass a valid CA certificate for an SSL feed, Pulp will not give you an
informative error message. The :command:`pulp-admin` utility will tell you to
look at ~/.pulp/admin.log, and in there, you will see a traceback like this::

    2012-12-13 16:10:38,251 - ERROR - Client-side exception occurred
    Traceback (most recent call last):
      File "/home/rbarlow/devel/pulp/platform/src/pulp/client/extensions/core.py", line 478, in run
        exit_code = Cli.run(self, args)
      File "/usr/lib/python2.7/site-packages/okaara/cli.py", line 933, in run
        exit_code = command_or_section.execute(self.prompt, remaining_args)
      File "/home/rbarlow/devel/pulp/platform/src/pulp/client/extensions/extensions.py", line 224, in execute
        return self.method(*arg_list, **clean_kwargs)
      File "/home/rbarlow/devel/pulp/platform/src/pulp/client/commands/repo/sync_publish.py", line 101, in run
        status.display_group_status(self.context, self.renderer, task_group_id)
      File "/home/rbarlow/devel/pulp/platform/src/pulp/client/commands/repo/status/status.py", line 63, in display_group_status
        _display_status(context, renderer, task_list)
      File "/home/rbarlow/devel/pulp/platform/src/pulp/client/commands/repo/status/status.py", line 95, in _display_status
        _display_task_status(context, renderer, task.task_id, quiet_waiting=quiet_waiting)
      File "/home/rbarlow/devel/pulp/platform/src/pulp/client/commands/repo/status/status.py", line 133, in _display_task_status
        renderer.display_report(response.response_body.progress)
      File "/home/rbarlow/devel/pulp_rpm/pulp_rpm/src/pulp_rpm/extension/admin/status.py", line 67, in display_report
        self.render_metadata_step(progress_report)
      File "/home/rbarlow/devel/pulp_rpm/pulp_rpm/src/pulp_rpm/extension/admin/status.py", line 93, in render_metadata_step
        self.prompt.render_failure_message(progress_report['yum_importer']['metadata']['error'])
    KeyError: 'error'

If you inspect /var/log/pulp/pulp.log on the server, you will see something like
this in the log::

    2012-12-13 16:10:37,540 pulp.plugins.yum_importer.importer_rpm:INFO: Begin sync of repo <rhel-6-server-7> from feed_url <https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/os>
    2012-12-13 16:10:37,959 pulp.plugins.yum_importer.importer_rpm:ERROR: Failed to fetch metadata on: https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/os
    2012-12-13 16:10:37,960 pulp.plugins.yum_importer.importer:ERROR: Caught Exception: failure: repodata/repomd.xml from rhel-6-server-7: [Errno 256] No more mirrors to try.
    Traceback (most recent call last):
      File "/usr/lib/pulp/plugins/importers/yum_importer/importer.py", line 488, in sync_repo
        status, summary, details = self._sync_repo(repo, sync_conduit, config)
      File "/usr/lib/pulp/plugins/importers/yum_importer/importer.py", line 542, in _sync_repo
        rpm_status, summary["packages"], details["packages"] = self.importer_rpm.sync(repo, sync_conduit, config, progress_callback)
      File "/usr/lib/pulp/plugins/importers/yum_importer/importer_rpm.py", line 472, in sync
        num_retries=num_retries, retry_delay=retry_delay)
      File "/usr/lib/python2.7/site-packages/grinder/RepoFetch.py", line 154, in setup
        info.setUp()
      File "/usr/lib/python2.7/site-packages/grinder/YumInfo.py", line 406, in setUp
        skip=self.skip)
      File "/usr/lib/python2.7/site-packages/grinder/activeobject.py", line 82, in __call__
        return self.object(self, *args, **kwargs)
      File "/usr/lib/python2.7/site-packages/grinder/activeobject.py", line 269, in __call__
        return self.__call(method, args, kwargs)
      File "/usr/lib/python2.7/site-packages/grinder/activeobject.py", line 245, in __call
        return self.__rmi(method.name, args, kwargs)
      File "/usr/lib/python2.7/site-packages/grinder/activeobject.py", line 137, in __rmi
        raise ex
    NoMoreMirrorsRepoError: failure: repodata/repomd.xml from rhel-6-server-7: [Errno 256] No more mirrors to try.
    2012-12-13 16:10:38,004 pulp.server.dispatch.task:ERROR: Importer indicated a failed response
    Traceback (most recent call last):
      File "/home/rbarlow/devel/pulp/platform/src/pulp/server/dispatch/task.py", line 123, in _run
        result = call(*args, **kwargs)
      File "/home/rbarlow/devel/pulp/platform/src/pulp/server/managers/repo/sync.py", line 158, in sync
        raise PulpExecutionException(_('Importer indicated a failed response'))
    PulpExecutionException: Importer indicated a failed response
    2012-12-13 16:10:38,004 pulp.server.dispatch.task:INFO: FAILURE: Task 4c241053-ef22-4cb2-afcb-fa05dc5ec8e7: CallRequest: RepoSyncManager.sync(u'rhel-6-server-7', sync_config_override=None, importer_config={}, importer_instance=<yum_importer.importer.YumImporter object at 0x7f82c4102910>)

If you see these symptoms and are using an SSL feed, please check your repo
settings to ensure that the CA certificate is correct.
