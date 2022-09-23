import copy
import collections
import numbers
from abc import ABCMeta, abstractproperty, abstractmethod

import six

FIELD_VALUE = object()


def fields_to_dict(fields):
    if not fields:
        return None

    output = {}
    for field in fields:
        hierarchy = field.split(".")
        last = hierarchy.pop(-1)
        value = output
        for part in hierarchy:
            if value is FIELD_VALUE:
                break

            if part not in value:
                value[part] = {}
            value = value[part]

        if value is not FIELD_VALUE:
            value[last] = FIELD_VALUE
    return output


def project_graphql_query(fields):
    query = GraphQlQuery("ProjectQuery")
    project_name_var = query.add_variable("projectName", "String!")
    project_query = query.add_field("project")
    project_query.set_filter("name", project_name_var)

    nested_fields = fields_to_dict(fields)

    query_queue = collections.deque()
    for key, value in nested_fields.items():
        query_queue.append((key, value, project_query))

    while query_queue:
        item = query_queue.popleft()
        key, value, parent = item
        field = parent.add_field(key)
        if value is FIELD_VALUE:
            continue

        for k, v in value.items():
            query_queue.append((k, v, field))
    return query


def projects_graphql_query(fields):
    query = GraphQlQuery("ProjectsQuery")
    projects_query = query.add_field("projects", has_edges=True)

    nested_fields = fields_to_dict(fields)

    query_queue = collections.deque()
    for key, value in nested_fields.items():
        query_queue.append((key, value, projects_query))

    while query_queue:
        item = query_queue.popleft()
        key, value, parent = item
        field = parent.add_field(key)
        if value is FIELD_VALUE:
            continue

        for k, v in value.items():
            query_queue.append((k, v, field))
    return query


def folders_graphql_query(fields):
    query = GraphQlQuery("FoldersQuery")
    project_name_var = query.add_variable("projectName", "String!")
    folder_ids_var = query.add_variable("folderIds", "[String!]")
    parent_folder_ids_var = query.add_variable("parentFolderIds", "[String!]")
    folder_names_var = query.add_variable("folderNames", "[String!]")
    has_subsets_var = query.add_variable("folderHasSubsets", "Boolean!")

    project_query = query.add_field("project")
    project_query.set_filter("name", project_name_var)

    folders_query = project_query.add_field("folders", has_edges=True)
    folders_query.set_filter("ids", folder_ids_var)
    folders_query.set_filter("parentIds", parent_folder_ids_var)
    folders_query.set_filter("names", folder_names_var)
    folders_query.set_filter("hasSubsets", has_subsets_var)

    fields = set(fields)
    if "tasks" in fields:
        fields.remove("tasks")
        tasks_query = folders_query.add_field("tasks", has_edges=True)
        tasks_query.add_field("name")
        tasks_query.add_field("taskType")

    nested_fields = fields_to_dict(fields)

    query_queue = collections.deque()
    for key, value in nested_fields.items():
        query_queue.append((key, value, folders_query))

    while query_queue:
        item = query_queue.popleft()
        key, value, parent = item
        field = parent.add_field(key)
        if value is FIELD_VALUE:
            continue

        for k, v in value.items():
            query_queue.append((k, v, field))
    return query


def subsets_graphql_query(fields):
    query = GraphQlQuery("SubsetsQuery")

    project_name_var = query.add_variable("projectName", "String!")
    folder_ids_var = query.add_variable("folderIds", "[String!]")
    subset_ids_var = query.add_variable("subsetIds", "[String!]")
    subset_names_var = query.add_variable("subsetNames", "[String!]")

    project_query = query.add_field("project")
    project_query.set_filter("name", project_name_var)

    subsets_query = project_query.add_field("subsets", has_edges=True)
    subsets_query.set_filter("ids", subset_ids_var)
    subsets_query.set_filter("names", subset_names_var)
    subsets_query.set_filter("folderIds", folder_ids_var)

    nested_fields = fields_to_dict(set(fields))

    query_queue = collections.deque()
    for key, value in nested_fields.items():
        query_queue.append((key, value, subsets_query))

    while query_queue:
        item = query_queue.popleft()
        key, value, parent = item
        field = parent.add_field(key)
        if value is FIELD_VALUE:
            continue

        for k, v in value.items():
            query_queue.append((k, v, field))
    return query


