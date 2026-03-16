# analogdata-esp new

Scaffold a new ESP-IDF project from the Analog Data template.

## Usage

```bash
analogdata-esp new [NAME] [OPTIONS]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `NAME` | Project name. Snake_case recommended. Prompted if omitted. |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--target`, `-t` | `esp32` | Target chip |
| `--path`, `-p` | `cwd` | Parent directory for the project |
| `--no-git` | `false` | Skip `git init` |

## Supported targets

`esp32` · `esp32s2` · `esp32s3` · `esp32c2` · `esp32c3` · `esp32c6` · `esp32h2` · `esp32p4`

## Examples

```bash
# Minimal — prompts for name
analogdata-esp new

# With name
analogdata-esp new blink

# ESP32-S3 project
analogdata-esp new sensor_node --target esp32s3

# Specific output directory
analogdata-esp new ble_beacon --target esp32c3 --path ~/esp

# Skip git
analogdata-esp new scratch --no-git
```

## What gets created

```
<name>/
├── .clangd                  # Removes Xtensa GCC flags clangd can't parse
├── .gitignore               # Excludes build/, sdkconfig.old, .DS_Store
├── CMakeLists.txt           # Root cmake with your project name
├── main/
│   ├── CMakeLists.txt       # Component registration
│   └── main.c               # Entry point with FreeRTOS loop
└── .vscode/
    ├── c_cpp_properties.json  # Points IntelliSense to compile_commands.json
    ├── settings.json          # Disables CMake interference
    ├── launch.json            # JTAG debug config
    └── extensions.json        # Recommended extensions
```

After scaffolding, `idf.py set-target` and `idf.py reconfigure` are run automatically,
so `build/compile_commands.json` is ready before you open the editor.

## Notes

- Project names with hyphens or spaces are converted to snake_case automatically.
- If a project with the same name already exists in the output directory, the command exits with an error.
