# Quick Start

## 1. Create your first project

```bash
analogdata-esp new blink
```

With a specific target:
```bash
analogdata-esp new sensor_node --target esp32s3
```

This will:

- Copy the project template
- Replace all placeholders with your project name
- Run `idf.py set-target` for your chip
- Run `idf.py reconfigure` to generate `compile_commands.json`
- Run `git init` and make an initial commit

## 2. Open in Windsurf / VSCode

```bash
cd blink
windsurf .   # or: code .
```

IntelliSense will work immediately — no red squiggles.

## 3. Build

```bash
idf.py build
```

## 4. Flash and monitor

```bash
# Find your port
ls /dev/tty.usbserial-*     # macOS
ls /dev/ttyUSB*              # Linux
# Windows: check Device Manager for COMx

idf.py -p /dev/tty.usbserial-XXXX flash monitor
```

## 5. Ask the AI agent

```bash
# Single question (auto-reads your build errors)
analogdata-esp agent "why is my task stack overflowing"

# Interactive chat
analogdata-esp agent --chat
```

## Project structure

After `analogdata-esp new blink`, your project looks like:

```
blink/
├── .clangd                  # Xtensa flag suppression
├── .gitignore
├── CMakeLists.txt
├── sdkconfig                # Generated after set-target
├── main/
│   ├── CMakeLists.txt
│   └── main.c               # Your entry point
├── build/
│   └── compile_commands.json  # Powers IntelliSense
└── .vscode/
    ├── c_cpp_properties.json
    ├── settings.json
    ├── launch.json
    └── extensions.json
```
