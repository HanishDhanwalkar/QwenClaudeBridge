import json
import time
import uuid


class QwenAdapter:
    """
    Qwen web-protocol adapter.

    This file is intentionally conservative until the Qwen EventStream payload
    is known. The request payload shown in the user's DevTools screenshot tells
    us the current guest request includes:
      chatId/chat_id
      chat_mode=guest
      incremental_output=true
      model=qwen3.7-plus
      parentId/parent_id
      stream=true
      version=2.1

    We will fill in the exact message and SSE translation after the
    EventStream screenshot is captured.
    """

    ready = False

    def __init__(self, app):
        self.app = app

    def handle_messages(self, request):
        return {
            "status": 501,
            "body": {
                "type": "not_implemented",
                "error": {
                    "type": "adapter_not_ready",
                    "message": (
                        "The local bridge is running, but the Qwen EventStream "
                        "translator has not been enabled yet. Capture the "
                        "Qwen DevTools EventStream for a test prompt such as "
                        "'Say exactly: HELLO123'."
                    ),
                },
            },
        }

    def build_probe(self, user_text):
        """
        Reference representation of the Qwen request we will generate once the
        exact message object is confirmed.
        """
        chat_id = str(uuid.uuid4())
        now = int(time.time())
        return {
            "chatId": chat_id,
            "chat_id": chat_id,
            "chat_mode": "guest",
            "incremental_output": True,
            "messages": [],
            "model": "qwen3.7-plus",
            "parentId": None,
            "parent_id": None,
            "stream": True,
            "timestamp": now,
            "version": "2.1",
        }
