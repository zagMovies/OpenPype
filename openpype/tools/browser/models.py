import collections
from qtpy import QtGui, QtCore

PROJECT_NAME_ROLE = QtCore.Qt.UserRole + 1
IS_CURRENT_PROJECT_ROLE = QtCore.Qt.UserRole + 2
IS_SELECT_ITEM_ROLE = QtCore.Qt.UserRole + 3
ASSET_NAME_ROLE = QtCore.Qt.UserRole + 4
ASSET_ID_ROLE = QtCore.Qt.UserRole + 5
SUBSET_ID_ROLE = QtCore.Qt.UserRole + 6
SUBSET_NAME_ROLE = QtCore.Qt.UserRole + 7
SUBSET_FAMILY_ROLE = QtCore.Qt.UserRole + 8
VERSION_ID_ROLE = QtCore.Qt.UserRole + 9
VERSION_HERO_ROLE = QtCore.Qt.UserRole + 10
VERSION_NAME_ROLE = QtCore.Qt.UserRole + 11
VERSION_NAME_EDIT_ROLE = QtCore.Qt.UserRole + 12
VERSION_PUBLISH_TIME_ROLE = QtCore.Qt.UserRole + 13
VERSION_AUTHOR_ROLE = QtCore.Qt.UserRole + 14
VERSION_FRAME_RANGE_ROLE = QtCore.Qt.UserRole + 15
VERSION_DURATION_ROLE = QtCore.Qt.UserRole + 16
VERSION_HANDLES_ROLE = QtCore.Qt.UserRole + 17
VERSION_STEP_ROLE = QtCore.Qt.UserRole + 18
VERSION_IN_SCENE_ROLE = QtCore.Qt.UserRole + 19
VERSION_AVAILABLE_ROLE = QtCore.Qt.UserRole + 20


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


