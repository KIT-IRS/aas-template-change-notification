"""Delivery of TCN records over MQTT, one topic per template family  (paper §4.1)."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt

HOST = os.environ.get("TCN_MQTT_HOST", "localhost")
PORT = int(os.environ.get("TCN_MQTT_PORT", "1883"))


def topic(family: str) -> str:
    return f"tcn/{family}"


def _client(client_id: str = "", persistent: bool = False) -> mqtt.Client:
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, clean_session=not persistent)
    c.connect(HOST, PORT)
    return c


def publish(family: str, message: dict[str, Any]) -> None:
    c = _client()
    c.loop_start()
    c.publish(topic(family), json.dumps(message), qos=1).wait_for_publish()
    c.loop_stop()
    c.disconnect()


def receive(families: list[str], handle: Callable[[dict[str, Any]], None], seconds: float,
            client_id: str = "tcn-reception", subscribed: threading.Event | None = None) -> None:
    """Subscribe for `seconds`. The session is persistent: records published while the receiver
    is offline are delivered on its next run. `subscribed` is set once the broker has confirmed
    all subscriptions."""
    c = _client(client_id, persistent=True)
    c.on_message = lambda client, userdata, msg: handle(json.loads(msg.payload))
    pending = set()

    def on_subscribe(client, userdata, mid, reason_codes, properties):
        pending.discard(mid)
        if not pending and subscribed is not None:
            subscribed.set()

    c.on_subscribe = on_subscribe
    c.loop_start()
    for f in families:
        pending.add(c.subscribe(topic(f), qos=1)[1])
    time.sleep(seconds)
    c.loop_stop()
    c.disconnect()
