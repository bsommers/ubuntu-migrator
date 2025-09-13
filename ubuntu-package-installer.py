#!/usr/bin/env python3

# MIT License
#
# Copyright (c) 2025 William Sommers 
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import curses
import subprocess
import os
import sys
import textwrap
import time
import fcntl
from enum import Enum
from datetime import datetime

# --- Configuration ---
MASTER_LIST = "installed_packages.list"
SUCCESS_LOG = "installed_successfully.list"
FAILURE_LOG = "failed.list"

class Status(Enum):
    QUEUED = 1
    PROCESSING = 2
    SUCCESS = 3
    FAILURE = 4
    SKIPPED = 5

# --- Curses Color Pair Definitions ---
COLOR_DEFAULT, COLOR_PROCESSING, COLOR_SUCCESS, COLOR_FAILURE, COLOR_SKIPPED, COLOR_BORDER, COLOR_ACCENT = 1, 2, 3, 4, 5, 6, 7

def setup_colors():
    """Initializes color pairs for the UI."""
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_DEFAULT, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_PROCESSING, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_SUCCESS, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_FAILURE, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_SKIPPED, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_BORDER, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_ACCENT, curses.COLOR_GREEN, -1)

class Package:
    """A simple class to hold package state."""
    def __init__(self, line):
        self.line = line.strip()
        self.name = self.line.split()[0] if self.line else ""
        self.status = Status.QUEUED

def check_if_installed(package_name):
    """Uses dpkg-query to check if a package is already installed."""
    try:
        subprocess.run(
            ['dpkg-query', '-W', '-f=${Status}', package_name],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def get_initial_packages():
    """Loads packages and sets initial status from log files."""
    if not os.path.exists(MASTER_LIST): return []
    open(SUCCESS_LOG, 'a').close()
    open(FAILURE_LOG, 'a').close()
    with open(SUCCESS_LOG) as f: success_lines = {line.strip() for line in f}
    with open(FAILURE_LOG) as f: failure_lines = {line.strip() for line in f}
    packages = []
    with open(MASTER_LIST) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            p = Package(line)
            if p.line in success_lines: p.status = Status.SUCCESS
            elif p.line in failure_lines: p.status = Status.FAILURE
            packages.append(p)
    return packages

def format_seconds(seconds):
    """Formats seconds into MM:SS."""
    if seconds is None or seconds < 0: return "--:--"
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes:02d}:{seconds:02d}"

def draw_package_list(pane, packages, scroll_offset):
    """Draws the list of packages and a scrollbar."""
    pane.erase()
    pane.box()
    pane.addstr(0, 2, " Packages (↑/↓ PgUp/PgDn) ", curses.A_BOLD)
    height, width = pane.getmaxyx()
    max_lines = height - 2
    visible_packages = packages[scroll_offset : scroll_offset + max_lines]

    symbols = {
        Status.QUEUED: ("  ", COLOR_DEFAULT),
        Status.PROCESSING: ("->", COLOR_PROCESSING | curses.A_BOLD),
        Status.SUCCESS: (" ✔", COLOR_SUCCESS),
        Status.FAILURE: (" ✖", COLOR_FAILURE),
        Status.SKIPPED: (" S", COLOR_SKIPPED)
    }

    for i, pkg in enumerate(visible_packages):
        symbol, color_attr = symbols[pkg.status]
        display_line = f"{symbol} {pkg.line}"
        pane.addstr(i + 1, 2, display_line[:width-4], curses.color_pair(color_attr))

    if len(packages) > max_lines:
        max_scroll = len(packages) - max_lines
        scroll_percent = scroll_offset / max_scroll if max_scroll > 0 else 0
        scrollbar_pos = int(scroll_percent * (max_lines - 1))
        pane.addstr(scrollbar_pos + 1, width - 2, "█", curses.color_pair(COLOR_BORDER))
    
    pane.noutrefresh()

