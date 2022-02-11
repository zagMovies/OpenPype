import time
import collections

import Qt
from Qt import QtWidgets, QtCore, QtGui

from avalon import style
from avalon.vendor import qtawesome

from openpype.style import get_objected_colors
from openpype.tools.flickcharm import FlickCharm

from openpype.tools.utils.views import (
    TreeViewSpinner,
    DeselectableTreeView
)
from openpype.tools.utils.widgets import PlaceholderLineEdit
from openpype.tools.utils.models import RecursiveSortFilterProxyModel
from openpype.tools.utils.lib import DynamicQThread

from .client import (
    get_project,
    get_project_folders,
)

if Qt.__binding__ == "PySide":
    from PySide.QtGui import QStyleOptionViewItemV4
elif Qt.__binding__ == "PyQt4":
    from PyQt4.QtGui import QStyleOptionViewItemV4

FOLDER_ID_ROLE = QtCore.Qt.UserRole + 1
FOLDER_NAME_ROLE = QtCore.Qt.UserRole + 2
FOLDER_LABEL_ROLE = QtCore.Qt.UserRole + 3
FOLDER_UNDERLINE_COLORS_ROLE = QtCore.Qt.UserRole + 4


class FoldersView(TreeViewSpinner, DeselectableTreeView):
    """Folders items view.

    Adds abilities to deselect, show loading spinner and add flick charm
    (scroll by mouse/touchpad click and move).
    """

    def __init__(self, parent=None):
        super(FoldersView, self).__init__(parent)
        self.setIndentation(15)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.setHeaderHidden(True)

        self._flick_charm_activated = False
        self._flick_charm = FlickCharm(parent=self)
        self._before_flick_scroll_mode = None

    def activate_flick_charm(self):
        if self._flick_charm_activated:
            return
        self._flick_charm_activated = True
        self._before_flick_scroll_mode = self.verticalScrollMode()
        self._flick_charm.activateOn(self)
        self.setVerticalScrollMode(self.ScrollPerPixel)

    def deactivate_flick_charm(self):
        if not self._flick_charm_activated:
            return
        self._flick_charm_activated = False
        self._flick_charm.deactivateFrom(self)
        if self._before_flick_scroll_mode is not None:
            self.setVerticalScrollMode(self._before_flick_scroll_mode)

    def mousePressEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            if modifiers == QtCore.Qt.ShiftModifier:
                return
            elif modifiers == QtCore.Qt.ControlModifier:
                return

        super(FoldersView, self).mousePressEvent(event)

    def set_loading_state(self, loading, empty):
        """Change loading state.

        TODO: Separate into 2 individual methods.

        Args:
            loading(bool): Is loading.
            empty(bool): Is model empty.
        """
        if self.is_loading != loading:
            if loading:
                self.spinner.repaintNeeded.connect(
                    self.viewport().update
                )
            else:
                self.spinner.repaintNeeded.disconnect()
                self.viewport().update()

        self.is_loading = loading
        self.is_empty = empty


