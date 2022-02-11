import os
import sys

openpype_root = ""
mongo_url = ""
paths = [
    openpype_root,
    os.path.join(openpype_root, ".venv/Lib/site-packages"),
    os.path.join(openpype_root, "vendor/python"),
    os.path.join(openpype_root, "repos/avalon-core")
]
for path in paths:
    sys.path.append(path)

os.environ["OPENPYPE_DATABASE_NAME"] = "openpype"
os.environ["OPENPYPE_MONGO"] = mongo_url
os.environ["AVALON_MONGO"] = mongo_url
os.environ["AVALON_DB"] = "avalon"
os.environ["AVALON_TIMEOUT"] = "1000"

from Qt import QtWidgets
from openpype.tools.launcher import LauncherWindow


if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    window = LauncherWindow()
    window.show()

    sys.exit(app.exec_())
