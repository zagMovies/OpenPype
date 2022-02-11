import re
import uuid
import logging
import collections
import time

import appdirs
from Qt import QtCore, QtGui
from avalon.vendor import qtawesome
from avalon import api
from openpype.lib import ApplicationManager, JSONSettingRegistry
from openpype.tools.utils.lib import DynamicQThread
from openpype.tools.utils.folders_widget import (
    FoldersModel,
    FOLDER_NAME_ROLE
)
from openpype.tools.utils.tasks_widget import (
    TasksModel,
    TasksProxyModel,
    TASK_TYPE_ROLE,
    TASK_ASSIGNEE_ROLE
)
from openpype.tools.utils.client import create_session
from . import lib
from .constants import (
    ACTION_ROLE,
    GROUP_ROLE,
    VARIANT_GROUP_ROLE,
    ACTION_ID_ROLE,
    FORCE_NOT_OPEN_WORKFILE_ROLE
)
from .actions import ApplicationAction

log = logging.getLogger(__name__)

# Must be different than roles in default folder model
FOLDER_TASK_TYPES_ROLE = QtCore.Qt.UserRole + 10
FOLDER_ASSIGNEE_ROLE = QtCore.Qt.UserRole + 11


class SelectedContext(object):
    def __init__(self):
        self._project_name = None
        self._folder_id = None
        self._task_id = None

    @property
    def project_name(self):
        return self._project_name

    @property
    def folder_id(self):
        return self._folder_id

    @property
    def task_id(self):
        return self._task_id

    def set_project_name(self, project_name):
        if project_name != self._project_name:
            self._project_name = project_name
            self.set_folder_id(None)

    def set_folder_id(self, folder_id):
        if self._folder_id != folder_id:
            self._folder_id = folder_id
            self.set_task_id(None)

    def set_task_id(self, task_id):
        if self._task_id != task_id:
            self._task_id = None


