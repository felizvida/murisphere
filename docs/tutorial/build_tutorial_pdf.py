from __future__ import annotations

import subprocess
from pathlib import Path

MD_PATH = Path("docs/tutorial/user_training_tutorial.md")
PDF_PATH = Path("docs/tutorial/user_training_tutorial.pdf")


def main() -> None:
    cmd = [
        "pandoc",
        str(MD_PATH),
        "-o",
        str(PDF_PATH),
        "--pdf-engine=xelatex",
        "-V",
        "mainfont=Helvetica",
        "-V",
        "sansfont=Helvetica",
        "-V",
        "monofont=Courier",
    ]
    subprocess.run(cmd, check=True)
    print(f"Wrote {PDF_PATH}")


if __name__ == "__main__":
    main()
