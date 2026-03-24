from __future__ import annotations

import re
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    dist_dir = root / "dist"
    out_dir = root / "standalone"
    out_dir.mkdir(parents=True, exist_ok=True)

    index_path = dist_dir / "index.html"
    if not index_path.exists():
        raise FileNotFoundError("dist/index.html not found. Run `npm run build` first.")

    html = index_path.read_text(encoding="utf-8")

    css_matches = re.findall(r'<link[^>]*href="([^"]+\.css)"[^>]*>', html)
    # Capture full script attributes to preserve `type="module"` etc.
    js_src_matches = re.findall(r'<script([^>]*)\s+src="([^"]+\.js)"[^>]*></script>', html)

    for css_href in css_matches:
        css_path = dist_dir / css_href.lstrip("/")
        css_content = css_path.read_text(encoding="utf-8")
        pattern = r'<link[^>]*href="' + re.escape(css_href) + r'"[^>]*>'
        html = re.sub(pattern, lambda _: "<style>\n" + css_content + "\n</style>", html, count=1)

    # Replace each external js script with an inline script keeping attributes.
    for attrs, js_src in js_src_matches:
        js_path = dist_dir / js_src.lstrip("/")
        js_content = js_path.read_text(encoding="utf-8")
        js_src_esc = re.escape(js_src)
        # Match the exact script tag with this src (and any attrs)
        pattern = r'<script[^>]*\s+src="' + js_src_esc + r'"[^>]*></script>'

        def _repl(_):
            # attrs already include leading spaces (from capture)
            return f"<script{attrs}>\n{js_content}\n</script>"

        html = re.sub(pattern, _repl, html, count=1)

    out_file = out_dir / "arknights_timeline_standalone.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"Standalone file created: {out_file}")


if __name__ == "__main__":
    main()
