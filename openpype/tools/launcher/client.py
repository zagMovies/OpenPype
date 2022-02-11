import os
import json
import logging
import collections
from http import HTTPStatus
import requests


class MissingEntityError(Exception):
    pass


class ProjectNotFound(MissingEntityError):
    def __init__(self, project_name, message=None):
        if not message:
            message = "Project \"{}\" was not found".format(project_name)
        self.project_name = project_name
        super(ProjectNotFound, self).__init__(message)


class FolderNotFound(MissingEntityError):
    def __init__(self, project_name, folder_id, message=None):
        self.project_name = project_name
        self.folder_id = folder_id
        if not message:
            message = (
                "Folder with id \"{}\" was not found in project \"{}\""
            ).format(folder_id, project_name)
        super(FolderNotFound, self).__init__(message)


class RestApiResponse():
    """API Response."""
    def __init__(self, status=200, **data):
        self.status = status
        self.data = data

    @property
    def detail(self):
        return self.get("detail", HTTPStatus(self.status).description)

    def __repr__(self):
        return "<{}: {} ({})>".format(
            self.__class__.__name__, self.status, self.detail
        )

    def __len__(self):
        return 200 <= self.status < 400

    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)


class GraphQlResponse:
    def __init__(self, data):
        self.data = data
        self.errors = data.get("errors")

    def __len__(self):
        if self.errors:
            return 0
        return 1

    def __repr__(self):
        if self.errors:
            return "<{} errors={}>".format(
                self.__class__.__name__, self.errors[0]['message']
            )
        return "<{}>".format(self.__class__.__name__)


def store_token(token):
    filepath = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "token"
    )
    with open(filepath, "w") as stream:
        stream.write(token)


def load_token():
    filepath = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "token"
    )
    if os.path.exists(filepath):
        with open(filepath, "r") as stream:
            token = stream.read()
        return str(token)
    return ""




class API(object):
    """
    Args:
        base_url(str): Example: http://localhost:5000
    """
    def __init__(self, base_url):
        base_url = base_url.rstrip("/")
        self._base_url = base_url
        self._rest_url = "{}/api".format(base_url)
        self._graphl_url = "{}/graphql".format(base_url)
        self._log = None
        self._access_token = None

    @property
    def log(self):
        if self._log is None:
            self._log = logging.getLogger(self.__class__.__name__)
        return self._log

    @property
    def headers(self):
        headers = {"Content-Type": "application/json"}
        if self._access_token:
            headers["Authorization"] = "Bearer {}".format(self._access_token)
        return headers

    def login(self, name, password):
        token = load_token()
        if token:
            self._access_token = token
            response = self.get("users/me")
            if response.status == 200:
                return
            store_token("")

        response = self._do_rest_request(
            requests.get,
            self._rest_url,
            headers=self.headers
        )
        response = self.post(
            "auth/login",
            name=name,
            password=password
        )
        if response:
            self._access_token = response["token"]
            store_token(self._access_token)

    def logout(self):
        if self._access_token:
            return self.post("auth/logout")

    def query(self, query, **kwargs):
        data = {"query": query, "variables": kwargs}
        response = requests.post(
            self._graphl_url, json=data, headers=self.headers
        )
        return GraphQlResponse(response.json())

    def _do_rest_request(self, function, url, **kwargs):
        try:
            response = function(url, **kwargs)
        except ConnectionRefusedError:
            response = RestApiResponse(
                500,
                detail="Unable to connect the server. Connection refused"
            )
        except requests.exceptions.ConnectionError:
            response = RestApiResponse(
                500,
                detail="Unable to connect the server. Connection error"
            )
        else:
            if response.text == "":
                data = None
                response = RestApiResponse(response.status_code)
            else:
                try:
                    data = response.json()
                except (
                    json.JSONDecodeError
                ):
                    response = RestApiResponse(
                        500,
                        detail="The response is not a JSON: {}".format(
                            response.text
                        )
                    )
                else:
                    response = RestApiResponse(response.status_code, **data)
        self.log.debug("Response {}".format(str(response)))
        return response

    def post(self, entrypoint, **kwargs):
        entrypoint = entrypoint.lstrip("/").rstrip("/")
        self.log.debug("Executing [POST] {}".format(entrypoint))
        url = "{}/{}".format(self._rest_url, entrypoint)
        return self._do_rest_request(
            requests.post,
            url,
            json=kwargs,
            headers=self.headers
        )

    def put(self, entrypoint, **kwargs):
        entrypoint = entrypoint.lstrip("/").rstrip("/")
        self.log.debug("Executing [PUT] {}".format(entrypoint))
        url = "{}/{}".format(self._rest_url, entrypoint)
        return self._do_rest_request(
            requests.put,
            url,
            json=kwargs,
            headers=self.headers
        )

    def patch(self, entrypoint, **kwargs):
        entrypoint = entrypoint.lstrip("/").rstrip("/")
        self.log.debug("Executing [PATCH] {}".format(entrypoint))
        url = "{}/{}".format(self._rest_url, entrypoint)
        return self._do_rest_request(
            requests.patch,
            url,
            json=kwargs,
            headers=self.headers
        )

    def get(self, entrypoint, **kwargs):
        entrypoint = entrypoint.lstrip("/").rstrip("/")
        self.log.debug("Executing [GET] {}".format(entrypoint))
        url = "{}/{}".format(self._rest_url, entrypoint)
        return self._do_rest_request(
            requests.get,
            url,
            params=kwargs,
            headers=self.headers
        )

    def delete(self, entrypoint, **kwargs):
        entrypoint = entrypoint.lstrip("/").rstrip("/")
        self.log.debug("Executing [DELETE] {}".format(entrypoint))
        url = "{}/{}".format(self._rest_url, entrypoint)
        return self._do_rest_request(
            requests.delete,
            url,
            params=kwargs,
            headers=self.headers
        )