class ActionModel(QtGui.QStandardItemModel):
    def __init__(self, launcher_model, parent=None):
        super(ActionModel, self).__init__(parent=parent)
        self.context = launcher_model.context

        self.application_manager = ApplicationManager()

        self.default_icon = qtawesome.icon("fa.cube", color="white")
        # Cache of available actions
        self._registered_actions = list()
        self.items_by_id = {}
        path = appdirs.user_data_dir("openpype", "pypeclub")
        self.launcher_registry = JSONSettingRegistry("launcher", path)

        try:
            _ = self.launcher_registry.get_item("force_not_open_workfile")
        except ValueError:
            self.launcher_registry.set_item("force_not_open_workfile", [])

    def discover(self):
        """Set up Actions cache. Run this for each new project."""
        # Discover all registered actions
        actions = api.discover(api.Action)

        # Get available project actions and the application actions
        app_actions = self.get_application_actions()
        actions.extend(app_actions)

        self._registered_actions = actions

        self.filter_actions()

    def get_application_actions(self):
        actions = []
        if not self.context.project_name:
            return actions

        # project_data = get_project(self.context.project_name)
        # if not project_data:
        #     return actions

        # NOTE hardcoded for now
        project_data = {"config": {"apps": [{"name": "maya/2020"}]}}
        self.application_manager.refresh()
        for app_def in project_data["config"]["apps"]:
            app_name = app_def["name"]
            app = self.application_manager.applications.get(app_name)
            if not app or not app.enabled:
                continue

            # Get from app definition, if not there from app in project
            action = type(
                "app_{}".format(app_name),
                (ApplicationAction,),
                {
                    "application": app,
                    "name": app.name,
                    "label": app.group.label,
                    "label_variant": app.label,
                    "group": None,
                    "icon": app.icon,
                    "color": getattr(app, "color", None),
                    "order": getattr(app, "order", None) or 0,
                    "data": {}
                }
            )

            actions.append(action)
        return actions

    def get_icon(self, action, skip_default=False):
        icon = lib.get_action_icon(action)
        if not icon and not skip_default:
            return self.default_icon
        return icon

    def filter_actions(self):
        self.items_by_id.clear()
        # Validate actions based on compatibility
        self.clear()

        actions = self.filter_compatible_actions(self._registered_actions)

        single_actions = []
        varianted_actions = collections.defaultdict(list)
        grouped_actions = collections.defaultdict(list)
        for action in actions:
            # Groups
            group_name = getattr(action, "group", None)

            # Label variants
            label = getattr(action, "label", None)
            label_variant = getattr(action, "label_variant", None)
            if label_variant and not label:
                print((
                    "Invalid action \"{}\" has set `label_variant` to \"{}\""
                    ", but doesn't have set `label` attribute"
                ).format(action.name, label_variant))
                action.label_variant = None
                label_variant = None

            if group_name:
                grouped_actions[group_name].append(action)

            elif label_variant:
                varianted_actions[label].append(action)
            else:
                single_actions.append(action)

        items_by_order = collections.defaultdict(list)
        for label, actions in tuple(varianted_actions.items()):
            if len(actions) == 1:
                varianted_actions.pop(label)
                single_actions.append(actions[0])
                continue

            icon = None
            order = None
            for action in actions:
                if icon is None:
                    _icon = lib.get_action_icon(action)
                    if _icon:
                        icon = _icon

                if order is None or action.order < order:
                    order = action.order

            if icon is None:
                icon = self.default_icon

            item = QtGui.QStandardItem(icon, label)
            item.setData(label, QtCore.Qt.ToolTipRole)
            item.setData(actions, ACTION_ROLE)
            item.setData(True, VARIANT_GROUP_ROLE)
            items_by_order[order].append(item)

        for action in single_actions:
            icon = self.get_icon(action)
            label = lib.get_action_label(action)
            item = QtGui.QStandardItem(icon, label)
            item.setData(label, QtCore.Qt.ToolTipRole)
            item.setData(action, ACTION_ROLE)
            items_by_order[action.order].append(item)

        for group_name, actions in grouped_actions.items():
            icon = None
            order = None
            for action in actions:
                if order is None or action.order < order:
                    order = action.order

                if icon is None:
                    _icon = lib.get_action_icon(action)
                    if _icon:
                        icon = _icon

            if icon is None:
                icon = self.default_icon

            item = QtGui.QStandardItem(icon, group_name)
            item.setData(actions, ACTION_ROLE)
            item.setData(True, GROUP_ROLE)

            items_by_order[order].append(item)

        self.beginResetModel()

        stored = self.launcher_registry.get_item("force_not_open_workfile")
        items = []
        for order in sorted(items_by_order.keys()):
            for item in items_by_order[order]:
                item_id = str(uuid.uuid4())
                item.setData(item_id, ACTION_ID_ROLE)

                if self.is_force_not_open_workfile(item,
                                                   stored):
                    self.change_action_item(item, True)

                self.items_by_id[item_id] = item
                items.append(item)

        self.invisibleRootItem().appendRows(items)

        self.endResetModel()

    def filter_compatible_actions(self, actions):
        """Collect all actions which are compatible with the environment

        Each compatible action will be translated to a dictionary to ensure
        the action can be visualized in the launcher.

        Args:
            actions (list): list of classes

        Returns:
            list: collection of dictionaries sorted on order int he
        """

        compatible = []
        session = {
            "AVALON_PROJECT": self.context.project_name,
            "AVALON_ASSET": self.context.folder_id,
            "AVALON_TASK": self.context.task_id,
        }

        for action in actions:
            if action().is_compatible(session):
                compatible.append(action)

        # Sort by order and name
        return sorted(
            compatible,
            key=lambda action: (action.order, action.name)
        )

    def update_force_not_open_workfile_settings(self, is_checked, action_id):
        """Store/remove config for forcing to skip opening last workfile.

        Args:
            is_checked (bool): True to add, False to remove
            action_id (str)
        """
        action_item = self.items_by_id.get(action_id)
        if not action_item:
            return

        action = action_item.data(ACTION_ROLE)
        actual_data = self._prepare_compare_data(action)

        stored = self.launcher_registry.get_item("force_not_open_workfile")
        if is_checked:
            stored.append(actual_data)
        else:
            final_values = []
            for config in stored:
                if config != actual_data:
                    final_values.append(config)
            stored = final_values

        self.launcher_registry.set_item("force_not_open_workfile", stored)
        self.launcher_registry._get_item.cache_clear()
        self.change_action_item(action_item, is_checked)

    def change_action_item(self, item, checked):
        """Modifies tooltip and sets if opening of last workfile forbidden"""
        tooltip = item.data(QtCore.Qt.ToolTipRole)
        if checked:
            tooltip += " (Not opening last workfile)"

        item.setData(tooltip, QtCore.Qt.ToolTipRole)
        item.setData(checked, FORCE_NOT_OPEN_WORKFILE_ROLE)

    def is_application_action(self, action):
        """Checks if item is of a ApplicationAction type

        Args:
            action (action)
        """
        if isinstance(action, list) and action:
            action = action[0]

        return ApplicationAction in action.__bases__

    def is_force_not_open_workfile(self, item, stored):
        """Checks if application for task is marked to not open workfile

        There might be specific tasks where is unwanted to open workfile right
        always (broken file, low performance). This allows artist to mark to
        skip opening for combination (project, folder_id, task_name, app)

        Args:
            item (QStandardItem)
            stored (list) of dict
        """
        action = item.data(ACTION_ROLE)
        if not self.is_application_action(action):
            return False

        actual_data = self._prepare_compare_data(action)
        for config in stored:
            if config == actual_data:
                return True

        return False

    def _prepare_compare_data(self, action):
        if isinstance(action, list) and action:
            action = action[0]

        compare_data = {}
        if action:
            compare_data = {
                "app_label": action.label.lower(),
                "project_name": self.context.project_name,
                "asset": self.context.folder_id,
                "task_name": self.context.task_id,
            }
        return compare_data


