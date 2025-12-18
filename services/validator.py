import logging
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

from clients.content_client import ContentClient
from config import EnvironmentConfig


logger = logging.getLogger(__name__)
pattern = r"@name='([^']*)'"


def _extract_default_ns(spec_xml: str) -> Optional[str]:
    if not spec_xml:
        return None
    root = ET.fromstring(spec_xml.strip())
    tag = root.tag
    if tag.startswith("{") and "}" in tag:
        return tag[1 : tag.index("}")]
    return None


def _get_sources(module: Dict) -> List[str]:
    sources = []
    for use_spec in module.get("useSpec", []):
        if (ancestor := use_spec.get("ancestors")) is not None:
            sources.append(ancestor[0]["defaultName"])
    return sources


class Validator:
    def __init__(self, dev_client: ContentClient, prod_client: ContentClient, config: EnvironmentConfig):
        self.dev_client = dev_client
        self.prod_client = prod_client
        self.config = config

    def validate(
        self,
        obj: Dict,
        dev_main_folders: Dict[str, str],
        prod_main_folders: Dict[str, str],
        is_new: bool = True,
    ) -> bool:
        if obj["type"] == "report":
            return self._check_report(obj, dev_main_folders, prod_main_folders, is_new)
        if obj["type"] == "module":
            return self._check_module(obj, dev_main_folders, prod_main_folders, is_new=is_new)
        logger.info(f"Skipping validation for unsupported type {obj['type']}")
        return True

    def _check_report(
        self,
        obj: Dict,
        dev_main_folders: Dict[str, str],
        prod_main_folders: Dict[str, str],
        is_new: bool = True,
    ) -> bool:
        is_ok = 1
        obj_name = obj["defaultName"].replace(self.config.tag, "").strip()
        module = self.dev_client.get_module(obj["id"])
        logger.info(f"Validating report {obj_name}")
        spec_xml = obj["specification"]
        root = ET.fromstring(spec_xml.strip())
        ns = _extract_default_ns(spec_xml)
        if ns:
            ET.register_namespace("", ns)
            if not root.tag.endswith("report"):
                return False
        ns_map = {"ns": ns}
        queries = root.findall(".//ns:sqlText", ns_map)

        sources = []
        path_module = []
        for md in module.get("useSpec", []):
            path_module.append(re.findall(pattern, md.get("searchPath")))

        for paths in path_module:
            if paths and paths[-1] != "Empty":
                dev_folder_id = dev_main_folders.get(paths[0])
                if not dev_folder_id:
                    logger.warning(f"Main folder {paths[0]} for module {paths[-1]} not found in DEV")
                    continue
                dev_obj_module_id = self.dev_client.find_object_in_path(
                    dev_folder_id,
                    paths[1:-1],
                    paths[-1],
                    "module",
                )
                if not dev_obj_module_id:
                    logger.warning(f"Module {paths[-1]} not found in DEV at path {paths}")
                    continue
                source_module = self.dev_client.get_module(dev_obj_module_id)
                sources.extend(_get_sources(source_module))
                module_content = self.dev_client.get_content(dev_obj_module_id)
                logger.info(f"Validating module {paths[-1]} used in report {obj_name}")
                is_ok = self._check_module(
                    module_content,
                    dev_main_folders,
                    prod_main_folders,
                    paths=paths,
                    is_new=True,
                    is_from_report=True,
                )

        if is_new and queries:
            logger.warning(f"Report {obj_name} contains SQL; creation not allowed")
            is_ok = 0

        for elem in queries:
            sql_text = elem.text
            sql_text = sql_text.replace("\n", " ").replace("\t", " ")
            sql_text = " ".join(sql_text.split())
            if "sql_" in sql_text:
                logger.warning(f"Report {obj_name} contains references to named SQL queries")
                is_ok = 0

        if "Greenplum" in sources:
            if root.attrib.get("viewPagesAsTabs") != "bottomLeft":
                logger.warning(
                    f"Report {obj_name} has incorrect page view settings for Greenplum source; expected bottomLeft"
                )
                is_ok = 0
            if "paginateHTMLOutput" in root.attrib:
                logger.warning(f"Report {obj_name} has HTML pagination enabled for Greenplum source")
                is_ok = 0

        if is_ok:
            logger.info(f"==========================================")
            logger.info(f"Report {obj['defaultName']} passed validation")
        else:
            logger.info(f"==========================================")
            logger.info(f"Report {obj['defaultName']} failed validation")
        return bool(is_ok)

    def _check_module(
        self,
        obj: Dict,
        dev_main_folders: Dict[str, str],
        prod_main_folders: Dict[str, str],
        paths: List[str] = None,
        is_new: bool = True,
        is_from_report: bool = False,
    ) -> bool:
        obj_name = obj["defaultName"].replace(self.config.tag, "").strip()
        obj_description = obj["defaultDescription"] if obj["defaultDescription"] is not None else "?‘?‘?‘'?"

        if paths is None:
            paths = []
        if is_from_report:
            prod_folder_id = prod_main_folders.get(paths[0])
            prod_obj_module_id = self.prod_client.find_object_in_path(
                prod_folder_id,
                paths[1:-1],
                obj_name,
                "module",
            )
            is_new = 0 if prod_obj_module_id is not None else 1

        logger.info(f"Validating module {obj_name}")
        module = self.dev_client.get_module(obj["id"])
        is_ok = 1

        if not obj_description.lower().startswith(("+ñú?ç‘? ?>ø?ç>ç‘Å:", "+ñú?ç‘?-?>ø?ç>ç‘Å:")):
            logger.info(f"Module {obj_name} missing required description prefix")
            is_ok = 0

        for qobj in module["querySubject"]:
            if "sqlQuery" in qobj:
                query = qobj["sqlQuery"]["sqlText"]
                qname = qobj["label"]
                matches = re.findall(r"sql_[A-Za-z0-9_]+", query)
                if matches:
                    logger.warning(f"Module {obj_name} uses named SQL in {qname}")
                    is_ok = 0

        if is_new:
            if not obj_name.isascii():
                is_ok = 0
                logger.warning(f"Module {obj_name} contains non-ASCII characters in name")

            for qobj in module["querySubject"]:
                if "sqlQuery" in qobj:
                    qname = qobj["label"]
                    logger.warning(f"Module {obj_name} contains SQL in {qname}")
                    is_ok = 0

            sources = _get_sources(module)
            for source in sources:
                if source != "Greenplum":
                    logger.warning(f"Module {obj_name} uses source {source} instead of Greenplum")
                    is_ok = 0
                    break

        if is_ok:
            logger.info(f"==========================================")
            logger.info(f"Module {obj['defaultName']} passed validation")
        else:
            logger.info(f"==========================================")
            logger.info(f"Module {obj['defaultName']} failed validation")
        return bool(is_ok)
