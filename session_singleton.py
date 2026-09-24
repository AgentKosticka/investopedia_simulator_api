import base64
import json
import os
import time
import warnings

import requests

from constants import API_URL, REFRESH_AUTH_TOKEN_URL
from queries import Queries

CWD = os.path.dirname(os.path.abspath(__file__))
DEFAULT_AUTH_FILE = os.path.join(CWD, "auth.json")


class NotLoggedInException(Exception):
    pass


class InvestopediaAuthException(Exception):
    pass


class Session:
    __session = None
    __auth_data = None
    __auth_file = DEFAULT_AUTH_FILE

    def __new__(cls):
        if cls.__session is None:
            cls.login()
        elif cls._access_token_expiring():
            if cls.__auth_data and cls.__auth_data.get("refresh_token"):
                cls.refresh_token()
            else:
                raise InvestopediaAuthException(
                    "The Investopedia access token has expired and no refresh token is available. "
                    "Sign in again and provide a fresh bearer token."
                )
        return cls.__session

    def __getattr__(self, name):
        return getattr(self.__session, name)

    @classmethod
    def _normalise_auth_data(cls, auth_data):
        if not auth_data:
            return None

        data = dict(auth_data)
        if data.get("auth_token") and not data.get("access_token"):
            data["access_token"] = data.pop("auth_token")
        if data.get("bearer_token") and not data.get("access_token"):
            data["access_token"] = data.pop("bearer_token")
        return data

    @classmethod
    def _load_auth_data(cls, auth_data=None):
        explicit = cls._normalise_auth_data(auth_data)
        if explicit and explicit.get("access_token"):
            return explicit

        access_token = (
            os.getenv("INVESTOPEDIA_ACCESS_TOKEN")
            or os.getenv("INVESTOPEDIA_AUTH_TOKEN")
        )
        refresh_token = os.getenv("INVESTOPEDIA_REFRESH_TOKEN")
        if access_token:
            env_data = {"access_token": access_token}
            if refresh_token:
                env_data["refresh_token"] = refresh_token
            return env_data

        if os.path.exists(cls.__auth_file):
            with open(cls.__auth_file, "r", encoding="utf-8") as auth_file:
                return cls._normalise_auth_data(json.load(auth_file))

        raise InvestopediaAuthException(
            "No Investopedia authentication token found. Provide {'access_token': '...'} "
            "to InvestopediaApi, set INVESTOPEDIA_ACCESS_TOKEN, or create auth.json. "
            "Investopedia uses passwordless sign-in, so username/password login is no longer supported."
        )

    @classmethod
    def _save_tokens(cls):
        if cls.__auth_data is None:
            return
        with open(cls.__auth_file, "w", encoding="utf-8") as auth_file:
            json.dump(cls.__auth_data, auth_file)

    @classmethod
    def _jwt_exp(cls):
        if not cls.__auth_data:
            return None

        token = cls.__auth_data.get("access_token")
        if not token or token.count(".") < 2:
            return None

        try:
            payload = token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
            return json.loads(decoded.decode("utf-8")).get("exp")
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return None

    @classmethod
    def _access_token_expiring(cls, leeway_seconds=60):
        exp = cls._jwt_exp()
        return exp is not None and exp <= time.time() + leeway_seconds

    @classmethod
    def _apply_access_token(cls):
        if not cls.__auth_data or not cls.__auth_data.get("access_token"):
            raise InvestopediaAuthException("Authentication data does not contain an access_token.")

        if cls.__session is None:
            cls.__session = requests.Session()

        cls.__session.headers.update(
            {
                "Authorization": "Bearer %s" % cls.__auth_data["access_token"],
                "Content-Type": "application/json",
            }
        )

    @classmethod
    def _validate(cls):
        return cls.__session.post(API_URL, data=Queries.read_user_id())

    @classmethod
    def refresh_token(cls):
        if not cls.__auth_data or not cls.__auth_data.get("refresh_token"):
            raise InvestopediaAuthException("No refresh_token is available.")

        response = requests.post(
            REFRESH_AUTH_TOKEN_URL,
            data=Queries.refresh_token(cls.__auth_data["refresh_token"]),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )

        if not response.ok:
            raise InvestopediaAuthException(
                "Investopedia rejected the refresh token with HTTP %s. "
                "Sign in again and provide a fresh token." % response.status_code
            )

        refreshed = response.json()
        # Some OIDC servers rotate refresh tokens; others omit refresh_token when
        # the previous one remains valid. Preserve it if the response omits it.
        if not refreshed.get("refresh_token"):
            refreshed["refresh_token"] = cls.__auth_data["refresh_token"]

        cls.__auth_data = refreshed
        cls._apply_access_token()
        cls._save_tokens()
        return cls.__session

    @classmethod
    def login(cls, auth_data=None, auth_file=None):
        if auth_file:
            cls.__auth_file = os.path.abspath(auth_file)

        cls.__auth_data = cls._load_auth_data(auth_data)
        cls.__session = requests.Session()
        cls._apply_access_token()

        if cls._access_token_expiring() and cls.__auth_data.get("refresh_token"):
            cls.refresh_token()

        response = cls._validate()
        if response.status_code in (401, 403) and cls.__auth_data.get("refresh_token"):
            warnings.warn("Access token was rejected; refreshing it and retrying once.")
            cls.refresh_token()
            response = cls._validate()

        if not response.ok:
            cls.__session = None
            raise InvestopediaAuthException(
                "Investopedia authentication failed with HTTP %s. "
                "Provide a fresh bearer token from the signed-in simulator session."
                % response.status_code
            )

        if auth_data is not None and cls.__auth_data.get("refresh_token"):
            cls._save_tokens()

        return cls.__session

    @classmethod
    def is_logged_in(cls):
        return (
            cls.__session is not None
            and cls.__session.headers.get("Authorization") is not None
        )

    @classmethod
    def logout(cls, remove_saved_tokens=False):
        cls.__session = None
        cls.__auth_data = None
        if remove_saved_tokens and os.path.exists(cls.__auth_file):
            os.remove(cls.__auth_file)
