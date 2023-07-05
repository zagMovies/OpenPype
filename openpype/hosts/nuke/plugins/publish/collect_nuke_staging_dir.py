import pyblish.api


class CollectNukeStagingDir(pyblish.api.InstancePlugin):
    """Collect Nuke host staging dir from transient data."""

    order = pyblish.api.CollectorOrder - 0.45
    label = "Collect Nuke staging directory"

    def process(self, instance):
        transient_data = instance.data.get("transientData", {})
        staging_dir = transient_data.get("stagingDir")

        if staging_dir:
            instance.data["stagingDir"] = staging_dir
            instance.data["stagingDirPersistence"] = transient_data.get(
                "stagingDirPersistence")

        self.log.info("Instance: {}".format(instance.data["name"]))
        self.log.info("Staging dir: {}".format(staging_dir))
        self.log.info("Staging dir persistent: {}".format(
            instance.data.get("stagingDirPersistence")))
