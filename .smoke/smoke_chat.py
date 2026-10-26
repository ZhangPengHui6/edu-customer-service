"""本地联调脚本：发一条文本消息并等待 AI 回复。"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import httpx

CS = "http://127.0.0.1:8010"
OUT = Path("C:/data/python_data/yxp_edu_file/.smoke/last_result.json")
CHANNEL = sys.argv[1] if len(sys.argv) > 1 else "smoke"
TEXT = sys.argv[2] if len(sys.argv) > 2 else "我的订单 ORDER_20251001 到哪了？"


def main() -> None:
    with httpx.Client(timeout=30, trust_env=False) as client:
        token = client.post(
            f"{CS}/api/v1/auth/demo-token",
            json={"tenant_code": "dlr_north", "external_id": "parent_001"},
        ).raise_for_status().json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        conversation = client.get(
            f"{CS}/api/v1/conversations/current",
            params={"channel": CHANNEL},
            headers=headers,
        ).raise_for_status().json()
        print("conversation", conversation["id"], "mode", conversation["mode"])

        sent = client.post(
            f"{CS}/api/v1/conversations/{conversation['id']}/messages",
            headers=headers,
            json={
                "message_id": str(uuid.uuid4()),
                "type": "text",
                "content": {"text": TEXT},
            },
        ).raise_for_status().json()
        print("sent", sent["message"]["content"]["text"])

        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            time.sleep(2)
            detail = client.get(
                f"{CS}/api/v1/conversations/{conversation['id']}",
                headers=headers,
            ).raise_for_status().json()
            replies = [
                message
                for message in detail["messages"]
                if message["role"] == "ai" and message["created_at"] >= sent["message"]["created_at"]
            ]
            if replies:
                result = {
                    "conversation_id": conversation["id"],
                    "sent": sent["message"]["content"],
                    "replies": [reply["content"] for reply in replies],
                    "mode": detail["mode"],
                    "processing": detail["is_processing"],
                }
                OUT.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                for reply in replies:
                    print(
                        "ai reply_type=",
                        reply["content"].get("reply_type"),
                        "chars=",
                        len(reply["content"].get("text", "")),
                        "action=",
                        reply["content"].get("action"),
                    )
                print("mode", detail["mode"], "processing", detail["is_processing"])
                return
        print("timeout waiting for AI reply")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
