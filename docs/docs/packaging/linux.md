# Linux Installation

---

## Debian / Ubuntu (.deb Package)

### Option A — apt (recommended)

```bash
# Download the latest .deb package
curl -LO https://github.com/analogdata/analogdata-esp/releases/latest/download/analogdata-esp.deb

# Install with apt (handles dependencies automatically)
sudo apt install ./analogdata-esp.deb
```

### Option B — dpkg

```bash
curl -LO https://github.com/analogdata/analogdata-esp/releases/latest/download/analogdata-esp.deb
sudo dpkg -i analogdata-esp.deb
```

### Verify

```bash
analogdata-esp --help
```

### Uninstall

```bash
sudo apt remove analogdata-esp
# or
sudo dpkg -r analogdata-esp
```

---

## Direct Binary Download

Works on any Linux distribution (x86_64).

1. Go to the [GitHub Releases page](https://github.com/analogdata/analogdata-esp/releases/latest)
2. Download the Linux binary: `analogdata-esp-linux`
3. Install it:

```bash
chmod +x analogdata-esp-linux

# System-wide (requires sudo)
sudo mv analogdata-esp-linux /usr/local/bin/analogdata-esp

# Per-user (no sudo required)
mkdir -p ~/.local/bin
mv analogdata-esp-linux ~/.local/bin/analogdata-esp
```

If you used the per-user path, ensure `~/.local/bin` is in your `PATH`:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

4. Verify:

```bash
analogdata-esp --help
```

---

## pip / pipx

If you have Python 3.10+ installed:

```bash
# pipx (recommended — runs in an isolated environment)
pipx install analogdata-esp

# pip (global install)
pip install analogdata-esp
```

Install `pipx` if needed:

```bash
# Debian / Ubuntu
sudo apt install pipx
pipx ensurepath

# Fedora / RHEL
sudo dnf install pipx
```

### Uninstalling

```bash
pipx uninstall analogdata-esp
```

---

## From Source

```bash
git clone https://github.com/analogdata/analogdata-esp.git
cd analogdata-esp
uv sync
uv run analogdata-esp --help
```

See [Local Installation](../getting-started/local-install.md) for the full developer setup guide.

---

## Maintainer: Setting Up a Custom APT Repository

This section is for project maintainers who want to distribute `analogdata-esp` via a self-hosted APT repository.

### Option A — reprepro

`reprepro` is a simple tool for managing a Debian package repository on your own server.

```bash
sudo apt install reprepro

# Create the repository directory structure
mkdir -p /srv/apt/conf

# Create a distributions config
cat > /srv/apt/conf/distributions <<EOF
Origin: Analog Data
Label: analogdata
Codename: stable
Architectures: amd64
Components: main
Description: Analog Data packages
EOF

# Add the .deb package
reprepro -b /srv/apt includedeb stable analogdata-esp.deb
```

Serve `/srv/apt` over HTTPS (nginx, Apache, or an S3 static site), then users can add it as:

```bash
echo "deb [trusted=yes] https://apt.analogdata.io stable main" | sudo tee /etc/apt/sources.list.d/analogdata.list
sudo apt update
sudo apt install analogdata-esp
```

### Option B — Packagecloud

[Packagecloud](https://packagecloud.io) provides hosted APT/YUM repositories with a free tier for open-source projects. Push packages using the `package_cloud` CLI and users install by running the one-line setup script that Packagecloud generates.
