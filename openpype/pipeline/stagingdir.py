import os
import tempfile
from openpype.lib import (
    Logger,
    filter_profiles
)
from openpype import pipeline
from openpype.settings import (
    get_project_settings
)


STAGING_DIR_TEMPLATES = "staging_dir"


def get_staging_dir_profile(
        project_name, host_name, family, task_name,
        task_type, subset_name,
        project_settings=None,
        anatomy=None, log=None
):
    """Get matching staging dir profiles.

    Args:
        project_name (str)
        host_name (str)
        family (str)
        task_name (str)
        task_type (str)
        subset_name (str)
        project_settings(Dict[str, Any]): Prepared project settings.
        anatomy (Dict[str, Any])
        log (Logger) (optional)

    Returns:
        Dict or None: Data with directory path and is_persistent or None
    Raises:
        ValueError - if misconfigured template should be used
    """
    settings = project_settings or get_project_settings(project_name)

    staging_dir_profiles = (
        settings["global"]["tools"]["publish"]["custom_staging_dir_profiles"]
    )

    if not staging_dir_profiles:
        return

    if not log:
        log = Logger.get_logger("get_staging_dir_profile")

    filtering_criteria = {
        "hosts": host_name,
        "families": family,
        "task_names": task_name,
        "task_types": task_type,
        "subsets": subset_name
    }
    profile = filter_profiles(
        staging_dir_profiles, filtering_criteria, logger=log)

    if not profile or not profile["active"]:
        return

    if not anatomy:
        anatomy = pipeline.Anatomy(project_name)

    if not profile.get("template"):
        template_name = profile["template_name"]
        _validate_template_name(project_name, template_name, anatomy)

        template = (
            anatomy.templates[STAGING_DIR_TEMPLATES][template_name])
    else:
        template = profile["template"]

    if not template:
        # template should always be found either from anatomy or from profile
        raise ValueError(
            "Staging dir profile is misconfigured! "
            "No template was found for profile! "
            "Check your project settings at: "
            "'project_settings/global/tools/publish/"
            "custom_staging_dir_profiles'"
        )

    data_persistence = (
        # TODO: make this compulsory in the future
        profile.get("data_persistence")
        # maintain backwards compatibility
        or profile.get("custom_staging_dir_persistent")
    )

    return {
        "template": template,
        "persistence": data_persistence
    }


def _validate_template_name(project_name, template_name, anatomy):
    """Check that staging dir section with appropriate template exist.

    Raises:
        ValueError - if misconfigured template
    """
    # TODO: only for backward compatibility of anatomy for older projects
    if STAGING_DIR_TEMPLATES not in anatomy.templates:
        raise ValueError((
            "Anatomy of project \"{}\" does not have set"
            " \"{}\" template section!").format(project_name, template_name)
        )

    if template_name not in anatomy.templates[STAGING_DIR_TEMPLATES]:
        raise ValueError((
            "Anatomy of project \"{}\" does not have set"
            " \"{}\" template key at Staging Dir section!").format(
                project_name, template_name)
        )

def get_staging_dir(
        project_name=None,
        anatomy=None,
        prefix=None, suffix=None,
        make_local=False
):
    """Get staging dir path.

    If `make_local` is set, tempdir will be created in local tempdir.
    If `anatomy` is not set, default anatomy will be used.
    If `prefix` or `suffix` is not set, default values will be used.

    It also supports `OPENPYPE_TMPDIR`, so studio can define own temp
    shared repository per project or even per more granular context.
    Template formatting is supported also with optional keys. Folder is
    created in case it doesn't exists.

    Available anatomy formatting keys:
        - root[work | <root name key>]
        - project[name | code]

    Note:
        Staging dir does not have to be necessarily in tempdir so be careful
        about its usage.

    Args:
        project_name (str)[optional]: Name of project.
        anatomy (openpype.pipeline.Anatomy)[optional]: Anatomy object.
        make_local (bool)[optional]: If True, staging dir will be created in
            local tempdir.
        suffix (str)[optional]: Suffix for tempdir.
        prefix (str)[optional]: Prefix for tempdir.

    Returns:
        str: Path to staging dir of instance.
    """
    prefix = prefix or "op_tmp_"
    suffix = suffix or ""

    if make_local:
        return _create_local_staging_dir(prefix, suffix)

    # make sure anatomy is set
    if not anatomy:
        anatomy = pipeline.Anatomy(project_name)

    # get customized tempdir path from `OPENPYPE_TMPDIR` env var
    custom_temp_dir = pipeline.create_custom_tempdir(
        anatomy.project_name, anatomy)

    if custom_temp_dir:
        return os.path.normpath(
            tempfile.mkdtemp(
                prefix=prefix,
                suffix=suffix,
                dir=custom_temp_dir
            )
        )
    else:
        return _create_local_staging_dir(prefix, suffix)


def _create_local_staging_dir(prefix, suffix):
    return os.path.normpath(
        tempfile.mkdtemp(
            prefix=prefix,
            suffix=suffix
        )
    )
