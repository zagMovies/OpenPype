import collections
from qtpy import QtGui, QtCore

PROJECT_NAME_ROLE = QtCore.Qt.UserRole + 1
IS_CURRENT_PROJECT_ROLE = QtCore.Qt.UserRole + 2
IS_SELECT_ITEM_ROLE = QtCore.Qt.UserRole + 3
ASSET_NAME_ROLE = QtCore.Qt.UserRole + 4
ASSET_ID_ROLE = QtCore.Qt.UserRole + 5


class ProjectsModel(QtGui.QStandardItemModel):
    def __init__(self, controller):
        super().__init__()
        self._controller = controller

        self._items_by_name = {}
        self._empty_item = None
        self._current_project_item = None
        self._select_project_item = None

        self._empty_in_root = False
        self._select_in_root = False

        controller.event_system.add_callback(
            "model.projects.refresh.finished",
            self.refresh
        )

    def _get_empty_item(self):
        if self._empty_item is None:
            item = QtGui.QStandardItem("<N/A>")
            self._empty_item = item

        return self._empty_item

    def _get_select_item(self):
        if self._select_project_item is None:
            item = QtGui.QStandardItem("<Select project>")
            item.setData(True, IS_SELECT_ITEM_ROLE)
            self._select_project_item = item

        return self._select_project_item

    def _add_empty_item(self):
        if self._empty_in_root:
            return

        self._empty_in_root = True
        self._items_by_name = {}

        root_item = self.invisibleRootItem()
        if self._select_in_root:
            select_project_item = self._get_select_item()
            root_item.takeChild(select_project_item.row())

        self.clear()
        root_item.appendRow(self._get_empty_item())

    def refresh(self):
        root_item = self.invisibleRootItem()
        project_names = self._controller.get_project_names()
        if not project_names:
            self._add_empty_item()
            return

        if self._empty_in_root:
            root_item.takeChild(self._empty_item.row())
            self._empty_in_root = False

        if not self._select_in_root:
            self._select_in_root = True
            select_project_item = self._get_select_item()
            root_item.appendRow(select_project_item)

        current_project = self._controller.get_current_project()
        current_project_item = None
        to_remove = []
        for project_name, item in self._items_by_name.items():
            if project_name not in project_names:
                to_remove.append(project_name)

        new_items = []
        for project_name in project_names:
            if project_name not in self._items_by_name:
                item = QtGui.QStandardItem(project_name)
                item.setFlags(
                    QtCore.Qt.ItemIsSelectable
                    | QtCore.Qt.ItemIsEnabled
                )
                item.setData(project_name, PROJECT_NAME_ROLE)
                self._items_by_name[project_name] = item
                new_items.append(item)

            if project_name == current_project:
                current_project_item = self._items_by_name[project_name]
                current_project_item.setData(True, IS_CURRENT_PROJECT_ROLE)

        if self._current_project_item is not None:
            self._current_project_item.setData(None, IS_CURRENT_PROJECT_ROLE)
        self._current_project_item = current_project_item

        for project_name in to_remove:
            item = self._items_by_name.pop(project_name)
            root_item.removeRow(item.row())

        if new_items:
            root_item.appendRows(new_items)


class HierarchyModel(QtGui.QStandardItemModel):
    def __init__(self, controller):
        super().__init__()
        self._controller = controller

        self._items_by_id = {}

        controller.event_system.add_callback(
            "model.hierarchy.refresh.finished",
            self.refresh
        )
        controller.event_system.add_callback(
            "model.hierarchy.cleared",
            self._on_hierarchy_clear
        )

    def _clear(self):
        root_item = self.invisibleRootItem()
        for row in reversed(range(root_item.rowCount())):
            item = root_item.child(row)
            root_item.removeRow(item.row())

        self._items_by_id = {}

    def _on_hierarchy_clear(self):
        self._clear()

    def refresh(self):
        hierarchy_items_by_id = self._controller.get_hierarchy_items()
        hierarchy_items_by_parent_id = collections.defaultdict(list)
        for hierarchy_item in hierarchy_items_by_id.values():
            hierarchy_items_by_parent_id[hierarchy_item.parent_id].append(
                hierarchy_item
            )

        ids_to_remove = (
            set(self._items_by_id.keys())
            - set(hierarchy_items_by_id.keys())
        )

        root_item = self.invisibleRootItem()
        items_queue = collections.deque()
        items_queue.append((None, root_item))
        while items_queue:
            queue_item = items_queue.popleft()
            parent_id, parent_item = queue_item
            new_items = []
            for hierarchy_item in hierarchy_items_by_parent_id[parent_id]:
                item_id = hierarchy_item.id
                item = self._items_by_id.get(item_id)
                if item is None:
                    item = QtGui.QStandardItem()
                    item.setFlags(
                        QtCore.Qt.ItemIsSelectable
                        | QtCore.Qt.ItemIsEnabled
                    )
                    new_items.append(item)
                    self._items_by_id[item_id] = item

                elif item.parent() is not parent_item:
                    new_items.append(item)

                item.setData(hierarchy_item.label, QtCore.Qt.DisplayRole)
                item.setData(hierarchy_item.name, ASSET_NAME_ROLE)
                item.setData(item_id, ASSET_ID_ROLE)
                items_queue.append((item_id, item))

            if new_items:
                parent_item.appendRows(new_items)

        for item_id in ids_to_remove:
            item = self._items_by_id.pop(item_id, None)
            if item is None:
                continue
            row = item.row()
            if row < 0:
                continue
            parent = item.parent()
            if parent is None:
                parent = root_item
            parent.takeRow(row)
