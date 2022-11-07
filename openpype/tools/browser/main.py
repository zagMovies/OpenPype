import os
import sys
import json
import copy
import uuid
import collections

os.environ["OPENPYPE_DATABASE_NAME"] = "openpype"
os.environ["OPENPYPE_MONGO"] = "mongodb://localhost:2707"
openpype_dir = r"C:\Users\JakubTrllo\Desktop\Prace\openpype3_1"


for path in [
    openpype_dir,
    r"{}\.venv\Lib\site-packages".format(openpype_dir),
    r"{}\vendor\python".format(openpype_dir),
    r"{}\openpype\vendor\python\common".format(openpype_dir),
]:
    sys.path.append(path)

from qtpy import QtWidgets, QtCore, QtGui

from openpype.tools.browser.window import (
    BrowserWindow
)


def main():
    """Main function for testing purposes."""
    app = QtWidgets.QApplication([])
    window = BrowserWindow()
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
