import logging
import warnings

import requests

from clients.content_client import ContentClient
from config import load_config
from services.discovery import DiscoveryService
from services.migrator import Migrator
from services.validator import Validator
from session import SessionFactory


warnings.filterwarnings("ignore", category=requests.packages.urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    config = load_config()

    dev_session = SessionFactory(config.dev).create()
    prod_session = SessionFactory(config.prod).create()

    dev_client = ContentClient(config.dev.base_url, dev_session)
    prod_client = ContentClient(config.prod.base_url, prod_session)

    dev_discovery = DiscoveryService(dev_client, config.dev)
    prod_discovery = DiscoveryService(prod_client, config.prod)

    dev_main_folders = dev_discovery.find_main_folders()
    prod_main_folders = prod_discovery.find_main_folders()
    prod_backup_folders = prod_discovery.find_backup_folders()

    objects_to_migrate = []
    for folder_name, folder_id in dev_main_folders.items():
        objects_to_migrate.extend(dev_discovery.recursive_search_objects(folder_id, [folder_name]))

    for item in objects_to_migrate:
        print(item["defaultName"])

    validator = Validator(dev_client, prod_client, config.dev)
    migrator = Migrator(dev_client, prod_client, config.dev, config.prod, validator)

    results_deploy = migrator.migrate_objects(objects_to_migrate, dev_main_folders, prod_main_folders, prod_backup_folders)
    print(results_deploy)


if __name__ == "__main__":
    main()
