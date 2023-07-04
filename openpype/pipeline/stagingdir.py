from openpype.lib import (
    Logger,
    filter_profiles,
    StringTemplate
)
from openpype.settings import get_project_settings
from .anatomy import Anatomy
from .tempdir import get_temp_dir
from openpype.pipeline.template_data import get_template_data_with_names

STAGING_DIR_TEMPLATES = "staging_dir"


def get_staging_dir_config(
        project_name, host_name, family, task_name,
        task_type, subset_name,
        project_settings=None,
        anatomy=None, log=None
):
    """Get matching staging dir profile.

    Args:
        project_name (str)
        host_name (str)
        family (str)
        task_name (str)
        task_type (str)
        subset_name (str)
        project_settings(Dict[str, Any]): Prepared project settings.
        anatomy (Dict[str, Any])
        log (Optional[logging.Logger])

    Returns:
        Dict or None: Data with directory template and is_persistent or None
    Raises:
        ValueError - if misconfigured template should be used
    """
    settings = project_settings or get_project_settings(project_name)

    staging_dir_profiles = (
        settings["global"]["tools"]["publish"]["custom_staging_dir_profiles"]
    )

    if not staging_dir_profiles:
        return None

    if not log:
        log = Logger.get_logger("get_staging_dir_config")

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
        return None

    if not anatomy:
        anatomy = Anatomy(project_name)

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
        project_name, asset_name, host_name,
        family, task_name, subset, anatomy,
        project_settings=None,
        system_settings=None,
        force_temp=False,
        always_get_some_dir=True,
        prefix=None,
        suffix=None,
        log=None,
):
    """Get staging dir data.

    If `force_temp` is set, staging dir will be created as tempdir.
    If `always_get_some_dir` is set, staging dir will be created as tempdir if
    no staging dir profile is found.
    If `prefix` or `suffix` is not set, default values will be used.

    Arguments:
        project_name (str)
        asset_name (str)
        host_name (str)
        family (str)
        task_name (str)
        subset (str)
        anatomy (Dict[str, Any])
        project_settings (Dict[str, Any])
        system_settings (Dict[str, Any])
        force_temp (bool)
        always_get_some_dir (bool)
        prefix (str)
        suffix (str)
        log (Optional[logging.Logger])

    Returns:
        Dict[str, Any]: Staging dir data
    """

    if not log:
        log = Logger.get_logger("get_staging_dir")

    if force_temp:
        return get_temp_dir(
            project_name=project_name,
            anatomy=anatomy,
            prefix=prefix, suffix=suffix
        )

    ctx_data = get_template_data_with_names(
        project_name, asset_name, task_name, system_settings)
    ctx_data.update({
        "subset": subset,
        "host": host_name,
        "family": family
    })

    # get staging dir config
    staging_dir_config = get_staging_dir_config(
        project_name, host_name, family, task_name,
        ctx_data.get("task", {}).get("type"), subset,
        project_settings=project_settings,
        anatomy=anatomy, log=log
    )

    # if no preset matching and always_get_some_dir is set, return tempdir
    if not staging_dir_config and always_get_some_dir:
        return {
            "stagingDir": get_temp_dir(
                project_name=project_name,
                anatomy=anatomy,
                prefix=prefix, suffix=suffix
            ),
            "stagingDirPersistent": False
        }

    return {
        "stagingDir": StringTemplate.format_template(
            staging_dir_config["template"], ctx_data
        ),
        "stagingDirPersistent": staging_dir_config["persistence"]
    }