class LauncherModel(QtCore.QObject):
    # Refresh interval of projects
    refresh_interval = 10000

    # Signals
    # Current project has changed
    project_changed = QtCore.Signal(str)
    # Filters has changed (any)
    filters_changed = QtCore.Signal()

    # Projects were refreshed
    projects_refreshed = QtCore.Signal()

    # Signals ONLY for folders model!
    # - other objects should listen to folder model signals
    # Folders refresh started
    folders_refresh_started = QtCore.Signal()
    # Folders refresh finished
    folders_refreshed = QtCore.Signal()

    # Refresh timer timeout
    #   - give ability to tell parent window that this timer still runs
    timer_timeout = QtCore.Signal()

    def __init__(self):
        super(LauncherModel, self).__init__()
        # Refresh timer
        #   - should affect only projects
        refresh_timer = QtCore.QTimer()
        refresh_timer.setInterval(self.refresh_interval)
        refresh_timer.timeout.connect(self._on_timeout)

        self._refresh_timer = refresh_timer

        self._context = SelectedContext()

        # Launcher is active
        self._active = False

        # Available project names
        self._project_names = set()

        # Context data
        self._folders = []
        self._folders_by_id = {}
        self._folder_filter_data_by_id = {}
        self._assignees = set()
        self._task_types = set()
        self._tasks_by_folder_id = {}

        # Filters
        self._folder_name_filter = ""
        self._assignee_filters = set()
        self._task_type_filters = set()

        # Last project for which were folders queried
        self._last_project_name = None
        # Folder refresh thread is running
        self._refreshing_folders = False
        # Folder refresh thread
        self._folders_refresh_thread = None

        self._session = create_session()

    def _on_timeout(self):
        """Refresh timer timeout."""
        if self._active:
            self.timer_timeout.emit()
            self.refresh_projects()

    def set_active(self, active):
        """Window change active state."""
        self._active = active

    def start_refresh_timer(self, trigger=False):
        """Start refresh timer."""
        self._refresh_timer.start()
        if trigger:
            self._on_timeout()

    def stop_refresh_timer(self):
        """Stop refresh timer."""
        self._refresh_timer.stop()

    @property
    def context(self):
        return self._context

    @property
    def project_name(self):
        """Current project name."""
        return self._context.project_name

    @property
    def refreshing_folders(self):
        """Refreshing thread is running."""
        return self._refreshing_folders

    @property
    def folders(self):
        """Access to folders."""
        return self._folders

    @property
    def project_names(self):
        """Available project names."""
        return self._project_names

    @property
    def folder_filter_data_by_id(self):
        """Prepared filter data by folder id."""
        return self._folder_filter_data_by_id

    @property
    def assignees(self):
        """All assignees for all folders in current project."""
        return self._assignees

    @property
    def task_types(self):
        """All task types for all folders in current project.

        TODO: This could be maybe taken from project document where are all
        task types...
        """
        return self._task_types

    @property
    def task_type_filters(self):
        """Currently set task type filters."""
        return self._task_type_filters

    @property
    def assignee_filters(self):
        """Currently set assignee filters."""
        return self._assignee_filters

    @property
    def folder_name_filter(self):
        """Folder name filter (can be used as regex filter)."""
        return self._folder_name_filter

    def get_folder_by_id(self, folder_id):
        """Get single folder by id."""
        return self._folders_by_id.get(folder_id)

    def get_tasks_by_folder_id(self, folder_id):
        if not folder_id:
            return None

        if folder_id not in self._tasks_by_folder_id:
            self._tasks_by_folder_id[folder_id] = (
                self._session.get_tasks_by_folder_ids(
                    self.project_name, folder_id
                )
            )
        return self._tasks_by_folder_id[folder_id]

    def set_project_name(self, project_name):
        """Change project name and refresh folder documents."""
        if project_name == self.project_name:
            return
        self._context.set_project_name(project_name)
        self.project_changed.emit(project_name)

        self.refresh_folders(force=True)

    def refresh(self):
        """Trigger refresh of whole model."""
        self.refresh_projects()
        self.refresh_folders(force=False)

    def refresh_projects(self):
        """Refresh projects."""
        current_project = self.project_name
        project_names = set()

        for project_name in self._session.get_project_names():
            project_names.add(project_name)

        self._project_names = project_names
        self.projects_refreshed.emit()
        if (
            current_project is not None
            and current_project not in project_names
        ):
            self.set_project_name(None)

    def _set_project_hierarchy(self, folders_data=None, tasks_data=None):
        """Set folder and all related data.

        Method extract and prepare data needed for folders and tasks widget and
        prepare filtering data.
        """
        if folders_data is None:
            folders_data = []

        if tasks_data is None:
            tasks_data = []

        tasks_by_folder_id = collections.defaultdict(list)
        for task_data in tasks_data:
            tasks_by_folder_id[task_data["folderId"]].append(task_data)

        folders_by_id = {}

        self._folders_by_id = folders_by_id
        self._folders = folders_data
        # NOTE disabled filtering options for now
        self._folder_filter_data_by_id = {}
        self._assignees = set()
        self._task_types = set()
        self._tasks_by_folder_id = {}

        self.folders_refreshed.emit()

    def set_task_type_filter(self, task_types):
        """Change task type filter.

        Args:
            task_types (set): Set of task types that should be visible.
                Pass empty set to turn filter off.
        """
        self._task_type_filters = task_types
        self.filters_changed.emit()

    def set_assignee_filter(self, assignees):
        """Change assignees filter.

        Args:
            assignees (set): Set of assignees that should be visible.
                Pass empty set to turn filter off.
        """
        self._assignee_filters = assignees
        self.filters_changed.emit()

    def set_folder_name_filter(self, text_filter):
        """Change folder name filter.

        Args:
            text_filter (str): Folder name filter. Pass empty string to
            turn filter off.
        """
        self._folder_name_filter = text_filter
        self.filters_changed.emit()

    def refresh_folders(self, force=True):
        """Refresh folders."""
        self.folders_refresh_started.emit()

        if self.project_name is None:
            self._set_project_hierarchy()
            return

        if (
            not force
            and self._last_project_name == self.project_name
        ):
            return

        self._stop_fetch_thread()

        self._refreshing_folders = True
        self._last_project_name = self.project_name
        self._folders_refresh_thread = DynamicQThread(self._refresh_folders)
        self._folders_refresh_thread.start()

    def _stop_fetch_thread(self):
        self._refreshing_folders = False
        if self._folders_refresh_thread is not None:
            while self._folders_refresh_thread.isRunning():
                # TODO this is blocking UI should be done in a different way
                time.sleep(0.01)
            self._folders_refresh_thread = None

    def _refresh_folders(self):
        folders_data = self._session.get_project_folders(
            self._context.project_name
        )
        if not self._refreshing_folders:
            return

        self._refreshing_folders = False
        self._set_project_hierarchy(folders_data)