def versions_graphql_query(fields):
    query = GraphQlQuery("VersionsQuery")

    project_name_var = query.add_variable("projectName", "String!")
    subset_ids_var = query.add_variable("subsetIds", "[String!]")
    version_ids_var = query.add_variable("versionIds", "[String!]")
    versions_var = query.add_variable("versions", "[Int]")
    hero_only_var = query.add_variable("heroOnly", "Boolean")
    latest_only_var = query.add_variable("latestOnly", "Boolean")
    hero_or_latest_only_var = query.add_variable(
        "heroOrLatestOnly", "Boolean"
    )

    project_query = query.add_field("project")
    project_query.set_filter("name", project_name_var)

    subsets_query = project_query.add_field("versions", has_edges=True)
    subsets_query.set_filter("ids", version_ids_var)
    subsets_query.set_filter("subsetIds", subset_ids_var)
    subsets_query.set_filter("versions", versions_var)
    subsets_query.set_filter("heroOnly", hero_only_var)
    subsets_query.set_filter("latestOnly", latest_only_var)
    subsets_query.set_filter("heroOrLatestOnly", hero_or_latest_only_var)

    nested_fields = fields_to_dict(set(fields))

    query_queue = collections.deque()
    for key, value in nested_fields.items():
        query_queue.append((key, value, subsets_query))

    while query_queue:
        item = query_queue.popleft()
        key, value, parent = item
        field = parent.add_field(key)
        if value is FIELD_VALUE:
            continue

        for k, v in value.items():
            query_queue.append((k, v, field))
    return query


def representations_graphql_query(fields):
    query = GraphQlQuery("RepresentationsQuery")

    project_name_var = query.add_variable("projectName", "String!")
    repre_ids_var = query.add_variable("representationIds", "[String!]")
    repre_names_var = query.add_variable("representationNames", "[String!]")
    version_ids_var = query.add_variable("versionIds", "[String!]")

    project_query = query.add_field("project")
    project_query.set_filter("name", project_name_var)

    repres_query = project_query.add_field("representations", has_edges=True)
    repres_query.set_filter("ids", repre_ids_var)
    repres_query.set_filter("versionIds", version_ids_var)
    repres_query.set_filter("representationNames", repre_names_var)

    nested_fields = fields_to_dict(set(fields))

    query_queue = collections.deque()
    for key, value in nested_fields.items():
        query_queue.append((key, value, repres_query))

    while query_queue:
        item = query_queue.popleft()
        key, value, parent = item
        field = parent.add_field(key)
        if value is FIELD_VALUE:
            continue

        for k, v in value.items():
            query_queue.append((k, v, field))
    return query


class QueryVariable(object):
    def __init__(self, variable_name):
        self._variable_name = variable_name
        self._name = "${}".format(variable_name)

    @property
    def name(self):
        return self._name

    @property
    def variable_name(self):
        return self._variable_name

    def __hash__(self):
        return self._name.__has__()

    def __str__(self):
        return self._name

    def __format__(self, *args, **kwargs):
        return self._name.__format__(*args, **kwargs)


