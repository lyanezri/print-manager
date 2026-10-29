"""Healthcheck local de Print Manager sin depender de DNS ni proxy."""

import json
from http.client import HTTPConnection


def check_health(host: str = "127.0.0.1", port: int = 8095) -> bool:
    connection = HTTPConnection(host, port, timeout=3)
    try:
        connection.request("GET", "/healthz", headers={"Host": host})
        response = connection.getresponse()
        payload = json.loads(response.read())
    finally:
        connection.close()
    return response.status == 200 and payload.get("ok") is True


if __name__ == "__main__":
    if not check_health():
        raise SystemExit(1)
