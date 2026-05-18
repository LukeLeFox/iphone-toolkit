# iPhone Toolkit

A personal, experimental, cross-platform GUI utility for iPhone firmware workflows.

The project focuses on **operating system management only**:

- device detection
- Normal / Recovery / DFU state detection
- enter Recovery Mode
- exit Recovery Mode
- guided IPSW dirty flash / update
- full erase restore with strong confirmation
- IPSW compatibility checks
- IPSW signing pre-flight check
- AppleDB device page lookup
- live iOS syslog
- automatic operation logs

> This is not an Apple product and is not affiliated with Apple.

---

## Current status

This project is currently a personal alpha-stage tool.

Tested manually:

| Device | iOS | Host OS | Operation | Result |
|---|---:|---|---|---|
| iPhone 13 Pro | iOS 26.5 | Kubuntu live | Dirty Flash / Update IPSW | Successful, data preserved |

---

## Safety model

The tool exposes two separate firmware workflows.

| GUI action | Backend command | Data impact |
|---|---|---|
| Dirty Flash / Update | `idevicerestore firmware.ipsw` | Attempts to reinstall iOS while preserving data |
| Erase Restore | `idevicerestore --erase firmware.ipsw` | Deletes all data and performs a full restore |

The destructive **Erase Restore** workflow requires:

1. first confirmation dialog
2. final typed confirmation: `ERASE`

The tool does not hide or bypass Apple restore restrictions. If an IPSW is not signed, Apple TSS validation will still reject the restore.

---

## Features

### Device management

- Detect iPhone in Normal Mode
- Detect Recovery / DFU via `irecovery`
- Enter Recovery Mode
- Exit Recovery Mode
- Read device info via `ideviceinfo`

### Firmware workflow

- Select local `.ipsw`
- Read `BuildManifest.plist`
- Extract:
  - iOS version
  - build number
  - supported ProductTypes
- Check if the IPSW supports the detected device
- Check signing status online
- Run update restore
- Run erase restore with double confirmation

### Pre-flight Check

The Pre-flight Check shows an immediate table with:

- required backend tools
- optional backend tools
- IPSW file validity
- IPSW compatibility
- IPSW signing status
- device state
- log directory writability

### AppleDB integration

After detecting the device model, the tool can open the matching AppleDB device page.

Example:

```text
iPhone14,2 -> https://appledb.dev/device/iPhone-13-Pro-series.html
```

### Log Center

The separate Log Center window includes:

- app console
- live iOS syslog
- save console logs
- save syslog
- clear logs
- open log directory

Logs are stored under:

```text
~/.iphone-toolkit/logs/
```

---

## External dependencies

The packaged application does not bundle Apple/mobile-device backend tools.

Install them on the host OS.

### Linux / Ubuntu / Kubuntu

```bash
sudo apt update
sudo apt install -y \
  python3 \
  python-is-python3 \
  python3-tk \
  libimobiledevice-utils \
  irecovery \
  usbmuxd \
  ideviceinstaller \
  idevicerestore
```

Useful checks:

```bash
which idevice_id
which ideviceinfo
which ideviceenterrecovery
which idevicerestore
which irecovery
which idevicesyslog
```

### macOS

Install Homebrew first, then:

```bash
brew install libimobiledevice ideviceinstaller idevicerestore libirecovery
```

Depending on Homebrew package availability, some tools may need to be installed from upstream projects or alternative taps.

### Windows

Windows support is planned through packaged GUI builds.

The host still needs Apple mobile device drivers / Apple Devices / iTunes components and compatible libimobiledevice backend binaries available in `PATH`.

---

## Development

Clone the repository:

```bash
git clone https://github.com/LukeLeFox/iphone-toolkit.git
cd iphone-toolkit
```

Run directly without installing the package:

```bash
PYTHONPATH=src python -m iphone_toolkit
```

On Linux, a convenience launcher can be used:

```bash
./run-dev.sh
```

Syntax check:

```bash
python -m py_compile \
  src/iphone_toolkit/core/*.py \
  src/iphone_toolkit/ui/*.py
```

Or:

```bash
python -m compileall src
```

---

## Build locally with PyInstaller

Install development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

### Linux

```bash
pyinstaller --noconfirm --clean --onefile --windowed \
  --name iPhoneToolkit \
  src/iphone_toolkit/__main__.py
```

Output:

```text
dist/iPhoneToolkit
```

### Windows

```powershell
pyinstaller --noconfirm --clean --onefile --windowed `
  --name iPhoneToolkit `
  src/iphone_toolkit/__main__.py
```

Output:

```text
dist/iPhoneToolkit.exe
```

### macOS

```bash
pyinstaller --noconfirm --clean --onedir --windowed \
  --name iPhoneToolkit \
  src/iphone_toolkit/__main__.py
```

Output:

```text
dist/iPhoneToolkit.app
```

---

## GitHub Actions builds

The repository includes a workflow that builds artifacts for:

- Linux
- Windows
- macOS

The workflow runs on:

- manual dispatch
- pushes to `main` / `master`
- tags matching `v*`

Artifacts are uploaded from the `dist/` directory.

---

## Disclaimer

This project is provided for personal, educational and laboratory use.

Use it only with devices you own or are authorized to service.

This project is not affiliated with Apple.

The author does not provide any warranty and is not responsible for:

- data loss
- failed restores
- device malfunction
- unsupported firmware use
- misuse of the tool

Always create a backup before running any firmware operation.

This tool is not intended for bypassing security mechanisms, activation lock, iCloud lock, ownership restrictions, or any other protection system.
