"""
Requires:
    anatomy


Provides:
    instance.data     -> stagingDir (folder path)
                      -> stagingDirPersistence (bool)
                      -> stagingDir_persistent (bool) [deprecated]
"""
import copy
import os.path

import pyblish.api

from openpype.pipeline import get_staging_dir_profile
from openpype.lib import StringTemplate


class CollectManagedStagingDir(pyblish.api.InstancePlugin):
    """Apply matching Staging Dir profile to a instance.

    Apply Staging dir via profiles could be useful in specific use cases
    where is desirable to have temporary renders in specific,
    persistent folders, could be on disks optimized for speed for example.

    It is studio's responsibility to clean up obsolete folders with data.

    Location of the folder is configured in:
        `project_anatomy/templates/staging_dir`.

    Which family/task type/subset is applicable is configured in:
        `project_settings/global/tools/publish/custom_staging_dir_profiles`
    """
    label = "Collect Managed Staging Directory"
    order = pyblish.api.CollectorOrder + 0.4990

    def process(self, instance):
        family = instance.data["family"]
        subset_name = instance.data["subset"]
        host_name = instance.context.data["hostName"]
        project_name = instance.context.data["projectName"]
        project_settings = instance.context.data["project_settings"]
        anatomy = instance.context.data["anatomy"]
        task = instance.data["anatomyData"].get("task", {})

        staging_dir_profile = get_staging_dir_profile(
            project_name, host_name, family, task.get("name"),
            task.get("type"), subset_name, project_settings=project_settings,
            anatomy=anatomy, log=self.log)

        if not staging_dir_profile:
            self.log.info("No matching profile for staging dir found ...")
            # debug info
            self.log.debug("project: {}".format(project_name))
            self.log.debug("host: {}".format(host_name))
            self.log.debug("family: {}".format(family))
            self.log.debug("subset: {}".format(subset_name))
            self.log.debug("task: {}".format(task.get("name")))
            return

        dirpath, persists = self._apply_staging_dir(
            instance, anatomy, staging_dir_profile
        )
        self.log.info(
            (
                "Instance staging dir was set to `{}` "
                "and persistence is set to `{}`"
            ).format(dirpath, persists)
        )

    def _apply_staging_dir(
            self, instance, anatomy, staging_dir_profile):

        # get persistence from staging_dir_profile
        is_persistent = staging_dir_profile["persistence"]

        # prepare formatting data
        formatting_data = copy.deepcopy(instance.data["anatomyData"])
        formatting_data["root"] = anatomy.roots
        scene_name = instance.context.data.get("currentFile")
        if scene_name:
            formatting_data["scene_name"] = os.path.basename(scene_name)

        # format staging dir template
        staging_dir = StringTemplate(
            staging_dir_profile["template"]
        ).format(formatting_data)

        if not os.path.exists(staging_dir):
            self.log.info(
                "Creating staging dir: {}".format(staging_dir)
            )
            os.makedirs(staging_dir)

        # apply staging dir to instance
        instance.data["stagingDir"] = staging_dir

        # set persistence flag to instance
        instance.data["stagingDirPersistence"] = is_persistent

        # TODO: remove traces of `stagingDir_persistent` in the future
        # maintain backward compatibility
        instance.data["stagingDir_persistent"] = is_persistent

        return staging_dir, is_persistent
