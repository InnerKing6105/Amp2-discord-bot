"""Small AMP 2 HTTP client, for a single Minecraft instance only."""

import threading
import requests
import json
from formatting import players_from_api
from urllib.parse import urlsplit


class AMPError(RuntimeError):
    pass


class AMPClient:
    def __init__(self, base_url, username, password, instance_id=""):
        base = base_url.strip().rstrip("/")
        if not base.startswith(("http://", "https://")):
            raise AMPError("AMP_URL must begin with http:// or https://")
        parts = urlsplit(base)
        if parts.username or parts.password or parts.query or parts.fragment:
            raise AMPError("AMP_URL must be a plain AMP management URL, without credentials or query parameters.")
        if "/instances/" in parts.path.lower():
            raise AMPError(
                "AMP_URL points to an AMP dashboard /instances/... page, not the API. "
                "Use the Minecraft instance's own AMP web port (e.g. http://127.0.0.1:8081) "
                "or use the ADS root with AMP_INSTANCE_ID."
            )
        if parts.path.rstrip("/").lower().endswith("/api"):
            raise AMPError("AMP_URL should not include /API; remove that suffix.")
        self.api_url = base + "/API"
        if instance_id.strip():
            self.api_url += f"/ADSModule/Servers/{instance_id.strip()}/API"
        self.username = username
        self.password = password
        self.session_id = ""
        self.session = requests.Session()
        self.lock = threading.RLock()

    def _post(self, method, params):
        try:
            response = self.session.post(
                f"{self.api_url}/{method}",
                data=json.dumps(params),
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            extra = f" (HTTP {status})" if status is not None else ""
            raise AMPError(f"AMP request {method} failed{extra}. Check AMP_URL and instance availability. {type(exc).__name__}") from exc
        try:
            result = response.json()
        except ValueError as exc:
            content_type = response.headers.get("Content-Type", "not provided").split(";")[0]
            raise AMPError(
                f"AMP request {method} returned a non-JSON response "
                f"(HTTP {response.status_code}, Content-Type: {content_type}). "
                "AMP_URL likely points to a dashboard page instead of an instance API. "
                "Check http://127.0.0.1:<instance-port>/API in your browser."
            ) from exc
        if isinstance(result, dict) and result.get("Title") == "UnauthorizedAccessException":
            raise AMPError("AMP refused the request. Check the bot account permissions.")
        return result

    def login(self):
        with self.lock:
            result = self._post("Core/Login", {
                "username": self.username,
                "password": self.password,
                "token": "",
                "rememberMe": False,
            })
            if not isinstance(result, dict) or not result.get("success"):
                raise AMPError("AMP login failed. Check the instance URL, login, and 2FA requirements.")
            self.session_id = result.get("sessionID", "")
            if not self.session_id:
                raise AMPError("AMP login did not return a session ID.")

    def call(self, method, **args):
        with self.lock:
            if not self.session_id:
                self.login()
            data = {"SESSIONID": self.session_id, **args}
            try:
                result = self._post(method, data)
            except AMPError as exc:
                if "401" not in str(exc) and "403" not in str(exc):
                    raise
                self.login()
                result = self._post(method, {"SESSIONID": self.session_id, **args})
            # Do not silently swallow session/permission errors returned as JSON.
            if isinstance(result, dict):
                reason = str(result.get("Reason", ""))
                error = str(result.get("Error", ""))
                if "Session.Exists" in reason + error or "UnauthorizedAccessException" in reason + error:
                    raise AMPError(f"AMP denied {method}: {reason or error}")
            return result

    def status(self):
        return self.call("Core/GetStatus")

    def updates(self):
        return self.call("Core/GetUpdates")

    def players(self):
        return players_from_api(self.call("Core/GetUserList"))

    def send_minecraft(self, text):
        return self.call("Core/SendConsoleMessage", message=text)

    def start(self):
        return self.call("Core/Start")

    def stop(self):
        return self.call("Core/Stop")

    def restart(self):
        return self.call("Core/Restart")
