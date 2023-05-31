Added NOCACHE_LIST config to enable specifying files to be served with a no-cache header.

By default, repomd.xml, repomd.key, and repomd.key.asc are served with
Cache-control: no-cache.
