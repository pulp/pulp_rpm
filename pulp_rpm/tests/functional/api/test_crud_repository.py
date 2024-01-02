import pytest


@pytest.mark.parametrize(
    "factory_kwargs,repo_config_result",
    [
        ({}, {}),
        ({"gpgcheck": 0}, {"gpgcheck": 0}),
        ({"repo_gpgcheck": 0}, {"repo_gpgcheck": 0}),
        ({"gpgcheck": 0, "repo_gpgcheck": 0}, {"gpgcheck": 0, "repo_gpgcheck": 0}),
        ({"gpgcheck": 1, "repo_gpgcheck": 1}, {"gpgcheck": 1, "repo_gpgcheck": 1}),
    ],
)
def test_create_repo_with_deprecated_gpg_options_3357(
    rpm_repository_factory, factory_kwargs, repo_config_result
):
    """Can create repository with deprecated gpgcheck and repo_gpgcheck options."""
    repo = rpm_repository_factory(**factory_kwargs)
    assert repo.repo_config == repo_config_result


@pytest.mark.parametrize(
    "original_repo_config,update_kwargs,repo_config_result",
    [
        ({}, {}, {}),
        ({}, {"gpgcheck": 0}, {"gpgcheck": 0}),
        ({}, {"repo_gpgcheck": 0}, {"repo_gpgcheck": 0}),
        ({}, {"gpgcheck": 0, "repo_gpgcheck": 0}, {"gpgcheck": 0, "repo_gpgcheck": 0}),
        ({}, {"gpgcheck": 1, "repo_gpgcheck": 1}, {"gpgcheck": 1, "repo_gpgcheck": 1}),
        (
            {"gpgcheck": 0, "repo_gpgcheck": 0},
            {"gpgcheck": 1, "repo_gpgcheck": 1},
            {"gpgcheck": 1, "repo_gpgcheck": 1},
        ),
    ],
)
def test_update_repo_with_deprecated_gpg_options_3357(
    rpm_repository_factory,
    rpm_repository_api,
    original_repo_config,
    update_kwargs,
    repo_config_result,
):
    """Can update repository with deprecated gpgcheck and repo_gpgcheck options."""
    original_repo = rpm_repository_factory(description="old", **original_repo_config)
    assert original_repo.repo_config == original_repo_config
    assert original_repo.description == "old"  # control group

    body = {"name": original_repo.name}
    body.update(update_kwargs)
    body.update({"description": "new"})
    rpm_repository_api.update(original_repo.pulp_href, body)
    updated_repo = rpm_repository_api.read(original_repo.pulp_href)
    assert updated_repo.repo_config == repo_config_result
    assert updated_repo.description == "new"  # control group
