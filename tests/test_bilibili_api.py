"""Tests for Bilibili API helpers."""

from __future__ import annotations

import pytest

from openbiliclaw.bilibili.api import BilibiliAPIClient, BilibiliAPIError


class FakeResponse:
    """Minimal fake HTTP response."""

    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class FakeAsyncClient:
    """Minimal fake async HTTP client."""

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    async def get(self, url: str, params: dict[str, object] | None = None) -> FakeResponse:
        self.calls.append((url, params))
        return FakeResponse(self.payload)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_get_nav_info_parses_login_payload() -> None:
    client = BilibiliAPIClient(cookie="SESSDATA=abc")
    fake_http = FakeAsyncClient(
        {
            "code": 0,
            "data": {
                "isLogin": True,
                "uname": "alice",
                "mid": 10086,
            },
        }
    )
    client._client = fake_http

    nav = await client.get_nav_info()

    assert nav.is_login is True
    assert nav.uname == "alice"
    assert nav.mid == 10086
    assert fake_http.calls[0][0].endswith("/x/web-interface/nav")


@pytest.mark.asyncio
async def test_get_nav_info_raises_on_nonzero_code() -> None:
    client = BilibiliAPIClient(cookie="SESSDATA=abc")
    client._client = FakeAsyncClient({"code": -101, "message": "账号未登录"})

    with pytest.raises(BilibiliAPIError, match="账号未登录"):
        await client.get_nav_info()
