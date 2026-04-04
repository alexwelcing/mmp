"""
AIDirectorWebhook — ComfyUI custom node that notifies the AI Director
when a prompt finishes executing.

Environment:
    AI_DIRECTOR_WEBHOOK_URL  — URL to POST to (default: http://localhost:8080/webhook/comfyui)
"""

import os
import threading
from typing import Any

import requests

WEBHOOK_URL = os.environ.get(
    "AI_DIRECTOR_WEBHOOK_URL", "http://localhost:8080/webhook/comfyui"
)


def _send_webhook(payload: dict[str, Any]) -> None:
    """Fire-and-forget POST to the AI Director webhook endpoint."""
    try:
        requests.post(WEBHOOK_URL, json=payload, timeout=5)
    except Exception:
        # Best-effort notification; polling in the AI Director is the fallback.
        pass


class AIDirectorWebhook:
    """
    ComfyUI node that passes through its input image and asynchronously
    notifies the AI Director that this prompt has completed.
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "images": ("IMAGE",),
                "client_id": ("STRING", {"default": ""}),
                "job_id": ("STRING", {"default": ""}),
                "node_type": (["image", "3dgs"], {"default": "image"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "notify"
    CATEGORY = "ai_director"
    OUTPUT_NODE = True

    def notify(
        self,
        images: Any,
        client_id: str,
        job_id: str,
        node_type: str,
    ) -> tuple[Any]:
        payload = {
            "client_id": client_id,
            "job_id": job_id,
            "node_type": node_type,
        }
        # Fire-and-forget so we don't block the ComfyUI executor.
        threading.Thread(target=_send_webhook, args=(payload,), daemon=True).start()
        return (images,)


NODE_CLASS_MAPPINGS = {"AIDirectorWebhook": AIDirectorWebhook}
NODE_DISPLAY_NAME_MAPPINGS = {"AIDirectorWebhook": "AI Director Webhook"}
