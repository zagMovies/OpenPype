import os
import tempfile
from openpype.lib import (
    Logger,
    filter_profiles
)
from openpype.pipeline import (
    tempdir,
    Anatomy
)
from openpype.settings import (
    get_project_settings
)


TRANSIENT_DIR_TEMPLATE = "transient"


def get_transient_data_profile_info(
        project_name, host_name, family, task_name,
        task_type, subset_name,
        project_settings=None,
        anatomy=None, log=None
):
    """Checks profiles if context should use special custom dir as staging.

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
        Tuple[Any, Any]: Tuple of staging dir and is_persistent or None
    Raises:
        ValueError - if misconfigured template should be used
    """
    settings = project_settings or get_project_settings(project_name)
    custom_staging_dir_profiles = (settings["global"]
                                           ["tools"]
                                           ["publish"]
                                           ["custom_staging_dir_profiles"])
    if not custom_staging_dir_profiles:
        return None, None

    if not log:
        log = Logger.get_logger("get_transient_data_profile_info")

    filtering_criteria = {
        "hosts": host_name,
        "families": family,
        "task_names": task_name,
        "task_types": task_type,
        "subsets": subset_name
    }
    profile = filter_profiles(custom_staging_dir_profiles,
                              filtering_criteria,
                              logger=log)

    if not profile or not profile["active"]:
        return None, None

    if not anatomy:
        anatomy = Anatomy(project_name)

    template_name = profile["template_name"] or TRANSIENT_DIR_TEMPLATE
    _validate_transient_template(project_name, template_name, anatomy)

    custom_staging_dir = anatomy.templates[template_name]["folder"]
    is_persistent = profile["custom_staging_dir_persistent"]

    return custom_staging_dir, is_persistent


def _validate_transient_template(project_name, template_name, anatomy):
    """Check that transient template is correctly configured.

    Raises:
        ValueError - if misconfigured template
    """
    if template_name not in anatomy.templates:
        raise ValueError((
            "Anatomy of project \"{}\" does not have set"
            " \"{}\" template key!").format(project_name, template_name)
        )

    if "folder" not in anatomy.templates[template_name]:
        raise ValueError((
            "There is not set \"folder\" template in \"{}\" anatomy"
            " for project \"{}\".").format(template_name, project_name)
        )


def get_instance_staging_dir(instance):
    """Unified way how staging dir is stored and created on instances.

    First check if 'stagingDir' is already set in instance data.
    In case there already is new tempdir will not be created.

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
        instance (pyblish.lib.Instance): Instance for which we want to get
            staging dir.

    Returns:
        str: Path to staging dir of instance.
    """
    staging_dir = instance.data.get('stagingDir')
    if staging_dir:
        return staging_dir

    anatomy = instance.context.data.get("anatomy")

    # get customized tempdir path from `OPENPYPE_TMPDIR` env var
    custom_temp_dir = tempdir.create_custom_tempdir(
        anatomy.project_name, anatomy)

    if custom_temp_dir:
        staging_dir = os.path.normpath(
            tempfile.mkdtemp(
                prefix="pyblish_tmp_",
                dir=custom_temp_dir
            )
        )
    else:
        staging_dir = os.path.normpath(
            tempfile.mkdtemp(prefix="pyblish_tmp_")
        )
    instance.data['stagingDir'] = staging_dir

    return staging_dir
