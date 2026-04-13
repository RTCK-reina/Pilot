"""Tests for settings read/write and cache."""

from __future__ import annotations

from pilot_common.config import (
    delete_setting,
    get_all_settings,
    get_setting,
    get_setting_json,
    invalidate_cache,
    set_setting,
    set_setting_json,
)


class TestSettings:
    def setup_method(self):
        invalidate_cache()

    def test_get_missing_returns_default(self, db):
        assert get_setting(db, "nonexistent") is None
        assert get_setting(db, "nonexistent", "fallback") == "fallback"

    def test_set_and_get(self, db):
        set_setting(db, "locale", "ja")
        assert get_setting(db, "locale") == "ja"

    def test_update_existing(self, db):
        set_setting(db, "locale", "ja")
        set_setting(db, "locale", "en")
        assert get_setting(db, "locale") == "en"

    def test_delete(self, db):
        set_setting(db, "locale", "ja")
        delete_setting(db, "locale")
        assert get_setting(db, "locale") is None

    def test_json_round_trip(self, db):
        rates = {"type": "tou", "night": 12.5, "day": 28.0, "peak": 38.0}
        set_setting_json(db, "electricity_rate_home", rates)
        result = get_setting_json(db, "electricity_rate_home")
        assert result == rates

    def test_json_default(self, db):
        assert get_setting_json(db, "missing_json", {"default": True}) == {"default": True}

    def test_get_all(self, db):
        set_setting(db, "locale", "ja")
        set_setting(db, "currency", "JPY")
        all_settings = get_all_settings(db)
        assert all_settings["locale"] == "ja"
        assert all_settings["currency"] == "JPY"


class TestCache:
    def setup_method(self):
        invalidate_cache()

    def test_cache_hit(self, db):
        set_setting(db, "locale", "ja")
        get_setting(db, "locale")  # populate cache

        # Modify DB directly (bypass cache)
        db.execute("UPDATE settings SET value = 'en' WHERE key = 'locale'")
        db.commit()

        # Should still return cached value
        assert get_setting(db, "locale") == "ja"

    def test_invalidate_single(self, db):
        set_setting(db, "locale", "ja")
        get_setting(db, "locale")

        db.execute("UPDATE settings SET value = 'en' WHERE key = 'locale'")
        db.commit()
        invalidate_cache("locale")

        assert get_setting(db, "locale") == "en"

    def test_invalidate_all(self, db):
        set_setting(db, "locale", "ja")
        set_setting(db, "currency", "JPY")
        get_setting(db, "locale")
        get_setting(db, "currency")

        invalidate_cache()

        db.execute("UPDATE settings SET value = 'en' WHERE key = 'locale'")
        db.commit()
        assert get_setting(db, "locale") == "en"