class LauncherTasksProxyModel(TasksProxyModel):
    """Tasks proxy model with more filtering.

    TODO:
    This can be (with few modifications) used in default tasks widget too.
    """
    def __init__(self, launcher_model, *args, **kwargs):
        self._launcher_model = launcher_model
        super(LauncherTasksProxyModel, self).__init__(*args, **kwargs)

        launcher_model.filters_changed.connect(self._on_filter_change)

        self._task_types_filter = set()
        self._assignee_filter = set()

    def _on_filter_change(self):
        self._task_types_filter = self._launcher_model.task_type_filters
        self._assignee_filter = self._launcher_model.assignee_filters
        self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        if not self._task_types_filter and not self._assignee_filter:
            return True

        model = self.sourceModel()
        source_index = model.index(row, self.filterKeyColumn(), parent)
        if not source_index.isValid():
            return False

        # Check current index itself
        if self._task_types_filter:
            task_type = model.data(source_index, TASK_TYPE_ROLE)
            if task_type not in self._task_types_filter:
                return False

        if self._assignee_filter:
            assignee = model.data(source_index, TASK_ASSIGNEE_ROLE)
            if not self._assignee_filter.intersection(assignee):
                return False
        return True


class LauncherTaskModel(TasksModel):
    def __init__(self, launcher_model, *args, **kwargs):
        self._launcher_model = launcher_model
        super(LauncherTaskModel, self).__init__(
            launcher_model.context, *args, **kwargs
        )

    def set_folder_id(self, folder_id):
        if not self._context_is_valid():
            folder_id = None

        tasks = self._launcher_model.get_tasks_by_folder_id(folder_id)
        self._set_folder_tasks(folder_id, tasks)


