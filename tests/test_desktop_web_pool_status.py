from pathlib import Path


def test_desktop_pool_status_distinguishes_pending_from_swappable() -> None:
    app_js = Path("src/openbiliclaw/web/desktop/assets/js/app.js").read_text()

    assert "pool_pending_count" in app_js
    assert "pool_raw_count" in app_js
    assert "找到 ${runtime.pool_pending_count} 条素材，正在整理成可换内容" in app_js
    assert "整理好就能换，不会把素材数当可换数" in app_js
