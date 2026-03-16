"""Shared pytest fixtures for analogdata-esp test suite."""

import copy
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def reset_default_settings():
    """
    Reset _DEFAULT_SETTINGS after every test to prevent mutation bleeding between tests.

    _deep_merge in settings.py performs a shallow copy, so nested dicts are shared.
    When a test mutates the returned settings dict (e.g. settings["ai"]["provider"] = "x"),
    it also mutates _DEFAULT_SETTINGS. This fixture restores the original state.
    """
    import analogdata_esp.core.settings as settings_module
    original = copy.deepcopy(settings_module._DEFAULT_SETTINGS)
    yield
    settings_module._DEFAULT_SETTINGS.clear()
    settings_module._DEFAULT_SETTINGS.update(original)
    for key, val in original.items():
        if isinstance(val, dict):
            settings_module._DEFAULT_SETTINGS[key] = copy.deepcopy(val)


@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """
    Patch CONFIG_DIR and CONFIG_FILE in the settings module to use a temp directory.
    This prevents tests from reading/writing to the real ~/.config/analogdata-esp.
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"

    import analogdata_esp.core.settings as settings_module
    monkeypatch.setattr(settings_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(settings_module, "CONFIG_FILE", config_file)

    return {"dir": config_dir, "file": config_file}


@pytest.fixture
def tmp_project_dir(tmp_path):
    """
    Create a minimal ESP-IDF project structure for testing context collection.

    Layout:
        <tmp_path>/
            CMakeLists.txt         (with project(test_blink))
            sdkconfig              (with CONFIG_IDF_TARGET and CONFIG_IDF_VER)
            build/
                log/
                    idf_py_stderr_output   (fake build errors)
    """
    project_dir = tmp_path / "test_blink"
    project_dir.mkdir()

    # CMakeLists.txt
    cmake = project_dir / "CMakeLists.txt"
    cmake.write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        'include($ENV{IDF_PATH}/tools/cmake/project.cmake)\n'
        "project(test_blink)\n"
    )

    # sdkconfig
    sdkconfig = project_dir / "sdkconfig"
    sdkconfig.write_text(
        'CONFIG_IDF_TARGET="esp32"\n'
        'CONFIG_IDF_VER="v5.2.0"\n'
        "CONFIG_FREERTOS_HZ=100\n"
    )

    # Build log with fake errors
    build_log_dir = project_dir / "build" / "log"
    build_log_dir.mkdir(parents=True)
    stderr_log = build_log_dir / "idf_py_stderr_output"
    stderr_log.write_text(
        "-- Configuring done\n"
        "main/main.c:10:5: error: 'gpio_pad_select_gpio' was not declared in this scope\n"
        "main/main.c:11:5: undefined reference to 'gpio_set_direction'\n"
        "ninja: build stopped: subcommand failed.\n"
        "CMake Error at CMakeLists.txt:3 (include): fatal: could not find IDF_PATH\n"
    )

    return project_dir


@pytest.fixture
def fake_idf_dir(tmp_path):
    """
    Create a fake ESP-IDF installation directory for testing config detection.

    Layout:
        <tmp_path>/fake-idf/
            tools/cmake/project.cmake
            version.txt  (contains "v5.2.0")
    """
    idf_dir = tmp_path / "fake-idf"
    idf_dir.mkdir()

    cmake_dir = idf_dir / "tools" / "cmake"
    cmake_dir.mkdir(parents=True)
    (cmake_dir / "project.cmake").write_text("# fake project.cmake\n")

    version_file = idf_dir / "version.txt"
    version_file.write_text("v5.2.0\n")

    return idf_dir
