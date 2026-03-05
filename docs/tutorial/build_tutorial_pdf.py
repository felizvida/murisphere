from __future__ import annotations

import os
import subprocess
from pathlib import Path

HTML_PATH = Path("docs/tutorial/user_training_tutorial.html")
PDF_PATH = Path("docs/tutorial/user_training_tutorial.pdf")


def main() -> None:
    chrome_bin = os.getenv("CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    profile_dir = os.getenv("CHROME_PROFILE_DIR", "/tmp/murisphere-chrome-profile")
    cmd = [
        chrome_bin,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--allow-file-access-from-files",
        f"--user-data-dir={profile_dir}",
        f"--print-to-pdf={PDF_PATH.resolve()}",
        "--virtual-time-budget=7000",
        f"file://{HTML_PATH.resolve()}",
    ]
    subprocess.run(cmd, check=True)
    print(f"Wrote {PDF_PATH}")


if __name__ == "__main__":
    main()
