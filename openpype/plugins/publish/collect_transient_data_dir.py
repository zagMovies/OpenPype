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

from openpype.pipeline import get_transient_data_profile
from openpype.lib import StringTemplate


class CollectTransientDataDir(pyblish.api.InstancePlugin):
    """Apply matching Transient data profile (custom stagingDir) to a instance.

    Transient dir could be useful in specific use cases where is
    desirable to have temporary renders in specific, persistent folders, could
    be on disks optimized for speed for example.

    It is studio responsibility to clean up obsolete folders with data.

    Location of the folder is configured in `project_anatomy/templates/others`.
    ('transient' key is expected, with 'folder' key)

    Which family/task type/subset is applicable is configured in:
    `project_settings/global/transient_data_profiles/profiles`

    Deprecated path (backward compatibility):
    `project_settings/global/tools/publish/custom_staging_dir_profiles`
    """
    label = "Collect Transient Data Directory"
    order = pyblish.api.CollectorOrder + 0.4990

    template_key = "transient"

    def process(self, instance):
        family = instance.data["family"]
        subset_name = instance.data["subset"]
        host_name = instance.context.data["hostName"]
        project_name = instance.context.data["projectName"]
        project_settings = instance.context.data["project_settings"]
        anatomy = instance.context.data["anatomy"]
        task = instance.data["anatomyData"].get("task", {})

        transient_data_profile = get_transient_data_profile(
            project_name, host_name, family, task.get("name"),
            task.get("type"), subset_name, project_settings=project_settings,
            anatomy=anatomy, log=self.log)

        if transient_data_profile:
            self.log.info("No matching profile for transient data found ...")
            # debug info
            self.log.debug("project: {}".format(project_name))
            self.log.debug("host: {}".format(host_name))
            self.log.debug("family: {}".format(family))
            self.log.debug("subset: {}".format(subset_name))
            self.log.debug("task: {}".format(task.get("name")))
            return

        dirpath, persists = self._apply_transient_data(
            instance, anatomy, transient_data_profile
        )
        self.log.info(
            (
                "Instance staging dir was set to `{}` "
                "and persistence is set to `{}`"
            ).format(dirpath, persists)
        )

    def _apply_transient_data(
            self, instance, anatomy, transient_data_profile):

        # get persistence from transient_data_profile
        is_persistent = transient_data_profile["transient_persistence"]

        # prepare formatting data
        formatting_data = copy.deepcopy(instance.data["anatomyData"])
        formatting_data["root"] = anatomy.roots
        scene_name = instance.context.data.get("currentFile")
        if scene_name:
            formatting_data["scene_name"] = os.path.basename(scene_name)

        # format transient dir template
        transient_dir = StringTemplate(
            transient_data_profile["transient_template"]
        ).format(formatting_data)

        # apply transient dir to instance
        instance.data["stagingDir"] = transient_dir

        # set persistence flag to instance
        instance.data["stagingDirPersistence"] = is_persistent

        # TODO: remove traces of `stagingDir_persistent` in the future
        # maintain backward compatibility
        instance.data["stagingDir_persistent"] = is_persistent

        return transient_dir, is_persistent
