import json
import os
import subprocess
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
    __auth_input = None

    def __new__(cls):
        if cls.__session is None:
            cls.login(cls.__auth_input)
        elif cls._access_token_expiring():
            if cls.__auth_data and cls.__auth_data.get("refresh_token"):
                cls.refresh_token()
            else:
                raise InvestopediaAuthException(
                    "The Investopedia access token is expiring and no refresh token "
                    "is available. Run the passwordless bootstrap again."
                )
        return cls.__session

    @classmethod
    def _normalise_auth_data(cls, auth_data):
        if not auth_data:
            return None

        if isinstance(auth_data, str):
            return {"access_token": auth_data}

        if not isinstance(auth_data, dict):
            raise TypeError("auth must be a dict, bearer-token string, or None")

        data = dict(auth_data)
        if data.get("auth_token") and not data.get("access_token"):
            data["access_token"] = data["auth_token"]
        if data.get("bearer_token") and not data.get("access_token"):
            data["access_token"] = data["bearer_token"]
        return data

    @classmethod
    def _email_from_auth(cls, auth_data):
        if isinstance(auth_data, dict):
            return auth_data.get("email") or auth_data.get("username")
        return os.getenv("INVESTOPEDIA_EMAIL")

    @classmethod
    def _load_tokens_from_file(cls):
        if not os.path.exists(cls.__auth_file):
            return None

        with open(cls.__auth_file, "r", encoding="utf-8") as auth_file:
            data = cls._normalise_auth_data(json.load(auth_file))

        return data if data and data.get("access_token") else None

    @classmethod
    def _load_tokens_from_env(cls):
        access_token = (
            os.getenv("INVESTOPEDIA_ACCESS_TOKEN")
            or os.getenv("INVESTOPEDIA_AUTH_TOKEN")
        )
        refresh_token = os.getenv("INVESTOPEDIA_REFRESH_TOKEN")

        if not access_token:
            return None

        data = {"access_token": access_token}
        if refresh_token:
            data["refresh_token"] = refresh_token
        return data

    @classmethod
    def _save_tokens(cls):
        if cls.__auth_data is None:
            return

        with open(cls.__auth_file, "w", encoding="utf-8") as auth_file:
            json.dump(cls.__auth_data, auth_file, indent=2)
            auth_file.write("\n")

    @classmethod
    def _access_token_expiring(cls, leeway_seconds=60):
        if not cls.__auth_data:
            return False

        obtained_at = cls.__auth_data.get("obtained_at")
        expires_in = cls.__auth_data.get("expires_in")
        if obtained_at is not None and expires_in is not None:
            try:
                return (
                    time.time()
                    >= float(obtained_at) + float(expires_in) - leeway_seconds
                )
            except (TypeError, ValueError):
                pass

        # Without timing metadata, let the API validation request decide. This
        # avoids decoding/depending on any particular access-token format.
        return False

    @classmethod
    def _apply_access_token(cls):
        if not cls.__auth_data or not cls.__auth_data.get("access_token"):
            raise InvestopediaAuthException(
                "Authentication data does not contain an access_token."
            )

        if cls.__session is None:
            cls.__session = requests.Session()

        cls.__session.headers.update(
            {
                "Authorization": "Bearer %s" % cls.__auth_data["access_token"],
                "Content-Type": "application/json",
            }
        )

    @classmethod
    def bootstrap_passwordless(cls, email):
        if not email:
            raise NotLoggedInException(
                "No Investopedia tokens were found. Provide an access token, set "
                "INVESTOPEDIA_ACCESS_TOKEN, create auth.json, or pass "
                "{'email': 'you@example.com'} for the passwordless bootstrap."
            )

        if not os.path.exists(os.path.join(CWD, "node_modules")):
            try:
                subprocess.run(
                    ["npm", "install", "--no-audit", "--no-fund"],
                    cwd=CWD,
                    check=True,
                )
            except (OSError, subprocess.CalledProcessError) as exc:
                raise InvestopediaAuthException(
                    "Unable to install the Puppeteer authentication helper."
                ) from exc

        env = os.environ.copy()
        env["INVESTOPEDIA_AUTH_FILE"] = cls.__auth_file

        print("Starting Investopedia passwordless login for %s..." % email)
        try:
            subprocess.run(
                ["node", os.path.join(CWD, "auth.js"), email],
                cwd=CWD,
                env=env,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise InvestopediaAuthException(
                "Passwordless bootstrap failed. Re-run `node auth.js <email>` "
                "to inspect the login error."
            ) from exc

        tokens = cls._load_tokens_from_file()
        if not tokens:
            raise InvestopediaAuthException(
                "Passwordless bootstrap finished without producing a usable auth.json."
            )
        return tokens

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
                "Run the passwordless bootstrap again." % response.status_code
            )

        try:
            refreshed = response.json()
        except ValueError as exc:
            raise InvestopediaAuthException(
                "Investopedia returned a non-JSON refresh-token response."
            ) from exc

        if not refreshed.get("access_token"):
            raise InvestopediaAuthException(
                "Investopedia's refresh response did not contain an access_token."
            )

        # Preserve the previous refresh token if the provider does not rotate it.
        if not refreshed.get("refresh_token"):
            refreshed["refresh_token"] = cls.__auth_data["refresh_token"]

        refreshed["obtained_at"] = time.time()
        cls.__auth_data = refreshed
        cls._apply_access_token()
        cls._save_tokens()
        return cls.__session

    @classmethod
    def _validate(cls):
        return cls.__session.post(
            API_URL,
            data=Queries.read_user_id(),
            timeout=30,
        )

    @classmethod
    def login(cls, auth=None, auth_file=None):
        cls.__auth_input = auth

        if auth_file:
            cls.__auth_file = os.path.abspath(auth_file)

        explicit = cls._normalise_auth_data(auth)
        if explicit and explicit.get("access_token"):
            cls.__auth_data = explicit
        else:
            cls.__auth_data = cls._load_tokens_from_env()
            if cls.__auth_data is None:
                cls.__auth_data = cls._load_tokens_from_file()
            if cls.__auth_data is None:
                cls.__auth_data = cls.bootstrap_passwordless(
                    cls._email_from_auth(auth)
                )

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
                "Run the passwordless bootstrap again or provide a fresh bearer token."
                % response.status_code
            )

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
        if cls.__session is not None:
            cls.__session.close()
        cls.__session = None
        cls.__auth_data = None

        if remove_saved_tokens and os.path.exists(cls.__auth_file):
            os.remove(cls.__auth_file)
