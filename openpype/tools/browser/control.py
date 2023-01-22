import copy
import logging
import collections
import time
from abc import ABCMeta, abstractmethod, abstractproperty
import six

from openpype.client import (
    get_projects,
    get_assets,
    get_subsets,
    get_versions,
    get_representations
)
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


class CacheItem:
    lifetime = 20

    def __init__(self, data, lifetime=None):
        self._data = data
        if lifetime is not None:
            self.lifetime = lifetime

        self._outdate_time = time.time() + self.lifetime

    @property
    def is_outdated(self):
        if not self.lifetime:
            return False
        return time.time() > self._outdate_time

    def set_lifetime(self, lifetime):
        self.lifetime = lifetime

    def set_outdated(self):
        self._outdate_time = 0

    def update_data(self, data):
        self._data = data
        self._outdate_time = time.time() + self.lifetime

    def get_data(self):
        return self._data

    @classmethod
    def create_outdated(cls):
        obj = cls(None)
        obj.set_outdated()
        return obj


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


class VersionItem:
    def __init__(
        self,
        version_id,
        subset_id,
        version,
        is_hero,
        published_time,
        author,
        frame_range,
        duration,
        handles,
        step,
        in_scene
    ):
        self.version_id = version_id
        self.subset_id = subset_id
        self.version = version
        self.is_hero = is_hero
        self.published_time = published_time
        self.author = author
        self.frame_range = frame_range
        self.duration = duration
        self.handles = handles
        self.step = step
        self.in_scene = in_scene

    def __eq__(self, other):
        if not isinstance(other, VersionItem):
            return False
        return (
            self.is_hero == other.is_hero
            and self.version == other.version
            and self.version_id == other.version_id
            and self.subset_id == other.subset_id
        )

    def __gt__(self, other):
        if not isinstance(other, VersionItem):
            return False
        if (
            other.version == self.version
            and self.is_hero
        ):
            return True
        return other.version < self.version

    def __ne__(self, other):
        return not self.__eq__(other)

    @classmethod
    def from_doc(cls, versions_doc):
        # Get the data from the version
        version_data = versions_doc["data"]
        is_hero = versions_doc["type"] == "hero_version"

        frame_range = None
        duration = None
        handles = None

        frame_start = version_data.get("frameStart")
        frame_end = version_data.get("frameEnd")
        handle_start = version_data.get("handleStart")
        handle_end = version_data.get("handleEnd")

        if frame_start is not None and frame_end is not None:
            # Remove superfluous zeros from numbers (3.0 -> 3) to improve
            # readability for most frame ranges
            frame_start = int(frame_start)
            frame_end = int(frame_end)
            frame_range = "{0}-{1}".format(frame_start, frame_end)
            duration = frame_end - frame_start + 1

        if handle_start is not None and handle_end is not None:
            handles = "{}-{}".format(int(handle_start), int(handle_end))

        return cls(
            str(versions_doc["_id"]),
            str(versions_doc["parent"]),
            versions_doc["name"],
            is_hero,
            version_data.get("time"),
            version_data.get("author"),
            frame_range,
            duration,
            handles,
            version_data.get("step"),
            None
        )