class FoldersRecursiveSortFilterModel(QtCore.QSortFilterProxyModel):
    def __init__(self, launcher_model, *args, **kwargs):
        self._launcher_model = launcher_model

        super(FoldersRecursiveSortFilterModel, self).__init__(*args, **kwargs)

        launcher_model.filters_changed.connect(self._on_filter_change)
        self._name_filter = ""
        self._task_types_filter = set()
        self._assignee_filter = set()

    def _on_filter_change(self):
        self._name_filter = self._launcher_model.folder_name_filter
        self._task_types_filter = self._launcher_model.task_type_filters
        self._assignee_filter = self._launcher_model.assignee_filters
        self.invalidateFilter()

    """Filters to the regex if any of the children matches allow parent"""
    def filterAcceptsRow(self, row, parent):
        if (
            not self._name_filter
            and not self._task_types_filter
            and not self._assignee_filter
        ):
            return True

        model = self.sourceModel()
        source_index = model.index(row, self.filterKeyColumn(), parent)
        if not source_index.isValid():
            return False

        # Check current index itself
        valid = True
        if self._name_filter:
            name = model.data(source_index, FOLDER_NAME_ROLE)
            if not re.search(self._name_filter, name, re.IGNORECASE):
                valid = False

        if valid and self._task_types_filter:
            task_types = model.data(source_index, FOLDER_TASK_TYPES_ROLE)
            if not self._task_types_filter.intersection(task_types):
                valid = False

        if valid and self._assignee_filter:
            assignee = model.data(source_index, FOLDER_ASSIGNEE_ROLE)
            if not self._assignee_filter.intersection(assignee):
                valid = False

        if valid:
            return True

        # Check children
        rows = model.rowCount(source_index)
        for child_row in range(rows):
            if self.filterAcceptsRow(child_row, source_index):
                return True
        return False


