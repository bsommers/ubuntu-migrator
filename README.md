# ubuntu-migrator
Helps you migrate package lists from previous Installs Ubuntu to a new fresh Ubuntu install.  This is ideal for quickly setting up a new machine to match an existing development environment.


## Description

This Python code provides a user-friendly terminal interface for batch-installing packages on Debian-based systems like Ubuntu. It reads a list of packages from a manifest file and automates the installation process, providing detailed feedback and logging.

## Features

- Interactive UI: A two-pane curses-based interface shows the package list on the left and live installation output on the right.
- Flicker-Free & Responsive: The display is optimized to only redraw what has changed, providing a smooth experience.
- Colorblind-Friendly: Uses a color palette designed to be distinguishable for most forms of color blindness.
- Resumes on Restart: The script logs successful and failed installations. If restarted, it automatically skips packages that have already been processed.
- System-Aware: Automatically skips packages that are already installed on the system, including those from the base installation.
- Detailed Stats: A toggleable stats window shows progress, elapsed time, and an estimated time remaining (ETR).
- In-App Help: A toggleable help screen explains the UI symbols and keyboard shortcuts.
- Logging: All successful installs are logged to installed_successfully.list and failures to failed.list.

## Requirements

- Python 3
- A Debian-based Linux distribution (e.g., Ubuntu, Mint)

Note: The script must be run with sudo privileges (it will auto-promote itself if needed) since packages are being installed.

## How to Use
1. Generate Your Package List
Before you can use the installer, you need to create the installed_packages.list manifest file. You can generate this file from an existing, configured system.

Run the following command on the machine you want to clone the package list from:

```
dpkg --get-selections | grep -v deinstall > installed_packages.list
```

(Note: grep -v deinstall is added to filter out packages that have been removed.)

This will create a file named installed_packages.list in your current directory. Copy this file to the same directory where the install_packages.py script is located on your new machine.

2. Run the Installer
With installed_packages.list in the same directory, make the script executable and run it:

```bash
chmod +x ubuntu-package-installer.py
./ubuntu-package-installer.py
```

The script will check for root privileges and re-launch with sudo if necessary, prompting for your password. The terminal user interface (TUI) will then launch.

## Controls

- `< Up/Down >`  Arrows: Scroll the package list line-by-line.
- `< PageUp >` / `< PageDown >`: Scroll the package list a full page at a time.
- `s` key: Toggle the statistics window on and off.
- `h` key: Toggle the help overlay on and off.
- `q` key: Quit the application at any time.
