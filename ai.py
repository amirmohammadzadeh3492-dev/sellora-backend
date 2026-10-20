import os
import json
import urllib.parse
import httpx


# ---------- عکس (Pollinations - بدون Key) ----------
def generate_image_url(product_name: str) -> str:
    prompt = (
        f"professional product photo of {product_name}, "
        "studio lighting, clean white background, high quality, e-commerce"
    )
    encoded = urllib.parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded}?width=800&height=800&nologo=true"


# ---------- متن (Metis AI) ----------
METIS_API_KEY = os.getenv("METIS_API_KEY", "")
METIS_BASE_URL = os.getenv("METIS_BASE_URL", "https://api.metisai.ir/openai/v1")
METIS_MODEL = os.getenv("METIS_MODEL", "gpt-4o-mini")


async def _chat(system: str, user: str) -> str:
    if not METIS_API_KEY or METIS_API_KEY == "your_key_here":
        raise RuntimeError("METIS_API_KEY تنظیم نشده")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{METIS_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {METIS_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": METIS_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.7,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def generate_description(product_name: str, price: int) -> str:
    system = (
        "تو یک کوپی‌رایتر حرفه‌ای فارسی‌زبان هستی. "
        "توضیح کوتاه، جذاب و فروشنده برای محصول بنویس. حداکثر ۲ جمله."
    )
    user = f"محصول: {product_name}\nقیمت: {price:,} تومان"
    try:
        return await _chat(system, user)
    except Exception as e:
        return f"توضیح خودکار در دسترس نیست ({e})"


async def generate_faq(product_name: str, description: str) -> list[dict]:
    system = (
        "تو دستیار فروش حرفه‌ای هستی. بر اساس محصول، دقیقاً ۸ سوال پرتکرار "
        "مشتری بساز و جواب کوتاه بده. فقط JSON خالص برگردون: "
        '{"faqs": [{"question": "...", "answer": "..."}]}'
    )
    user = f"محصول: {product_name}\nتوضیحات: {description}"
    try:
        raw = (await _chat(system, user)).strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.lower().startswith("json"):
                raw = raw[4:]
        return json.loads(raw).get("faqs", [])
    except Exception:
        return []


async def chat_reply(
    message: str, shop_name: str, products: list[dict], faqs: list[dict]
) -> str:
    products_text = "\n".join(
        [f"- {p['name']} | {p['price']:,} تومان | {p['description']}" for p in products]
    ) or "هنوز محصولی ثبت نشده."
    faqs_text = "\n".join(
        [f"سوال: {f['question']}\nجواب: {f['answer']}" for f in faqs]
    ) or "بدون FAQ."

    system = (
        f"تو دستیار فروش فروشگاه «{shop_name}» هستی. "
        "کوتاه، مودب و مفید جواب بده. اگه نمی‌دونی بگو: «لطفاً با پشتیبانی تماس بگیرید».\n\n"
        f"محصولات:\n{products_text}\n\nFAQ:\n{faqs_text}"
    )
    try:
        return await _chat(system, message)
    except Exception as e:
        return f"متأسفم، الان نمی‌تونم جواب بدم. ({e})"