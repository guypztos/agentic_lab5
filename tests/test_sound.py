"""Sound runs in the browser; these checks serve it and run its Node tests."""

import shutil
import subprocess
import threading
from pathlib import Path
from urllib.request import urlopen

import pytest

from server import make_server

ROOT = Path(__file__).parent.parent


@pytest.fixture
def base_url():
    server = make_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def test_sound_module_is_served_as_javascript(base_url):
    with urlopen(base_url + "/sound.mjs") as response:
        assert response.headers["Content-Type"].startswith("text/javascript")
        assert b"export function createSound" in response.read()


def test_page_has_a_mute_control(base_url):
    with urlopen(base_url + "/") as response:
        page = response.read().decode()
    assert 'id="mute"' in page
    assert 'aria-pressed="false"' in page
    with urlopen(base_url + "/app.js") as response:
        assert b"from '/sound.mjs'" in response.read()


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_sound_module_in_node():
    result = subprocess.run(
        ["node", "--test", str(ROOT / "tests" / "js" / "sound.test.mjs")],
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
