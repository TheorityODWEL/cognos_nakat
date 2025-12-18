import logging
from typing import Dict, List

from clients.content_client import ContentClient
from config import EnvironmentConfig
from services.validator import Validator


logger = logging.getLogger(__name__)


class Migrator:
    def __init__(
        self,
        dev_client: ContentClient,
        prod_client: ContentClient,
        dev_config: EnvironmentConfig,
        prod_config: EnvironmentConfig,
        validator: Validator,
    ):
        self.dev_client = dev_client
        self.prod_client = prod_client
        self.dev_config = dev_config
        self.prod_config = prod_config
        self.validator = validator

    def migrate_objects(
        self,
        objects_to_migrate: List[dict],
        dev_main_folders: Dict[str, str],
        prod_main_folders: Dict[str, str],
        prod_backup_folders: Dict[str, str],
    ) -> List[str]:
        migrated = []
        ordered_objects = sorted(objects_to_migrate, key=lambda x: x["type"] != "module")
        for obj in ordered_objects:
            logger.info(f"Migrating object: {obj['defaultName']} (type: {obj['type']}, id: {obj['id']})")
            if self._migrate_object(obj, dev_main_folders, prod_main_folders, prod_backup_folders):
                migrated.append(obj["defaultName"])
        return migrated

    def _resolve_folder_path(self, root_id: str, path: List[str]) -> str:
        current_id = root_id
        for segment in path:
            current_id = self.prod_client.find_folder_id(current_id, segment)
            if not current_id:
                raise ValueError(f"Prod path not found for segment {segment} in {path}")
        return current_id

    def _migrate_object(
        self,
        dev_obj: dict,
        dev_main_folders: Dict[str, str],
        prod_main_folders: Dict[str, str],
        prod_backup_folders: Dict[str, str],
    ) -> bool:
        obj_type = dev_obj["type"]
        if obj_type not in ["report", "dashboard", "module"]:
            logger.warning(f"Unsupported type {obj_type} for object {dev_obj['id']}")
            return False

        original_name = dev_obj["defaultName"].replace(self.dev_config.tag, "").strip()
        full_path = dev_obj.get("full_path", [])
        main_folder_name = full_path[0] if full_path else None

        if main_folder_name not in self.dev_config.main_folders:
            logger.warning(f"Object {dev_obj['id']} not in main folders")
            return False

        prod_folder_id = prod_main_folders.get(main_folder_name)
        if not prod_folder_id:
            logger.error(f"Prod main folder {main_folder_name} not found")
            return False

        prod_obj_id = self.prod_client.find_object_in_path(prod_folder_id, full_path[1:], original_name, obj_type)
        is_new = prod_obj_id is None

        is_ok = self.validator.validate(dev_obj, dev_main_folders, prod_main_folders, is_new=is_new)
        if not is_ok:
            logger.info(f"Validation failed for {original_name}, skipping migration")
            return False

        logger.info(f"Is new object: {is_new}. Prod object ID: {prod_obj_id}")

        dev_description = dev_obj.get("defaultDescription")

        if obj_type == "report":
            dev_spec = dev_obj["specification"]
            dev_module = dev_obj["module"]
        else:
            dev_spec = None
            dev_module = None

        if is_new:
            prod_target_folder_id = self._resolve_folder_path(prod_folder_id, full_path[1:])
            if obj_type == "module":
                module = self.dev_client.get_module(dev_obj["id"])
                module["label"] = original_name
                self.prod_client.create_module(prod_target_folder_id, module)
                prod_obj_id = self.prod_client.get_module_id(prod_target_folder_id, original_name)
                payload = {"type": obj_type, "defaultDescription": dev_description}
                self.prod_client.update_object(prod_obj_id, payload)
            else:
                template_id = (
                    self.prod_config.template_report_id if obj_type == "report" else self.prod_config.template_dashboard_id
                )
                prod_obj_id = self.prod_client.copy_object(template_id, prod_target_folder_id, recursive=False)
                self.prod_client.rename_object(prod_obj_id, original_name, obj_type)
                payload = {"type": obj_type, "specification": dev_spec, "module": dev_module, "defaultDescription": dev_description}
                self.prod_client.update_object(prod_obj_id, payload)
        else:
            backup_dest_id = prod_backup_folders.get(obj_type)
            if backup_dest_id:
                self.prod_client.copy_object(prod_obj_id, backup_dest_id)
            else:
                logger.warning(f"No backup folder for {obj_type}")

            if obj_type == "module":
                module = self.dev_client.get_module(dev_obj["id"])
                prod_module = self.prod_client.get_module(prod_obj_id)
                module["label"] = prod_module["label"]
                module["identifier"] = prod_module["identifier"]
                self.prod_client.update_module_spec(prod_obj_id, module)
                payload = {"type": obj_type, "defaultDescription": dev_description}
                self.prod_client.update_object(prod_obj_id, payload)
            else:
                payload = {"type": obj_type, "specification": dev_spec, "module": dev_module, "defaultDescription": dev_description}
                self.prod_client.update_object(prod_obj_id, payload)

        self.dev_client.rename_object(dev_obj["id"], original_name, obj_type)
        return True
