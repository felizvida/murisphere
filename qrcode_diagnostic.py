#!/usr/bin/env python3

# Copyright 2026 Murisphere Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""End-to-end diagnostic for cage-card QR rendering.

This script verifies that:
1) Cage cards are generated.
2) Card QR URL points to the public scan endpoint.
3) QR image endpoint returns a valid PNG payload.
4) Barcode image endpoint returns SVG payload.
5) Index page does not depend on CDN QR/barcode scripts.
"""

from __future__ import annotations

import tempfile
from typing import Any

import app as appmod


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(client: Any, email: str, password: str) -> str:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    if res.status_code != 200:
        raise RuntimeError(f"Login failed ({res.status_code}): {res.get_data(as_text=True)}")
    return res.get_json()["token"]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        old_db = appmod.DB_PATH
        try:
            appmod.DB_PATH = f"{tmpdir}/diag_murisphere.db"
            appmod.init_db()
            appmod.app.config.update(TESTING=True)
            client = appmod.app.test_client()

            token = _login(client, "admin@murisphere.local", "admin1234")

            cages_res = client.get("/api/cages", headers=_auth_headers(token))
            if cages_res.status_code != 200:
                raise RuntimeError(f"Failed to list cages: {cages_res.status_code}")
            cages = cages_res.get_json()
            if not cages:
                raise RuntimeError("No cages returned from /api/cages")

            first = cages[0]
            cards_res = client.post("/api/cages/cards", headers=_auth_headers(token), json={"ids": [first["id"]]})
            if cards_res.status_code != 200:
                raise RuntimeError(f"Failed to generate cage cards: {cards_res.status_code}")
            cards = cards_res.get_json()
            if not cards:
                raise RuntimeError("No card payload returned")

            card = cards[0]
            scan_url = f"https://murisphere.local{card['scanUrl']}"
            qr_res = client.get(f"/api/assets/qrcode.png?v={scan_url}")
            if qr_res.status_code != 200:
                raise RuntimeError(f"QR endpoint failed: {qr_res.status_code}")
            if not qr_res.data.startswith(PNG_SIGNATURE):
                raise RuntimeError("QR endpoint did not return a PNG payload")
            if len(qr_res.data) < 300:
                raise RuntimeError(f"QR payload unexpectedly small: {len(qr_res.data)} bytes")

            barcode_res = client.get(f"/api/assets/barcode.svg?v={card['cageCode']}")
            if barcode_res.status_code != 200:
                raise RuntimeError(f"Barcode endpoint failed: {barcode_res.status_code}")
            if b"<svg" not in barcode_res.data[:200]:
                raise RuntimeError("Barcode endpoint did not return SVG content")

            index_res = client.get("/")
            if index_res.status_code != 200:
                raise RuntimeError("Index page failed")
            body = index_res.get_data(as_text=True)
            if "cdn.jsdelivr.net/npm/qrcode" in body or "cdn.jsdelivr.net/npm/jsbarcode" in body:
                raise RuntimeError("Index page still references CDN QR/barcode scripts")

            print("QR diagnostic passed")
            print(f"cage={card['cageCode']}")
            print(f"scan_url={scan_url}")
            print(f"qr_bytes={len(qr_res.data)}")
            print(f"barcode_bytes={len(barcode_res.data)}")
            return 0
        finally:
            appmod.DB_PATH = old_db


if __name__ == "__main__":
    raise SystemExit(main())