class UnderlinesFolderDelegate(QtWidgets.QItemDelegate):
    """Item delegate drawing bars under folder label.

    This is used in loader and library loader tools. Multiselection of folders
    may group subsets by name under colored groups. Selected color groups are
    then propagated back to selected folders as underlines.
    """
    bar_height = 3

    def __init__(self, *args, **kwargs):
        super(UnderlinesFolderDelegate, self).__init__(*args, **kwargs)
        view_colors = get_objected_colors()["loader"]["asset-view"]
        self._selected_color = view_colors["selected"].get_qcolor()
        self._hover_color = view_colors["hover"].get_qcolor()
        self._selected_hover_color = view_colors["selected-hover"].get_qcolor()

    def sizeHint(self, option, index):
        """Add bar height to size hint."""
        result = super(UnderlinesFolderDelegate, self).sizeHint(option, index)
        height = result.height()
        result.setHeight(height + self.bar_height)

        return result

    def paint(self, painter, option, index):
        """Replicate painting of an item and draw color bars if needed."""
        # Qt4 compat
        if Qt.__binding__ in ("PySide", "PyQt4"):
            option = QStyleOptionViewItemV4(option)

        painter.save()

        item_rect = QtCore.QRect(option.rect)
        item_rect.setHeight(option.rect.height() - self.bar_height)

        subset_colors = index.data(FOLDER_UNDERLINE_COLORS_ROLE) or []
        subset_colors_width = 0
        if subset_colors:
            subset_colors_width = option.rect.width() / len(subset_colors)

        subset_rects = []
        counter = 0
        for subset_c in subset_colors:
            new_color = None
            new_rect = None
            if subset_c:
                new_color = QtGui.QColor(*subset_c)

                new_rect = QtCore.QRect(
                    option.rect.left() + (counter * subset_colors_width),
                    option.rect.top() + (
                        option.rect.height() - self.bar_height
                    ),
                    subset_colors_width,
                    self.bar_height
                )
            subset_rects.append((new_color, new_rect))
            counter += 1

        # Background
        if option.state & QtWidgets.QStyle.State_Selected:
            if len(subset_colors) == 0:
                item_rect.setTop(item_rect.top() + (self.bar_height / 2))

            if option.state & QtWidgets.QStyle.State_MouseOver:
                bg_color = self._selected_hover_color
            else:
                bg_color = self._selected_color
        else:
            item_rect.setTop(item_rect.top() + (self.bar_height / 2))
            if option.state & QtWidgets.QStyle.State_MouseOver:
                bg_color = self._hover_color
            else:
                bg_color = QtGui.QColor()
                bg_color.setAlpha(0)

        # When not needed to do a rounded corners (easier and without
        #   painter restore):
        painter.fillRect(
            option.rect,
            QtGui.QBrush(bg_color)
        )

        if option.state & QtWidgets.QStyle.State_Selected:
            for color, subset_rect in subset_rects:
                if not color or not subset_rect:
                    continue
                painter.fillRect(subset_rect, QtGui.QBrush(color))

        # Icon
        icon_index = index.model().index(
            index.row(), index.column(), index.parent()
        )
        # - Default icon_rect if not icon
        icon_rect = QtCore.QRect(
            item_rect.left(),
            item_rect.top(),
            # To make sure it's same size all the time
            option.rect.height() - self.bar_height,
            option.rect.height() - self.bar_height
        )
        icon = index.model().data(icon_index, QtCore.Qt.DecorationRole)

        if icon:
            mode = QtGui.QIcon.Normal
            if not (option.state & QtWidgets.QStyle.State_Enabled):
                mode = QtGui.QIcon.Disabled
            elif option.state & QtWidgets.QStyle.State_Selected:
                mode = QtGui.QIcon.Selected

            if isinstance(icon, QtGui.QPixmap):
                icon = QtGui.QIcon(icon)
                option.decorationSize = icon.size() / icon.devicePixelRatio()

            elif isinstance(icon, QtGui.QColor):
                pixmap = QtGui.QPixmap(option.decorationSize)
                pixmap.fill(icon)
                icon = QtGui.QIcon(pixmap)

            elif isinstance(icon, QtGui.QImage):
                icon = QtGui.QIcon(QtGui.QPixmap.fromImage(icon))
                option.decorationSize = icon.size() / icon.devicePixelRatio()

            elif isinstance(icon, QtGui.QIcon):
                state = QtGui.QIcon.Off
                if option.state & QtWidgets.QStyle.State_Open:
                    state = QtGui.QIcon.On
                actual_size = option.icon.actualSize(
                    option.decorationSize, mode, state
                )
                option.decorationSize = QtCore.QSize(
                    min(option.decorationSize.width(), actual_size.width()),
                    min(option.decorationSize.height(), actual_size.height())
                )

            state = QtGui.QIcon.Off
            if option.state & QtWidgets.QStyle.State_Open:
                state = QtGui.QIcon.On

            icon.paint(
                painter, icon_rect,
                QtCore.Qt.AlignLeft, mode, state
            )

        # Text
        text_rect = QtCore.QRect(
            icon_rect.left() + icon_rect.width() + 2,
            item_rect.top(),
            item_rect.width(),
            item_rect.height()
        )

        painter.drawText(
            text_rect, QtCore.Qt.AlignVCenter,
            index.data(QtCore.Qt.DisplayRole)
        )

        painter.restore()


