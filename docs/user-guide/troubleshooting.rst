***************
Troubleshooting
***************

RPM with non UTF-8 fields results in error
==========================================

Pulp does not support uploading of RPMs with non UTF-8 fields. When such an RPM is uploaded the following traceback will appear in the logs::

    Content unit association failed [Unit [key={'name': 'ruby-zypptools', 'checksum': 'aa647a75db016962b72b8d7c1a328a2cf8cfd6a8d5827b58064ab383fde47231', 'epoch': '0', 'version': '0.2.0', 'release': '1.26', 'arch': 'x86_64', 'checksumtype': 'sha256'}] [type=rpm] [id=None]]
    Traceback (most recent call last):
      File "/usr/lib/python2.6/site-packages/pulp/plugins/conduits/mixins.py", line 480, in save_unit
        unit.id = self._update_unit(unit, pulp_unit)
      File "/usr/lib/python2.6/site-packages/pulp/plugins/conduits/mixins.py", line 512, in _update_unit
        return self._add_unit(unit, pulp_unit)
      File "/usr/lib/python2.6/site-packages/pulp/plugins/conduits/mixins.py", line 534, in _add_unit
        unit_id = content_manager.add_content_unit(unit.type_id, None, pulp_unit)
      File "/usr/lib/python2.6/site-packages/pulp/server/managers/content/cud.py", line 35, in add_content_unit
        collection.insert(unit_doc, safe=True)
      File "/usr/lib/python2.6/site-packages/pulp/server/db/connection.py", line 140, in retry
        return method(*args, **kwargs)
      File "/usr/lib64/python2.6/site-packages/pymongo/collection.py", line 357, in insert
        continue_on_error, self.__uuid_subtype), safe)
    InvalidStringData: strings in documents must be valid UTF-8

If you experience this problem, contact the RPM maintainer and ask them to change non UTF-8 fields to UTF-8. 