class SubsetsModel(QtGui.QStandardItemModel):
    column_labels = [
        "Subset",
        "Asset",
        "Family",
        "Version",
        "Time",
        "Author",
        "Frames",
        "Duration",
        "Handles",
        "Step",
        "In scene",
        "Availability"
    ]

    column_labels_mapping = {
        idx: label
        for idx, label in enumerate(column_labels)
    }
    version_col = column_labels.index("Version")
    published_time_col = column_labels.index("Time")

    def __init__(self, controller):
        super().__init__()
        self.setColumnCount(len(self.column_labels))
        self._controller = controller

        # Variables to store 'QStandardItem'
        self._items_by_id = {}
        self._group_items_by_name = {}
        self._merged_items_by_id = {}

        # Subset item objects (they have version information)
        self._subset_items_by_id = {}
        self._grouping_enabled = False

        controller.event_system.add_callback(
            "model.subsets.refresh.finished",
            self.refresh
        )
        controller.event_system.add_callback(
            "model.subsets.cleared",
            self._on_subsets_clear
        )

    def headerData(self, section, orientation, role):
        """Remap column names to labels"""
        if role == QtCore.Qt.DisplayRole:
            label = self.column_labels_mapping.get(section)
            if label is not None:
                return label

        return super().headerData(section, orientation, role)

    def flags(self, index):
        flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

        # Make the version column editable
        if index.column() == self.version_col and index.data(SUBSET_ID_ROLE):
            flags |= QtCore.Qt.ItemIsEditable
        return flags

    def _clear(self):
        root_item = self.invisibleRootItem()
        for row in reversed(range(root_item.rowCount())):
            item = root_item.child(row)
            root_item.removeRow(item.row())

        self._items_by_id = {}
        self._group_items_by_name = {}
        self._merged_items_by_id = {}

        self._subset_items_by_id = {}

    def _on_subsets_clear(self):
        self._clear()

    def _remove_items(self, items):
        root_item = self.invisibleRootItem()
        for item in items:
            if item is None:
                continue
            row = item.row()
            if row < 0:
                continue
            parent = item.parent()
            if parent is None:
                parent = root_item
            parent.takeRow(row)

    def _get_group_model_item(self, group_name):
        if group_name is None:
            return self.invisibleRootItem()

        model_item = self._group_items_by_name.get(group_name)
        if model_item is None:
            model_item = QtGui.QStandardItem(group_name)
            self._group_items_by_name[group_name] = model_item
        return model_item

    def _get_merged_model_item(self, path):
        model_item = self._merged_items_by_id.get(path)
        if model_item is None:
            model_item = QtGui.QStandardItem(path)
            self._merged_items_by_id[path] = model_item
        return model_item

    def _set_version_data_to_subset_item(self, model_item, version_item):
        """

        Args:
            model_item (QtGui.QStandardItem): Item which should have values
                from version item.
            version_item (VersionItem): Item from entities model with
                information about version.
        """

        model_item.setData(version_item.version_id, VERSION_ID_ROLE)
        model_item.setData(version_item.version, VERSION_NAME_ROLE)
        model_item.setData(version_item.version_id, VERSION_ID_ROLE)
        model_item.setData(version_item.is_hero, VERSION_HERO_ROLE)
        model_item.setData(
            version_item.published_time, VERSION_PUBLISH_TIME_ROLE
        )
        model_item.setData(version_item.author, VERSION_AUTHOR_ROLE)
        model_item.setData(version_item.frame_range, VERSION_FRAME_RANGE_ROLE)
        model_item.setData(version_item.duration, VERSION_DURATION_ROLE)
        model_item.setData(version_item.handles, VERSION_HANDLES_ROLE)
        model_item.setData(version_item.step, VERSION_STEP_ROLE)
        model_item.setData(version_item.in_scene, VERSION_IN_SCENE_ROLE)

    def _get_subset_model_item(self, subset_item):
        model_item = self._items_by_id.get(subset_item.subset_id)
        versions = list(subset_item.versions)
        versions.sort()
        last_version = versions[-1]
        if model_item is None:
            subset_id = subset_item.subset_id
            model_item = QtGui.QStandardItem(subset_item.subset_name)
            model_item.setData(subset_id, SUBSET_ID_ROLE)
            model_item.setData(subset_item.subset_name, SUBSET_NAME_ROLE)
            model_item.setData(subset_item.family, SUBSET_FAMILY_ROLE)
            model_item.setData(subset_item.asset_id, ASSET_ID_ROLE)
            model_item.setData(subset_item.asset_name, ASSET_NAME_ROLE)

            self._subset_items_by_id[subset_id] = subset_item
            self._items_by_id[subset_id] = model_item
        self._set_version_data_to_subset_item(model_item, last_version)
        return model_item

    def refresh(self):
        subset_items_by_id = self._controller.get_subset_items()

        # Remove subset items that are not available
        subset_ids_to_remove = (
            set(self._items_by_id.keys()) - set(subset_items_by_id.keys())
        )
        items_to_remove = [
            self._items_by_id.pop(subset_id)
            for subset_id in subset_ids_to_remove
        ]
        (
            self._subset_items_by_id.pop(subset_id)
            for subset_id in subset_ids_to_remove
        )
        self._remove_items(items_to_remove)

        # Prepare subset groups
        subset_name_matches_by_group = collections.defaultdict(dict)
        for subset_item in subset_items_by_id.values():
            group_name = None
            if self._grouping_enabled:
                group_name = subset_item.group_name

            subset_name = subset_item.subset_name
            group = subset_name_matches_by_group[group_name]
            if subset_name not in group:
                group[subset_name] = [subset_item]
                continue
            group[subset_name].append(subset_item)

        group_names = set(subset_name_matches_by_group.keys())
        has_root_items = None in group_names
        if has_root_items:
            group_names.remove(None)
        s_group_names = list(sorted(group_names))
        if has_root_items:
            s_group_names.insert(0, None)

        root_item = self.invisibleRootItem()
        merged_paths = set()
        for group_name in s_group_names:
            key_parts = ["M"]
            if group_name:
                key_parts.append(group_name)

            groups = subset_name_matches_by_group[group_name]
            merged_subset_items = {}
            top_items = []
            for subset_name, subset_items in groups.items():
                if len(subset_items) == 1:
                    top_items.append(subset_items[0])
                else:
                    path = "/".join(key_parts + [subset_name])
                    merged_paths.add(path)
                    merged_subset_items[path] = subset_items

            new_items = []
            parent_item = self._get_group_model_item(group_name)
            c_parent_item = None
            if parent_item is not root_item:
                c_parent_item = parent_item

            for subset_item in top_items:
                item = self._get_subset_model_item(subset_item)
                if (
                    item.row() < 0
                    or item.parent() is not c_parent_item
                ):
                    new_items.append(item)

            for path, subset_items in merged_subset_items.items():
                merged_item = self._get_merged_model_item(path)
                if merged_item.parent() is not parent_item:
                    new_items.append(merged_item)

                new_merged_items = []
                for subset_item in subset_items:
                    item = self._get_subset_model_item(subset_item)
                    if item.parent() is not merged_item:
                        new_merged_items.append(item)

                if new_merged_items:
                    merged_item.appendRows(new_merged_items)

            if new_items:
                parent_item.appendRows(new_items)

        merged_item_ids_to_remove = (
            set(self._merged_items_by_id.keys()) - merged_paths
        )
        self._remove_items(
            self._merged_items_by_id.pop(item_id)
            for item_id in merged_item_ids_to_remove
        )

        group_names_to_remove = (
            set(self._group_items_by_name.keys()) - set(s_group_names)
        )
        self._remove_items(
            self._group_items_by_name.pop(group_name)
            for group_name in group_names_to_remove
        )

    def data(self, index, role):
        if not index.isValid():
            return None

        col = index.column()
        if col == 0:
            return super().data(index, role)

        if role == QtCore.Qt.DecorationRole:
            return None

        if (
            role == VERSION_NAME_EDIT_ROLE
            or (role == QtCore.Qt.EditRole and col == self.version_col)
        ):
            index = self.index(index.row(), 0, index.parent())
            subset_id = index.data(SUBSET_ID_ROLE)
            subset_item = self._subset_items_by_id.get(subset_id)
            if subset_item is None:
                return None
            return subset_item.versions

        if role == QtCore.Qt.EditRole:
            return None

        index = self.index(index.row(), 0, index.parent())
        if role == QtCore.Qt.DisplayRole:
            if not index.data(SUBSET_ID_ROLE):
                pass
            elif col == 1:
                role = ASSET_NAME_ROLE
            elif col == 2:
                role = SUBSET_FAMILY_ROLE
            elif col == self.version_col:
                role = VERSION_NAME_ROLE
            elif col == 4:
                role = VERSION_PUBLISH_TIME_ROLE
            elif col == 5:
                role = VERSION_AUTHOR_ROLE
            elif col == 6:
                role = VERSION_FRAME_RANGE_ROLE
            elif col == 7:
                role = VERSION_DURATION_ROLE
            elif col == 8:
                role = VERSION_HANDLES_ROLE
            elif col == 9:
                role = VERSION_STEP_ROLE
            elif col == 10:
                role = VERSION_IN_SCENE_ROLE
            elif col == 11:
                role = VERSION_AVAILABLE_ROLE
            else:
                return None

        index = self.index(index.row(), 0, index.parent())

        return super().data(index, role)

    def setData(self, index, value, role):
        if not index.isValid():
            return False

        col = index.column()
        if (col == self.version_col and role == QtCore.Qt.EditRole):
            role = VERSION_NAME_EDIT_ROLE

        if role == VERSION_NAME_EDIT_ROLE:
            if col != 0:
                index = self.index(index.row(), 0, index.parent())
            subset_id = index.data(SUBSET_ID_ROLE)
            subset_item = self._subset_items_by_id[subset_id]
            version_item = subset_item.get_version_by_id(value)
            if version_item is None:
                return False
            if index.data(VERSION_ID_ROLE) == version_item.version_id:
                return True
            item = self.itemFromIndex(index)
            self._set_version_data_to_subset_item(item, version_item)
            return True
        return False