class GraphQlQuery:
    """GraphQl query which can have fields to query.

    Single use object which can be used only for one query. Object and children
    objects keep track about paging and progress.

    Args:
        name (str): Name of query.
    """

    offset = 2

    def __init__(self, name):
        self._name = name
        self._variables = {}
        self._children = []

    @property
    def indent(self):
        """Indentation for preparation of query string.

        Returns:
            int: Ident spaces.
        """

        return 0

    @property
    def child_indent(self):
        """Indentation for preparation of query string used by children.

        Returns:
            int: Ident spaces for children.
        """

        return self.indent

    @property
    def need_query(self):
        """Still need query from server.

        Needed for edges which use pagination.

        Returns:
            bool: If still need query from server.
        """

        for child in self._children:
            if child.need_query:
                return True
        return False

    def add_variable(self, key, value_type, value=None):
        """Add variable to query.

        Args:
            key (str): Variable name.
            value_type (str): Type of expected value in variables. This is
                graphql type e.g. "[String!]", "Int", "Boolean", etc.
            value (Any): Default value for variable. Can be changed later.

        Returns:
            QueryVariable: Created variable object.

        Raises:
            KeyError: If variable was already added before.
        """

        if key in self._variables:
            raise KeyError(
                "Variable \"{}\" was already set with type {}.".format(
                    key, value_type
                )
            )

        variable = QueryVariable(key)
        self._variables[key] = {
            "type": value_type,
            "variable": variable,
            "value": value
        }
        return variable

    def get_variable(self, key):
        """Variable object.

        Args:
            key (str): Variable name added to headers.

        Returns:
            QueryVariable: Variable object used in query string.
        """

        return self._variables[key]["variable"]

    def get_variable_value(self, key, default=None):
        """Get Current value of variable.

        Args:
            key (str): Variable name.
            default (Any): Default value if variable is available.

        Returns:
            Any: Variable value.
        """

        variable_item = self._variables.get(key)
        if variable_item:
            return variable_item["value"]
        return default

    def set_variable_value(self, key, value):
        """Set value for variable.

        Args:
            key (str): Variable name under which the value is stored.
            value (Any): Variable value used in query. Variable is not used
                if value is 'None'.
        """

        self._variables[key]["value"] = value

    def get_variables_values(self):
        """Calculate variable values used that should be used in query.

        Variables with value set to 'None' are skipped.

        Returns:
            Dict[str, Any]: Variable values by their name.
        """

        output = {}
        for key, item in self._variables.items():
            value = item["value"]
            if value is not None:
                output[key] = item["value"]

        return output

    def add_obj_field(self, field):
        """Add field object to children.

        Args:
            field (BaseGraphQlQueryField): Add field to query children.
        """

        if field in self._children:
            return

        self._children.append(field)
        field.set_parent(self)

    def add_field(self, name, has_edges=None):
        """Add field to query.

        Args:
            name (str): Field name e.g. 'id'.
            has_edges (bool): Field has edges so it need paging.

        Returns:
            BaseGraphQlQueryField: Created field object.
        """

        if has_edges:
            item = GraphQlQueryEdgeField(name, self)
        else:
            item = GraphQlQueryField(name, self)
        self.add_obj_field(item)
        return item

    def calculate_query(self):
        """Calculate query string which is sent to server.

        Returns:
            str: GraphQl string with variables and headers.

        Raises:
            ValueError: Query has no fiels.
        """

        if not self._children:
            raise ValueError("Missing fields to query")

        variables = []
        for key, item in self._variables.items():
            if item["value"] is None:
                continue

            variables.append(
                "{}: {}".format(item["variable"], item["type"])
            )

        variables_str = ""
        if variables:
            variables_str = "({})".format(",".join(variables))
        header = "query {}{}".format(self._name, variables_str)

        output = []
        output.append(header + " {")
        for field in self._children:
            output.append(field.calculate_query())
        output.append("}")

        return "\n".join(output)

    def parse_result(self, data, output):
        """Parse data from response for output.

        Output is stored to passed 'output' variable. That's because of paging
        during which objects must have access to both new and previous values.

        Args:
            data (Dict[str, Any]): Data received using calculated query.
            output (Dict[str, Any]): Where parsed data are stored.
        """

        if not data:
            return

        for child in self._children:
            child.parse_result(data, output)

    def cleanup_result(self, output):
        """Remove temporary data from output.

        Some fields may require to store temporary data into output because of
        paging.

        Passed object is modified during processing.

        Args:
            output (Dict[str, Any]): Output which is result of all queries from
                all pages.
        """

        if not output:
            return

        for child in self._children:
            child.cleanup_result(output)

    def query(self, con):
        """Do a query from server.

        Args:
            con (ServerAPI): Connection to server with 'query' method.

        Returns:
            Dict[str, Any]: Parsed output from GraphQl query.
        """

        output = {}
        while self.need_query:
            response = con.query(
                self.calculate_query(),
                self.get_variables_values()
            )
            if response.errors:
                raise ValueError("QueryFailed {}".format(str(response.errors)))
            self.parse_result(response.data["data"], output)
        self.cleanup_result(output)

        return output


