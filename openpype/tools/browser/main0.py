import os
import sys
import json
import copy
import uuid
import collections

openpype_dir = r"C:\Users\JakubTrllo\Desktop\Prace\openpype3_1"
mongo_url = "mongodb://localhost:2707"

os.environ["OPENPYPE_MONGO"] = mongo_url
os.environ["OPENPYPE_DATABASE_NAME"] = "openpype"
os.environ["AVALON_CONFIG"] = "openpype"
os.environ["AVALON_TIMEOUT"] = "1000"
os.environ["AVALON_DB"] = "avalon"
for path in [
    openpype_dir,
    r"{}\.venv\Lib\site-packages".format(openpype_dir),
    r"{}\vendor\python".format(openpype_dir),
    r"{}\openpype\vendor\python\common".format(openpype_dir),
]:
    sys.path.append(path)

from Qt import QtWidgets, QtCore, QtGui

from openpype import style
from openpype.modules import ModulesManager
from openpype.pipeline import register_loader_plugin, LoaderPlugin
from openpype.tools.libraryloader import (
    LibraryLoaderWindow
)
ModulesManager()


class MyPlugin(LoaderPlugin):
    families = ["image"]
    representations = ["*"]

    def load(self, *args, **kwargs):
        pass

register_loader_plugin(MyPlugin)


def main():
    """Main function for testing purposes."""
    app = QtWidgets.QApplication([])
    window = LibraryLoaderWindow(show_projects=True)

    # log_path = os.path.join(os.path.dirname(__file__), "logs.json")
    # with open(log_path, "r") as file_stream:
    #     report_data = json.load(file_stream)
    #
    # window.set_report(report_data)

    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