def draw_right_pane(pad, height, width, line_buffer, scroll_pos):
    """Draws the pre-wrapped lines from the line_buffer."""
    pad.erase()
    
    for i, line in enumerate(line_buffer):
        if i >= pad.getmaxyx()[0]: break
        pad.addstr(i, 0, line)
    
    pad.noutrefresh(scroll_pos, 0, 1, width // 2 + 1, height - 2, width - 2)

def draw_stats_window(stats):
    """Draws the statistics overlay window."""
    win = stats['window']
    win.erase()
    win.box()
    win.addstr(0, 2, " Statistics ", curses.A_BOLD)
    win.addstr(1, 2, f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    win.addstr(2, 2, f"Time: {datetime.now().strftime('%I:%M:%S %p')}")
    win.addstr(4, 2, "Progress", curses.A_UNDERLINE)
    win.addstr(5, 2, f"Packages: {stats['processed']} / {stats['total']}")
    win.addstr(6, 2, f"Elapsed:  {format_seconds(stats['elapsed'])}")
    win.addstr(7, 2, f"ETR:      {format_seconds(stats['etr'])}")
    win.noutrefresh()

def draw_help_window(win):
    """Draws the help overlay window."""
    win.erase()
    win.box()
    win.addstr(0, 2, " Help ", curses.A_BOLD)
    
    symbols = {
        "->": ("Processing", COLOR_PROCESSING), " ✔": ("Success", COLOR_SUCCESS),
        " ✖": ("Failed", COLOR_FAILURE), " S": ("Skipped", COLOR_SKIPPED),
        "  ": ("Queued", COLOR_DEFAULT)
    }
    
    i = 2
    for symbol, (text, color) in symbols.items():
        win.addstr(i, 3, symbol, curses.color_pair(color) | curses.A_BOLD)
        win.addstr(f" - {text}")
        i += 1
    
    win.addstr(i + 1, 3, "s - Toggle Stats")
    win.addstr(i + 2, 3, "h - Toggle Help")
    win.addstr(i + 3, 3, "q - Quit")
    win.noutrefresh()

def main_ui(stdscr):
    """The main application function."""
    curses.curs_set(0)
    stdscr.nodelay(True)
    setup_colors()

    packages = get_initial_packages()
    if not packages: return

    height, width = stdscr.getmaxyx()
    split_pos = width // 2
    left_pane = curses.newwin(height, split_pos, 0, 0)
    right_pad = curses.newpad(5000, split_pos - 2)
    stats_win = curses.newwin(9, 30, 1, width - 31)
    help_win = curses.newwin(12, 30, (height-12)//2, (width-30)//2)

    scroll_offset, right_scroll_pos = 0, 0
    show_stats, show_help = True, False
    
    stats_data = {'total': len(packages), 'processed': 0, 'times': [], 'elapsed': 0, 'etr': None, 'window': stats_win}
    start_time = time.time()
    pkg_start_time = 0
    
    current_index = 0
    process = None
    output_lines = ["Welcome! Press 'h' for help or 's' to toggle stats."]

    while current_index < len(packages):
        needs_redraw = False

        # --- Handle User Input ---
        key = stdscr.getch()
        if key == ord('q'): break
        elif key == ord('h'): show_help = not show_help; needs_redraw = True
        elif key == ord('s'): show_stats = not show_stats; needs_redraw = True
        elif key in [curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE]:
            max_list_lines = height - 2
            if key == curses.KEY_UP: scroll_offset -= 1
            elif key == curses.KEY_DOWN: scroll_offset += 1
            elif key == curses.KEY_PPAGE: scroll_offset -= max_list_lines
            elif key == curses.KEY_NPAGE: scroll_offset += max_list_lines
            
            max_scroll = max(0, len(packages) - max_list_lines)
            scroll_offset = max(0, min(scroll_offset, max_scroll))
            needs_redraw = True
        
        # --- Main State Machine ---
        if process is None:
            pkg = packages[current_index]
            if pkg.status == Status.QUEUED:
                if check_if_installed(pkg.name):
                    pkg.status = Status.SKIPPED
                else:
                    pkg.status = Status.PROCESSING
                    output_lines = [f"Running: sudo apt-get install -y {pkg.name}", "-"*40]
                    cmd = ['sudo', 'apt-get', 'install', '-y', pkg.name]
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
                    pkg_start_time = time.time()
                    fd = process.stdout.fileno()
                    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            
            if pkg.status != Status.PROCESSING:
                current_index += 1
            needs_redraw = True
        else: # A process is running
            try:
                for line in iter(process.stdout.readline, ''):
                    if line: output_lines.append(line.strip()); needs_redraw = True
            except TypeError: pass

            if process.poll() is not None:
                pkg = packages[current_index]
                if process.returncode == 0:
                    pkg.status = Status.SUCCESS
                    if pkg_start_time > 0: stats_data['times'].append(time.time() - pkg_start_time)
                else:
                    pkg.status = Status.FAILURE
                
                process, pkg_start_time = None, 0
                current_index += 1
                needs_redraw = True
                time.sleep(0.5)

        # --- Update stats and redraw ---
        stats_data['processed'] = sum(1 for p in packages if p.status in [Status.SUCCESS, Status.FAILURE, Status.SKIPPED])
        stats_data['elapsed'] = time.time() - start_time
        if stats_data['times']:
            avg_time = sum(stats_data['times']) / len(stats_data['times'])
            remaining_to_install = sum(1 for p in packages if p.status == Status.QUEUED)
            stats_data['etr'] = avg_time * remaining_to_install
        
        # --- CORRECTED LIVE AUTO-SCROLL & FLICKER-FREE DRAWING ---
        max_list_lines = height - 2
        new_offset = current_index - (max_list_lines // 2)
        max_scroll = max(0, len(packages) - max_list_lines)
        scroll_offset = max(0, min(new_offset, max_scroll))

        if needs_redraw or process is not None:
            pad_width = width - split_pos - 4
            line_buffer = [wrapped for line in output_lines for wrapped in textwrap.wrap(line, pad_width if pad_width > 0 else 10)]

            if len(line_buffer) > height - 3:
                right_scroll_pos = max(0, len(line_buffer) - (height - 3))

            stdscr.noutrefresh() 
            draw_package_list(left_pane, packages, scroll_offset)
            draw_right_pane(right_pad, height, width, line_buffer, right_scroll_pos)
            if show_stats: draw_stats_window(stats_data)
            if show_help: draw_help_window(help_win)
            curses.doupdate()
        
        time.sleep(0.02)

    # --- End of Script ---
    final_message = "Installation run complete. Press 'q' to exit."
    status_bar = curses.newwin(1, width, height - 1, 0)
    status_bar.bkgd(' ', curses.color_pair(COLOR_SUCCESS))
    # *** THIS IS THE FIX: Pad to width - 1 to avoid writing to the bottom-right corner ***
    status_bar.addstr(0, 0, final_message.ljust(width - 1))
    status_bar.refresh()
    stdscr.nodelay(False)
    while stdscr.getch() != ord('q'): pass

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Root privileges are required. Re-running with sudo...")
        os.execvp('sudo', ['sudo', 'python3'] + sys.argv)

    if not os.path.exists(MASTER_LIST):
        print(f"Error: Master list '{MASTER_LIST}' not found.", file=sys.stderr)
        sys.exit(1)

    curses.wrapper(main_ui)

