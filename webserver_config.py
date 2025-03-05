import os
import jwt
import requests
import logging
from base64 import b64decode
from cryptography.hazmat.primitives import serialization
from flask_appbuilder.security.manager import AUTH_DB, AUTH_OAUTH
from airflow import configuration as conf
from airflow.www.security import AirflowSecurityManager
from airflow.exceptions import AirflowException

log = logging.getLogger(__name__)
log.info("init my provider")
AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_ROLES_SYNC_AT_LOGIN = True
AUTH_USER_REGISTRATION_ROLE = "Viewer"
OIDC_ISSUER = "https://identity.infra.aurin-prod.cloud.edu.au/realms/infrastructure"

AUTH_ROLES_MAPPING = {
    "Viewer": ["Viewer"],
    "Admin": ["Admin"],
    "User": ["User"],
    "Public": ["Public"],
    "Op": ["Op"],
}


OAUTH_PROVIDERS = [
    {
        "name": "AURIN-Infra-Platform",
        "icon": "fa-key",
        "token_key": "access_token",
        "remote_app": {
            "client_id": "airflow",
            "client_secret": "xxxxxxxx",
            "server_metadata_url": "https://identity.infra.aurin-prod.cloud.edu.au/realms/infrastructure/.well-known/openid-configuration",
            "api_base_url": "https://identity.infra.aurin-prod.cloud.edu.au/realms/infrastructure/protocol/openid-connect",
            "client_kwargs": {"scope": "openid email profile"},
            "access_token_url": "https://identity.infra.aurin-prod.cloud.edu.au/realms/infrastructure/protocol/openid-connect/token",
            "authorize_url": "https://identity.infra.aurin-prod.cloud.edu.au/realms/infrastructure/protocol/openid-connect/auth",
            "request_token_url": None,
        },
    }
]

# Fetch public key
req = requests.get(OIDC_ISSUER)
key_der_base64 = req.json()["public_key"]
key_der = b64decode(key_der_base64.encode())
public_key = serialization.load_der_public_key(key_der)


class CustomSecurityManager(AirflowSecurityManager):
    def get_oauth_user_info(self, provider, response):
        if provider == "AURIN-Infra-Platform":
            token = response["access_token"]
            log.info("token: {0}".format(token))
            me = jwt.decode(token, public_key, algorithms=["HS256", "RS256"], audience="airflow")
            log.info("decoded")

            # Extract roles from resource access
            realm_access = me.get("realm_access", {})
            groups = realm_access.get("roles", [])

            log.info("roles: {0}".format(groups))

            if "pipeline-squad" in groups:
                log.info("Required Roles Found")
                groups = ["Admin", "User"]
            else:
                raise AirflowException("User does not have required roles")

            log.info("groups: {0}".format(groups))

            userinfo = {
                "username": me.get("preferred_username"),
                "email": me.get("email"),
                "first_name": me.get("given_name"),
                "last_name": me.get("family_name"),
                "role_keys": groups,
            }

            log.info("user info: {0}".format(userinfo))

            return userinfo
        else:
            return {}


# Make sure to replace this with your own implementation of AirflowSecurityManager class
SECURITY_MANAGER_CLASS = CustomSecurityManager