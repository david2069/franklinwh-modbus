# Python Environment Setup

This library requires Python. The setup you need depends on what you're doing:

| Goal | What you need |
|------|--------------|
| **Run only** — use the CLI and library | Python + a virtual environment |
| **Develop** — modify the library, run tests | Python + virtual environment + dev dependencies |
| **Both** | Same as develop |

---

## 1. Get Python

### What version?

- **Minimum:** Python 3.8
- **Recommended:** Python 3.12 (used in CI and tested on hardware)
- **Avoid:** Python 3.7 and below — f-strings and `dataclasses` used throughout

Check your current version:

```bash
python3 --version
```

---

## 2. Platform Setup

=== "macOS"

    **Recommended: install Python via [Homebrew](https://brew.sh)**

    Homebrew manages Python cleanly, avoids conflicts with the macOS system Python, and makes upgrades easy.

    **Step 1 — Install Homebrew** (if you don't have it):

    ```bash
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    ```

    **Step 2 — Install Python:**

    ```bash
    brew install python
    ```

    This installs the latest stable Python and makes `python3` and `pip3` available on your PATH.

    **Step 3 — Verify:**

    ```bash
    python3 --version    # Should be 3.12+
    which python3        # Should be /opt/homebrew/bin/python3 (Apple Silicon)
                         # or /usr/local/bin/python3 (Intel)
    ```

    !!! tip "Don't use the system Python"
        macOS ships with `/usr/bin/python3` (typically 3.9). It's managed by the OS — never install packages into it. Always use Homebrew Python with a venv.

=== "Linux (Ubuntu / Debian)"

    Python 3.12 may not be in the default APT repos on older Ubuntu versions. Use the `deadsnakes` PPA:

    ```bash
    sudo apt update
    sudo apt install software-properties-common -y
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt update
    sudo apt install python3.12 python3.12-venv python3.12-dev -y
    ```

    Verify:

    ```bash
    python3.12 --version
    ```

    !!! note "Ubuntu 24.04+"
        Python 3.12 is in the standard repos — just `sudo apt install python3.12 python3.12-venv`.

=== "Windows"

    **Option A — Microsoft Store (easiest):**

    Open the Microsoft Store and search for **Python 3.12**. Install directly.

    **Option B — python.org installer:**

    1. Download from [python.org/downloads](https://www.python.org/downloads/)
    2. Run the installer — **check "Add Python to PATH"** before clicking Install

    **Option C — winget:**

    ```powershell
    winget install Python.Python.3.12
    ```

    Verify (in a new terminal):

    ```powershell
    python --version     # Windows uses `python`, not `python3`
    python -m pip --version
    ```

    !!! tip "Use PowerShell or Windows Terminal"
        Avoid `cmd.exe` — PowerShell handles paths and venvs much more reliably.

---

## 3. Virtual Environments

### Why use a virtual environment?

A virtual environment (`venv`) creates an **isolated Python installation** for your project. This means:

- Package versions for this project don't conflict with other projects
- You can `pip install` freely without affecting the system Python
- Easy to delete and recreate if something goes wrong
- Required for the Modbus library since it pulls in `pysunspec2` and `pymodbus`

**Never install packages with `pip install` globally** — always use a venv.

### Create and activate

=== "macOS / Linux"

    ```bash
    # Create the venv (do this once, inside the project folder)
    python3 -m venv venv

    # Activate it (do this every time you open a new terminal)
    source venv/bin/activate

    # Your prompt will show (venv) when active:
    # (venv) user@host modbus %
    ```

    Deactivate when done:
    ```bash
    deactivate
    ```

=== "Windows"

    ```powershell
    # Create the venv
    python -m venv venv

    # Activate it
    venv\Scripts\Activate.ps1

    # If you get a permission error, run once:
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    ```

    Deactivate:
    ```powershell
    deactivate
    ```

---

## 4. Install the Library

### Run only (no development)

Install from PyPI into your active venv:

```bash
pip install franklinwh-modbus
```

For the TUI monitor (`franklinwh_cli.py --monitor`), install with the `monitor` extra:

```bash
pip install "franklinwh-modbus[monitor]"
```

### Develop (editable install)

Clone the repo and install in editable (`-e`) mode with dev dependencies:

```bash
git clone https://github.com/david2069/franklinwh-modbus.git
cd franklinwh-modbus

python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\Activate.ps1

pip install -e ".[dev,monitor]"
```

The `-e` flag means changes you make to the source are immediately reflected — no reinstall needed.

Verify the install:

```bash
python3 -c "import franklinwh_modbus; print(franklinwh_modbus.__version__)"
```

---

## 5. Best Practices & Housekeeping

### Always work in the venv

Before running any commands, check your prompt shows `(venv)`. If not, run `source venv/bin/activate`.

### Keep dependencies up to date

```bash
pip install --upgrade franklinwh-modbus          # if installed from PyPI
pip install --upgrade pysunspec2 pymodbus rich   # individual packages
```

### Check what's installed

```bash
pip list                     # all packages in the venv
pip show franklinwh-modbus   # just this library
```

### Recreate a broken venv

Venvs are disposable — if something goes wrong, just delete and recreate:

```bash
deactivate
rm -rf venv/           # macOS/Linux
# rmdir /s venv        # Windows

python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev,monitor]"
```

### Don't commit the venv

The `venv/` directory is already in `.gitignore`. Never commit it — each developer creates their own.

### IDEs (VS Code, PyCharm)

Point your IDE to the venv interpreter so it finds all packages:

- **VS Code**: `Cmd+Shift+P` → *Python: Select Interpreter* → choose `./venv/bin/python`
- **PyCharm**: *Settings → Project → Python Interpreter* → Add Local → Existing Environment → `venv/bin/python`
