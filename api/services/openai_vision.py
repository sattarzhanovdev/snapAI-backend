import os
import base64
import json
from openai import OpenAI
from mimetypes import guess_type

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_image(image_field):
    try:
        image_field.seek(0)
        mime_type, _ = guess_type(image_field.name)
        if not mime_type:
            mime_type = "image/jpeg"

        image_bytes = image_field.read()
        print("Image size:", len(image_bytes))  # debug

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{image_b64}"

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты нутрициолог. ВСЕГДА отвечай строго JSON-объектом.\n"
                        "Формат:\n"
                        "{\n"
                        '  "title": str,\n'
                        '  "calories": int,\n'
                        '  "protein_g": int,\n'
                        '  "fat_g": int,\n'
                        '  "carbs_g": int,\n'
                        '  "ingredients": [ {"name": str, "calories": int, "protein_g": int, "fat_g": int, "carbs_g": int} ],\n'
                        '  "meta": { "health_score": int, "labels": [str] }\n'
                        "}"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Проанализируй это фото еды и верни JSON."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            max_tokens=800,
            response_format={"type": "json_object"},  # 👈 жёстко заставляем JSON
        )

        text = resp.choices[0].message.content
        print("AI raw response:", text[:200])  # debug

        return json.loads(text)

    except Exception as e:
        print("OpenAI Vision error:", e)
        return None