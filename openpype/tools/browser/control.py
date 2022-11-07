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
    def __init__(self, item_id, parent_id, name, label):
        self.id = item_id
        self.name = name
        self.label = label or name
        self.parent_id = parent_id

    @classmethod
    def from_asset_doc(cls, asset_doc):
        asset_data = asset_doc.get("data") or {}
        label = asset_data.get("label")
        parent_id = asset_data["visualParent"]
        if parent_id is not None:
            parent_id = str(parent_id)

        return cls(
            str(asset_doc["_id"]),
            parent_id,
            asset_doc["name"],
            label,
        )


class EntityModel:
    def __init__(self, controller):
        self._controller = controller
        self._projects = set()
        self._hierarchy_items = {}
        self._subsets = {}
        self._versions = {}
        self._representation = {}

        controller.event_system.add_callback(
            "selection.project.changed",
            self._on_project_change
        )
        controller.event_system.add_callback(
            "selection.assets.changed",
            self._on_project_change
        )

    def refresh(self):
        self._projects = set()
        self._hierarchy_items = {}
        self._subsets = {}
        self._versions = {}
        self._representations = {}
        self.refresh_projects()
        self.refresh_hierarchy()
        self.refresh_versions()

    def _emit_event(self, topic, data=None):
        self._controller.event_system.emit(topic, data or {}, "model")

    def get_project_names(self):
        return set(self._projects)

    def get_hierarchy_items(self):
        return list(self._hierarchy_items.values())

    def refresh_projects(self):
        self._emit_event("model.projects.refresh.started")

        self._projects = {
            project["name"]
            for project in get_projects(fields=["name"])
        }
        self._emit_event("model.projects.refresh.finished")

    def refresh_hierarchy(self, project_name=-1):
        self._emit_event("model.hierarchy.refresh.started")
        items = {}
        if project_name == -1:
            project_name = self._controller.get_selected_project()
        if project_name:
            for asset_doc in get_assets(project_name):
                item = HierarchyItem.from_asset_doc(asset_doc)
                items[item.id] = item
        self._hierarchy_items = items

        self._emit_event("model.hierarchy.refresh.finished")

    def refresh_subsets(self):
        self._emit_event("model.subsets.refresh.started")
        self._emit_event("model.subsets.refresh.finished")

    def refresh_versions(self):
        self._emit_event("model.versions.refresh.started")
        self._emit_event("model.versions.refresh.finished")

    def refresh_representations(self):
        self._emit_event("model.representations.refresh.started")
        self._emit_event("model.representations.refresh.finished")

    def _on_project_change(self, event):
        self._hierarchy_items = {}
        self._subsets = {}
        self._versions = {}
        self._representations = {}
        self._emit_event("model.hierarchy.cleared")
        self._emit_event("model.subsets.cleared")
        self._emit_event("model.versions.cleared")
        self._emit_event("model.representations.cleared")
        self.refresh_hierarchy(event["new"])
        self.refresh_subsets()
        self.refresh_versions()


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

        old_value = self._selected_project
        self._selected_project = project_name
        self._emit_event(
            "selection.project.changed",
            {"old": old_value, "new": project_name}
        )

    def set_selected_assets(self, asset_ids):
        if self._selected_assets == asset_ids:
            return

        old_value = self._selected_assets
        self._selected_assets = set(asset_ids)
        self._emit_event(
            "selection.assets.changed",
            {
                "old": old_value,
                "new": set(asset_ids),
                "project_name": self._selected_project
            }
        )

    def set_selected_versions(self, subset_ids, version_ids):
        if self._selected_versions == version_ids:
            return

        old_value = self._selected_subsets
        self._emit_event(
            "selection.subsets.changed",
            {"old": old_value, "new": set(subset_ids)}
        )
        old_value = self._selected_versions
        self._selected_versions = set(version_ids)
        self._emit_event(
            "selection.versions.changed",
            {"old": old_value, "new": set(version_ids)}
        )


class BaseController(AbstractController):
    def __init__(self):
        self._event_system = None
        self._log = None

    @property
    def log(self):
        if self._log is None:
            self._log = logging.getLogger(self.__class__.__name__)
        return self._log

    def _emit_event(self, topic, data=None):
        self.event_system.emit(topic, data or {}, "controller")

    @property
    def event_system(self):
        """Inner event system for publisher controller.

        Is used for communication with UI. Event system is autocreated.
        """

        if self._event_system is None:
            self._event_system = EventSystem()
        return self._event_system


class BrowserController(BaseController):
    def __init__(self):
        super().__init__()
        self._selection_model = SelectionModel(self)
        self._entity_model = EntityModel(self)

    def reset(self):
        self._emit_event("controller.reset.started")
        self._entity_model.refresh()
        self._emit_event("controller.reset.finished")

    def get_current_project(self):
        return None

    # Entity model wrappers
    def get_project_names(self):
        return self._entity_model.get_project_names()

    def get_hierarchy_items(self):
        return self._entity_model.get_hierarchy_items()

    # Selection model wrappers
    def get_selected_project(self):
        return self._selection_model.get_selected_project()

    def set_selected_project(self, project_name):
        self._selection_model.set_selected_project(project_name)
