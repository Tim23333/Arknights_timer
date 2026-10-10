"""Portable packaging and strict-CSP browser fixture regressions."""
from html.parser import HTMLParser
from pathlib import Path
import re
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import urlopen

from backend.app.services.webui_server import WebUiServer
from backend.app.field_policy import FIELD_REGISTRY


class FixtureParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inline = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "style" in attrs or any(key.startswith("on") for key in attrs):
            self.inline.append(tag)
        if tag == "script":
            if "src" not in attrs:
                self.inline.append(tag)
            else:
                self.scripts.append(attrs["src"])


def test_regression_pages_work_under_unchanged_strict_csp():
    # ROOT CAUSE: inline fixtures were blocked by production script-src/self;
    # checking only HTTP 200 did not prove their buttons could run.
    server = WebUiServer(lambda: {}, lambda: {}, lambda *_: {}, lambda *_: {}, lambda *_: '')
    url = server.start()
    try:
        for name in ("refresh", "sourceMeta", "tableLayout"):
            with urlopen(f"{url}test/{name}.html", timeout=3) as response:
                assert response.status == 200
                assert "unsafe-inline" not in response.headers['Content-Security-Policy']
                body = response.read()
            parser = FixtureParser()
            parser.feed(body.decode())
            assert parser.inline == []
            assert len(parser.scripts) == 1
            with urlopen(url + 'test/' + parser.scripts[0], timeout=3) as script:
                assert script.status == 200
    finally:
        server.stop()


def test_packaged_webui_includes_runtime_modules_not_docs_or_tests(tmp_path, monkeypatch):
    # build_exe is a CLI module whose supported import root is backend/.
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parent))
    import build_exe
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "run.py").touch()
    assets = tmp_path / "webui"
    assets.mkdir()
    (assets / "test").mkdir()
    for name in ("index.html", "logs.html", "app.mjs", "detailSelection.mjs", "styles.css", "README.md"):
        (assets / name).touch()
    (assets / "test" / "refresh.html").touch()
    args = SimpleNamespace(name="fixture", onedir=False, console=False, test=False)
    with patch.object(build_exe, "_write_windows_version_file", return_value=tmp_path / "version.txt"), \
         patch.object(build_exe.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
        assert build_exe._build_main_app(backend, tmp_path, tmp_path / "icon.ico", args) == 0
    command = run.call_args.args[0]
    packaged = [command[index + 1] for index, flag in enumerate(command) if flag == "--add-data"]
    sources = [Path(arg.rsplit(";" if build_exe.os.name == "nt" else ":", 1)[0]) for arg in packaged]
    web_sources = [path for path in sources if path.parent == assets]
    assert {path.name for path in web_sources} == {"index.html", "logs.html", "app.mjs", "detailSelection.mjs", "styles.css"}
    assert assets not in sources
    assert assets / "test" not in sources


def test_flat_packaging_boundary_contains_all_current_runtime_imports():
    assets = Path(__file__).resolve().parents[1] / "webui"
    for source in assets.iterdir():
        if source.suffix not in {".html", ".mjs", ".css"}:
            continue
        contents = source.read_text(encoding="utf-8")
        references = re.findall(r"(?:from\s*|\b(?:src|href)\s*=\s*)['\"](\./[^'\"]+)['\"]", contents)
        for reference in references:
            target = (source.parent / reference).resolve()
            assert target.parent == assets.resolve(), f"runtime asset left flat bundle: {source.name} -> {reference}"
            assert target.is_file(), f"missing runtime asset: {reference}"


def test_auto_address_button_precedes_timer_tool():
    markup = (Path(__file__).resolve().parents[1] / 'webui' / 'index.html').read_text(encoding='utf-8')
    assert markup.index('data-action="auto-address-once"') < markup.index('data-action="timer"')


def test_field_policy_document_counts_match_runtime_registry():
    document = (Path(__file__).resolve().parents[1] / "docs/webui/FIELD_POLICY.md").read_text(encoding="utf-8")
    internal = sum(spec.domain == "internal" for spec in FIELD_REGISTRY.values())
    enemies = sum(spec.domain == "enemy" for spec in FIELD_REGISTRY.values())
    characters = sum(spec.domain == "character" for spec in FIELD_REGISTRY.values())
    assert f"包含 {len(FIELD_REGISTRY)} 项：{len(FIELD_REGISTRY) - internal} 项公开策略" in document
    assert f"敌人{enemies}项、干员{characters}项" in document
