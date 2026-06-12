Added a `scan` action to `RepositoryVersion` endpoint that scans all RPM packages in a repository version via <https://osv.dev/>.
Repositories must be configured via the `osv_config` field, which specifies the ecosystems and releases to query.
