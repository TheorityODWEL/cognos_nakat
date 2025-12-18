import logging
from typing import Dict, List, Optional

from clients.content_client import ContentClient
from config import EnvironmentConfig


logger = logging.getLogger(__name__)


class DiscoveryService:
    def __init__(self, client: ContentClient, config: EnvironmentConfig):
        self.client = client
        self.config = config

    def find_main_folders(self) -> Dict[str, str]:
        main_folder_ids = {}
        for folder_name in self.config.main_folders:
            folder_id = self.client.find_folder_id(self.config.root_folder_id, folder_name)
            if folder_id:
                main_folder_ids[folder_name] = folder_id
            else:
                logger.warning(f"Main folder '{folder_name}' not found in {self.client.base_url}")
        return main_folder_ids

    def find_backup_folders(self) -> Dict[str, str]:
        admin_id = self.client.find_folder_id(self.config.root_folder_id, self.config.admin_folder_name)
        if not admin_id:
            raise ValueError(f"Admin folder '{self.config.admin_folder_name}' not found")
        backup_id = self.client.find_folder_id(admin_id, self.config.backup_folder_name)
        if not backup_id:
            raise ValueError(f"Backup folder '{self.config.backup_folder_name}' not found")
        backup_sub_ids: Dict[str, str] = {}
        for obj_type, sub_name in self.config.backup_subfolders.items():
            sub_id = self.client.find_folder_id(backup_id, sub_name)
            if sub_id:
                backup_sub_ids[obj_type] = sub_id
            else:
                logger.warning(f"Backup subfolder '{sub_name}' not found")
        return backup_sub_ids

    def recursive_search_objects(self, folder_id: str, path: Optional[List[str]] = None) -> List[dict]:
        if path is None:
            path = []
        objects_to_migrate: List[dict] = []
        items = self.client.get_folder_items(folder_id)
        for item in items:
            current_path = path + [item["defaultName"]]
            if item["type"] == "folder":
                objects_to_migrate.extend(self.recursive_search_objects(item["id"], current_path))
            elif item["type"] in ["report", "dashboard", "module"] and self.config.tag in item["defaultName"]:
                item["full_path"] = current_path[:-1]
                objects_to_migrate.append(item)
        return objects_to_migrate

    def find_object_in_path(self, root_id: str, path: List[str], name: str, obj_type: str) -> Optional[str]:
        return self.client.find_object_in_path(root_id, path, name, obj_type)
