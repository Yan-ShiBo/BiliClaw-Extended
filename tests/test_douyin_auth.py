"""Tests for persisted Douyin direct-cookie auth state."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openbiliclaw.sources.douyin_auth import (
    DouyinCookieManager,
    resolve_douyin_cookie,
    resolve_douyin_cookie_records,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_douyin_cookie_manager_persists_cookie_without_config(tmp_path: Path) -> None:
    manager = DouyinCookieManager(tmp_path)

    manager.set_cookie("msToken=real; ttwid=tw;", source="extension")

    payload = json.loads((tmp_path / "douyin_cookie.json").read_text(encoding="utf-8"))
    assert payload["cookie"] == "msToken=real; ttwid=tw;"
    assert payload["source"] == "extension"


def test_resolve_douyin_cookie_prefers_env_over_persisted(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manager = DouyinCookieManager(tmp_path)
    manager.set_cookie("msToken=file;")
    monkeypatch.setenv("TEST_DOUYIN_COOKIE", "msToken=env;")

    assert (
        resolve_douyin_cookie(data_dir=tmp_path, cookie_env="TEST_DOUYIN_COOKIE") == "msToken=env;"
    )


def test_resolve_douyin_cookie_falls_back_to_persisted_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manager = DouyinCookieManager(tmp_path)
    manager.set_cookie("msToken=file;")
    monkeypatch.delenv("TEST_DOUYIN_COOKIE", raising=False)

    assert (
        resolve_douyin_cookie(data_dir=tmp_path, cookie_env="TEST_DOUYIN_COOKIE") == "msToken=file;"
    )


def test_douyin_cookie_manager_keeps_multiple_accounts(tmp_path: Path) -> None:
    manager = DouyinCookieManager(tmp_path)

    manager.set_cookie("sessionid=one; uid_tt=u1;", source="profile-a")
    manager.set_cookie(
        "sessionid=two; uid_tt=u2;",
        source="profile-b",
        account_id="account2",
        label="second",
    )

    records = manager.load_records()
    assert [record.account_id for record in records] == ["primary", "account2"]
    assert [record.cookie for record in records] == [
        "sessionid=one; uid_tt=u1;",
        "sessionid=two; uid_tt=u2;",
    ]
    assert json.loads((tmp_path / "douyin_cookie.json").read_text(encoding="utf-8"))[
        "cookie"
    ] == "sessionid=one; uid_tt=u1;"
    payload = json.loads((tmp_path / "douyin_cookies.json").read_text(encoding="utf-8"))
    assert payload["active_account_id"] == "account2"
    assert payload["accounts"][1]["label"] == "second"

    manager.set_cookie("sessionid=one-new; uid_tt=u1;", source="profile-a")
    records = manager.load_records()
    assert [record.account_id for record in records] == ["primary", "account2"]
    assert records[0].cookie == "sessionid=one-new; uid_tt=u1;"


def test_douyin_cookie_manager_auto_selects_second_slot_for_new_account(
    tmp_path: Path,
) -> None:
    manager = DouyinCookieManager(tmp_path)
    manager.set_cookie("sessionid=one; uid_tt=u1;", source="profile-a")

    assert manager.account_id_for_cookie("sessionid=one; uid_tt=u1; ttwid=changed;") == "primary"
    assert manager.account_id_for_cookie("sessionid=two; uid_tt=u2;") == "account2"


def test_douyin_cookie_manager_matches_existing_account_by_uid_when_tokens_rotate(
    tmp_path: Path,
) -> None:
    manager = DouyinCookieManager(tmp_path)
    manager.set_cookie(
        "sessionid=old-session; uid_tt=same-user; passport_mfa_token=old-mfa;",
        source="profile-a",
        account_id="account2",
    )

    assert (
        manager.account_id_for_cookie(
            "sessionid=new-session; uid_tt=same-user; passport_mfa_token=new-mfa; ttwid=new;"
        )
        == "account2"
    )


def test_resolve_douyin_cookie_records_includes_second_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manager = DouyinCookieManager(tmp_path)
    manager.set_cookie("sessionid=file; uid_tt=uf;")
    monkeypatch.setenv("TEST_DOUYIN_COOKIE", "sessionid=env1; uid_tt=u1;")
    monkeypatch.setenv("TEST_DOUYIN_COOKIE_2", "sessionid=env2; uid_tt=u2;")

    records = resolve_douyin_cookie_records(data_dir=tmp_path, cookie_env="TEST_DOUYIN_COOKIE")

    assert [record.cookie for record in records] == [
        "sessionid=env1; uid_tt=u1;",
        "sessionid=env2; uid_tt=u2;",
        "sessionid=file; uid_tt=uf;",
    ]
