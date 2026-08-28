"""app.core.paths — Phase 10 P0-2 (docs/phase-10/ARCHITECTURE-AUDIT.md
§5-6): real, per-platform app-data resolution, and the separate
bundled-resource resolution a frozen sidecar needs for Alembic's
migrations/ (which Alembic loads from disk, not via a normal import).
"""

from __future__ import annotations

from pathlib import Path

from app.core.paths import is_frozen, resolve_app_data_dir, resolve_bundled_resource_dir


class TestResolveAppDataDir:
    def test_explicit_override_always_wins(self, monkeypatch):
        monkeypatch.setenv("VEYRA_APP_DATA_DIR", "/custom/veyra-data")
        monkeypatch.setattr("sys.platform", "win32")
        assert resolve_app_data_dir() == Path("/custom/veyra-data")

    def test_windows_uses_appdata_env_var(self, monkeypatch):
        monkeypatch.delenv("VEYRA_APP_DATA_DIR", raising=False)
        monkeypatch.setattr("sys.platform", "win32")
        monkeypatch.setenv("APPDATA", r"C:\Users\test\AppData\Roaming")
        result = resolve_app_data_dir()
        assert result == Path(r"C:\Users\test\AppData\Roaming") / "VEYRA"

    def test_windows_falls_back_when_appdata_env_var_missing(self, monkeypatch):
        monkeypatch.delenv("VEYRA_APP_DATA_DIR", raising=False)
        monkeypatch.setattr("sys.platform", "win32")
        monkeypatch.delenv("APPDATA", raising=False)
        result = resolve_app_data_dir()
        assert result.name == "VEYRA"
        assert "AppData" in str(result)

    def test_macos_uses_application_support(self, monkeypatch):
        monkeypatch.delenv("VEYRA_APP_DATA_DIR", raising=False)
        monkeypatch.setattr("sys.platform", "darwin")
        result = resolve_app_data_dir()
        assert result == Path.home() / "Library" / "Application Support" / "VEYRA"

    def test_linux_uses_xdg_data_home_when_set(self, monkeypatch):
        monkeypatch.delenv("VEYRA_APP_DATA_DIR", raising=False)
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", "/home/test/.data")
        assert resolve_app_data_dir() == Path("/home/test/.data") / "veyra"

    def test_linux_falls_back_to_local_share(self, monkeypatch):
        monkeypatch.delenv("VEYRA_APP_DATA_DIR", raising=False)
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        assert resolve_app_data_dir() == Path.home() / ".local" / "share" / "veyra"

    def test_never_resolves_inside_the_source_tree(self, monkeypatch):
        # The whole point of P0-2: this must never again be
        # __file__-relative — it should not contain "services/local-api"
        # under any platform branch.
        monkeypatch.delenv("VEYRA_APP_DATA_DIR", raising=False)
        for plat in ("win32", "darwin", "linux"):
            monkeypatch.setattr("sys.platform", plat)
            assert "services" not in str(resolve_app_data_dir()).replace("\\", "/")


class TestResolveBundledResourceDir:
    def test_source_checkout_resolves_to_the_real_repo_root(self):
        result = resolve_bundled_resource_dir()
        assert (result / "database" / "alembic.ini").exists()
        assert (result / "database" / "migrations").is_dir()

    def test_frozen_build_resolves_to_meipass(self, monkeypatch, tmp_path):
        monkeypatch.setattr("sys.frozen", True, raising=False)
        monkeypatch.setattr("sys._MEIPASS", str(tmp_path), raising=False)
        assert resolve_bundled_resource_dir() == tmp_path

    def test_is_frozen_reflects_sys_frozen(self, monkeypatch):
        monkeypatch.delattr("sys.frozen", raising=False)
        assert is_frozen() is False
        monkeypatch.setattr("sys.frozen", True, raising=False)
        assert is_frozen() is True
