import json
from http.client import HTTPConnection
import threading

from astrochecker.server import create_server


MASK = {
    "version": 1,
    "pieces": [{"points": [[350, 12], [10, 12], [10, 42], [350, 42]]}],
}


class V1Service:
    def api_v1_status(self):
        return {"version": 1, "connected": True}

    def api_v1_objects(self, query):
        return {"version": 1, "objects": [{"name": query}]}

    def export_horizon(self, payload):
        from astrochecker.sky_mask import SkyMask

        return {
            "filename": "test-horizon.txt",
            "content": SkyMask.from_payload(payload["mask"]).to_nina_horizon(),
        }

    def api_v1_check(self, payload):
        return {"version": 1, "status": "none", "object": payload["object"]}


def request(server, method, path, body=None):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    headers = {"Content-Type": "application/json"} if body is not None else {}
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    content_type = response.getheader("Content-Type")
    content_disposition = response.getheader("Content-Disposition")
    result = response.read()
    connection.close()
    return response.status, content_type, content_disposition, result


def running_server():
    server = create_server(port=0, service=V1Service())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_v1_status_and_object_search_are_versioned():
    server, thread = running_server()
    try:
        status, content_type, _, result = request(server, "GET", "/api/v1/status")
        assert status == 200
        assert content_type.startswith("application/json")
        assert json.loads(result) == {"version": 1, "connected": True}

        status, _, _, result = request(server, "GET", "/api/v1/objects?q=M31")
        assert status == 200
        assert json.loads(result) == {"version": 1, "objects": [{"name": "M31"}]}
    finally:
        server.shutdown()
        thread.join(timeout=3)


def test_v1_horizon_returns_nina_text_for_the_supplied_mask():
    server, thread = running_server()
    try:
        status, content_type, disposition, result = request(
            server, "POST", "/api/v1/horizon", json.dumps({"mask": MASK})
        )
        text = result.decode("utf-8")
        assert status == 200
        assert content_type.startswith("text/plain")
        assert 'filename="test-horizon.txt"' in disposition
        assert text.startswith("# AstroChecker sky mask version 1")
        assert "# The upper ceiling" in text
        assert "0 12\n" in text
    finally:
        server.shutdown()
        thread.join(timeout=3)


def test_v1_check_is_a_post_json_endpoint():
    server, thread = running_server()
    try:
        status, content_type, _, result = request(
            server, "POST", "/api/v1/check", json.dumps({"object": "M31"})
        )
        assert status == 200
        assert content_type.startswith("application/json")
        assert json.loads(result) == {
            "version": 1, "status": "none", "object": "M31"
        }
    finally:
        server.shutdown()
        thread.join(timeout=3)
