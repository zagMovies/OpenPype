from qtpy import QtWidgets, QtCore, QtGui

from openpype.style import load_stylesheet

from .control import BrowserController
from .models import ProjectsModel, PROJECT_NAME_ROLE, HierarchyModel


class BrowserWindow(QtWidgets.QWidget):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)

        if controller is None:
            controller = BrowserController()

        main_splitter = QtWidgets.QSplitter(self)
        # Context selection widget
        context_widget = QtWidgets.QWidget(main_splitter)

        projects_combobox = QtWidgets.QComboBox(context_widget)
        combobox_delegate = QtWidgets.QStyledItemDelegate(self)
        projects_combobox.setItemDelegate(combobox_delegate)
        projects_model = ProjectsModel(controller)
        projects_combobox.setModel(projects_model)

        assets_filter_input = QtWidgets.QLineEdit(context_widget)
        assets_filter_input.setPlaceholderText("Name filter...")

        assets_view = QtWidgets.QTreeView(context_widget)
        assets_model = HierarchyModel(controller)
        assets_view.setModel(assets_model)

        context_layout = QtWidgets.QVBoxLayout(context_widget)
        context_layout.setContentsMargins(0, 0, 0, 0)
        context_layout.addWidget(projects_combobox, 0)
        context_layout.addWidget(assets_filter_input, 0)
        context_layout.addWidget(assets_view, 1)

        # Subset + version selection item
        subsets_widget = QtWidgets.QWidget(main_splitter)

        subsets_filter_input = QtWidgets.QLineEdit(subsets_widget)
        subsets_filter_input.setPlaceholderText("Subset name filter...")

        subsets_view = QtWidgets.QTreeView(subsets_widget)

        subsets_layout = QtWidgets.QVBoxLayout(subsets_widget)
        subsets_layout.setContentsMargins(0, 0, 0, 0)
        subsets_layout.addWidget(subsets_filter_input, 0)
        subsets_layout.addWidget(subsets_view, 1)

        main_splitter.addWidget(context_widget)
        main_splitter.addWidget(subsets_widget)

        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 7)

        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.addWidget(main_splitter)

        show_timer = QtCore.QTimer()
        show_timer.setInterval(1)

        show_timer.timeout.connect(self._on_show_timer)
        projects_combobox.currentIndexChanged.connect(self._on_project_change)

        self._projects_combobox = projects_combobox

        self._assets_filter_input = assets_filter_input
        self._assets_view = assets_view
        self._assets_model = assets_model

        self._subsets_filter_input = subsets_filter_input
        self._subsets_view = subsets_view

        self._controller = controller
        self._first_show = True
        self._reset_on_show = True
        self._show_counter = 0
        self._show_timer = show_timer

    def showEvent(self, event):
        super().showEvent(event)

        if self._first_show:
            self._on_first_show()

        self._show_timer.start()

    def _on_first_show(self):
        self._first_show = False
        self.resize(1000, 600)
        self.setStyleSheet(load_stylesheet())

    def _on_show_timer(self):
        if self._show_counter < 2:
            self._show_counter += 1
            return

        self._show_counter = 0
        self._show_timer.stop()

        if self._reset_on_show:
            self._reset_on_show = False
            self._controller.reset()

    def _on_project_change(self):
        idx = self._projects_combobox.currentIndex()
        project_name = self._projects_combobox.itemData(idx, PROJECT_NAME_ROLE)
        self._controller.set_selected_project(project_name)
