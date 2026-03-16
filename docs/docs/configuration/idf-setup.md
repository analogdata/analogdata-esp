# ESP-IDF Configuration

This guide explains how `analogdata-esp` finds and configures your ESP-IDF installation.

---

## Auto-Detection

When you run `analogdata-esp config idf`, the tool searches for ESP-IDF installations in the following order:

1. **`IDF_PATH` environment variable** — if set, this path is used first
2. **Windsurf extension** — checks the default location used by the ESP-IDF VS Code / Windsurf extension
3. **EIM (ESP-IDF Installation Manager)** — checks paths managed by `eim`
4. **`~/esp/esp-idf`** — the default manual installation path on macOS/Linux
5. **`C:\Espressif`** — the default installer path on Windows

---

## Multiple Installations

If more than one ESP-IDF installation is detected, the wizard lists all of them and lets you choose:

```
Found multiple ESP-IDF installations:

  [1] /home/user/esp/esp-idf-v5.3    (v5.3.0)
  [2] /home/user/esp/esp-idf-v5.2    (v5.2.3)
  [3] /home/user/esp/esp-idf         (v5.1.0)

  [0] Enter a custom path

Select installation [1]:
```

Enter the number corresponding to the installation you want to use, or enter `0` to specify a custom path.

---

## Running the Configuration Wizard

```bash
analogdata-esp config idf
```

### Example session (auto-detected path)

```
Searching for ESP-IDF installations...

Found: /home/user/esp/esp-idf (v5.3.0)

Use this installation? [Y/n]: Y

Detecting tools path...
Tools path: /home/user/.espressif

Configuration saved to ~/.config/analogdata-esp/config.toml
```

### Example session (custom path)

```
Searching for ESP-IDF installations...

No installations found automatically.

Enter the path to your ESP-IDF installation: /opt/esp/esp-idf-5.2

Detecting tools path for /opt/esp/esp-idf-5.2...
Tools path: /home/user/.espressif

Configuration saved to ~/.config/analogdata-esp/config.toml
```

---

## What Gets Saved

After running the wizard, your `config.toml` will contain:

```toml
[idf]
path = "/home/user/esp/esp-idf"
tools_path = "/home/user/.espressif"
```

- `path` — the root directory of the ESP-IDF installation (contains `idf.py`)
- `tools_path` — the directory containing compiled compiler toolchains and utilities

---

## Changing IDF Version

To switch to a different ESP-IDF version, run the wizard again:

```bash
analogdata-esp config idf
```

Select the new installation from the list (or enter a custom path). The config file is overwritten with the new values.

---

## Overriding with an Environment Variable

The `IDF_PATH` environment variable always takes precedence over the saved config:

```bash
export IDF_PATH=/path/to/esp-idf
analogdata-esp agent  # uses /path/to/esp-idf regardless of config.toml
```

This is useful in CI pipelines or when switching between projects that require different IDF versions without permanently changing your config.

---

## Verifying the Configuration

Run the `doctor` command to confirm ESP-IDF is configured and working:

```bash
analogdata-esp doctor
```

Expected output when everything is correct:

```
[OK] ESP-IDF: /home/user/esp/esp-idf (v5.3.0)
[OK] IDF tools: /home/user/.espressif
[OK] idf.py found and executable
```