class FoldersModel(QtGui.QStandardItemModel):
    """A model listing files in the active project.

    The folders are displayed in a treeview, they are visually parented by
    a `parentId` field in the database containing an `id` to a parent
    folder.

    Folder document may have defined label, icon or icon color.

    Loading of data for model happens in thread which means that refresh
    is not sequential. When refresh is triggered it is required to listen for
    'refreshed' signal.

    Args:
        context (AvalonMongoDB): Ready to use connection to mongo with.
        parent (QObject): Parent Qt object.
    """

    _doc_fetched = QtCore.Signal()
    refreshed = QtCore.Signal(bool)

    def __init__(self, context, parent=None):
        super(FoldersModel, self).__init__(parent=parent)

        self._context = context
        self._refreshing = False
        self._doc_fetching_thread = None
        self._doc_fetching_stop = False
        self._doc_payload = []

        self._doc_fetched.connect(self._on_docs_fetched)

        self._items_with_color_by_id = {}
        self._items_by_folder_id = {}

        self._last_project_name = None

    @property
    def refreshing(self):
        return self._refreshing

    def get_index_by_folder_id(self, folder_id):
        item = self._items_by_folder_id.get(folder_id)
        if item is not None:
            return item.index()
        return QtCore.QModelIndex()

    def get_indexes_by_folder_ids(self, folder_ids):
        return [
            self.get_index_by_folder_id(folder_id)
            for folder_id in folder_ids
        ]

    def refresh(self, force=False):
        """Refresh the data for the model.

        Args:
            force (bool): Stop currently running refresh start new refresh.
        """
        # Skip fetch if there is already other thread fetching documents
        if self._refreshing:
            if not force:
                return
            self.stop_refresh()

        project_name = self._context.project_name
        clear_model = False
        if project_name != self._last_project_name:
            clear_model = True
            self._last_project_name = project_name

        if clear_model:
            self._clear_items()

        # Fetch documents from mongo
        # Restart payload
        self._refreshing = True
        self._doc_payload = []
        self._doc_fetching_thread = DynamicQThread(self._threaded_fetch)
        self._doc_fetching_thread.start()

    def stop_refresh(self):
        self._stop_fetch_thread()

    def clear_underlines(self):
        for folder_id in tuple(self._items_with_color_by_id.keys()):
            item = self._items_with_color_by_id.pop(folder_id)
            item.setData(None, FOLDER_UNDERLINE_COLORS_ROLE)

    def set_underline_colors(self, colors_by_folder_id):
        self.clear_underlines()

        for folder_id, colors in colors_by_folder_id.items():
            item = self._items_by_folder_id.get(folder_id)
            if item is None:
                continue
            item.setData(colors, FOLDER_UNDERLINE_COLORS_ROLE)

    def _clear_items(self):
        root_item = self.invisibleRootItem()
        root_item.removeRows(0, root_item.rowCount())
        self._items_by_folder_id = {}
        self._items_with_color_by_id = {}

    def _on_docs_fetched(self):
        # Make sure refreshing did not change
        # - since this line is refreshing sequential and
        #   triggering of new refresh will happen when this method is done
        if not self._refreshing:
            self._clear_items()
            return

        self._fill_folders(self._doc_payload)

        self.refreshed.emit(bool(self._items_by_folder_id))

        self._stop_fetch_thread()

    def _fill_folders(self, folders):
        # Collect folders data as needed
        folders_by_id = {}
        folder_ids_by_parents = collections.defaultdict(set)
        for folder in folders:
            folder_id = folder["id"]
            folders_by_id[folder_id] = folder
            parent_id = folder["parentId"]
            folder_ids_by_parents[parent_id].add(folder_id)

        # Prepare removed folder ids
        removed_folder_ids = (
            set(self._items_by_folder_id.keys())
            - set(folders_by_id.keys())
        )

        # Prepare queue for adding new items
        folder_items_queue = collections.deque()

        # Queue starts with root item and 'visualParent' None
        root_item = self.invisibleRootItem()
        folder_items_queue.append((None, root_item))

        while folder_items_queue:
            # Get item from queue
            parent_id, parent_item = folder_items_queue.popleft()
            # Skip if there are no children
            children_ids = folder_ids_by_parents[parent_id]

            # Go through current children of parent item
            # - find out items that were deleted and skip creation of already
            #   existing items
            for row in reversed(range(parent_item.rowCount())):
                child_item = parent_item.child(row, 0)
                folder_id = child_item.data(FOLDER_ID_ROLE)
                # Remove item that is not available
                if folder_id not in children_ids:
                    if folder_id in removed_folder_ids:
                        # Remove and destroy row
                        parent_item.removeRow(row)
                    else:
                        # Just take the row from parent without destroying
                        parent_item.takeRow(row)
                    continue

                # Remove folder id from `children_ids` set
                #   - is used as set for creation of "new items"
                children_ids.remove(folder_id)
                # Add existing children to queue
                folder_items_queue.append((folder_id, child_item))

            new_items = []
            for folder_id in children_ids:
                # Look for item in cache (maybe parent changed)
                item = self._items_by_folder_id.get(folder_id)
                # Create new item if was not found
                if item is None:
                    item = QtGui.QStandardItem()
                    item.setEditable(False)
                    item.setData(folder_id, FOLDER_ID_ROLE)
                    self._items_by_folder_id[folder_id] = item
                new_items.append(item)
                # Add item to queue
                folder_items_queue.append((folder_id, item))

            if new_items:
                parent_item.appendRows(new_items)

        # Remove cache of removed items
        for folder_id in removed_folder_ids:
            self._items_by_folder_id.pop(folder_id)
            if folder_id in self._items_with_color_by_id:
                self._items_with_color_by_id.pop(folder_id)

        # Refresh data
        # - all items refresh all data except id
        for folder_id, item in self._items_by_folder_id.items():
            folder = folders_by_id[folder_id]

            folder_name = folder["name"]
            if item.data(FOLDER_NAME_ROLE) != folder_name:
                item.setData(folder_name, FOLDER_NAME_ROLE)

            folder_data = folder.get("data") or {}
            folder_label = folder_data.get("label") or folder_name
            if item.data(FOLDER_LABEL_ROLE) != folder_label:
                item.setData(folder_label, QtCore.Qt.DisplayRole)
                item.setData(folder_label, FOLDER_LABEL_ROLE)

            icon_color = folder_data.get("color") or style.colors.default
            icon_name = folder_data.get("icon")
            if not icon_name:
                # Use default icons if no custom one is specified.
                # If it has children show a full folder, otherwise
                # show an open folder
                if item.rowCount() > 0:
                    icon_name = "folder"
                else:
                    icon_name = "folder-o"

            try:
                # font-awesome key
                full_icon_name = "fa.{0}".format(icon_name)
                icon = qtawesome.icon(full_icon_name, color=icon_color)
                item.setData(icon, QtCore.Qt.DecorationRole)

            except Exception:
                pass

    def _threaded_fetch(self):
        folders_data = self._fetch_folders_data()
        if not self._refreshing:
            return

        self._doc_payload = folders_data

        # Emit doc fetched only if was not stopped
        self._doc_fetched.emit()

    def _fetch_folders_data(self):
        if not self._context.project_name:
            return []

        project = get_project(self._context.project_name)
        if not project:
            return []

        # Get all folders sorted by name
        return get_project_folders(self._context.project_name)

    def _stop_fetch_thread(self):
        self._refreshing = False
        if self._doc_fetching_thread is not None:
            while self._doc_fetching_thread.isRunning():
                time.sleep(0.01)
            self._doc_fetching_thread = None


