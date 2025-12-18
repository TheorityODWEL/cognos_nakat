import json
import os
from dataclasses import dataclass
from typing import Dict, List


# Defaults preserved from the original script. Override via environment variables.
DEFAULT_DEV_URL = "url" \"
DEFAULT_PROD_URL = "url"
DEFAULT_NAMESPACE = "****"
DEFAULT_USERNAME = "****"
DEFAULT_PASSWORD = "****"
DEFAULT_TAG = "(накат)"
DEFAULT_ROOT_FOLDER_ID = "team_folders"
DEFAULT_MAIN_FOLDERS = [
]
DEFAULT_ADMIN_FOLDER_NAME = "*****"
DEFAULT_BACKUP_FOLDER_NAME = "Backup"
DEFAULT_BACKUP_SUBFOLDERS = {
    "report": "****",
    "dashboard": "****",
    "module": "****",
}
DEFAULT_TEMPLATE_REPORT_ID = "i89740B1A4FE54835B1EB17AFB3618D22"
DEFAULT_TEMPLATE_DASHBOARD_ID = "i4AA85B4F0F64440AA020BF583B360483"


def _load_json_or_default(env_var: str, default):
    raw = os.getenv(env_var)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: split by comma or semicolon for simple lists.
        if isinstance(default, list):
            return [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]
        return default


@dataclass
class EnvironmentConfig:
    base_url: str
    namespace: str
    username: str
    password: str
    root_folder_id: str
    main_folders: List[str]
    admin_folder_name: str
    backup_folder_name: str
    backup_subfolders: Dict[str, str]
    template_report_id: str
    template_dashboard_id: str
    tag: str
    verify_ssl: bool = False


@dataclass
class AppConfig:
    dev: EnvironmentConfig
    prod: EnvironmentConfig


def load_config() -> AppConfig:
    main_folders = _load_json_or_default("MAIN_FOLDERS", DEFAULT_MAIN_FOLDERS)
    backup_subfolders = _load_json_or_default("BACKUP_SUBFOLDERS", DEFAULT_BACKUP_SUBFOLDERS)
    verify_ssl = os.getenv("VERIFY_SSL", "false").lower() == "true"

    shared = {
        "namespace": os.getenv("NAMESPACE", DEFAULT_NAMESPACE),
        "username": os.getenv("USERNAME", DEFAULT_USERNAME),
        "password": os.getenv("PASSWORD", DEFAULT_PASSWORD),
        "root_folder_id": os.getenv("ROOT_FOLDER_ID", DEFAULT_ROOT_FOLDER_ID),
        "main_folders": main_folders,
        "admin_folder_name": os.getenv("ADMIN_FOLDER_NAME", DEFAULT_ADMIN_FOLDER_NAME),
        "backup_folder_name": os.getenv("BACKUP_FOLDER_NAME", DEFAULT_BACKUP_FOLDER_NAME),
        "backup_subfolders": backup_subfolders,
        "template_report_id": os.getenv("TEMPLATE_REPORT_ID", DEFAULT_TEMPLATE_REPORT_ID),
        "template_dashboard_id": os.getenv("TEMPLATE_DASHBOARD_ID", DEFAULT_TEMPLATE_DASHBOARD_ID),
        "tag": os.getenv("TAG", DEFAULT_TAG),
        "verify_ssl": verify_ssl,
    }

    dev = EnvironmentConfig(
        base_url=os.getenv("DEV_URL", DEFAULT_DEV_URL),
        **shared,
    )
    prod = EnvironmentConfig(
        base_url=os.getenv("PROD_URL", DEFAULT_PROD_URL),
        **shared,
    )
    return AppConfig(dev=dev, prod=prod)
