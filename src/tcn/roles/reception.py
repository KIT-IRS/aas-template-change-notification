"""Role of the asset maintainer: reception  (paper §4.1).

Files every received TCN record into the TCN submodel of the asset maintainer's AAS and performs
no further action. A record belongs to the group whose version chain it continues: its PreVersion
is the observed template of the group or the PostVersion of a record already filed there.
"""

from __future__ import annotations

import threading
from typing import Any

from tcn.infra import broker
from tcn.infra.gateway import Gateway


def _value(element: dict[str, Any], id_short: str) -> Any:
    return next(c for c in element["value"] if c.get("idShort") == id_short)["value"]


def file_record(gw: Gateway, tcn_id: str, record: dict[str, Any]) -> str:
    sm = gw.get_submodel(tcn_id)
    pre, nid = _value(record, "PreVersion"), _value(record, "NotificationId")
    for group in sm["submodelElements"][0].get("value", []):
        records = next(c for c in group["value"] if c["idShort"] == "TCNRecords")
        filed = records.setdefault("value", [])
        if any(_value(r, "NotificationId") == nid for r in filed):
            return "duplicate"
        versions = {_value(group, "ObservedSMT")["keys"][0]["value"]} | {_value(r, "PostVersion") for r in filed}
        if pre in versions:
            filed.append(record)
            gw.put_submodel(sm)
            return "filed"
    return "not observed"


def run(gw: Gateway, tcn_id: str, families: list[str], seconds: float,
        subscribed: threading.Event | None = None) -> list[str]:
    log = []

    def handle(message: dict[str, Any]) -> None:
        rec = message["Record"]
        log.append(f"{file_record(gw, tcn_id, rec)}: {_value(rec, 'NotificationId')}")

    broker.receive(families, handle, seconds, subscribed=subscribed)
    return log

