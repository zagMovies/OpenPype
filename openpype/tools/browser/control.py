import logging
import collections
from abc import ABCMeta, abstractmethod, abstractproperty
import six

from openpype.client import get_projects, get_assets
from openpype.lib.events import EventSystem


@six.add_metaclass(ABCMeta)
class AbstractController:
    @abstractproperty
    def event_system(self):
        pass

    @abstractmethod
    def get_current_project(self):
        pass

    @abstractmethod
    def reset(self):
        pass

    # Model wrapper calls
    @abstractmethod
    def get_project_names(self):
        pass

    # Selection model wrapper calls
    @abstractmethod
    def get_selected_project(self):
        pass

    @abstractmethod
    def set_selected_project(self, project_name):
        pass


class HierarchyItem:
    def __init__(
        self,
        entity_id,
        name,
        icon_name,
        icon_color,
        parent_id,
        label,
        has_children
    ):
        self.id = entity_id
        self.name = name
        self.label = label or name
        self.icon_name = icon_name
        self.icon_color = icon_color
        self.parent_id = parent_id
        self.has_children = has_children

    @classmethod
    def from_doc(cls, asset_doc, has_children=True):
        parent_id = asset_doc["data"].get("visualParent")
        if parent_id is not None:
            parent_id = str(parent_id)
        return cls(
            str(asset_doc["_id"]),
            asset_doc["name"],
            asset_doc["data"].get("icon"),
            asset_doc["data"].get("color"),
            parent_id,
            asset_doc["data"].get("label"),
            has_children,
        )


class EntityModel:
    def __init__(self, controller):
        self._controller = controller
        self._projects = set()
        self._hierarchy_items_by_project = {None: {}}
        self._version_items_by_project = {None: {}}
        self._repre_items_by_project = {None: {}}

    def clear_cache(self):
        self._projects = set()
        self._hierarchy_items_by_project = {None: {}}
        self._version_items_by_project = {None: {}}
        self._repre_items_by_project = {None: {}}

    def _emit_event(self, topic, data=None):
        self._controller.event_system.emit(topic, data or {}, "model")

    def get_project_names(self):
        return set(self._projects)

    def get_hierarchy_items(self, project_name):
        if project_name not in self._hierarchy_items_by_project:
            self.refresh_hierarchy(project_name)
        return dict(self._hierarchy_items_by_project[project_name])

    def refresh_projects(self):
        self._emit_event("model.projects.refresh.started")

        self._projects = {
            project["name"]
            for project in get_projects(fields=["name"])
        }
        self._emit_event("model.projects.refresh.finished")

    def _refresh_hierarchy(self, project_name):
        if not project_name:
            return
        hierarchy_items_by_id = {}
        self._hierarchy_items_by_project[project_name] = hierarchy_items_by_id

        asset_docs_by_parent_id = collections.defaultdict(list)
        for asset_doc in get_assets(project_name):
            parent_id = asset_doc["data"].get("visualParent")
            asset_docs_by_parent_id[parent_id].append(asset_doc)

        hierarchy_queue = collections.deque()
        for asset_doc in asset_docs_by_parent_id[None]:
            hierarchy_queue.append(asset_doc)

        while hierarchy_queue:
            asset_doc = hierarchy_queue.popleft()
            children = asset_docs_by_parent_id[asset_doc["_id"]]
            hierarchy_item = HierarchyItem.from_doc(
                asset_doc, len(children) > 0)
            hierarchy_items_by_id[hierarchy_item.id] = hierarchy_item
            for child in children:
                hierarchy_queue.append(child)

    def refresh_hierarchy(self, project_name):
        self._emit_event("model.hierarchy.refresh.started")
        self._refresh_hierarchy(project_name)
        self._emit_event("model.hierarchy.refresh.finished")

    def _refresh_versions(self, project_name, asset_ids):
        pass

    def refresh_versions(self, project_name, asset_ids):
        self._emit_event("model.versions.refresh.started")
        self._refresh_versions(project_name, asset_ids)
        self._emit_event("model.versions.refresh.finished")

    def refresh_representations(self, project_name, asset_ids, version_ids):
        self._emit_event("model.representations.refresh.started")
        self._emit_event("model.representations.refresh.finished")


class SelectionModel:
    def __init__(self, controller):
        self._controller = controller
        self._selected_project = None
        self._selected_assets = set()
        self._selected_subsets = set()
        self._selected_versions = set()

    def _emit_event(self, topic, data=None):
        self._controller.event_system.emit(
            topic, data or {}, "selection_model")

    def get_selected_project(self):
        return self._selected_project

    def get_selected_asset_ids(self):
        return set(self._selected_assets)

    def get_selected_subset_ids(self):
        return set(self._selected_subsets)

    def get_selected_version_ids(self):
        return set(self._selected_versions)

    def set_selected_project(self, project_name):
        if self._selected_project == project_name:
            return

        self._selected_project = project_name
        self._emit_event(
            "selection.project.changed",
            {"project_name": project_name}
        )

    def set_selected_asset_ids(self, asset_ids):
        if self._selected_assets == asset_ids:
            return

        self._selected_assets = set(asset_ids)
        self._emit_event(
            "selection.assets.changed",
            {"asset_ids": set(asset_ids)}
        )

    def set_selected_versions(self, subset_ids, version_ids):
        if self._selected_versions == version_ids:
            return

        self._selected_versions = set(version_ids)
        self._emit_event(
            "selection.subsets.changed",
            {"subset_ids": set(subset_ids), "version_ids": set(version_ids)}
        )


class BaseController(AbstractController):
    def __init__(self):
        self._event_system = self._create_event_system()
        self._log = None

    @property
    def log(self):
        if self._log is None:
            self._log = logging.getLogger(self.__class__.__name__)
        return self._log

    def _create_event_system(self):
        return EventSystem()

    def _emit_event(self, topic, data=None):
        self.event_system.emit(topic, data or {}, "controller")

    @property
    def event_system(self):
        """Inner event system for publisher controller."""

        return self._event_system


class BrowserController(BaseController):
    def __init__(self):
        super().__init__()
        self._selection_model = SelectionModel(self)
        self._entity_model = EntityModel(self)

        self.event_system.add_callback(
            "selection.project.changed",
            self._on_project_change
        )
        self.event_system.add_callback(
            "selection.assets.changed",
            self._on_assets_change
        )

    def _on_project_change(self, event):
        self._entity_model.refresh_hierarchy(event["project_name"])

    def _on_assets_change(self, event):
        print(event.data)

    def reset(self):
        self._emit_event("controller.reset.started")
        self._entity_model.clear_cache()
        self._entity_model.refresh_projects()
        self._emit_event("controller.reset.finished")

    def get_current_project(self):
        return None

    # Entity model wrappers
    def get_project_names(self):
        return self._entity_model.get_project_names()

    def get_hierarchy_items(self):
        project_name = self.get_selected_project()
        return self._entity_model.get_hierarchy_items(project_name)

    # Selection model wrappers
    def get_selected_project(self):
        return self._selection_model.get_selected_project()

    def set_selected_project(self, project_name):
        self._selection_model.set_selected_project(project_name)

    # Selection model wrappers
    def get_selected_asset_ids(self):
        return self._selection_model.get_selected_asset_ids()

    def set_selected_asset_ids(self, asset_ids):
        self._selection_model.set_selected_asset_ids(asset_ids)