@six.add_metaclass(ABCMeta)
class BaseGraphQlQueryField(object):
    """Field in GraphQl query.

    Args:
        name (str): Name of field.
        parent (Union[BaseGraphQlQueryField, GraphQlQuery]): Parent object of a
            field.
        has_edges (bool): Field has edges and should handle paging.
    """

    def __init__(self, name, parent):
        if isinstance(parent, GraphQlQuery):
            query_item = parent
        else:
            query_item = parent.query_item

        self._name = name
        self._parent = parent

        self._filters = {}

        self._children = []
        # Value is changed on first parse of result
        self._need_query = True

        self._query_item = query_item

    @property
    def need_query(self):
        """Still need query from server.

        Needed for edges which use pagination. Look into children values too.

        Returns:
            bool: If still need query from server.
        """

        if self._need_query:
            return True

        for child in self._children:
            if child.need_query:
                return True
        return False

    @property
    def offset(self):
        return self._query_item.offset

    @property
    def indent(self):
        return self._parent.child_indent + self.offset

    @abstractproperty
    def child_indent(self):
        pass

    @property
    def query_item(self):
        return self._query_item

    @abstractproperty
    def has_edges(self):
        pass

    @property
    def child_has_edges(self):
        for child in self._children:
            if child.has_edges or child.child_has_edges:
                return True
        return False

    @property
    def path(self):
        """Field path for debugging purposes.

        Returns:
            str: Field path in query.
        """

        if isinstance(self._parent, GraphQlQuery):
            return self._name
        return "/".join((self._parent.path, self._name))

    def reset_cursor(self):
        for child in self._children:
            child.reset_cursor()

    def get_variable_value(self, *args, **kwargs):
        return self._query_item.get_variable_value(*args, **kwargs)

    def set_variable_value(self, *args, **kwargs):
        return self._query_item.set_variable_value(*args, **kwargs)

    def set_filter(self, key, value):
        self._filters[key] = value

    def has_filter(self, key):
        return key in self._filters

    def remove_filter(self, key):
        self._filters.pop(key, None)

    def set_parent(self, parent):
        if self._parent is parent:
            return
        self._parent = parent
        parent.add_obj_field(self)

    def add_obj_field(self, field):
        if field in self._children:
            return

        self._children.append(field)
        field.set_parent(self)

    def add_field(self, name, has_edges=None):
        if has_edges:
            item = GraphQlQueryEdgeField(name, self)
        else:
            item = GraphQlQueryField(name, self)
        self.add_obj_field(item)
        return item

    def _filter_value_to_str(self, value):
        if isinstance(value, QueryVariable):
            if self.get_variable_value(value.variable_name) is None:
                return None
            return str(value)

        if isinstance(value, numbers.Number):
            return str(value)

        if isinstance(value, six.string_types):
            return '"{}"'.format(value)

        if isinstance(value, (list, set, tuple)):
            return "[{}]".format(
                ", ".join(
                    self._filter_value_to_str(item)
                    for item in iter(value)
                )
            )
        raise TypeError(
            "Unknown type to convert '{}'".format(str(type(value)))
        )

    def get_filters(self):
        """Receive filters for item.

        By default just use copy of set filters.

        Returns:
            Dict[str, Any]: Fields filters.
        """

        return copy.deepcopy(self._filters)

    def _filters_to_string(self):
        filters = self.get_filters()
        if not filters:
            return ""

        filter_items = []
        for key, value in filters.items():
            string_value = self._filter_value_to_str(value)
            if string_value is None:
                continue

            filter_items.append("{}: {}".format(key, string_value))

        if not filter_items:
            return ""
        return "({})".format(", ".join(filter_items))

    def _fake_children_parse(self):
        """Mark children as they don't need query."""

        for child in self._children:
            child.parse_result({}, {})

    @abstractmethod
    def calculate_query(self):
        pass

    @abstractmethod
    def parse_result(self, data, output):
        pass

    def cleanup_result(self, data):
        if not isinstance(data, dict):
            raise TypeError("{} Expected 'dict' type got '{}'".format(
                self._name, str(type(data))
            ))

        value = data.get(self._name)
        if not value:
            return

        if isinstance(value, dict):
            for child in self._children:
                child.cleanup_result(value)
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                for child in self._children:
                    child.cleanup_result(item)