class LauncherFoldersModel(FoldersModel):
    def __init__(self, launcher_model, parent=None):
        self._launcher_model = launcher_model
        # Make sure that variable is available (even if is in FoldersModel)
        self._last_project_name = None

        super(LauncherFoldersModel, self).__init__(None, parent)

        launcher_model.project_changed.connect(self._on_project_change)
        launcher_model.folders_refresh_started.connect(
            self._on_launcher_refresh_start
        )
        launcher_model.folders_refreshed.connect(self._on_launcher_refresh)

    def _on_launcher_refresh_start(self):
        self._refreshing = True
        project_name = self._launcher_model.project_name
        if self._last_project_name != project_name:
            self._clear_items()
            self._last_project_name = project_name

    def _on_launcher_refresh(self):
        self._fill_folders(self._launcher_model.folders)
        self._refreshing = False
        self.refreshed.emit(bool(self._items_by_folder_id))

    def _fill_folders(self, *args, **kwargs):
        super(LauncherFoldersModel, self)._fill_folders(*args, **kwargs)
        # folder_filter_data_by_id = (
        #     self._launcher_model.folder_filter_data_by_id
        # )
        # for folder_id, item in self._items_by_folder_id.items():
        #     filter_data = folder_filter_data_by_id.get(folder_id)
        #
        #     assignees = filter_data["assignees"]
        #     task_types = filter_data["task_types"]
        #
        #     item.setData(assignees, FOLDER_ASSIGNEE_ROLE)
        #     item.setData(task_types, FOLDER_TASK_TYPES_ROLE)

    def _on_project_change(self):
        self._clear_items()

    def refresh(self, *args, **kwargs):
        raise ValueError("This is a bug!")

    def stop_refresh(self, *args, **kwargs):
        raise ValueError("This is a bug!")


class ProjectModel(QtGui.QStandardItemModel):
    """List of projects"""

    def __init__(self, launcher_model, parent=None):
        super(ProjectModel, self).__init__(parent=parent)

        self._launcher_model = launcher_model
        self.project_icon = qtawesome.icon("fa.map", color="white")
        self._project_names = set()

        launcher_model.projects_refreshed.connect(self._on_refresh)

    def _on_refresh(self):
        project_names = set(self._launcher_model.project_names)
        origin_project_names = set(self._project_names)
        self._project_names = project_names

        project_names_to_remove = origin_project_names - project_names
        if project_names_to_remove:
            row_counts = {}
            continuous = None
            for row in range(self.rowCount()):
                index = self.index(row, 0)
                index_name = index.data(QtCore.Qt.DisplayRole)
                if index_name in project_names_to_remove:
                    if continuous is None:
                        continuous = row
                        row_counts[continuous] = 0
                    row_counts[continuous] += 1
                else:
                    continuous = None

            for row in reversed(sorted(row_counts.keys())):
                count = row_counts[row]
                self.removeRows(row, count)

        continuous = None
        row_counts = {}
        for idx, project_name in enumerate(sorted(project_names)):
            if project_name in origin_project_names:
                continuous = None
                continue

            if continuous is None:
                continuous = idx
                row_counts[continuous] = []

            row_counts[continuous].append(project_name)

        for row in reversed(sorted(row_counts.keys())):
            items = []
            for project_name in row_counts[row]:
                item = QtGui.QStandardItem(self.project_icon, project_name)
                items.append(item)

            self.invisibleRootItem().insertRows(row, items)
