from __future__ import annotations

import re
from pathlib import Path

HTML_PATH = Path("docs/tutorial/user_training_tutorial.html")
PDF_PATH = Path("docs/tutorial/user_training_tutorial.pdf")


def simple_pdf(lines: list[str]) -> bytes:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    stream_lines = ["BT", "/F1 11 Tf", "48 790 Td", "14 TL"]
    for line in lines:
        stream_lines.append(f"({esc(line)}) Tj")
        stream_lines.append("T*")
    stream_lines.append("ET")
    content = "\n".join(stream_lines).encode("latin-1", errors="replace")

    objs = []
    objs.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    objs.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    objs.append(b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n")
    objs.append(b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")
    objs.append(f"5 0 obj << /Length {len(content)} >> stream\n".encode("ascii") + content + b"\nendstream endobj\n")

    body = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objs:
        offsets.append(len(body))
        body += obj
    xref_start = len(body)
    xref = [f"xref\n0 {len(offsets)}\n".encode("ascii"), b"0000000000 65535 f \n"]
    for off in offsets[1:]:
        xref.append(f"{off:010d} 00000 n \n".encode("ascii"))
    trailer = f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF".encode("ascii")
    return body + b"".join(xref) + trailer


def html_to_lines(html: str) -> list[str]:
    html = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "\n", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    raw = [ln.strip() for ln in text.splitlines()]
    cleaned = [ln for ln in raw if ln]

    wrapped: list[str] = []
    width = 96
    for line in cleaned:
        while len(line) > width:
            cut = line.rfind(" ", 0, width)
            if cut <= 0:
                cut = width
            wrapped.append(line[:cut].strip())
            line = line[cut:].strip()
        if line:
            wrapped.append(line)

    max_lines = 52
    if len(wrapped) > max_lines:
        wrapped = wrapped[: max_lines - 1] + ["(truncated; see HTML tutorial for full detail)"]

    return wrapped


def main() -> None:
    html = HTML_PATH.read_text(encoding="utf-8")
    lines = html_to_lines(html)
    PDF_PATH.write_bytes(simple_pdf(lines))
    print(f"Wrote {PDF_PATH}")


if __name__ == "__main__":
    main()
