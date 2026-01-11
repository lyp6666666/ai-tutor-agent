from __future__ import annotations

import argparse
import base64
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _now_ts() -> float:
    return time.time()


def _http_post_json(url: str, payload: dict[str, Any], timeout_s: float = 15.0) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {url}: {raw}") from e
    except URLError as e:
        raise RuntimeError(f"Request failed {url}: {e}") from e


@dataclass(frozen=True)
class WsMessage:
    raw: str


class WsListener:
    def __init__(self, ws_url: str) -> None:
        self.ws_url = ws_url
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen[str] | None = None
        self.messages: queue.Queue[WsMessage] = queue.Queue()

    def start(self) -> str:
        if self._thread is not None:
            return "already_started"

        try:
            from websocket import create_connection  # type: ignore[import-not-found]
        except Exception:
            create_connection = None

        if create_connection is not None:
            self._thread = threading.Thread(
                target=self._run_websocket_client, args=(create_connection,), daemon=True
            )
            self._thread.start()
            return "python_websocket_client"

        if shutil.which("websocat"):
            self._thread = threading.Thread(target=self._run_websocat, daemon=True)
            self._thread.start()
            return "websocat"

        return "unavailable"

    def stop(self) -> None:
        self._stop.set()
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _run_websocket_client(self, create_connection) -> None:
        ws = None
        try:
            ws = create_connection(self.ws_url, timeout=5)
            try:
                ws.settimeout(0.5)
            except Exception:
                pass
            while not self._stop.is_set():
                try:
                    msg = ws.recv()
                except Exception:
                    continue
                if msg is None:
                    continue
                self.messages.put(WsMessage(raw=str(msg)))
        finally:
            try:
                if ws is not None:
                    ws.close()
            except Exception:
                pass

    def _run_websocat(self) -> None:
        self._proc = subprocess.Popen(
            ["websocat", "-t", self.ws_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert self._proc.stdout is not None
        while not self._stop.is_set():
            line = self._proc.stdout.readline()
            if not line:
                break
            self.messages.put(WsMessage(raw=line.rstrip("\n")))


def _print_json(title: str, obj: dict[str, Any]) -> None:
    print(title)
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _send_realtime_frame(ws_url: str, frame: dict[str, Any]) -> dict[str, Any]:
    if not shutil.which("websocat"):
        raise RuntimeError("websocat not found. Install it or send realtime frames via Apifox.")
    proc = subprocess.run(
        ["websocat", "-t", ws_url],
        input=json.dumps(frame, ensure_ascii=False) + "\n",
        text=True,
        capture_output=True,
        timeout=10,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "websocat failed")
    out = (proc.stdout or "").strip()
    return json.loads(out) if out else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--session-id", default=os.getenv("SESSION_ID"))
    parser.add_argument("--no-ws", action="store_true")
    args = parser.parse_args()

    session_id = args.session_id or f"manual_{int(_now_ts())}"
    api_base = args.base_url.rstrip("/") + "/api/v1"
    ws_url = args.base_url.replace("http://", "ws://").replace("https://", "wss://").rstrip("/")
    ws_url = f"{ws_url}/api/v1/ws/{session_id}"

    listener: WsListener | None = None
    if not args.no_ws:
        listener = WsListener(ws_url)
        mode = listener.start()
        if mode == "unavailable":
            print("WS listener unavailable: install websocat or websocket-client, or run with --no-ws")
        else:
            print(f"WS listening via {mode}: {ws_url}")

    open_url = f"{api_base}/classroom/open"
    end_url = f"{api_base}/classroom/end"
    agent_cmd_url = f"{api_base}/agent/command"
    realtime_ws_url = args.base_url.replace("http://", "ws://").replace("https://", "wss://").rstrip("/")
    realtime_ws_url = f"{realtime_ws_url}/api/v1/classroom/realtime"

    r1 = _http_post_json(
        open_url,
        {
            "session_id": session_id,
            "course_id": "c_1",
            "course_name": "英语课",
            "teacher": {"teacher_id": "t_1", "teacher_name": "张老师"},
            "start_time": _now_ts(),
        },
    )
    _print_json("1) open classroom", r1)

    audio_b64 = base64.b64encode(b"\x00\x00\x00\x00").decode("utf-8")
    a1 = _send_realtime_frame(
        realtime_ws_url,
        {
            "session_id": session_id,
            "user_id": "t_1",
            "user_name": "张老师",
            "role": "teacher",
            "timestamp": _now_ts(),
            "audio_chunk": audio_b64,
            "is_last": True,
            "mock_text": "今天我们学习一般现在时。知识点：一般现在时的基本结构。",
        },
    )
    _print_json("2) realtime frame (teacher mock_text)", a1)

    a2 = _send_realtime_frame(
        realtime_ws_url,
        {
            "session_id": session_id,
            "user_id": "stu_1",
            "user_name": "小明",
            "role": "student",
            "timestamp": _now_ts(),
            "audio_chunk": audio_b64,
            "is_last": True,
            "mock_text": "老师我不太懂第三人称单数要不要加s？",
        },
    )
    _print_json("3) realtime frame (student mock_text)", a2)

    r2 = _http_post_json(
        agent_cmd_url,
        {"session_id": session_id, "teacher_id": "t_1", "instruction": "请基于本节课内容给我一段课中提醒话术"},
    )
    _print_json("4) agent command (reply via /ws/{session_id})", r2)

    r3 = _http_post_json(end_url, {"session_id": session_id, "end_time": _now_ts()})
    _print_json("5) end classroom (final report async)", r3)

    time.sleep(1.0)
    if listener is not None:
        listener.stop()
        drained: list[str] = []
        while True:
            try:
                drained.append(listener.messages.get_nowait().raw)
            except queue.Empty:
                break
        print(f"WS messages captured: {len(drained)}")
        for i, raw in enumerate(drained[:30], start=1):
            print(f"[{i}] {raw}")

    print(f"session_id={session_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
