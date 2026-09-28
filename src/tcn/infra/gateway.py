"""The single point of access to the AAS environment (Eclipse BaSyx, AAS API v3)  (paper §4.1)."""

from __future__ import annotations

import base64
import os
from typing import Any

import requests

URL = os.environ.get("TCN_AAS_URL", "http://localhost:8081")


def _b64(identifier: str) -> str:
    return base64.urlsafe_b64encode(identifier.encode()).decode().rstrip("=")


class Gateway:
    def __init__(self, url: str = URL):
        self.url = url.rstrip("/")

    def _call(self, method: str, path: str, body: Any = None) -> Any:
        r = requests.request(method, self.url + path, json=body, timeout=30)
        r.raise_for_status()
        return r.json() if r.content else None

    # --- submodels ------------------------------------------------------------------------

    def get_submodel(self, sm_id: str) -> dict[str, Any]:
        return self._call("GET", f"/submodels/{_b64(sm_id)}")

    def post_submodel(self, sm: dict[str, Any]) -> None:
        self._call("POST", "/submodels", sm)

    def put_submodel(self, sm: dict[str, Any]) -> None:
        self._call("PUT", f"/submodels/{_b64(sm['id'])}", sm)

    def delete_submodel(self, sm_id: str) -> None:
        self._call("DELETE", f"/submodels/{_b64(sm_id)}")

    def submodels(self) -> list[dict[str, Any]]:
        return self._all("/submodels")

    # --- shells ---------------------------------------------------------------------------

    def get_shell(self, aas_id: str) -> dict[str, Any]:
        return self._call("GET", f"/shells/{_b64(aas_id)}")

    def post_shell(self, shell: dict[str, Any]) -> None:
        self._call("POST", "/shells", shell)

    def put_shell(self, shell: dict[str, Any]) -> None:
        self._call("PUT", f"/shells/{_b64(shell['id'])}", shell)

    def delete_shell(self, aas_id: str) -> None:
        self._call("DELETE", f"/shells/{_b64(aas_id)}")

    def shells(self) -> list[dict[str, Any]]:
        return self._all("/shells")

    def _all(self, path: str) -> list[dict[str, Any]]:
        result, cursor = [], None
        while True:
            page = self._call("GET", f"{path}?limit=100" + (f"&cursor={cursor}" if cursor else ""))
            result += page["result"]
            if not (cursor := page.get("paging_metadata", {}).get("cursor")):
                return result

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Complete enumeration of the environment, for before/after comparisons (V6, V7)."""
        return {x["id"]: x for x in self.shells() + self.submodels()}