class SubsetItem:
    def __init__(
        self,
        subset_id,
        asset_id,
        asset_name,
        family,
        subset_name,
        group_name,
        versions
    ):
        versions.sort()
        self.subset_id = subset_id
        self.asset_id = asset_id
        self.asset_name = asset_name
        self.family = family
        self.subset_name = subset_name
        self.group_name = group_name
        self.versions = versions
        self._versions_by_id = None

    def get_version_by_id(self, version_id):
        if self._versions_by_id is None:
            self._versions_by_id = {
                version.version_id: version
                for version in self.versions
            }
        return self._versions_by_id.get(version_id)

    @staticmethod
    def extract_family(data):
        if not data:
            return None
        family = data.get("family")
        if family:
            return family
        families = data.get("families")
        if families:
            return families[0]
        return None

    @classmethod
    def from_docs(cls, subset_doc, version_docs, asset_name):
        family = cls.extract_family(subset_doc["data"])

        hero_version = None
        versions_by_id = {}
        for versions_doc in version_docs:
            versions_by_id[versions_doc["_id"]] = versions_doc
            if versions_doc["type"] == "hero_version":
                hero_version = versions_doc
            elif not family:
                family = cls.extract_family(versions_doc["data"])

        if hero_version:
            match_version = versions_by_id.get(hero_version["version_id"])
            if match_version:
                hero_version["name"] = match_version["name"]
                if "data" not in hero_version:
                    hero_version["data"] = copy.deepcopy(
                        match_version["data"]
                    )
            else:
                versions_by_id.pop(hero_version["_id"])
        versions = [
            VersionItem.from_doc(versions_doc)
            for versions_doc in versions_by_id.values()
        ]
        return cls(
            str(subset_doc["_id"]),
            str(subset_doc["parent"]),
            asset_name,
            family,
            subset_doc["name"],
            subset_doc["data"].get("group"),
            versions
        )


class RepreItem:
    def __init__(self, repre_id, version_id):
        self.repre_id = repre_id
        self.version_id = version_id

    @classmethod
    def from_doc(cls, repre_doc):
        return cls(
            str(repre_doc["_id"]),
            str(repre_doc["parent"]),
        )