class GlobalContext:
    _connection = None

    @classmethod
    def get_connection(cls):
        if cls._connection is None:
            con = API(url)
            con.login(username, password)
            cls._connection = con
        return cls._connection


def get_projects_basic():
    projects_query = """
    query ProjectsBasic {
        projects {
            edges { node {
                name
                active
                library
            }}
        }
    }
    """
    con = GlobalContext.get_connection()
    data = con.query(projects_query).data
    return data["data"]["projects"]["edges"]


def get_project_names():
    con = GlobalContext.get_connection()
    response = con.get("projects")
    # TODO check status
    response.status
    data = response.data
    project_names = []
    if data:
        for project in data["projects"]:
            project_names.append(project["name"])
    return project_names


def get_project(project_name):
    con = GlobalContext.get_connection()
    output = con.get("projects/{}".format(project_name)).data
    if output.get("code") == 404:
        return None
    return output


def get_project_folders(project_name):
    structure_query = """
    query ProjectFolders($projectName: String!) {
        project(name: $projectName) {
            folders { edges { node {
                name
                active
                id
                folderType
                parentId
                parents
            }}}
        }
    }
    """
    con = GlobalContext.get_connection()
    result_data = con.query(structure_query, projectName=project_name).data
    folders = []
    project_data = result_data["data"]["project"]
    if project_data is None:
        return folders

    hierarchy_queue = collections.deque()
    hierarchy_queue.append(project_data)
    while hierarchy_queue:
        folder = hierarchy_queue.popleft()
        if "folders" in folder:
            for edge in folder.pop("folders")["edges"]:
                hierarchy_queue.append(edge["node"])

        if folder:
            folders.append(folder)
    return folders


def get_project_tasks(project_name):
    structure_query = """
    query ProjectTasks($projectName: String!) {
        project(name: $projectName) {
            tasks { edges { node {
                active
                id
                name
                taskType
                folderId
            }}}
        }
    }
    """
    con = GlobalContext.get_connection()
    result_data = con.query(structure_query, projectName=project_name).data
    tasks = []
    project_data = result_data["data"]["project"]
    if project_data is None:
        return tasks

    hierarchy_queue = collections.deque()
    hierarchy_queue.append(project_data)
    while hierarchy_queue:
        task = hierarchy_queue.popleft()
        if "tasks" in task:
            for edge in task.pop("tasks")["edges"]:
                hierarchy_queue.append(edge["node"])

        if tasks:
            tasks.append(task)
    return tasks


def get_tasks_by_folder_id(project_name, folder_id):
    con = GlobalContext.get_connection()
    tasks_query = """
    query Project($projectName: String!, $folderId: String!) {
        project(name: $projectName) {
            folder(id: $folderId) {
                tasks { edges { node {
                    active
                    id
                    name
                    taskType
                    folderId
                }}}
            }
        }
    }
    """
    response = con.query(
        tasks_query, projectName=project_name, folderId=folder_id
    )
    result_data = response.data
    tasks = []
    project_data = result_data["data"]["project"]
    if project_data is None:
        raise ProjectNotFound(project_name)

    folder_data = result_data["data"]["project"]["folder"]
    if folder_data is None:
        raise FolderNotFound(project_name, folder_id)

    for edge in folder_data["tasks"]["edges"]:
        tasks.append(edge["node"])
    return tasks

