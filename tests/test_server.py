import json
import threading
import urllib.error
import urllib.request

import pytest

from server import make_server


@pytest.fixture
def url(tmp_path):
    server = make_server(0, save_path=tmp_path / "game.save.json")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def get(url, path):
    try:
        with urllib.request.urlopen(url + path) as response:
            return response.status, response.headers["Content-Type"], response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers["Content-Type"], error.read()


def post(url, path, body, content_length=None):
    headers = {"Content-Type": "application/json"}
    if content_length is not None:
        headers["Content-Length"] = str(content_length)
    request = urllib.request.Request(url + path, body, headers)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


@pytest.mark.parametrize("path,content_type,marker", [
    ("/", "text/html; charset=utf-8", b"<div id=\"board\">"),
    ("/app.js", "text/javascript; charset=utf-8", b"function render()"),
    ("/style.css", "text/css; charset=utf-8", b"#board"),
])
def test_static_files_are_served_with_their_types(url, path, content_type, marker):
    status, served_type, body = get(url, path)
    assert status == 200
    assert served_type == content_type
    assert marker in body


def test_state_reports_the_game(url):
    status, content_type, body = get(url, "/api/state")
    assert status == 200
    assert content_type == "application/json"
    state = json.loads(body)
    assert state["turn"] == "w" and len(state["board"]) == 32
    assert state["captured"] == [] and state["can_undo"] is False


def test_unknown_paths_are_not_found(url):
    assert get(url, "/missing")[0] == 404
    assert post(url, "/api/other", b"{}")[0] == 404


def test_a_move_returns_the_new_state(url):
    status, state = post(url, "/api/action",
                         json.dumps({"action": "move", "source": "e2", "target": "e4"}).encode())
    assert status == 200
    assert state["moves"] == ["e2-e4"] and state["board"]["e4"] == "wP"


@pytest.mark.parametrize("body,kwargs,fragment", [
    (b"", {}, "request size"),
    (b"[]", {}, "action object"),
    (b"{", {}, ""),
    (json.dumps({"action": "dance"}).encode(), {}, "Unknown action"),
    (json.dumps({"action": "move", "source": "e2", "target": "e5"}).encode(), {},
     "not allowed"),
    (json.dumps({"action": "load"}).encode(), {}, "no saved game"),
])
def test_bad_requests_get_an_error_message(url, body, kwargs, fragment):
    status, result = post(url, "/api/action", body, **kwargs)
    assert status == 400
    assert fragment in result["error"]
    assert get(url, "/api/state")[0] == 200  # The server is still serving.
