import logging
from typing import Any, Dict, List, Optional

import requests

from session import SessionData


logger = logging.getLogger(__name__)


class ContentClient:
    def __init__(self, base_url: str, session_data: SessionData):
        self.base_url = base_url
        self.headers = session_data.headers
        self.cookies = session_data.cookies
        self.session = session_data.session

    def get_folder_items(self, folder_id: str) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/content/{folder_id}/items?fields=*"
        response = self.session.get(url, headers=self.headers, cookies=self.cookies, verify=self.session.verify)
        response.raise_for_status()
        return response.json().get("content", [])

    def find_folder_id(self, parent_id: str, folder_name: str) -> Optional[str]:
        items = self.get_folder_items(parent_id)
        for item in items:
            if item.get("type") == "folder" and item.get("defaultName") == folder_name:
                return item["id"]
        return None

    def get_object_spec(self, obj_id: str, obj_type: str):
        if obj_type == "module":
            url = f"{self.base_url}/modules/{obj_id}"
        else:
            url = f"{self.base_url}/content/{obj_id}?fields=specification"
        response = self.session.get(url, headers=self.headers, cookies=self.cookies, verify=self.session.verify)
        response.raise_for_status()
        data = response.json()
        if obj_type == "module":
            return data
        spec = data.get("fields", {}).get("specification")
        if spec is None:
            raise ValueError("Specification not found in response")
        return spec

    def get_object_description(self, obj_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/content/{obj_id}?fields=description"
        response = self.session.get(url, headers=self.headers, cookies=self.cookies, verify=self.session.verify)
        response.raise_for_status()
        return response.json()

    def get_content(self, obj_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/content/{obj_id}?fields=*"
        response = self.session.get(url, headers=self.headers, cookies=self.cookies, verify=self.session.verify)
        response.raise_for_status()
        return response.json()

    def copy_object(self, source_id: str, dest_id: str, recursive: bool = True) -> str:
        url = f"{self.base_url}/content/copy"
        payload = {"source_id": source_id, "destination_id": dest_id, "recursive": recursive}
        response = self.session.post(url, json=payload, headers=self.headers, cookies=self.cookies, verify=self.session.verify)
        response.raise_for_status()
        new_obj = response.json()
        logger.info(f"Object {source_id} copied to {dest_id}, new ID: {new_obj['id']}")
        return new_obj["id"]

    def update_object(self, obj_id: str, data: Dict[str, Any]) -> None:
        url = f"{self.base_url}/content/{obj_id}"
        response = self.session.put(url, json=data, headers=self.headers, cookies=self.cookies, verify=self.session.verify)
        response.raise_for_status()
        logger.info(f"Object {obj_id} updated")

    def update_module_spec(self, obj_id: str, spec: Dict[str, Any]) -> None:
        url = f"{self.base_url}/modules/{obj_id}"
        response = self.session.put(url, json=spec, headers=self.headers, cookies=self.cookies, verify=self.session.verify)
        response.raise_for_status()
        logger.info(f"Module spec {obj_id} updated")

    def create_module(self, folder_id: str, data: Dict[str, Any]) -> str:
        url = f"{self.base_url}/modules?location={folder_id}"
        response = self.session.post(url, json=data, headers=self.headers, cookies=self.cookies, verify=self.session.verify)
        response.raise_for_status()
        new_obj = response.json()
        return new_obj.get("id", "")

    def find_object_in_path(self, root_id: str, path: List[str], name: str, obj_type: str) -> Optional[str]:
        current_id = root_id
        for folder_name in path:
            current_id = self.find_folder_id(current_id, folder_name)
            if not current_id:
                return None
        if not current_id:
            return None
        items = self.get_folder_items(current_id)
        logger.info(f"Searching for object '{name}' (type: {obj_type}) in path {path}")
        for item in items:
            if item["type"] == obj_type and item["defaultName"] == name:
                return item["id"]
        return None

    def rename_object(self, obj_id: str, new_name: str, obj_type: str) -> None:
        url = f"{self.base_url}/content/{obj_id}"
        data = {"defaultName": new_name, "type": obj_type}
        response = self.session.put(url, json=data, headers=self.headers, cookies=self.cookies, verify=self.session.verify)
        response.raise_for_status()
        logger.info(f"Object {obj_id} renamed to {new_name} with type {obj_type}")

    def get_module(self, obj_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/modules/{obj_id}"
        response = self.session.get(url, headers=self.headers, cookies=self.cookies, verify=self.session.verify)
        response.raise_for_status()
        return response.json()

    def get_module_id(self, folder_id: str, module_name: str) -> str:
        folder_items_url = f"{self.base_url}/content/{folder_id}/items"
        response = self.session.get(folder_items_url, headers=self.headers, cookies=self.cookies, verify=self.session.verify)
        response.raise_for_status()
        items = response.json()["content"]
        module_id = next((item["id"] for item in items if item["defaultName"] == module_name), None)
        if not module_id:
            raise ValueError(f"Module {module_name} not found in folder {folder_id}")
        return module_id
