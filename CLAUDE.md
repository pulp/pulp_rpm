# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`pulp_rpm` is a Pulp 3 plugin that provides RPM repository management. It is a Django application that integrates with `pulpcore` via the Pulp plugin architecture.

## Common Commands

### Linting
```bash
pip install -r lint_requirements.txt
black --check --diff .
flake8
sh .ci/scripts/check_pulpcore_imports.sh
sh .ci/scripts/check_gettext.sh
```

### Unit Tests
```bash
pip install -r unittest_requirements.txt
# Run all unit tests
pytest -v -r sx --suppress-no-test-exit-code -p no:pulpcore pulp_rpm/tests/unit
# Run a single test
pytest -v pulp_rpm/tests/unit/test_rpm_version.py::TestRpmVersionComparison::test_evr_tostr
```

### Functional Tests (requires a running Pulp server)
```bash
pip install -r functest_requirements.txt
# Parallel tests
pytest -v --timeout=300 -r sx --suppress-no-test-exit-code pulp_rpm/tests/functional -m parallel -n 8
# Non-parallel tests
pytest -v --timeout=300 -r sx --suppress-no-test-exit-code pulp_rpm/tests/functional -m 'not parallel'
```

### Code Formatting
```bash
# black line-length is 100 (see pyproject.toml)
black .
```

## Architecture

### Plugin Structure
The plugin follows the standard Pulp plugin layout under `pulp_rpm/app/`:

- **`models/`** — Django ORM models for all content types and repository components
- **`viewsets/`** — DRF API endpoints (CRUD + custom actions like sync, publish, copy, prune)
- **`serializers/`** — DRF serializers for request/response validation (mirrors viewsets structure)
- **`tasks/`** — Async Celery task implementations:
  - `synchronizing.py` — Sync from remotes using Pulpcore's declarative stages pipeline
  - `publishing.py` — Metadata generation using `createrepo_c`
  - `copy.py` — Content copying between repository versions
  - `prune.py` — Removal of old/superseded packages
  - `signing.py` — Package and metadata signing

### Content Types
The plugin manages these content types (each is a Django model inheriting from Pulpcore's `Content`):
- `Package` — Individual RPM packages
- `UpdateRecord` — Advisories/errata (security, bugfix, enhancement)
- `Modulemd` / `ModulemdDefaults` — Modular RPM metadata
- `PackageGroup`, `PackageCategory`, `PackageEnvironment`, `PackageLangpacks` — COMPS metadata
- `DistributionTree` — Installer/distribution tree metadata
- `RepoMetadataFile` — Custom repository metadata files

### Repository Components
- `RpmRepository` — Repository with prune settings and retain-package-versions
- `RpmRemote` — Remote source (HTTP/HTTPS, with ULN variant `UlnRemote`)
- `RpmPublication` — Published repository (generates repomd.xml and all repodata)
- `RpmDistribution` — Serves a publication over HTTP
- `RpmAlternateContentSource` — ACS for distributed content sources

### Sync Pipeline (Declarative Stages)
Sync uses Pulpcore's declarative content framework:
1. Parse remote repodata (primary.xml, filelists.xml, other.xml, modules.yaml, updateinfo.xml, comps.xml)
2. Build `DeclarativeContent` / `DeclarativeArtifact` objects
3. Pass through stages: `QueryExistingContents` → `ArtifactDownloader` → `ArtifactSaver` → `ContentSaver` → `ResolveContentFutures` → `RemoteArtifactSaver`
4. Create new `RepositoryVersion` with the resolved content set

### Key Utilities
- `rpm_version.py` — RPM EVR (Epoch:Version-Release) parsing and comparison (labelCompare algorithm)
- `advisory.py` — Advisory merging and conflict detection logic
- `modulemd.py` — Module metadata YAML parsing
- `comps.py` — COMPS XML parsing via `libcomps`
- `constants.py` — Repodata type constants, sync policy enums, checksum types
- `shared_utils.py` — Package formatting utilities

### Key Dependencies
- `pulpcore>=3.103.0,<3.115` — Core framework (models, stages, downloaders, tasks)
- `createrepo_c~=1.2.1` — RPM repository metadata generation
- `libcomps>=0.1.23` — COMPS group/category parsing
- `productmd~=1.33.0` — Distribution tree metadata
- `solv~=0.7.21` — Dependency solving

### Pulpcore Integration Points
- Models inherit from `pulpcore.plugin.models` base classes
- Viewsets extend Pulpcore's viewset mixins
- Tasks use `pulpcore.plugin.stages` for the declarative sync pipeline
- Downloaders extend `pulpcore.plugin.download.DownloaderFactory`
- Plugin registered via `pulpcore.plugin` entry point in `pyproject.toml`

### Testing Patterns
- Unit tests in `pulp_rpm/tests/unit/` — pure Python, no server required, use `-p no:pulpcore` flag
- Functional tests in `pulp_rpm/tests/functional/` — require a live Pulp server, use API clients
- `pytest_plugin.py` provides shared pytest fixtures (API clients, object factories)
- `gen_object_with_cleanup` pattern used in functional tests for lifecycle management