class EntityModel:
    def __init__(self, controller):
        self._controller = controller
        self._projects = None
        self._hierarchy_items_by_project = collections.defaultdict(
            CacheItem.create_outdated
        )
        self._hierarchy_items_by_project[None].set_lifetime(0)

        self._subset_items_by_project = {None: {}}
        self._repre_items_by_project = {None: {}}

    def clear_cache(self):
        self._projects = None
        self._hierarchy_items_by_project = collections.defaultdict(
            CacheItem.create_outdated
        )
        self._hierarchy_items_by_project[None].set_lifetime(0)
        self._subset_items_by_project = {None: {}}
        self._repre_items_by_project = {None: {}}

    def _emit_event(self, topic, data=None):
        self._controller.event_system.emit(topic, data or {}, "model")

    def get_project_names(self):
        if self._projects is None:
            return None
        return set(self._projects)

    def get_hierarchy_items(self, project_name):
        data = self._hierarchy_items_by_project[project_name].get_data()
        if data is None:
            return None
        return dict(data)

    def get_subset_items(self, project_name, asset_ids):
        if not asset_ids:
            return {}

        asset_ids_cache = self._subset_items_by_project.get(project_name)
        if not asset_ids_cache:
            return {}
        output = {}
        for asset_id in asset_ids:
            data = asset_ids_cache[asset_id].get_data()
            if data:
                output.update(data)
        return output

    def get_repre_items(self, project_name, version_ids):
        output = {}
        if not version_ids:
            return output
        repre_ids_cache = self._repre_items_by_project.get(project_name)
        if repre_ids_cache is None:
            return output

        for version_id in version_ids:
            data = repre_ids_cache[version_id].get_data()
            if data:
                output.update(data)
        return output

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

        cache = self._hierarchy_items_by_project[project_name]
        if not cache.is_outdated:
            return

        hierarchy_items_by_id = {}
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

        cache.update_data(hierarchy_items_by_id)

    def refresh_hierarchy(self, project_name):
        self._emit_event("model.hierarchy.refresh.started")
        self._refresh_hierarchy(project_name)
        self._emit_event("model.hierarchy.refresh.finished")

    def _refresh_subsets(self, project_name, asset_ids):
        if project_name not in self._subset_items_by_project:
            self._subset_items_by_project[project_name] = (
                collections.defaultdict(CacheItem.create_outdated)
            )

        hierarchy_items_by_id = (
            self._hierarchy_items_by_project[project_name].get_data()
        )

        asset_ids_cache = self._subset_items_by_project[project_name]
        asset_ids_to_query = {
            asset_id
            for asset_id in asset_ids
            if asset_ids_cache[asset_id].is_outdated
        }

        subset_docs = []
        version_docs = []
        if asset_ids_to_query:
            subset_docs = list(get_subsets(
                project_name,
                asset_ids=asset_ids_to_query,
                fields=["_id", "parent", "name", "data.group"]
            ))

        subset_ids = [subset_doc["_id"] for subset_doc in subset_docs]
        if subset_ids:
            version_docs = list(get_versions(
                project_name,
                subset_ids=subset_ids,
                fields=["_id", "type", "parent", "name", "version_id", "data"]
            ))
        versions_by_subset_id = collections.defaultdict(list)
        for version_doc in version_docs:
            versions_by_subset_id[version_doc["parent"]].append(version_doc)

        subset_docs_by_asset_id = {
            asset_id: []
            for asset_id in asset_ids_to_query
        }
        for subset_doc in subset_docs:
            asset_id = str(subset_doc["parent"])
            subset_docs_by_asset_id[asset_id].append(subset_doc)

        for asset_id, subset_docs in subset_docs_by_asset_id.items():
            asset_item = hierarchy_items_by_id.get(asset_id)
            asset_name = None
            if asset_item:
                asset_name = asset_item.name

            asset_value = {}
            for subset_doc in subset_docs:
                version_docs = versions_by_subset_id[subset_doc["_id"]]
                item = SubsetItem.from_docs(
                    subset_doc, version_docs, asset_name)
                asset_value[item.subset_id] = item
            asset_ids_cache[asset_id].update_data(asset_value)

    def refresh_subsets(self, project_name, asset_ids):
        self._emit_event("model.subsets.refresh.started")
        self._refresh_subsets(project_name, asset_ids)
        # Add information about which project and asset ids did refresh
        self._emit_event("model.subsets.refresh.finished")

    def _refresh_representations(self, project_name, version_ids):
        if project_name not in self._repre_items_by_project:
            self._repre_items_by_project[project_name] = (
                collections.defaultdict(CacheItem.create_outdated)
            )

        version_ids_to_query = set()
        repre_cache = self._repre_items_by_project[project_name]
        for version_id in version_ids:
            if repre_cache[version_id].is_outdated:
                version_ids_to_query.add(version_id)

        if not version_ids_to_query:
            return

        repre_docs_by_version_id = {
            version_id: {}
            for version_id in version_ids_to_query
        }
        repre_docs = get_representations(
            project_name, version_ids=version_ids_to_query
        )
        for repre_doc in repre_docs:
            repre_item = RepreItem.from_doc(repre_doc)
            repre_docs_by_version_id[repre_item.version_id][repre_item.id] = {
                repre_item
            }

        for version_id, repre_items in repre_docs_by_version_id.items():
            repre_cache[version_id].update_data(repre_items)

    def refresh_representations(self, project_name, version_ids):
        self._emit_event("model.representations.refresh.started")
        self._refresh_representations(project_name, version_ids)
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
        self._selected_subsets = set(subset_ids)
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
        self._entity_model.refresh_subsets(
            self.get_selected_project(), event["asset_ids"]
        )

    def reset(self):
        self._emit_event("controller.reset.started")
        self._entity_model.clear_cache()
        self._entity_model.refresh_projects()
        self._emit_event("controller.reset.finished")

    def get_current_project(self):
        return None

    # Entity model wrappers
    def get_project_names(self):
        project_names = self._entity_model.get_project_names()
        if project_names is None:
            self._entity_model.refresh_projects()
            return self._entity_model.get_project_names()
        return project_names

    def get_hierarchy_items(self):
        project_name = self.get_selected_project()
        return self._entity_model.get_hierarchy_items(project_name)

    def get_subset_items(self):
        project_name = self.get_selected_project()
        asset_ids = self.get_selected_asset_ids()
        return self._entity_model.get_subset_items(project_name, asset_ids)

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
