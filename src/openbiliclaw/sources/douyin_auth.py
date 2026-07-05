"""Persisted Douyin cookie helpers for direct-cookie discovery."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from re import sub
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class DouyinCookieRecord:
    """Stored Douyin Cookie header plus lightweight provenance."""

    cookie: str
    source: str = "unknown"
    account_id: str = "primary"
    label: str = ""
    updated_at: str = ""


class DouyinCookieManager:
    """Store Douyin Cookie headers outside config.toml.

    ``douyin_cookie.json`` is the legacy single-account file. New writes also
    maintain ``douyin_cookies.json`` so one backend instance can keep multiple
    Douyin accounts and rotate them for direct-cookie discovery.
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._legacy_cookie_path = data_dir / "douyin_cookie.json"
        self._multi_cookie_path = data_dir / "douyin_cookies.json"

    @property
    def cookie_path(self) -> Path:
        return self._legacy_cookie_path

    @property
    def multi_cookie_path(self) -> Path:
        return self._multi_cookie_path

    def set_cookie(
        self,
        cookie: str,
        *,
        source: str = "unknown",
        account_id: str = "primary",
        label: str = "",
    ) -> None:
        normalized = cookie.strip()
        normalized_account_id = normalize_douyin_account_id(account_id)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        records = [
            record
            for record in self.load_records(include_legacy=True)
            if normalize_douyin_account_id(record.account_id) != normalized_account_id
        ]
        records.append(
            DouyinCookieRecord(
                cookie=normalized,
                source=source.strip() or "unknown",
                account_id=normalized_account_id,
                label=label.strip(),
                updated_at=datetime.now(UTC).isoformat(),
            )
        )
        self._write_records(records, active_account_id=normalized_account_id)

        # Keep the legacy single-account file current for older callers and
        # existing tests. Secondary-account writes must not overwrite primary.
        if normalized_account_id == "primary":
            self._write_legacy_cookie(normalized, source=source)

    def load_cookie(self, account_id: str | None = None) -> str:
        record = self.load_record(account_id=account_id)
        return record.cookie if record is not None else ""

    def load_record(self, account_id: str | None = None) -> DouyinCookieRecord | None:
        records = self.load_records(include_legacy=True)
        if not records:
            return None

        if account_id is not None:
            normalized_account_id = normalize_douyin_account_id(account_id)
            for record in records:
                if normalize_douyin_account_id(record.account_id) == normalized_account_id:
                    return record
            return None

        active = self._load_active_account_id()
        if active:
            for record in records:
                if normalize_douyin_account_id(record.account_id) == active:
                    return record
        return records[0]

    def load_records(self, *, include_legacy: bool = True) -> list[DouyinCookieRecord]:
        records = self._load_multi_records()
        if include_legacy:
            legacy = self._load_legacy_record()
            if legacy is not None and not any(
                normalize_douyin_account_id(record.account_id) == "primary"
                for record in records
            ):
                records.insert(0, legacy)

        deduped: list[DouyinCookieRecord] = []
        seen_ids: set[str] = set()
        seen_cookies: set[str] = set()
        for record in records:
            account_id = normalize_douyin_account_id(record.account_id)
            cookie = record.cookie.strip()
            if not cookie or account_id in seen_ids or cookie in seen_cookies:
                continue
            seen_ids.add(account_id)
            seen_cookies.add(cookie)
            deduped.append(
                DouyinCookieRecord(
                    cookie=cookie,
                    source=record.source.strip() or "unknown",
                    account_id=account_id,
                    label=record.label.strip(),
                    updated_at=record.updated_at.strip(),
                )
            )
        return sorted(deduped, key=lambda record: _douyin_account_sort_key(record.account_id))

    def account_count(self) -> int:
        return len(self.load_records(include_legacy=True))

    def set_active_account(self, account_id: str) -> None:
        records = self.load_records(include_legacy=True)
        normalized_account_id = normalize_douyin_account_id(account_id)
        if not any(record.account_id == normalized_account_id for record in records):
            return
        self._write_records(records, active_account_id=normalized_account_id)

    def account_id_for_cookie(self, cookie: str) -> str:
        """Choose the best account slot for an incoming Cookie header."""

        normalized = cookie.strip()
        if not normalized:
            return "primary"
        incoming_account_key = douyin_cookie_account_key(normalized)
        incoming_fingerprint = douyin_cookie_fingerprint(normalized)
        records = self.load_records(include_legacy=True)
        for record in records:
            if record.cookie.strip() == normalized:
                return record.account_id
            if (
                incoming_account_key
                and douyin_cookie_account_key(record.cookie) == incoming_account_key
            ):
                return record.account_id
            if (
                incoming_fingerprint
                and douyin_cookie_fingerprint(record.cookie) == incoming_fingerprint
            ):
                return record.account_id

        existing_ids = {record.account_id for record in records}
        if "primary" not in existing_ids:
            return "primary"
        for index in range(2, 100):
            candidate = f"account{index}"
            if candidate not in existing_ids:
                return candidate
        return "account99"

    def clear_cookie(self, account_id: str | None = None) -> None:
        if account_id is None:
            if self._legacy_cookie_path.exists():
                self._legacy_cookie_path.unlink()
            if self._multi_cookie_path.exists():
                self._multi_cookie_path.unlink()
            return

        normalized_account_id = normalize_douyin_account_id(account_id)
        records = [
            record
            for record in self.load_records(include_legacy=True)
            if record.account_id != normalized_account_id
        ]
        self._write_records(records, active_account_id=records[0].account_id if records else "")
        if normalized_account_id == "primary" and self._legacy_cookie_path.exists():
            self._legacy_cookie_path.unlink()

    def _write_records(
        self,
        records: list[DouyinCookieRecord],
        *,
        active_account_id: str = "",
    ) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        normalized_active = (
            normalize_douyin_account_id(active_account_id) if active_account_id else ""
        )
        ordered_records = sorted(
            records,
            key=lambda record: _douyin_account_sort_key(record.account_id),
        )
        payload = {
            "active_account_id": normalized_active,
            "accounts": [
                {
                    "account_id": normalize_douyin_account_id(record.account_id),
                    "label": record.label.strip(),
                    "cookie": record.cookie.strip(),
                    "source": record.source.strip() or "unknown",
                    "updated_at": record.updated_at.strip(),
                }
                for record in ordered_records
                if record.cookie.strip()
            ],
        }
        with open(self._multi_cookie_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _write_legacy_cookie(self, cookie: str, *, source: str = "unknown") -> None:
        with open(self._legacy_cookie_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "cookie": cookie.strip(),
                    "source": source.strip() or "unknown",
                },
                f,
                ensure_ascii=False,
            )

    def _load_multi_records(self) -> list[DouyinCookieRecord]:
        if not self._multi_cookie_path.exists():
            return []
        with open(self._multi_cookie_path, encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return []
        raw_accounts = payload.get("accounts", [])
        if not isinstance(raw_accounts, list):
            return []
        records: list[DouyinCookieRecord] = []
        for raw in raw_accounts:
            if not isinstance(raw, dict):
                continue
            cookie = str(raw.get("cookie", "") or "").strip()
            if not cookie:
                continue
            records.append(
                DouyinCookieRecord(
                    cookie=cookie,
                    source=str(raw.get("source", "") or "unknown").strip() or "unknown",
                    account_id=normalize_douyin_account_id(raw.get("account_id", "")),
                    label=str(raw.get("label", "") or "").strip(),
                    updated_at=str(raw.get("updated_at", "") or "").strip(),
                )
            )
        return records

    def _load_legacy_record(self) -> DouyinCookieRecord | None:
        if not self._legacy_cookie_path.exists():
            return None
        with open(self._legacy_cookie_path, encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return None
        cookie = str(payload.get("cookie", "") or "").strip()
        if not cookie:
            return None
        return DouyinCookieRecord(
            cookie=cookie,
            source=str(payload.get("source", "") or "unknown").strip() or "unknown",
            account_id="primary",
            label="",
            updated_at="",
        )

    def _load_active_account_id(self) -> str:
        if not self._multi_cookie_path.exists():
            return ""
        with open(self._multi_cookie_path, encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return ""
        return normalize_douyin_account_id(payload.get("active_account_id", ""))


def normalize_douyin_account_id(value: object) -> str:
    """Return a stable filesystem-safe Douyin account id."""

    raw = str(value or "").strip().lower()
    if raw in {"", "default", "main"}:
        return "primary"
    normalized = sub(r"[^a-z0-9_.-]+", "_", raw).strip("._-")
    return (normalized or "primary")[:64]


def _douyin_account_sort_key(account_id: str) -> tuple[int, int, str]:
    normalized = normalize_douyin_account_id(account_id)
    if normalized == "primary":
        return (0, 0, normalized)
    if normalized.startswith("account"):
        suffix = normalized.removeprefix("account")
        if suffix.isdigit():
            return (1, int(suffix), normalized)
    return (2, 0, normalized)


def _parse_douyin_cookie(cookie: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in str(cookie or "").split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip()
        if name and value:
            parsed[name] = value
    return parsed


def douyin_cookie_account_key(cookie: str) -> str:
    """Return the most stable available account key from a Douyin Cookie."""

    parsed = _parse_douyin_cookie(cookie)
    for primary_name in ("uid_tt", "uid_tt_ss"):
        value = parsed.get(primary_name)
        if value:
            return f"{primary_name}={value}"
    for secondary_name in ("sessionid", "sessionid_ss", "sid_tt"):
        value = parsed.get(secondary_name)
        if value:
            return f"{secondary_name}={value}"
    return ""


def douyin_cookie_fingerprint(cookie: str) -> str:
    """Return a stable-ish account fingerprint from important Cookie fields."""

    parsed = _parse_douyin_cookie(cookie)
    identity_names = (
        "sessionid",
        "sessionid_ss",
        "sid_guard",
        "sid_tt",
        "uid_tt",
        "uid_tt_ss",
        "passport_assist_user",
        "passport_mfa_token",
    )
    pairs = [f"{name}={parsed[name]}" for name in identity_names if parsed.get(name)]
    if pairs:
        return ";".join(pairs)
    return ""


def resolve_douyin_cookie(
    *,
    data_dir: Path,
    cookie_env: str = "OPENBILICLAW_DOUYIN_COOKIE",
) -> str:
    """Resolve Douyin Cookie for direct discovery.

    The environment variable remains the explicit override for debugging,
    while the browser extension can keep ``data/douyin_cookie.json`` fresh
    for normal use.
    """
    env_cookie = os.environ.get(cookie_env, "").strip()
    if env_cookie:
        return env_cookie
    return DouyinCookieManager(data_dir).load_cookie()


def resolve_douyin_cookie_records(
    *,
    data_dir: Path,
    cookie_env: str = "OPENBILICLAW_DOUYIN_COOKIE",
    extra_cookie_envs: tuple[str, ...] | list[str] = (),
) -> list[DouyinCookieRecord]:
    """Resolve every available Douyin account Cookie.

    Env cookies are returned first and never persisted. The configured
    ``cookie_env`` remains the primary override; ``<cookie_env>_2`` is accepted
    as a lightweight second-account override for single-instance deployments.
    Persisted accounts from ``douyin_cookies.json`` follow, with legacy
    ``douyin_cookie.json`` folded in as account ``primary``.
    """

    records: list[DouyinCookieRecord] = []
    env_names = [str(cookie_env or "").strip()]
    env_names.extend(str(name or "").strip() for name in extra_cookie_envs)
    if env_names[0]:
        env_names.append(f"{env_names[0]}_2")

    seen_envs: set[str] = set()
    for index, env_name in enumerate(env_names):
        if not env_name or env_name in seen_envs:
            continue
        seen_envs.add(env_name)
        cookie = os.environ.get(env_name, "").strip()
        if not cookie:
            continue
        account_id = "env" if index == 0 else normalize_douyin_account_id(env_name)
        records.append(
            DouyinCookieRecord(
                cookie=cookie,
                source=f"env:{env_name}",
                account_id=account_id,
                label=env_name,
            )
        )

    records.extend(DouyinCookieManager(data_dir).load_records(include_legacy=True))

    deduped: list[DouyinCookieRecord] = []
    seen_cookies: set[str] = set()
    for record in records:
        cookie = record.cookie.strip()
        if not cookie or cookie in seen_cookies:
            continue
        seen_cookies.add(cookie)
        deduped.append(record)
    return deduped
