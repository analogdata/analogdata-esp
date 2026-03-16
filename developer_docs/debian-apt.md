# Debian / APT — How it Works and How to Set It Up

There are two levels here:

| Approach | User experience | Complexity |
|---|---|---|
| **Direct .deb** | `sudo dpkg -i analogdata-esp.deb` | Zero setup — just link to file |
| **Custom APT repo** | `sudo apt install analogdata-esp` | One-time repo setup — then works like any apt package |

---

## How APT finds packages

When a user runs `sudo apt install analogdata-esp`, APT:

1. Reads `/etc/apt/sources.list.d/` for repo URLs
2. Downloads the `Packages` index from each repo
3. Finds `analogdata-esp` in the index
4. Downloads the matching `.deb` from the repo
5. Runs `dpkg -i` to install it

Your job as a maintainer: **host a repo** that APT can read. Two practical options are covered below.

---

## Option A — Direct .deb (simplest)

No repo needed. Users download the `.deb` directly from GitHub Releases.

GitHub Actions already builds `analogdata-esp_X.Y.Z_amd64.deb` on every tagged release.

**User install commands:**
```bash
# Download
curl -LO https://github.com/analogdata/analogdata-esp/releases/download/v0.1.0/analogdata-esp_0.1.0_amd64.deb

# Install
sudo dpkg -i analogdata-esp_0.1.0_amd64.deb

# Or combined (apt handles deps automatically)
sudo apt install ./analogdata-esp_0.1.0_amd64.deb

# Verify
analogdata-esp --help
analogdata-esp doctor
```

**To uninstall:**
```bash
sudo dpkg -r analogdata-esp
# or
sudo apt remove analogdata-esp
```

**Updating:** Users re-download the new `.deb` and run `dpkg -i` again. dpkg upgrades the package in place.

---

## Option B — Packagecloud APT repo (recommended — free tier available)

