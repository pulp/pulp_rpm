# Configure Alternate Content Sources

Alternate Content Sources (ACS) can help speed up populating of new repositories.
If you have content stored locally or geographically near you which matches
the remote content, Alternate Content Sources will allow you to substitute
this content, allowing for faster data transfer.

[Alternate Content Sources](site:/pulpcore/docs/user/guides/alternate-content-sources/)
base is provided by pulpcore plugin.

To use an Alternate Content Source you need a `RPMRemote` with path of your ACS.

!!! warning
    Remotes with mirrorlist URLs cannot be used as an Alternative Content Source.


```bash
pulp rpm remote create --name rpm_acs_remote --policy on_demand --url http://fixtures.pulpproject.org/rpm-unsigned/
```

## Create Alternate Content Source

Create an Alternate Content Source.

```bash
pulp rpm acs create --name rpm_acs --remote rpm_acs_remote
```

### Alternate Content Source Paths

If you have more places with ACS within one base path you can specify them
by paths and all of them will be considered as a ACS.

```bash
pulp rpm remote create --name rpm_acs_remote --policy on_demand --url http://fixtures.pulpproject.org/
pulp rpm acs create --name rpm_acs --remote rpm_acs_remote --path "rpm-unsigned/" --path "rpm-distribution-tree/"
```

## Refresh Alternate Content Source

To make your ACS available for future syncs you need to call `refresh` endpoint
on your ACS. This create a catalogue of available content which will be used instead
new content if found.

```bash
pulp rpm acs refresh --name rpm_acs
```

Alternate Content Source has a global scope so if any content is found in ACS it
will be used in all future syncs.