class GraphQlQueryField(BaseGraphQlQueryField):
    has_edges = False

    @property
    def child_indent(self):
        return self.indent

    def parse_result(self, data, output):
        if not isinstance(data, dict):
            raise TypeError("{} Expected 'dict' type got '{}'".format(
                self._name, str(type(data))
            ))

        self._need_query = False
        value = data.get(self._name)
        if value is None:
            self._fake_children_parse()
            if self._name in data:
                output[self._name] = None
            return

        if not self._children:
            output[self._name] = value
            return

        output_value = output.get(self._name)
        if isinstance(value, dict):
            if output_value is None:
                output_value = {}
                output[self._name] = output_value

            for child in self._children:
                child.parse_result(value, output_value)
            return

        if output_value is None:
            output_value = []
            output[self._name] = output_value

        if not value:
            self._fake_children_parse()
            return

        diff = len(value) - len(output_value)
        if diff > 0:
            for _ in range(diff):
                output_value.append({})

        for idx, item in enumerate(value):
            item_value = output_value[idx]
            for child in self._children:
                child.parse_result(item, item_value)

    def calculate_query(self):
        offset = self.indent * " "
        header = "{}{}{}".format(
            offset,
            self._name,
            self._filters_to_string()
        )
        if not self._children:
            return header

        output = []
        output.append(header + " {")

        output.extend([
            field.calculate_query()
            for field in self._children
        ])
        output.append(offset + "}")

        return "\n".join(output)


class GraphQlQueryEdgeField(BaseGraphQlQueryField):
    has_edges = True

    def __init__(self, *args, **kwargs):
        super(GraphQlQueryEdgeField, self).__init__(*args, **kwargs)
        self._cursor = None

    @property
    def child_indent(self):
        offset = self.offset * 2
        return self.indent + offset

    def reset_cursor(self):
        # Reset cursor only for edges
        self._cursor = None
        self._need_query = True

        super(GraphQlQueryEdgeField, self).reset_cursor()

    def parse_result(self, data, output):
        if not isinstance(data, dict):
            raise TypeError("{} Expected 'dict' type got '{}'".format(
                self._name, str(type(data))
            ))

        if self._name in output:
            node_values = output[self._name]
        else:
            node_values = []
            output[self._name] = node_values

        handle_cursors = self.child_has_edges
        if handle_cursors:
            cursor_key = self._get_cursor_key()
            if cursor_key in output:
                nodes_by_cursor = output[cursor_key]
            else:
                nodes_by_cursor = {}
                output[cursor_key] = nodes_by_cursor

        value = data.get(self._name)
        if value is None:
            self._need_query = False
            return

        page_info = value["pageInfo"]
        new_cursor = page_info["endCursor"]
        self._need_query = page_info["hasNextPage"]
        edges = value["edges"]
        # Fake result parse
        if not edges:
            self._fake_children_parse()

        for edge in edges:
            if not handle_cursors:
                edge_value = {}
                node_values.append(edge_value)
            else:
                edge_cursor = edge["cursor"]
                edge_value = nodes_by_cursor.get(edge_cursor)
                if edge_value is None:
                    edge_value = {}
                    nodes_by_cursor[edge_cursor] = edge_value
                    node_values.append(edge_value)

            for child in self._children:
                child.parse_result(edge["node"], edge_value)

        if not self._need_query:
            return

        change_cursor = True
        for child in self._children:
            if child.need_query:
                change_cursor = False

        if change_cursor:
            for child in self._children:
                child.reset_cursor()
            self._cursor = new_cursor

    def cleanup_result(self, data):
        super(GraphQlQueryEdgeField, self).cleanup_result(data)
        if self.child_has_edges:
            cursor_key = self._get_cursor_key()
            data.pop(cursor_key)

    def _get_cursor_key(self):
        return "__cursor__{}".format(self._name)

    def get_filters(self):
        filters = super(GraphQlQueryEdgeField, self).get_filters()

        filters["first"] = 300
        if self._cursor:
            filters["after"] = self._cursor
        return filters

    def calculate_query(self):
        if not self._children:
            raise ValueError("Missing child definitions for edges {}".format(
                self.path
            ))

        offset = self.indent * " "
        header = "{}{}{}".format(
            offset,
            self._name,
            self._filters_to_string()
        )

        output = []
        output.append(header + " {")

        edges_offset = offset + self.offset * " "
        node_offset = edges_offset + self.offset * " "
        output.append(edges_offset + "edges {")
        output.append(node_offset + "node {")

        for field in self._children:
            output.append(
                field.calculate_query()
            )

        output.append(node_offset + "}")
        if self.child_has_edges:
            output.append(node_offset + "cursor")
        output.append(edges_offset + "}")

        # Add page information
        output.append(edges_offset + "pageInfo {")
        for page_key in (
            "endCursor",
            "hasNextPage",
        ):
            output.append(node_offset + page_key)
        output.append(edges_offset + "}")
        output.append(offset + "}")

        return "\n".join(output)