[Packagecloud.io](https://packagecloud.io) hosts your APT (and RPM) repo for free on the free tier. It generates the `Packages` index and GPG signing automatically.

### Part 1: Set up Packagecloud (one-time)

**1. Create an account**
Sign up at https://packagecloud.io — free tier supports public repos.

**2. Create a repository**
- Click **New Repository**
- Name: `analogdata-esp`
- Type: **Deb** (for APT)
- Visibility: **Public**

**3. Note your repository details**
After creation you'll see:
```
Repository: https://packagecloud.io/analogdata/analogdata-esp
```
And an installation script URL like:
```
https://packagecloud.io/install/repositories/analogdata/analogdata-esp/script.deb.sh
```

**4. Get your API token**
- Go to Account Settings → API Token
- Copy the token — you'll add it to GitHub Secrets

**5. Add to GitHub Secrets**
In your GitHub repo: **Settings → Secrets and variables → Actions → New secret**
- Name: `PACKAGECLOUD_TOKEN`
- Value: (your token)

### Part 2: Auto-upload .deb in GitHub Actions

Add this job to `.github/workflows/release.yml` after the `release` job:

```yaml
  packagecloud:
    name: Upload to Packagecloud APT repo
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Download Linux artifact
        uses: actions/download-artifact@v4
        with:
          name: analogdata-esp-linux
          path: dist/

      - name: Install packagecloud CLI
        run: gem install package_cloud

      - name: Push .deb to Packagecloud
        env:
          PACKAGECLOUD_TOKEN: ${{ secrets.PACKAGECLOUD_TOKEN }}
        run: |
          VERSION="${GITHUB_REF_NAME#v}"
          package_cloud push analogdata/analogdata-esp/ubuntu/jammy \
            dist/analogdata-esp_${VERSION}_amd64.deb
          package_cloud push analogdata/analogdata-esp/ubuntu/focal \
            dist/analogdata-esp_${VERSION}_amd64.deb
          package_cloud push analogdata/analogdata-esp/debian/bookworm \
            dist/analogdata-esp_${VERSION}_amd64.deb
```

### Part 3: User install experience (after Packagecloud setup)

```bash
# Add the repo and install (one-time setup)
curl -s https://packagecloud.io/install/repositories/analogdata/analogdata-esp/script.deb.sh | sudo bash
sudo apt install analogdata-esp

# Future updates
sudo apt update && sudo apt upgrade analogdata-esp
```

That's it. Users never need to download a `.deb` manually again.

---

## Option C — Self-hosted APT repo on GitHub Pages

If you want to avoid third-party services, you can host the APT repo on GitHub Pages. This is more work but fully self-contained.

### How it works

```
GitHub Pages repo (analogdata/apt-repo)  ← users point apt sources here
├── dists/
│   └── stable/
│       ├── Release          ← GPG-signed metadata
│       ├── Release.gpg
│       └── main/
│           └── binary-amd64/
│               └── Packages.gz   ← index of all .deb files
└── pool/
    └── main/
        └── analogdata-esp_0.1.0_amd64.deb
```

### One-time setup

**1. Create a GPG signing key (on your dev machine)**
```bash
gpg --batch --gen-key <<EOF
Key-Type: RSA
Key-Length: 4096
Name-Real: Analog Data
Name-Email: packages@analogdata.io
Expire-Date: 0
%no-passphrase
EOF

# Export the public key (users will import this to trust your repo)
gpg --armor --export packages@analogdata.io > analogdata.gpg.key
```

**2. Export the private key for GitHub Actions**
```bash
gpg --armor --export-secret-keys packages@analogdata.io | base64
```
Add to GitHub Secrets as `GPG_PRIVATE_KEY`.
Also add the passphrase (if any) as `GPG_PASSPHRASE`.

**3. Create the GitHub Pages repo**
Create a new GitHub repo: `analogdata/apt-repo`
- Enable GitHub Pages: Settings → Pages → Branch: `main`, folder: `/ (root)`

**4. Add a workflow to build and publish the APT repo**

Create `.github/workflows/apt-repo.yml` in the `apt-repo` repo:

```yaml
name: Update APT repo

on:
  workflow_dispatch:
    inputs:
      deb_url:
        description: URL of .deb file to add
        required: true
      version:
        description: Version (e.g. 0.2.0)
        required: true

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Import GPG key
        run: |
          echo "${{ secrets.GPG_PRIVATE_KEY }}" | base64 -d | gpg --import

      - name: Download .deb
        run: |
          mkdir -p pool/main
          curl -Lo pool/main/analogdata-esp_${{ inputs.version }}_amd64.deb "${{ inputs.deb_url }}"

      - name: Generate Packages index
        run: |
          mkdir -p dists/stable/main/binary-amd64
          dpkg-scanpackages pool/main /dev/null | gzip -9c > dists/stable/main/binary-amd64/Packages.gz
          dpkg-scanpackages pool/main /dev/null > dists/stable/main/binary-amd64/Packages

      - name: Generate Release file
        run: |
          cd dists/stable
          cat > Release <<EOF
          Origin: Analog Data
          Label: analogdata-esp
          Suite: stable
          Codename: stable
          Architectures: amd64
          Components: main
          Description: Analog Data ESP-IDF CLI
          EOF
          apt-ftparchive release . >> Release
          gpg --armor --detach-sign --output Release.gpg Release
          gpg --clearsign --output InRelease Release

      - name: Commit and push
        run: |
          git config user.email "actions@github.com"
          git config user.name "GitHub Actions"
          git add .
          git commit -m "Add analogdata-esp v${{ inputs.version }}"
          git push
```

**5. User install experience**

```bash
# Import your GPG key (one-time)
curl -fsSL https://analogdata.github.io/apt-repo/analogdata.gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/analogdata-archive-keyring.gpg

# Add repo (one-time)
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/analogdata-archive-keyring.gpg] https://analogdata.github.io/apt-repo stable main" | sudo tee /etc/apt/sources.list.d/analogdata.list

# Install
sudo apt update
sudo apt install analogdata-esp

# Future updates
sudo apt update && sudo apt upgrade analogdata-esp
```

---

## Comparison: which APT approach to use?

| | Direct .deb | Packagecloud | GitHub Pages APT |
|---|---|---|---|
| Setup time | Zero | ~30 min | ~2 hours |
| User experience | Download manually | `apt install` | `apt install` |
| Auto-updates via apt | No | Yes | Yes |
| Cost | Free | Free tier | Free |
| GPG signing | No | Packagecloud handles | You manage |
| Best for | Getting started | Most teams | Full control |

**Recommendation:** Start with **direct .deb** (zero work, GitHub Actions already does it). Move to **Packagecloud** when you have regular users who expect `apt upgrade` to work.

---

## Verifying your .deb package

```bash
# Inspect package contents before distributing
dpkg -c dist/analogdata-esp_0.1.0_amd64.deb

# Inspect package metadata
dpkg -I dist/analogdata-esp_0.1.0_amd64.deb

# Test install in a Docker container (clean environment)
docker run --rm -it ubuntu:22.04 bash
# Inside the container:
apt update
dpkg -i /path/to/analogdata-esp_0.1.0_amd64.deb
analogdata-esp --help
```
