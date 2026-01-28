from typing import List, Optional, Dict
from pydantic import BaseModel, Field
import requests

class Pipeline:
    # IMPORTANT: must be "filter" so Open WebUI executes it automatically
    type = "filter"
    class Valves(BaseModel):
        # Apply this filter to specific Open WebUI model IDs.
        # Use ["*"] to apply to all text models.
        pipelines: List[str] = Field(default_factory=lambda: ["*"])
        # Lower value = runs earlier
        priority: int = 0
        # Vision model backend (OpenAI-compatible)
        qwen_base_url: str = "http://192.xxx.xxx.xxx:8282"
        qwen_model: str = "vLLMQwen3VL30B"
        qwen_api_key: str = ""
        caption_prompt: str = (
            "You convert the given image into a rich text in english language. "
            "Return ONLY the final prompt as a single line, no quotes, no extra text. "
            "Include: subject, environment, style, lighting, camera/lens, composition, "
            "key details, ethnicity of people, position and angle of the object in the picture, "
            "detailed clothes description, face description of people, look direction of people, "
            "posture of people, age of people. "
            "All these key description instructions need to be applied on each recognized object, "
            "person, scenery etc. be very detailed and structured in the description. "
            "Avoid meta-commentary."
        )
        timeout_sec: int = 120
        strip_images_on_error: bool = True
        allowed_image_extensions: List[str] = Field(
            default_factory=lambda: [
                ".png", ".jpg", ".jpeg", ".webp",
                ".gif", ".bmp", ".tif", ".tiff"
            ]
        )
    def __init__(self):
        self.valves = self.Valves()
    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.valves.qwen_api_key:
            h["Authorization"] = f"Bearer {self.valves.qwen_api_key}"
        return h
    def _is_image(self, url: str) -> bool:
        u = (url or "").lower()
        if u.startswith("data:image/"):
            return True
        return any(u.endswith(ext) for ext in self.valves.allowed_image_extensions)
    def _extract_images(self, messages: List[dict]) -> List[dict]:
        images = []
        for m in messages:
            content = m.get("content")
            if isinstance(content, list):
                for part in content:
                    if part.get("type") == "image_url":
                        url = part.get("image_url", {}).get("url", "")
                        if self._is_image(url):
                            images.append(part)
        return images
    def _strip_images(self, messages: List[dict]) -> List[dict]:
        out = []
        for m in messages:
            nm = dict(m)
            c = nm.get("content")
            if isinstance(c, list):
                texts = [
                    p.get("text", "")
                    for p in c
                    if p.get("type") == "text"
                ]
                nm["content"] = "\n".join(t for t in texts if t).strip()
            out.append(nm)
        return out
    def _inject_caption(self, messages: List[dict], caption: str) -> List[dict]:
        caption = caption.strip()
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                m = dict(messages[i])
                base = m.get("content", "")
                if base:
                    base += "\n\n"
                base += caption
                m["content"] = base
                messages = list(messages)
                messages[i] = m
                return messages
        return messages + [{"role": "user", "content": caption}]
    def _caption(self, image_part: dict) -> str:
        payload = {
            "model": self.valves.qwen_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.valves.caption_prompt},
                        image_part,
                    ],
                }
            ],
            "temperature": 0.2,
        }
        r = requests.post(
            self.valves.qwen_base_url.rstrip("/") + "/v1/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=self.valves.timeout_sec,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    async def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        messages = body.get("messages")
        if not isinstance(messages, list):
            return body
        images = self._extract_images(messages)
        if not images:
            return body
        caption = ""
        try:
            caption = self._caption(images[0])
        except Exception as e:
            print("Vision error:", e)
        if caption or self.valves.strip_images_on_error:
            new_messages = self._strip_images(messages)
            if caption:
                new_messages = self._inject_caption(new_messages, caption)
            body = dict(body)
            body["messages"] = new_messages
        return body
