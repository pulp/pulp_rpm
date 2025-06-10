from datetime import datetime, timedelta
from logging import getLogger, DEBUG

from django.conf import settings
from django.db.models import F, Subquery
from django.utils import timezone

from pulpcore.plugin.models import ProgressReport
from pulpcore.plugin.constants import TASK_STATES
from pulpcore.plugin.models import (
    GroupProgressReport,
    RepositoryContent,
    TaskGroup,
)
from pulpcore.plugin.tasking import dispatch
from pulp_rpm.app.models.package import Package
from pulp_rpm.app.models.repository import RpmRepository

log = getLogger(__name__)


def prune_repo_packages(repo_pk, keep_days, dry_run):
    """
    This task prunes old Packages from the latest_version of the specified repository.

    Args:
        repo_pk (UUID): UUID of the RpmRepository to be pruned.
        keep_days(int): Keep RepositoryContent created less than this many days ago.
        dry_run (boolean): If True, don't actually do the prune, just log to-be-pruned Packages.
    """
    repo = RpmRepository.objects.filter(pk=repo_pk).get()
    curr_vers = repo.latest_version()
    eldest_datetime = datetime.now(tz=timezone.utc) - timedelta(days=keep_days)
    log.info(f"PRUNING REPOSITORY {repo.name}.")
    log.debug(f">>> TOTAL RPMS: {curr_vers.get_content(Package.objects).count()}")

    # We only care about RPM-Names that have more than one EVRA - "singles" are always kept.
    rpm_by_name_age = (
        curr_vers.get_content(Package.objects.with_age())
        .filter(age__gt=1)
        .order_by("name", "epoch", "version", "release", "arch")
        .values("pk")
    )
    log.debug(f">>> NAME/AGE COUNT {rpm_by_name_age.count()}")
    log.debug(
        ">>> # NAME/ARCH w/ MULTIPLE EVRs: {}".format(
            curr_vers.get_content(Package.objects)
            .filter(pk__in=rpm_by_name_age)
            .values("name", "arch")
            .distinct()
            .count()
        )
    )
    log.debug(
        ">>> # UNIQUE NAME/ARCHS: {}".format(
            curr_vers.get_content(Package.objects).values("name", "arch").distinct().count()
        )
    )

    # Find the RepositoryContents associated with the multi-EVR-names from above,
    # whose maximum-pulp-created date is LESS THAN eldest_datetime.
    #
    # Note that we can "assume" the latest-date is an "add" with no "remove", since we're
    # limiting ourselves to the list of ids that we know are in the repo's current latest-version!
    target_ids_q = (
        RepositoryContent.objects.filter(
            content__in=Subquery(rpm_by_name_age), repository=repo, version_removed=None
        )
        .filter(pulp_created__lt=eldest_datetime)
        .values("content_id")
    )
    log.debug(f">>> TARGET IDS: {target_ids_q.count()}.")
    to_be_removed = target_ids_q.count()
    # Use the progressreport to report back numbers. The prune happens as one
    # action.
    data = dict(
        message=f"Pruning {repo.name}",
        code="rpm.package.prune.repository",
        total=to_be_removed,
        state=TASK_STATES.COMPLETED,
        done=0,
    )

    if dry_run:
        if log.getEffectiveLevel() == DEBUG:  # Don't go through the loop unless debugging
            log.debug(">>> Packages to be removed : ")
            for p in (
                Package.objects.filter(pk__in=target_ids_q)
                .order_by("name", "epoch", "version", "release", "arch")
                .values("name", "epoch", "version", "release", "arch")
            ):
                log.debug(f'{p["name"]}-{p["epoch"]}:{p["version"]}-{p["release"]}.{p["arch"]}')
    else:
        with repo.new_version(base_version=None) as new_version:
            new_version.remove_content(target_ids_q)
        data["done"] = to_be_removed

    pb = ProgressReport(**data)
    pb.save()

    # Report back that this repo has completed.
    gpr = TaskGroup.current().group_progress_reports.filter(code="rpm.package.prune")
    gpr.update(done=F("done") + 1)


def prune_packages(
    repo_pks,
    keep_days=14,
    dry_run=False,
):
    """
    This task prunes old Packages from the latest_version of the specified list of repos.

    "Old" in this context is defined by the RepositoryContent record that added a Package
    to the repository in question.

    It will issue one task-per-repository.

    Kwargs:
        repo_pks (list): A list of repo pks the pruning is performed on.
        keep_days(int): Keep RepositoryContent created less than this many days ago.
        repo_concurrency (int): number of repos to prune at a time.
        dry_run (boolean): If True, don't actually do the prune, just record to-be-pruned Packages..
    """

    repos_to_prune = RpmRepository.objects.filter(pk__in=repo_pks)
    task_group = TaskGroup.current()

    # We want to be able to limit the number of available-workers that prune will consume,
    # so that pulp can continue to work while pruning many repositories. We accomplish this by
    # creating a reserved-resource string for each repo-prune-task based on that repo's index in
    # the dispatch loop, mod number-of-workers-to-consume.
    #
    # By default, prune will consume up to 5 workers.
    #
    # (This comment and code below based on
    #   https://github.com/pulp/pulpcore/blob/main/pulpcore/app/tasks/importer.py#L503-L512
    # When we have a generic-approach to throttling mass-task-spawning, both places should
    # be refactored to take advantage thereof.
    prune_workers = int(settings.get("PRUNE_WORKERS_MAX", 5))

    gpr = GroupProgressReport(
        message="Pruning old Packages",
        code="rpm.package.prune",
        total=len(repo_pks),
        done=0,
        task_group=task_group,
    )
    gpr.save()

    # Dispatch a task-per-repository.
    # Lock on the the repository *and* to insure the max-concurrency specified.
    # This will keep an "all repositories" prune from locking up all the workers
    # until all repositories are completed.
    for index, a_repo in enumerate(repos_to_prune):
        worker_rsrc = f"rpm-prune-worker-{index % prune_workers}"
        exclusive_resources = [worker_rsrc, a_repo]

        dispatch(
            prune_repo_packages,
            exclusive_resources=exclusive_resources,
            args=(
                a_repo.pk,
                keep_days,
                dry_run,
            ),
            task_group=task_group,
        )