class FoldersWidget(QtWidgets.QWidget):
    """Base widget to display a tree of folders with filter.

    Folders have only one column and are sorted by name.

    Refreshing of folders happens in thread so calling 'refresh' method
    is not sequential. To capture moment when refreshing is finished listen
    to 'refreshed' signal.

    To capture selection changes listen to 'selection_changed' signal. It won't
    send any information about new selection as it may be different based on
    inheritance changes.

    Args:
        context (): Object holding context (can change).
        parent (QWidget): Parent Qt widget.
    """

    # on model refresh
    refresh_triggered = QtCore.Signal()
    refreshed = QtCore.Signal()
    # on view selection change
    selection_changed = QtCore.Signal()
    # It was double clicked on view
    double_clicked = QtCore.Signal()

    def __init__(self, context, parent=None):
        super(FoldersWidget, self).__init__(parent=parent)

        self.context = context

        # Tree View
        model = self._create_source_model()
        proxy = self._create_proxy_model(model)

        view = FoldersView(self)
        view.setModel(proxy)

        current_folder_icon = qtawesome.icon(
            "fa.arrow-down", color=style.colors.light
        )
        current_folder_btn = QtWidgets.QPushButton(self)
        current_folder_btn.setIcon(current_folder_icon)
        current_folder_btn.setToolTip("Go to Folder from current context")
        # Hide by default
        current_folder_btn.setVisible(False)

        refresh_icon = qtawesome.icon("fa.refresh", color=style.colors.light)
        refresh_btn = QtWidgets.QPushButton(self)
        refresh_btn.setIcon(refresh_icon)
        refresh_btn.setToolTip("Refresh items")

        filter_input = PlaceholderLineEdit(self)
        filter_input.setPlaceholderText("Filter folders..")

        # Header
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.addWidget(filter_input)
        header_layout.addWidget(current_folder_btn)
        header_layout.addWidget(refresh_btn)

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(header_layout)
        layout.addWidget(view)

        # Signals/Slots
        filter_input.textChanged.connect(self._on_filter_text_change)

        selection_model = view.selectionModel()
        selection_model.selectionChanged.connect(self._on_selection_change)
        refresh_btn.clicked.connect(self.refresh)
        current_folder_btn.clicked.connect(self._on_current_folder_click)
        view.doubleClicked.connect(self.double_clicked)

        self._refresh_btn = refresh_btn
        self._current_folder_btn = current_folder_btn
        self._model = model
        self._proxy = proxy
        self._view = view
        self._last_project_name = None

        self.model_selection = {}

    def _create_source_model(self):
        model = FoldersModel(parent=self)
        model.refreshed.connect(self._on_model_refresh)
        return model

    def _create_proxy_model(self, source_model):
        proxy = RecursiveSortFilterProxyModel()
        proxy.setSourceModel(source_model)
        proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        proxy.setSortCaseSensitivity(QtCore.Qt.CaseInsensitive)
        return proxy

    @property
    def refreshing(self):
        return self._model.refreshing

    def refresh(self):
        self._refresh_model()

    def stop_refresh(self):
        self._model.stop_refresh()

    def _get_current_context_folder_id(self):
        return self.context.folder_id

    def _on_current_folder_click(self):
        """Trigger change of folder to current context folder.
        This separation gives ability to override this method and use it
        in differnt way.
        """
        self.set_current_context_folder()

    def set_current_context_folder(self):
        folder_id = self._get_current_context_folder_id()
        if folder_id:
            self.select_folder_by_id(folder_id)

    def set_refresh_btn_visibility(self, visible=None):
        """Hide set refresh button.
        Some tools may have their global refresh button or do not support
        refresh at all.
        """
        if visible is None:
            visible = not self._refresh_btn.isVisible()
        self._refresh_btn.setVisible(visible)

    def set_current_folder_btn_visibility(self, visible=None):
        """Hide set current folder button.

        Not all tools support using of current context folder.
        """
        if visible is None:
            visible = not self._current_folder_btn.isVisible()
        self._current_folder_btn.setVisible(visible)

    def select_folder(self, folder_id):
        index = self._model.get_index_by_folder_id(folder_id)
        new_index = self._proxy.mapFromSource(index)
        self._select_indexes([new_index])

    def activate_flick_charm(self):
        self._view.activate_flick_charm()

    def deactivate_flick_charm(self):
        self._view.deactivate_flick_charm()

    def _on_selection_change(self):
        self.selection_changed.emit()

    def _on_filter_text_change(self, new_text):
        self._proxy.setFilterFixedString(new_text)

    def _on_model_refresh(self, has_item):
        """This method should be triggered on model refresh.

        Default implementation register this callback in '_create_source_model'
        so if you're modifying model keep in mind that this method should be
        called when refresh is done.
        """
        self._proxy.sort(0)
        self._set_loading_state(loading=False, empty=not has_item)
        self.refreshed.emit()

    def _refresh_model(self):
        # Store selection
        self._set_loading_state(loading=True, empty=True)

        # Trigger signal before refresh is called
        self.refresh_triggered.emit()
        # Refresh model
        self._model.refresh()

    def _set_loading_state(self, loading, empty):
        self._view.set_loading_state(loading, empty)

    def _clear_selection(self):
        selection_model = self._view.selectionModel()
        selection_model.clearSelection()

    def _select_indexes(self, indexes):
        valid_indexes = [
            index
            for index in indexes
            if index.isValid()
        ]
        if not valid_indexes:
            return

        selection_model = self._view.selectionModel()
        selection_model.clearSelection()

        mode = selection_model.Select | selection_model.Rows
        for index in valid_indexes:
            self._view.expand(self._proxy.parent(index))
            selection_model.select(index, mode)
        self._view.setCurrentIndex(valid_indexes[0])


