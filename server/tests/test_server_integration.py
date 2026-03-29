from __future__ import annotations

from fastapi.testclient import TestClient

from proxylens_server.app import create_app
from proxylens_server.config import ServerConfig


def test_end_to_end_http_flow_and_queries(tmp_path: Path) -> None:
    with TestClient(create_app(ServerConfig(data_dir=tmp_path))) as client:
        blob_request = "01K0BLOBREQUESTBODYCHUNK0000"
        blob_response = "01K0BLOBRESPONSEBODYCHUNK00"
        request_id = "01K0REQUESTEXAMPLE0000000000"
        hop_chain = "4bf92f3577b34da6a3ce929d0e0e4736@edge-a,proxy-a"

        assert (
            client.put(f"/blobs/{blob_request}", content=b'{"name":"demo"}').status_code
            == 200
        )
        assert (
            client.put(f"/blobs/{blob_response}", content=b'{"ok":true}').status_code
            == 200
        )

        batch = {
            "events": [
                {
                    "type": "http_request_started",
                    "request_id": request_id,
                    "event_index": 0,
                    "node_name": "proxy-a",
                    "hop_chain": hop_chain,
                    "payload": {
                        "method": "POST",
                        "url": "https://example.test/widgets",
                        "http_version": "HTTP/1.1",
                        "headers": [["content-type", "application/json"]],
                    },
                },
                {
                    "type": "http_request_body",
                    "request_id": request_id,
                    "event_index": 1,
                    "node_name": "proxy-a",
                    "hop_chain": hop_chain,
                    "payload": {
                        "blob_id": blob_request,
                        "size_bytes": 15,
                        "complete": True,
                    },
                },
                {
                    "type": "http_request_completed",
                    "request_id": request_id,
                    "event_index": 2,
                    "node_name": "proxy-a",
                    "hop_chain": hop_chain,
                    "payload": {},
                },
                {
                    "type": "http_response_started",
                    "request_id": request_id,
                    "event_index": 3,
                    "node_name": "proxy-a",
                    "hop_chain": hop_chain,
                    "payload": {
                        "status_code": 201,
                        "http_version": "HTTP/1.1",
                        "headers": [["content-type", "application/json"]],
                    },
                },
                {
                    "type": "http_response_body",
                    "request_id": request_id,
                    "event_index": 4,
                    "node_name": "proxy-a",
                    "hop_chain": hop_chain,
                    "payload": {
                        "blob_id": blob_response,
                        "size_bytes": 11,
                        "complete": True,
                    },
                },
                {
                    "type": "http_response_completed",
                    "request_id": request_id,
                    "event_index": 5,
                    "node_name": "proxy-a",
                    "hop_chain": hop_chain,
                    "payload": {},
                },
            ]
        }

        response = client.post("/events", json=batch)
        assert response.status_code == 200
        assert all(item["status"] == "accepted" for item in response.json()["results"])

        summaries = client.get("/requests").json()["requests"]
        assert len(summaries) == 1
        assert summaries[0]["request_id"] == request_id
        assert "request_body_chunks" not in summaries[0]

        histogram = client.get(
            "/requests/histogram", params={"bucket": "minute"}
        ).json()
        assert histogram["bucket"] == "minute"
        assert histogram["points"][0]["request_count"] == 1

        detail = client.get(f"/requests/{request_id}").json()
        assert detail["response_status_code"] == 201
        assert detail["request_body_chunks"][0]["blob_id"] == blob_request

        events = client.get(f"/requests/{request_id}/events").json()
        assert [event["event_index"] for event in events] == [0, 1, 2, 3, 4, 5]

        assert client.get(f"/requests/{request_id}/body").content == b'{"name":"demo"}'
        assert (
            client.get(f"/requests/{request_id}/response/body").content
            == b'{"ok":true}'
        )
        openapi = client.get("/openapi.json").json()
        assert "/openapi.yaml" not in openapi["paths"]
        assert "/scalar" not in openapi["paths"]
        assert client.get("/openapi.yaml").status_code == 200
        assert client.get("/scalar").status_code == 200

        assert client.delete(f"/requests/{request_id}").status_code == 202
        assert (
            client.post("/events", json={"events": [batch["events"][0]]}).status_code
            == 409
        )


def test_server_allows_local_ui_origin_via_cors(tmp_path: Path) -> None:
    with TestClient(create_app(ServerConfig(data_dir=tmp_path))) as client:
        response = client.options(
            "/requests",
            headers={
                "Origin": "http://127.0.0.1:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
