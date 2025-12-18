import logging
from dataclasses import dataclass
from typing import Dict

import requests

from config import EnvironmentConfig


logger = logging.getLogger(__name__)


@dataclass
class SessionData:
    headers: Dict[str, str]
    cookies: Dict[str, str]
    session: requests.Session


class SessionFactory:
    def __init__(self, config: EnvironmentConfig):
        self.config = config

    def create(self) -> SessionData:
        session = requests.Session()
        session.verify = self.config.verify_ssl
        session.trust_env = False
        session_endpoint = f"{self.config.base_url}/session"
        payload = {
            "parameters": [
                {"name": "CAMNamespace", "value": self.config.namespace},
                {"name": "CAMUsername", "value": self.config.username},
                {"name": "CAMPassword", "value": self.config.password},
            ]
        }
        response = session.put(session_endpoint, json=payload, verify=self.config.verify_ssl, timeout=(10, 60))
        response.raise_for_status()
        cookies = response.cookies
        cam_passport = cookies.get("cam_passport")
        xsrf_token = cookies.get("XSRF-TOKEN")
        headers = {
            "Content-Type": "application/json",
            "IBM-BA-Authorization": f"CAM {cam_passport}",
            "X-XSRF-Token": xsrf_token,
        }
        logger.info(f"Session created for {self.config.base_url}")
        return SessionData(headers=headers, cookies=cookies, session=session)
