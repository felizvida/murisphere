from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from shutil import which

MD_PATH = Path("docs/tutorial/user_training_tutorial.md")
PDF_PATH = Path("docs/tutorial/user_training_tutorial.pdf")


def _convert_svg_to_png(svg_path: Path, png_path: Path, rsvg_bin: str) -> None:
    cmd = [
        rsvg_bin,
        "-f",
        "png",
        "-o",
        str(png_path),
        str(svg_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _prepare_markdown_with_png_assets(md_text: str, tmp_dir: Path, rsvg_bin: str) -> tuple[Path, Path]:
    tmp_assets = tmp_dir / "assets"
    tmp_assets.mkdir(parents=True, exist_ok=True)

    rewritten = md_text
    refs = sorted(set(re.findall(r"!\[[^\]]*\]\((assets/[^)]+\.svg)\)", md_text)))
    for rel_ref in refs:
        svg_src = Path("docs/tutorial") / rel_ref
        png_rel = rel_ref[:-4] + ".png"
        png_dst = tmp_dir / png_rel
        png_dst.parent.mkdir(parents=True, exist_ok=True)
        _convert_svg_to_png(svg_src, png_dst, rsvg_bin)
        rewritten = rewritten.replace(rel_ref, png_rel)

    tmp_md = tmp_dir / "user_training_tutorial_pdf.md"
    tmp_md.write_text(rewritten, encoding="utf-8")
    return tmp_md, tmp_assets


def main() -> None:
    pandoc_bin = os.getenv("PANDOC_BIN", "pandoc")
    pdf_engine = os.getenv("MURISPHERE_PDF_ENGINE", "xelatex")
    rsvg_bin = os.getenv("RSVG_CONVERT_BIN", "rsvg-convert")
    if which(rsvg_bin) is None:
        raise RuntimeError(
            f"{rsvg_bin} not found. Install librsvg (rsvg-convert) before building the tutorial PDF."
        )
    md_text = MD_PATH.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="murisphere-pdf-build-") as td:
        tmp_dir = Path(td)
        tmp_md, _tmp_assets = _prepare_markdown_with_png_assets(md_text, tmp_dir, rsvg_bin)
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
