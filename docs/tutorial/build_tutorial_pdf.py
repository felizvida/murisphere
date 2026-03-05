from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

MD_PATH = Path("docs/tutorial/user_training_tutorial.md")
PDF_PATH = Path("docs/tutorial/user_training_tutorial.pdf")


def _svg_viewbox_size(svg_path: Path) -> tuple[int, int]:
    raw = svg_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'viewBox="[^"]*?\s(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)"', raw)
    if not m:
        return (1600, 1000)
    w = max(640, min(2800, int(float(m.group(1)))))
    h = max(420, min(2200, int(float(m.group(2)))))
    return (w, h)


def _convert_svg_to_png(svg_path: Path, png_path: Path, chrome_bin: str) -> None:
    w, h = _svg_viewbox_size(svg_path)
    cmd = [
        chrome_bin,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        f"--window-size={w},{h}",
        f"--screenshot={png_path}",
        f"file://{svg_path.resolve()}",
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _prepare_markdown_with_png_assets(md_text: str, tmp_dir: Path, chrome_bin: str) -> tuple[Path, Path]:
    tmp_assets = tmp_dir / "assets"
    tmp_assets.mkdir(parents=True, exist_ok=True)

    rewritten = md_text
    refs = sorted(set(re.findall(r"!\[[^\]]*\]\((assets/[^)]+\.svg)\)", md_text)))
    for rel_ref in refs:
        svg_src = Path("docs/tutorial") / rel_ref
        png_rel = rel_ref[:-4] + ".png"
        png_dst = tmp_dir / png_rel
        png_dst.parent.mkdir(parents=True, exist_ok=True)
        _convert_svg_to_png(svg_src, png_dst, chrome_bin)
        rewritten = rewritten.replace(rel_ref, png_rel)

    tmp_md = tmp_dir / "user_training_tutorial_pdf.md"
    tmp_md.write_text(rewritten, encoding="utf-8")
    return tmp_md, tmp_assets


def main() -> None:
    pandoc_bin = os.getenv("PANDOC_BIN", "pandoc")
    pdf_engine = os.getenv("MURISPHERE_PDF_ENGINE", "xelatex")
    chrome_bin = os.getenv("CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    md_text = MD_PATH.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="murisphere-pdf-build-") as td:
        tmp_dir = Path(td)
        tmp_md, _tmp_assets = _prepare_markdown_with_png_assets(md_text, tmp_dir, chrome_bin)
        cmd = [
            pandoc_bin,
            str(tmp_md),
            "--from=markdown",
            f"--pdf-engine={pdf_engine}",
            f"--resource-path={tmp_dir}:docs/tutorial",
            "-o",
            str(PDF_PATH),
        ]
        subprocess.run(cmd, check=True)

    pdf_bytes = PDF_PATH.read_bytes()
    markers = [
        str(MD_PATH.resolve()).encode("utf-8"),
        str(Path.cwd().resolve()).encode("utf-8"),
        b"file://",
    ]
    leaked = [m.decode("utf-8", errors="ignore") for m in markers if m in pdf_bytes]
    if leaked:
        raise RuntimeError(f"PDF contains leaked local path markers: {leaked}")

    print(f"Wrote {PDF_PATH}")


if __name__ == "__main__":
    main()