class SingleSelectFoldersWidget(FoldersWidget):
    """Single selection folder widget.

    Contain single selection specific api methods.
    """
    def get_selected_folder_id(self):
        """Currently selected folder id."""
        selection_model = self._view.selectionModel()
        indexes = selection_model.selectedRows()
        for index in indexes:
            return index.data(FOLDER_ID_ROLE)
        return None


class MultiSelectFoldersWidget(FoldersWidget):
    """Multiselection folder widget.

    Main purpose is for loader and library loader. If another tool would use
    multiselection folders this widget should be split and loader's logic
    separated.
    """
    def __init__(self, *args, **kwargs):
        super(MultiSelectFoldersWidget, self).__init__(*args, **kwargs)
        self._view.setSelectionMode(QtWidgets.QTreeView.ExtendedSelection)

        delegate = UnderlinesFolderDelegate()
        self._view.setItemDelegate(delegate)
        self._delegate = delegate

    def get_selected_folder_ids(self):
        """Currently selected folder ids."""
        selection_model = self._view.selectionModel()
        indexes = selection_model.selectedRows()
        return [
            index.data(FOLDER_ID_ROLE)
            for index in indexes
        ]

    def select_folders(self, folder_ids):
        """Select folders by their ids.

        Args:
            folder_ids (list): List of folder ids.
        """
        indexes = self._model.get_indexes_by_folder_ids(folder_ids)
        new_indexes = [
            self._proxy.mapFromSource(index)
            for index in indexes
        ]
        self._select_indexes(new_indexes)

    def clear_underlines(self):
        """Clear underlines in folder items."""
        self._model.clear_underlines()

        self._view.updateGeometries()

    def set_underline_colors(self, colors_by_folder_id):
        """Change underline colors for passed fodlers.

        Args:
            colors_by_folder_id (dict): Key is folder id and value is list
                of underline colors.
        """
        self._model.set_underline_colors(colors_by_folder_id)
        # Trigger repaint
        self._view.updateGeometries()
