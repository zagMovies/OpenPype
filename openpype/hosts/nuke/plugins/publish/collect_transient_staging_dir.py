from pprint import pformat
import pyblish.api


class CollectTransientStagingDir(pyblish.api.InstancePlugin):
    """
    """

    order = pyblish.api.CollectorOrder
    label = "Collect Staging Dir"
    hosts = ["nuke"]

    def process(self, instance):
        transfer_keys = ["stagingDir", "transientData"]
        transient_data = instance.data["transientData"]
