# Welcome to Pulp RPM!

The pulp_rpm plugin extends pulpcore to support hosting RPM family content types.

If you just got here, you should take our [Getting Started with RPM](site:pulp_rpm/docs/user/tutorials/01-create_sync_publish/) tutorial to get your first RPM repository up and running.
We also recommended that you read the [Basic Concepts](site:pulp_rpm/docs/user/learn/01-manage/) section before diving into the workflows and reference material.

## Features

- `sync-publish-workflow`:
    * Support for RPM Packages, Advisories, Modularity, and Comps
    * Support for ULN servers
- `Versioned Repositories` so every operation is a restorable snapshot
- `Download content on-demand` when requested by clients to reduce disk space.
- Upload local RPM content
- Add, remove, copy, and organize RPM content into various repositories
- De-duplication of all saved content
- Host content either [locally or on S3](https://docs.pulpproject.org/installation/storage.html)
- View distributions served by pulpcore-content in a browser

## Requirements

`pulp_rpm` plugin requires some dependencies such as `libsolv` and `libmodulemd`
which is provided only by RedHat family distributions like Fedora.
