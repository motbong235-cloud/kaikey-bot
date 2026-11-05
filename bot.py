#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KaiKey Bot — sell Mode / File Key / DNS
User: /start → BUY NOW → Categories → Pack → Cart → ABA QR → auto key
Admin: full panel — products, stock, emoji premium, broadcast, users, orders, settings
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import telebot
from telebot import types
from telebot.types import InlineKeyboardButton as _IKB_orig
from telebot.types import KeyboardButton as _KB_orig
from telebot.types import MessageEntity as _MessageEntity
import re as _re

# ─── Premium emoji (Kai- style): char → custom_emoji_id ───────────────────
_EMOJI_CHAR_LIST = [
    '🛒', '📦', '💬', '🔑', '💵', '💳', '✅', '❌', '⚠️', '👥',
    '📊', '📢', '⚙️', '✨', '🟢', '🔴', '⬅️', '➕', '✏️', '🗑',
    '📱', '🧾', '🔢', '💰', '📘', '💀', '🟣', '👋', '🔗', '🌲',
    '⏱', '🔖', '🎨', '🛡', '🔄', '📋', '📤', '🎬', '🏠', '❓',
    '🛠', '💎', '⭐', '🔥', '🎯', '📁', '🔐', '💡', '🎉', '📌',
]
EMOJI_MAP = {ch: None for ch in _EMOJI_CHAR_LIST}
_STRIPPED_TEXT_MAP = {}

def _valid_emoji_id(eid):
    if eid is None:
        return None
    s = str(eid).strip()
    if not s or s.lower() in ("none", "null", "0"):
        return None
    if s.isdigit() and len(s) >= 8:
        return s
    try:
        n = int(float(s))
        if n > 0:
            return str(n)
    except Exception:
        pass
    return s if len(s) >= 8 else None

_EMOJI_CHARS_SORTED = sorted(EMOJI_MAP.keys(), key=len, reverse=True)
_LEADING_EMOJI_RE = _re.compile("^(" + "|".join(_re.escape(c) for c in _EMOJI_CHARS_SORTED) + ")")
_EMOJI_ANY_RE = _re.compile("(" + "|".join(_re.escape(c) for c in _EMOJI_CHARS_SORTED) + ")")

def _norm_emoji(ch):
    return (ch or "").replace("\ufe0f", "")

def _lookup_emoji_id(ch):
    if not ch:
        return None
    eid = _valid_emoji_id(EMOJI_MAP.get(ch))
    if eid:
        return eid
    n = _norm_emoji(ch)
    for k, v in EMOJI_MAP.items():
        eid = _valid_emoji_id(v)
        if eid and (k == ch or _norm_emoji(k) == n):
            return eid
    return None

def _leading_emoji(text):
    if not text:
        return None
    m = _LEADING_EMOJI_RE.match(text)
    return m.group(1) if m else None

def _entities_for_emoji_text(text):
    if not text:
        return []
    entities, utf16_pos, idx = [], 0, 0
    while idx < len(text):
        m = _EMOJI_ANY_RE.match(text, idx)
        if m:
            ch = m.group(1)
            length = len(ch.encode("utf-16-le")) // 2
            eid = _lookup_emoji_id(ch)
            if eid:
                entities.append(_MessageEntity(type="custom_emoji", offset=utf16_pos, length=length, custom_emoji_id=str(eid)))
            utf16_pos += length
            idx += len(ch)
        else:
            c = text[idx]
            utf16_pos += len(c.encode("utf-16-le")) // 2
            idx += 1
    return entities

def _strip_leading_emoji_text(text, ch):
    if not text or not ch:
        return text
    if text.startswith(ch):
        return text[len(ch):].lstrip()
    n = _norm_emoji(ch)
    if n and text.startswith(n):
        return text[len(n):].lstrip()
    return text

def _strip_emoji_once(text, ch):
    if not text or not ch:
        return text
    for v in (ch, _norm_emoji(ch)):
        if not v:
            continue
        i = text.find(v)
        if i >= 0:
            return (text[:i] + text[i + len(v):]).replace("  ", " ").strip()
    return text

_COLOR_MAP = {"active": "success", "progress": "primary", "danger": "danger", "inactive": None, "default": None}

def _to_style(color):
    if not color:
        return None
    return _COLOR_MAP.get(color, color if color in ("danger", "primary", "success") else None)

class InlineKeyboardButton(_IKB_orig):
    def __init__(self, *args, color=None, emoji_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._color = color
        label = kwargs.get("text") if "text" in kwargs else (args[0] if args else None)
        self._emoji_char = _leading_emoji(label)
        self._emoji_id = emoji_id

    def _resolve_emoji_id(self):
        if self._emoji_id:
            return _valid_emoji_id(self._emoji_id)
        return _lookup_emoji_id(self._emoji_char)

    def to_dict(self):
        d = super().to_dict()
        style = _to_style(self._color)
        if style:
            d["style"] = style
        eid = self._resolve_emoji_id()
        if eid and "text" in d:
            original = d["text"]
            d["icon_custom_emoji_id"] = eid
            stripped = _strip_leading_emoji_text(original, self._emoji_char)
            if stripped == original and self._emoji_char:
                stripped = _strip_emoji_once(original, self._emoji_char)
            if stripped != original:
                _STRIPPED_TEXT_MAP[stripped] = original
                d["text"] = stripped or original
        return d

class KeyboardButton(_KB_orig):
    def __init__(self, *args, color=None, emoji_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._color = color
        label = kwargs.get("text") if "text" in kwargs else (args[0] if args else None)
        self._emoji_char = _leading_emoji(label)
        self._emoji_id = emoji_id

    def _resolve_emoji_id(self):
        if self._emoji_id:
            return _valid_emoji_id(self._emoji_id)
        return _lookup_emoji_id(self._emoji_char)

    def to_dict(self):
        d = super().to_dict()
        style = _to_style(self._color)
        if style:
            d["style"] = style
        eid = self._resolve_emoji_id()
        if eid and "text" in d:
            original = d["text"]
            d["icon_custom_emoji_id"] = eid
            stripped = _strip_leading_emoji_text(original, self._emoji_char)
            if stripped == original and self._emoji_char:
                stripped = _strip_emoji_once(original, self._emoji_char)
            if stripped != original:
                _STRIPPED_TEXT_MAP[stripped] = original
                d["text"] = stripped or original
        return d

types.InlineKeyboardButton = InlineKeyboardButton
types.KeyboardButton = KeyboardButton


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",")
    if x.strip().isdigit()
}
KHMER_API_URL = (os.getenv("KHMER_API_URL") or "https://khmer-system.com").rstrip("/")
KHMER_API_KEY = os.getenv("KHMER_API_KEY", "").strip()
KHMER_PROFILE_KEY = os.getenv("KHMER_PROFILE_KEY", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
BOT_NAME = os.getenv("BOT_NAME", "KaiKey Store")
DATA_DIR = Path(os.getenv("DATA_DIR") or Path(__file__).parent / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

STORE_FILE = DATA_DIR / "store.json"
ORDERS_FILE = DATA_DIR / "orders.json"
USERS_FILE = DATA_DIR / "users.json"
EMOJI_FILE = DATA_DIR / "emoji.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

KH_TZ = timezone(timedelta(hours=7))
if not BOT_TOKEN:
    raise SystemExit("Set BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
_lock = threading.RLock()
# admin wizard state: uid -> {action, ...}
_wait: dict[int, dict] = {}

DEFAULT_STORE = {
    "welcome_text": (
        "👋 Hello <b>{name}</b>!\n\n"
        "🔗 Welcome to <b>{bot}</b>\n"
        "លក់ Mode / File Key / DNS\n"
        "Pls click button <b>BUY NOW</b>"
    ),
    "welcome_video": "",
    "categories": [
        {
            "id": "vpn_drip",
            "name": "VPN DRIP WIRE (IOS&ADR)",
            "icon": "🟣",
            "enabled": True,
            "packs": [
                {"id": "drip_1m", "name": "1ខែ", "price": 2.10, "stock": [], "stock_type": "text", "enabled": True},
                {"id": "drip_6m", "name": "6ខែ", "price": 1.00, "stock": [], "stock_type": "text", "enabled": True},
            ],
        },
        {
            "id": "esign",
            "name": "Esign Certificate",
            "icon": "📘",
            "enabled": True,
            "packs": [
                {"id": "esign_1", "name": "1 Certificate", "price": 3.00, "stock": [], "stock_type": "file", "enabled": True},
            ],
        },
        {
            "id": "vpn_phantom",
            "name": "VPN PHANTOM VIP (IOS & ADR)",
            "icon": "💀",
            "enabled": True,
            "packs": [
                {"id": "ph_1m", "name": "1ខែ", "price": 2.50, "stock": [], "stock_type": "text", "enabled": True},
            ],
        },
        {
            "id": "dns_key",
            "name": "DNS / File Key",
            "icon": "🔑",
            "enabled": True,
            "packs": [
                {"id": "dns_std", "name": "DNS Config", "price": 1.50, "stock": [], "stock_type": "text", "enabled": True},
                {"id": "key_file", "name": "File Key", "price": 2.00, "stock": [], "stock_type": "file", "enabled": True},
            ],
        },
    ],
}

# Premium custom emoji ids (Telegram premium) — admin can set
DEFAULT_EMOJI = {}


def _read(path: Path, default):
    with _lock:
        if not path.exists():
            return json.loads(json.dumps(default))
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return json.loads(json.dumps(default))


def _write(path: Path, data):
    with _lock:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


def load_store():
    s = _read(STORE_FILE, None)
    if not s:
        _write(STORE_FILE, DEFAULT_STORE)
        return json.loads(json.dumps(DEFAULT_STORE))
    return s


def save_store(s):
    _write(STORE_FILE, s)


def load_orders():
    return _read(ORDERS_FILE, {})


def save_orders(o):
    _write(ORDERS_FILE, o)


def load_users():
    return _read(USERS_FILE, {})


def save_users(u):
    _write(USERS_FILE, u)


def load_emoji():
    """Load char→custom_emoji_id into global EMOJI_MAP (Kai- style)."""
    global EMOJI_MAP, _EMOJI_CHARS_SORTED, _LEADING_EMOJI_RE, _EMOJI_ANY_RE
    data = _read(EMOJI_FILE, {}) or {}
    for ch in list(EMOJI_MAP.keys()):
        if ch in data and data[ch]:
            EMOJI_MAP[ch] = str(data[ch]).strip()
    for k, v in data.items():
        if k and v:
            EMOJI_MAP[str(k)] = str(v).strip()
    _EMOJI_CHARS_SORTED = sorted(EMOJI_MAP.keys(), key=len, reverse=True)
    if _EMOJI_CHARS_SORTED:
        _LEADING_EMOJI_RE = _re.compile("^(" + "|".join(_re.escape(c) for c in _EMOJI_CHARS_SORTED) + ")")
        _EMOJI_ANY_RE = _re.compile("(" + "|".join(_re.escape(c) for c in _EMOJI_CHARS_SORTED) + ")")
    return {k: v for k, v in EMOJI_MAP.items() if v}


def save_emoji(e=None):
    data = e if e is not None else {k: v for k, v in EMOJI_MAP.items() if v}
    _write(EMOJI_FILE, data)


def load_settings():
    return _read(
        SETTINGS_FILE,
        {
            "support_text": "💬 Support — ទាក់ទង admin",
            "force_channel": "",
            "maintenance": False,
        },
    )


def save_settings(s):
    _write(SETTINGS_FILE, s)


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def now_kh():
    return datetime.now(KH_TZ).strftime("%Y-%m-%d %H:%M:%S")


def esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def pe(key: str, fallback: str = "") -> str:
    return fallback or ""


def pack_stock_count(pack) -> int:
    return len(pack.get("stock") or [])


def find_cat(store, cat_id):
    for c in store.get("categories") or []:
        if c.get("id") == cat_id:
            return c
    return None


def find_pack(store, cat_id, pack_id):
    c = find_cat(store, cat_id)
    if not c:
        return None, None
    for p in c.get("packs") or []:
        if p.get("id") == pack_id:
            return c, p
    return c, None


def pop_stock(store, cat_id, pack_id):
    c, p = find_pack(store, cat_id, pack_id)
    if not p:
        return None, store
    stock = list(p.get("stock") or [])
    if not stock:
        return None, store
    item = stock.pop(0)
    p["stock"] = stock
    save_store(store)
    return item, store


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", (name or "").lower()).strip("_")
    return (s or "item")[:24]


# ─── Payment ──────────────────────────────────────────────────────────────
def create_qr(amount: float, order_id: str, remark: str = ""):
    if not KHMER_API_KEY and not KHMER_PROFILE_KEY:
        return {"ok": False, "error": "payment_not_configured"}
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    payloads = [
        {
            "url": f"{KHMER_API_URL}/api/qr/create",
            "json": {
                "api_key": KHMER_API_KEY or KHMER_PROFILE_KEY,
                "profile_key": KHMER_PROFILE_KEY or KHMER_API_KEY,
                "amount": float(amount),
                "order_id": order_id,
                "remark": remark or order_id,
            },
        },
        {
            "url": f"{KHMER_API_URL}/api/v1/qr",
            "json": {
                "key": KHMER_API_KEY or KHMER_PROFILE_KEY,
                "amount": float(amount),
                "reference": order_id,
                "description": remark or order_id,
            },
        },
    ]
    last_err = "unknown"
    for p in payloads:
        try:
            r = requests.post(p["url"], json=p["json"], headers=headers, timeout=25)
            data = r.json() if r.content else {}
            if r.ok and (data.get("ok") is True or data.get("success") or data.get("qr") or data.get("data")):
                d = data.get("data") or data
                return {
                    "ok": True,
                    "transaction_id": str(
                        d.get("transaction_id") or d.get("tran_id") or d.get("id") or d.get("reference") or order_id
                    ),
                    "qr_image": d.get("qr_image") or d.get("qr_url") or d.get("image") or d.get("qr"),
                    "qr_string": d.get("qr_string") or d.get("qr_data") or d.get("khqr"),
                    "deeplink": d.get("deeplink") or d.get("aba_deeplink") or d.get("app_link") or "",
                }
            last_err = data.get("error") or data.get("message") or f"HTTP {r.status_code}"
        except Exception as e:
            last_err = str(e)
    return {"ok": False, "error": last_err}


def check_payment(transaction_id: str):
    if not transaction_id:
        return {"paid": False}
    headers = {"Content-Type": "application/json"}
    urls = [
        (f"{KHMER_API_URL}/api/qr/status", {"api_key": KHMER_API_KEY or KHMER_PROFILE_KEY, "transaction_id": transaction_id}),
        (f"{KHMER_API_URL}/api/v1/qr/check", {"key": KHMER_API_KEY or KHMER_PROFILE_KEY, "transaction_id": transaction_id}),
    ]
    for url, body in urls:
        try:
            r = requests.post(url, json=body, headers=headers, timeout=20)
            data = r.json() if r.content else {}
            d = data.get("data") or data
            st = str(d.get("status") or data.get("status") or "").lower()
            paid = st in ("paid", "success", "completed", "done") or d.get("paid") is True
            if paid:
                return {"paid": True, "status": st or "paid"}
            if r.ok:
                return {"paid": False, "status": st or "pending"}
        except Exception:
            continue
    return {"paid": False, "status": "unknown"}


# ─── Keyboards ────────────────────────────────────────────────────────────
def kb_main():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row(types.KeyboardButton("🛒 BUY NOW"))
    m.row(types.KeyboardButton("📦 ការបញ្ជាទិញរបស់ខ្ញុំ"), types.KeyboardButton("💬 Support"))
    return m


def kb_buy_inline():
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("🛒 BUY NOW", callback_data="buy"))
    return m


def kb_categories(store):
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("🛒 Categories all 🔀", callback_data="cats"))
    for c in store.get("categories") or []:
        if not c.get("enabled", True):
            continue
        icon = c.get("icon") or "📦"
        m.add(types.InlineKeyboardButton(f"{icon} {c.get('name')}", callback_data=f"cat:{c['id']}"))
    return m


def kb_packs(cat):
    m = types.InlineKeyboardMarkup()
    for p in cat.get("packs") or []:
        if not p.get("enabled", True):
            continue
        n = pack_stock_count(p)
        if n <= 0:
            m.add(types.InlineKeyboardButton(f"🔴 {p.get('name')} - ${p.get('price'):.2f} (Out)", callback_data="noop"))
        else:
            m.add(
                types.InlineKeyboardButton(
                    f"🟢 {p.get('name')} - ${p.get('price'):.2f} ({n})",
                    callback_data=f"pack:{cat['id']}:{p['id']}",
                )
            )
    m.add(types.InlineKeyboardButton("⬅️ Back ( Category )", callback_data="cats"))
    return m


def kb_cart(order_id: str):
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("💳 បង់ប្រាក់ (ABA PAY)", callback_data=f"pay:{order_id}"))
    m.add(types.InlineKeyboardButton("⬅️ Back", callback_data="cats"))
    return m


def kb_qr(order_id: str, deeplink: str = ""):
    m = types.InlineKeyboardMarkup()
    if deeplink:
        m.add(types.InlineKeyboardButton("📱 Open ABA Mobile", url=deeplink))
    m.add(types.InlineKeyboardButton("❌ Cancel QR / បោះបង់", callback_data=f"cancel:{order_id}"))
    return m


def kb_admin_home():
    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(
        types.InlineKeyboardButton("📦 Products", callback_data="ad:products"),
        types.InlineKeyboardButton("🔑 Stock", callback_data="ad:stock"),
    )
    m.add(
        types.InlineKeyboardButton("📋 Orders", callback_data="ad:orders"),
        types.InlineKeyboardButton("👥 Users", callback_data="ad:users"),
    )
    m.add(
        types.InlineKeyboardButton("📢 Broadcast", callback_data="ad:broadcast"),
        types.InlineKeyboardButton("✨ Emoji Premium", callback_data="ad:emoji"),
    )
    m.add(
        types.InlineKeyboardButton("⚙️ Settings", callback_data="ad:settings"),
        types.InlineKeyboardButton("📊 Stats", callback_data="ad:stats"),
    )
    m.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="ad:home"))
    return m


def kb_admin_products(store):
    m = types.InlineKeyboardMarkup()
    for c in store.get("categories") or []:
        en = "✅" if c.get("enabled", True) else "⛔"
        m.add(
            types.InlineKeyboardButton(
                f"{en} {c.get('icon') or '📦'} {c.get('name')}",
                callback_data=f"ad:cat:{c['id']}",
            )
        )
    m.add(types.InlineKeyboardButton("➕ បង្កើត Category", callback_data="ad:newcat"))
    m.add(types.InlineKeyboardButton("⬅️ Admin", callback_data="ad:home"))
    return m


def kb_admin_cat(cat):
    m = types.InlineKeyboardMarkup()
    m.add(
        types.InlineKeyboardButton("➕ បន្ថែម Pack", callback_data=f"ad:newpack:{cat['id']}"),
        types.InlineKeyboardButton(
            "⛔ បិទ" if cat.get("enabled", True) else "✅ បើក",
            callback_data=f"ad:togglecat:{cat['id']}",
        ),
    )
    m.add(types.InlineKeyboardButton("✏️ ឈ្មោះ Category", callback_data=f"ad:renamecat:{cat['id']}"))
    m.add(types.InlineKeyboardButton("🎨 Icon", callback_data=f"ad:iconcat:{cat['id']}"))
    for p in cat.get("packs") or []:
        st = pack_stock_count(p)
        en = "✅" if p.get("enabled", True) else "⛔"
        m.add(
            types.InlineKeyboardButton(
                f"{en} {p.get('name')} ${p.get('price'):.2f} · {st}",
                callback_data=f"ad:pack:{cat['id']}:{p['id']}",
            )
        )
    m.add(types.InlineKeyboardButton("🗑 លុប Category", callback_data=f"ad:delcat:{cat['id']}"))
    m.add(types.InlineKeyboardButton("⬅️ Products", callback_data="ad:products"))
    return m


def kb_admin_pack(cat_id, pack):
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("🔑 បន្ថែម Stock", callback_data=f"ad:addstock:{cat_id}:{pack['id']}"))
    m.add(types.InlineKeyboardButton("💵 កែតម្លៃ", callback_data=f"ad:price:{cat_id}:{pack['id']}"))
    m.add(types.InlineKeyboardButton("✏️ ឈ្មោះ Pack", callback_data=f"ad:renamepack:{cat_id}:{pack['id']}"))
    m.add(
        types.InlineKeyboardButton(
            "⛔ បិទ Pack" if pack.get("enabled", True) else "✅ បើក Pack",
            callback_data=f"ad:togglepack:{cat_id}:{pack['id']}",
        )
    )
    m.add(
        types.InlineKeyboardButton(
            f"Type: {pack.get('stock_type') or 'text'}",
            callback_data=f"ad:stocktype:{cat_id}:{pack['id']}",
        )
    )
    m.add(types.InlineKeyboardButton("🗑 លុប Pack", callback_data=f"ad:delpack:{cat_id}:{pack['id']}"))
    m.add(types.InlineKeyboardButton("⬅️ Category", callback_data=f"ad:cat:{cat_id}"))
    return m


def kb_emoji_menu(per_row=5):
    """Grid of unicode emojis used in bot — ✅ = has premium id."""
    load_emoji()
    m = types.InlineKeyboardMarkup(row_width=per_row)
    row = []
    for ch in _EMOJI_CHAR_LIST:
        mark = "✅" if _valid_emoji_id(EMOJI_MAP.get(ch)) else "⬜"
        # callback cannot always carry full emoji safely — use index
        idx = _EMOJI_CHAR_LIST.index(ch)
        row.append(types.InlineKeyboardButton(f"{mark}{ch}", callback_data=f"ad:emset:{idx}"))
        if len(row) >= per_row:
            m.row(*row)
            row = []
    if row:
        m.row(*row)
    m.add(types.InlineKeyboardButton("📋 Set many (reply message)", callback_data="ad:emmulti"))
    m.add(types.InlineKeyboardButton("👁 Preview", callback_data="ad:empreview"))
    m.add(types.InlineKeyboardButton("⬅️ Admin", callback_data="ad:home"))
    return m


def _apply_setemojis_from_message(src_msg):
    """Map premium custom_emoji entities in a message onto unicode chars in same text (Kai-)."""
    text = src_msg.text or src_msg.caption or ""
    ents = list(src_msg.entities or []) + list(src_msg.caption_entities or [])
    applied = []
    for e in ents:
        if getattr(e, "type", None) != "custom_emoji":
            continue
        cid = str(getattr(e, "custom_emoji_id", "") or "")
        if not _valid_emoji_id(cid):
            continue
        # Telegram entity offsets are UTF-16
        # Extract the underlying character(s) at that span from text — often a normal emoji
        # Approximate: find any known EMOJI_MAP char near that region by scanning text
        # Prefer: pair by order of appearance of custom_emoji with leading normal emoji in text
        applied.append(cid)
    # Pair sequential normal emojis in text with sequential custom_emoji ids
    normals = _EMOJI_ANY_RE.findall(text) if text else []
    customs = []
    for e in ents:
        if getattr(e, "type", None) == "custom_emoji" and _valid_emoji_id(getattr(e, "custom_emoji_id", None)):
            customs.append(str(e.custom_emoji_id))
    n = min(len(normals), len(customs))
    report = []
    for i in range(n):
        ch, cid = normals[i], customs[i]
        EMOJI_MAP[ch] = cid
        report.append(f"{ch} → <code>{cid}</code>")
    if report:
        save_emoji()
        load_emoji()
    return report


# ─── Orders / deliver ─────────────────────────────────────────────────────
def new_order(uid, cat, pack, qty=1):
    oid = "MK" + uuid.uuid4().hex[:10].upper()
    total = round(float(pack.get("price", 0)) * qty, 2)
    orders = load_orders()
    orders[oid] = {
        "id": oid,
        "user_id": uid,
        "cat_id": cat["id"],
        "cat_name": cat.get("name"),
        "pack_id": pack["id"],
        "pack_name": pack.get("name"),
        "price": float(pack.get("price", 0)),
        "qty": qty,
        "total": total,
        "status": "cart",
        "created_at": now_kh(),
        "transaction_id": None,
        "delivered": [],
    }
    save_orders(orders)
    return orders[oid]


def touch_user(msg):
    u = load_users()
    uid = str(msg.from_user.id)
    row = u.get(uid) or {}
    row.update(
        {
            "id": msg.from_user.id,
            "name": msg.from_user.first_name or "",
            "username": msg.from_user.username or "",
            "last": now_kh(),
            "orders": row.get("orders") or 0,
        }
    )
    if "first" not in row:
        row["first"] = now_kh()
    u[uid] = row
    save_users(u)


def deliver_order(order):
    store = load_store()
    delivered = []
    for _ in range(int(order.get("qty") or 1)):
        item, store = pop_stock(store, order["cat_id"], order["pack_id"])
        if item is None:
            break
        delivered.append(item)
    orders = load_orders()
    o = orders.get(order["id"]) or order
    o["status"] = "delivered" if delivered else "paid_nostock"
    o["delivered"] = delivered
    o["paid_at"] = now_kh()
    orders[o["id"]] = o
    save_orders(orders)
    # bump user order count
    u = load_users()
    uid = str(o.get("user_id"))
    if uid in u:
        u[uid]["orders"] = int(u[uid].get("orders") or 0) + 1
        save_users(u)
    return o


def send_delivery(chat_id, order):
    items = order.get("delivered") or []
    if not items:
        bot.send_message(
            chat_id,
            f"✅ បង់ប្រាក់រួច <code>{esc(order['id'])}</code>\n⚠️ ស្តុកអស់ — Admin នឹងផ្ញើដោយដៃ។",
        )
        notify_admins(
            f"⚠️ PAID no stock\n<code>{esc(order['id'])}</code>\nUser {order.get('user_id')}\n"
            f"{esc(order.get('cat_name'))} / {esc(order.get('pack_name'))}"
        )
        return
    bot.send_message(
        chat_id,
        f"✅ <b>បង់ប្រាក់ជោគជ័យ</b>\n"
        f"Order: <code>{esc(order['id'])}</code>\n"
        f"📦 {esc(order.get('cat_name'))} · {esc(order.get('pack_name'))} ×{order.get('qty')}\n"
        f"ខាងក្រោមជា Key / File៖",
    )
    for i, item in enumerate(items, 1):
        if isinstance(item, dict) and item.get("file_id"):
            try:
                bot.send_document(chat_id, item["file_id"], caption=f"🔑 File #{i}")
            except Exception:
                bot.send_message(chat_id, f"🔑 #{i}: <code>{esc(item.get('file_id'))}</code>")
        else:
            bot.send_message(chat_id, f"🔑 <b>Key #{i}</b>\n<code>{esc(item)}</code>")
    notify_admins(
        f"✅ DELIVERED <code>{esc(order['id'])}</code>\nUser {order.get('user_id')} · ${order.get('total')}"
    )


def notify_admins(text):
    for aid in ADMIN_IDS:
        try:
            bot.send_message(aid, text)
        except Exception:
            pass
    if CHANNEL_ID:
        try:
            bot.send_message(CHANNEL_ID, text)
        except Exception:
            pass


def poll_payment(order_id: str, chat_id: int, tries: int = 40):
    for _ in range(tries):
        time.sleep(15)
        orders = load_orders()
        o = orders.get(order_id)
        if not o or o.get("status") in ("delivered", "paid_nostock", "cancelled"):
            return
        tid = o.get("transaction_id")
        if not tid:
            return
        res = check_payment(tid)
        if res.get("paid"):
            o = deliver_order(o)
            try:
                send_delivery(chat_id, o)
            except Exception as e:
                notify_admins(f"deliver error {order_id}: {e}")
            return


def admin_stats_text():
    users = load_users()
    orders = load_orders()
    store = load_store()
    paid = [o for o in orders.values() if o.get("status") in ("delivered", "paid_nostock")]
    revenue = sum(float(o.get("total") or 0) for o in paid)
    stock_n = 0
    for c in store.get("categories") or []:
        for p in c.get("packs") or []:
            stock_n += pack_stock_count(p)
    return (
        f"📊 <b>Stats</b>\n\n"
        f"👥 Users: <b>{len(users)}</b>\n"
        f"📋 Orders: <b>{len(orders)}</b>\n"
        f"✅ Paid/Delivered: <b>{len(paid)}</b>\n"
        f"💰 Revenue: <b>${revenue:.2f}</b>\n"
        f"🔑 Stock left: <b>{stock_n}</b>\n"
        f"🕒 {now_kh()}"
    )


# ─── User handlers ────────────────────────────────────────────────────────
@bot.message_handler(commands=["start", "menu"])
def cmd_start(msg):
    touch_user(msg)
    st = load_settings()
    if st.get("maintenance") and not is_admin(msg.from_user.id):
        bot.send_message(msg.chat.id, "🛠 កំពុងថែទាំ — សូមមកវិញពេលក្រោយ")
        return
    store = load_store()
    name = esc(msg.from_user.first_name or "friend")
    text = (store.get("welcome_text") or DEFAULT_STORE["welcome_text"]).format(name=name, bot=esc(BOT_NAME))
    vid = store.get("welcome_video") or ""
    if vid:
        try:
            bot.send_video(msg.chat.id, vid, caption=text, reply_markup=kb_buy_inline())
            bot.send_message(msg.chat.id, "👇", reply_markup=kb_main())
            return
        except Exception:
            pass
    bot.send_message(msg.chat.id, text, reply_markup=kb_buy_inline())
    bot.send_message(msg.chat.id, "ជ្រើសមុខងារ៖", reply_markup=kb_main())


@bot.message_handler(commands=["admin", "panel"])
def cmd_admin(msg):
    if not is_admin(msg.from_user.id):
        return
    bot.send_message(
        msg.chat.id,
        f"🛡 <b>Admin Panel</b> — {esc(BOT_NAME)}\n\nជ្រើសមុខងារ៖",
        reply_markup=kb_admin_home(),
    )


@bot.message_handler(func=lambda m: m.text and "BUY NOW" in (m.text or "").upper())
def msg_buy(msg):
    touch_user(msg)
    store = load_store()
    bot.send_message(msg.chat.id, "🛒 <b>Categories all</b>\nជ្រើសប្រភេទទំនិញ៖", reply_markup=kb_categories(store))


@bot.message_handler(func=lambda m: m.text and "Support" in (m.text or ""))
def msg_support(msg):
    st = load_settings()
    bot.send_message(msg.chat.id, st.get("support_text") or "💬 Support")


@bot.message_handler(func=lambda m: m.text and "ការបញ្ជាទិញ" in (m.text or ""))
def msg_my_orders(msg):
    orders = load_orders()
    mine = [o for o in orders.values() if o.get("user_id") == msg.from_user.id]
    mine = sorted(mine, key=lambda x: x.get("created_at") or "", reverse=True)[:10]
    if not mine:
        bot.send_message(msg.chat.id, "អត់មាន order ទេ។")
        return
    lines = ["📦 <b>Orders ថ្មីៗ</b>\n"]
    for o in mine:
        lines.append(
            f"• <code>{esc(o['id'])}</code> · {esc(o.get('pack_name'))} · ${o.get('total')} · <b>{esc(o.get('status'))}</b>"
        )
    bot.send_message(msg.chat.id, "\n".join(lines))


# ─── Callbacks: user + admin ──────────────────────────────────────────────
@bot.callback_query_handler(func=lambda c: True)
def on_cb(c: types.CallbackQuery):
    data = c.data or ""
    uid = c.from_user.id
    chat_id = c.message.chat.id

    # ——— Admin ———
    if data.startswith("ad:"):
        if not is_admin(uid):
            bot.answer_callback_query(c.id, "Admin only", show_alert=True)
            return
        handle_admin_cb(c)
        return

    if data == "noop":
        bot.answer_callback_query(c.id, "Out of stock", show_alert=True)
        return

    if data in ("buy", "cats"):
        store = load_store()
        bot.answer_callback_query(c.id)
        try:
            bot.edit_message_text(
                "🛒 <b>Categories all</b>\nជ្រើសប្រភេទទំនិញ៖",
                chat_id,
                c.message.message_id,
                reply_markup=kb_categories(store),
            )
        except Exception:
            bot.send_message(chat_id, "🛒 <b>Categories all</b>", reply_markup=kb_categories(store))
        return

    if data.startswith("cat:"):
        cat_id = data.split(":", 1)[1]
        store = load_store()
        cat = find_cat(store, cat_id)
        if not cat:
            bot.answer_callback_query(c.id, "Not found", show_alert=True)
            return
        bot.answer_callback_query(c.id)
        bot.send_message(
            chat_id,
            f"{cat.get('icon') or '📦'} <b>{esc(cat.get('name'))}</b>\nជ្រើសកញ្ចប់៖",
            reply_markup=kb_packs(cat),
        )
        return

    if data.startswith("pack:"):
        _, cat_id, pack_id = data.split(":", 2)
        store = load_store()
        cat, pack = find_pack(store, cat_id, pack_id)
        if not pack or pack_stock_count(pack) <= 0:
            bot.answer_callback_query(c.id, "Out of stock", show_alert=True)
            return
        order = new_order(uid, cat, pack, qty=1)
        bot.answer_callback_query(c.id)
        text = (
            "🧾 <b>កំណត់ត្រាទំនិញដែលបានជ្រើស</b>\n\n"
            f"🛒 · ទំនិញ៖ {esc(cat.get('name'))}\n"
            f"📦 · កញ្ចប់៖ {esc(pack.get('name'))}\n"
            f"💵 · តម្លៃ៖ ${pack.get('price'):.2f} / ឯកតា\n"
            f"🔢 · ស្តុកនៅសល់៖ {pack_stock_count(pack)}\n"
            f"━━━━━━━━━━━━\n"
            f"📦 · ចំនួន៖ {order['qty']}\n"
            f"💰 · សរុប៖ <b>${order['total']:.2f}</b>\n\n"
            "ចុច <b>បង់ប្រាក់ (ABA PAY)</b> ដើម្បីបង្កើត QR"
        )
        bot.send_message(chat_id, text, reply_markup=kb_cart(order["id"]))
        return

    if data.startswith("pay:"):
        oid = data.split(":", 1)[1]
        orders = load_orders()
        o = orders.get(oid)
        if not o or o.get("user_id") != uid:
            bot.answer_callback_query(c.id, "Order not found", show_alert=True)
            return
        if o.get("status") not in ("cart", "pending"):
            bot.answer_callback_query(c.id, f"Status: {o.get('status')}", show_alert=True)
            return
        bot.answer_callback_query(c.id, "កំពុងបង្កើត QR…")
        qr = create_qr(o["total"], o["id"], f"{o.get('pack_name')} x{o.get('qty')}")
        if not qr.get("ok"):
            bot.send_message(
                chat_id,
                f"⚠️ មិនអាចបង្កើត QR\n<code>{esc(qr.get('error'))}</code>",
            )
            return
        o["status"] = "pending"
        o["transaction_id"] = qr.get("transaction_id")
        orders[oid] = o
        save_orders(orders)
        caption = (
            "💳 <b>ABA PAY WAY (KHQR)</b>\n"
            f"- 💵 ចំនួនត្រូវ pay : <b>${o['total']:.2f}</b>\n"
            f"- 📦 ទំនិញ : {esc(o.get('pack_name'))} x{o.get('qty')}\n"
            f"- 🔖 Ref : <code>{esc(o.get('transaction_id'))}</code>\n"
            f"- ⏱ QR ~ 10 នាទី\n"
            "- 🌲 បន្ទាប់ពីបង់ នឹងផ្ញើ Key/File ស្វ័យប្រវត្តិ"
        )
        deeplink = qr.get("deeplink") or ""
        img = qr.get("qr_image")
        try:
            if img and str(img).startswith("http"):
                bot.send_photo(chat_id, img, caption=caption, reply_markup=kb_qr(oid, deeplink))
            else:
                extra = qr.get("qr_string") or ""
                bot.send_message(
                    chat_id,
                    caption + (f"\n\n<code>{esc(extra)[:300]}</code>" if extra else ""),
                    reply_markup=kb_qr(oid, deeplink),
                )
        except Exception as e:
            bot.send_message(chat_id, caption + f"\n({esc(e)})", reply_markup=kb_qr(oid, deeplink))
        threading.Thread(target=poll_payment, args=(oid, chat_id), daemon=True).start()
        notify_admins(
            f"🛒 NEW QR <code>{esc(oid)}</code>\nUser {uid}\n"
            f"{esc(o.get('cat_name'))} / {esc(o.get('pack_name'))} = ${o.get('total')}"
        )
        return

    if data.startswith("cancel:"):
        oid = data.split(":", 1)[1]
        orders = load_orders()
        o = orders.get(oid)
        if o and o.get("user_id") == uid and o.get("status") == "pending":
            o["status"] = "cancelled"
            orders[oid] = o
            save_orders(orders)
            bot.answer_callback_query(c.id, "Cancelled")
            bot.send_message(chat_id, "❌ បានបោះបង់ QR", reply_markup=kb_main())
        else:
            bot.answer_callback_query(c.id, "Cannot cancel")
        return

    bot.answer_callback_query(c.id)


def handle_admin_cb(c: types.CallbackQuery):
    data = c.data or ""
    uid = c.from_user.id
    chat_id = c.message.chat.id
    mid = c.message.message_id
    store = load_store()

    def edit(text, markup=None):
        try:
            bot.edit_message_text(text, chat_id, mid, reply_markup=markup)
        except Exception:
            bot.send_message(chat_id, text, reply_markup=markup)

    if data in ("ad:home", "ad:"):
        bot.answer_callback_query(c.id)
        edit(f"🛡 <b>Admin Panel</b> — {esc(BOT_NAME)}", kb_admin_home())
        return

    if data == "ad:stats":
        bot.answer_callback_query(c.id)
        edit(admin_stats_text(), kb_admin_home())
        return

    if data == "ad:products":
        bot.answer_callback_query(c.id)
        edit("📦 <b>Products / Categories</b>\nចុច category ដើម្បីកែ · ឬបង្កើតថ្មី", kb_admin_products(store))
        return

    if data == "ad:stock":
        bot.answer_callback_query(c.id)
        lines = ["🔑 <b>Stock overview</b>\n"]
        for cat in store.get("categories") or []:
            lines.append(f"\n{cat.get('icon')} <b>{esc(cat.get('name'))}</b> <code>{cat['id']}</code>")
            for p in cat.get("packs") or []:
                lines.append(
                    f"  · <code>{p['id']}</code> {esc(p.get('name'))} "
                    f"${p.get('price'):.2f} · <b>{pack_stock_count(p)}</b>"
                )
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("⬅️ Admin", callback_data="ad:home"))
        edit("\n".join(lines), m)
        return

    if data == "ad:orders":
        bot.answer_callback_query(c.id)
        orders = load_orders()
        items = sorted(orders.values(), key=lambda x: x.get("created_at") or "", reverse=True)[:12]
        lines = ["📋 <b>Recent orders</b>\n"]
        m = types.InlineKeyboardMarkup()
        if not items:
            lines.append("គ្មាន")
        for o in items:
            lines.append(
                f"<code>{esc(o['id'])}</code> u={o.get('user_id')} "
                f"{esc(o.get('pack_name'))} ${o.get('total')} · {esc(o.get('status'))}"
            )
            if o.get("status") in ("pending", "paid_nostock", "cart"):
                m.add(
                    types.InlineKeyboardButton(
                        f"✅ Force {o['id'][-6:]}",
                        callback_data=f"ad:force:{o['id']}",
                    )
                )
        m.add(types.InlineKeyboardButton("⬅️ Admin", callback_data="ad:home"))
        edit("\n".join(lines), m)
        return

    if data.startswith("ad:force:"):
        oid = data.split(":", 2)[2]
        orders = load_orders()
        o = orders.get(oid)
        if not o:
            bot.answer_callback_query(c.id, "Not found", show_alert=True)
            return
        o = deliver_order(o)
        try:
            send_delivery(o["user_id"], o)
        except Exception as e:
            bot.answer_callback_query(c.id, str(e)[:100], show_alert=True)
            return
        bot.answer_callback_query(c.id, "Delivered")
        edit(f"✅ Forced <code>{esc(oid)}</code> → {esc(o.get('status'))}", kb_admin_home())
        return

    if data == "ad:users":
        bot.answer_callback_query(c.id)
        users = load_users()
        rows = sorted(users.values(), key=lambda x: x.get("last") or "", reverse=True)[:20]
        lines = [f"👥 <b>Users</b> (total {len(users)})\n"]
        for u in rows:
            un = f"@{u['username']}" if u.get("username") else "—"
            lines.append(
                f"• <code>{u.get('id')}</code> {esc(u.get('name'))} {un}\n"
                f"  orders={u.get('orders') or 0} · last {esc(u.get('last'))}"
            )
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("📤 Export IDs", callback_data="ad:exportusers"))
        m.add(types.InlineKeyboardButton("⬅️ Admin", callback_data="ad:home"))
        edit("\n".join(lines)[:3500], m)
        return

    if data == "ad:exportusers":
        bot.answer_callback_query(c.id)
        users = load_users()
        text = "\n".join(str(u.get("id")) for u in users.values())
        bot.send_message(chat_id, f"<code>{esc(text)[:3500]}</code>" if text else "empty")
        return

    if data == "ad:broadcast":
        bot.answer_callback_query(c.id)
        _wait[uid] = {"action": "broadcast"}
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("❌ បោះបង់", callback_data="ad:home"))
        edit("📢 ផ្ញើសារ broadcast\n\nវាយសារ (HTML បាន) រួចផ្ញើមក:", m)
        return

    if data == "ad:emoji":
        bot.answer_callback_query(c.id)
        set_n = sum(1 for v in EMOJI_MAP.values() if _valid_emoji_id(v))
        edit(
            "✨ <b>Emoji Premium Setup</b> (Kai- style)\n\n"
            f"កំណត់រួច: <b>{set_n}</b> / {len(_EMOJI_CHAR_LIST)}\n\n"
            "• ចុច emoji ⬜ → ផ្ញើ <b>Premium emoji</b> មួយ\n"
            "• ឬ <b>Set many</b>: reply សារមាន premium emoji ច្រើន\n"
            "• ប៊ូតុងដែលចាប់ផ្តើមដោយ emoji នឹងបង្ហាញ premium icon ស្វ័យប្រវត្តិ",
            kb_emoji_menu(),
        )
        return

    if data == "ad:emmulti":
        bot.answer_callback_query(c.id)
        _wait[uid] = {"action": "set_emoji_multi"}
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("⬅️ Emoji", callback_data="ad:emoji"))
        edit(
            "📋 <b>Set many</b>\n\n"
            "ផ្ញើសារមួយដែលមាន <b>emoji ធម្មតា + premium emoji</b>\n"
            "(ឬ premium តាមលំដាប់ emoji ក្នុង bot)\n\n"
            "ឧទាហរណ៍: 🛒📦🔑 ជាមួយ premium icons",
            m,
        )
        return

    if data == "ad:empreview":
        bot.answer_callback_query(c.id)
        load_emoji()
        parts, entities, offset = [], [], 0
        for ch in _EMOJI_CHAR_LIST:
            eid = _valid_emoji_id(EMOJI_MAP.get(ch))
            if not eid:
                continue
            parts.append(ch + " ")
            length = len(ch.encode("utf-16-le")) // 2
            entities.append(
                _MessageEntity(
                    type="custom_emoji",
                    offset=offset,
                    length=length,
                    custom_emoji_id=str(eid),
                )
            )
            offset += length + 1
        if not parts:
            bot.send_message(chat_id, "មិនទាន់មាន emoji premium — ចុច ⬜ ដើម្បីកំណត់")
            return
        prefix = "Preview:\n"
        body = "".join(parts)
        prefix_u16 = len(prefix.encode("utf-16-le")) // 2
        try:
            bot.send_message(
                chat_id,
                prefix + body,
                entities=[
                    _MessageEntity(
                        type="custom_emoji",
                        offset=e.offset + prefix_u16,
                        length=e.length,
                        custom_emoji_id=e.custom_emoji_id,
                    )
                    for e in entities
                ],
            )
        except Exception as ex:
            lines = "\n".join(
                f"{ch} <code>{EMOJI_MAP.get(ch)}</code>"
                for ch in _EMOJI_CHAR_LIST
                if EMOJI_MAP.get(ch)
            )
            bot.send_message(chat_id, "Preview (ids):\n" + lines)
            bot.send_message(chat_id, f"entities err: <code>{esc(ex)}</code>")
        return

    if data.startswith("ad:emset:"):
        key = data.split(":", 2)[2]
        bot.answer_callback_query(c.id)
        try:
            idx = int(key)
            ch = _EMOJI_CHAR_LIST[idx]
        except Exception:
            ch = key
        _wait[uid] = {"action": "set_emoji", "key": ch}
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("⬅️ Emoji", callback_data="ad:emoji"))
        cur = EMOJI_MAP.get(ch) or "—"
        edit(
            f"✨ Set premium for {ch}\n"
            f"Current id: <code>{esc(cur)}</code>\n\n"
            "ផ្ញើ:\n• <b>Premium emoji</b> មួយ\n"
            "• ឬ custom_emoji_id លេខ\n"
            "• ឬ /clear ដើម្បីលុប",
            m,
        )
        return

    if data == "ad:settings":
        bot.answer_callback_query(c.id)
        st = load_settings()
        m = types.InlineKeyboardMarkup()
        m.add(
            types.InlineKeyboardButton(
                f"Maintenance: {'ON' if st.get('maintenance') else 'OFF'}",
                callback_data="ad:togmaint",
            )
        )
        m.add(types.InlineKeyboardButton("✏️ Support text", callback_data="ad:setsupport"))
        m.add(types.InlineKeyboardButton("✏️ Welcome text", callback_data="ad:setwelcome"))
        m.add(types.InlineKeyboardButton("🎬 Welcome video (reply)", callback_data="ad:setvideo_hint"))
        m.add(types.InlineKeyboardButton("⬅️ Admin", callback_data="ad:home"))
        pay_ok = "✅" if (KHMER_API_KEY or KHMER_PROFILE_KEY) else "❌"
        edit(
            f"⚙️ <b>Settings</b>\n\n"
            f"Bot: {esc(BOT_NAME)}\n"
            f"Payment keys: {pay_ok}\n"
            f"Channel: <code>{esc(CHANNEL_ID) or '—'}</code>\n"
            f"Admins: {len(ADMIN_IDS)}\n"
            f"Maintenance: <b>{'ON' if st.get('maintenance') else 'OFF'}</b>",
            m,
        )
        return

    if data == "ad:togmaint":
        st = load_settings()
        st["maintenance"] = not st.get("maintenance")
        save_settings(st)
        bot.answer_callback_query(c.id, f"Maintenance {st['maintenance']}")
        # refresh
        c.data = "ad:settings"
        handle_admin_cb(c)
        return

    if data == "ad:setsupport":
        bot.answer_callback_query(c.id)
        _wait[uid] = {"action": "set_support"}
        edit("វាយ support text ថ្មី:", types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("⬅️", callback_data="ad:settings")
        ))
        return

    if data == "ad:setwelcome":
        bot.answer_callback_query(c.id)
        _wait[uid] = {"action": "set_welcome"}
        edit(
            "វាយ welcome text ថ្មី\nប្រើ <code>{name}</code> និង <code>{bot}</code>",
            types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️", callback_data="ad:settings")),
        )
        return

    if data == "ad:setvideo_hint":
        bot.answer_callback_query(c.id, "Reply to a video with /setvideo", show_alert=True)
        return

    if data == "ad:newcat":
        bot.answer_callback_query(c.id)
        _wait[uid] = {"action": "new_cat"}
        edit(
            "➕ បង្កើត Category\nផ្ញើឈ្មោះ (ឧ. VPN GOLD):",
            types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️", callback_data="ad:products")),
        )
        return

    if data.startswith("ad:cat:"):
        cat_id = data.split(":", 2)[2]
        cat = find_cat(store, cat_id)
        if not cat:
            bot.answer_callback_query(c.id, "Not found", show_alert=True)
            return
        bot.answer_callback_query(c.id)
        edit(
            f"{cat.get('icon')} <b>{esc(cat.get('name'))}</b>\n"
            f"id: <code>{cat['id']}</code>\n"
            f"packs: {len(cat.get('packs') or [])}",
            kb_admin_cat(cat),
        )
        return

    if data.startswith("ad:togglecat:"):
        cat_id = data.split(":", 2)[2]
        cat = find_cat(store, cat_id)
        if cat:
            cat["enabled"] = not cat.get("enabled", True)
            save_store(store)
            bot.answer_callback_query(c.id, "OK")
            c.data = f"ad:cat:{cat_id}"
            handle_admin_cb(c)
        return

    if data.startswith("ad:delcat:"):
        cat_id = data.split(":", 2)[2]
        store["categories"] = [x for x in (store.get("categories") or []) if x.get("id") != cat_id]
        save_store(store)
        bot.answer_callback_query(c.id, "Deleted")
        c.data = "ad:products"
        handle_admin_cb(c)
        return

    if data.startswith("ad:renamecat:"):
        cat_id = data.split(":", 2)[2]
        _wait[uid] = {"action": "rename_cat", "cat_id": cat_id}
        bot.answer_callback_query(c.id)
        edit("ផ្ញើឈ្មោះ category ថ្មី:", types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("⬅️", callback_data=f"ad:cat:{cat_id}")
        ))
        return

    if data.startswith("ad:iconcat:"):
        cat_id = data.split(":", 2)[2]
        _wait[uid] = {"action": "icon_cat", "cat_id": cat_id}
        bot.answer_callback_query(c.id)
        edit("ផ្ញើ icon (emoji 1 តួ):", types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("⬅️", callback_data=f"ad:cat:{cat_id}")
        ))
        return

    if data.startswith("ad:newpack:"):
        cat_id = data.split(":", 2)[2]
        _wait[uid] = {"action": "new_pack", "cat_id": cat_id}
        bot.answer_callback_query(c.id)
        edit(
            "➕ Pack ថ្មី\nផ្ញើទម្រង់:\n<code>ឈ្មោះ | តម្លៃ</code>\nឧ. <code>1ខែ | 2.10</code>",
            types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️", callback_data=f"ad:cat:{cat_id}")),
        )
        return

    if data.startswith("ad:pack:"):
        _, _, cat_id, pack_id = data.split(":", 3)
        cat, pack = find_pack(store, cat_id, pack_id)
        if not pack:
            bot.answer_callback_query(c.id, "Not found", show_alert=True)
            return
        bot.answer_callback_query(c.id)
        edit(
            f"📦 <b>{esc(pack.get('name'))}</b>\n"
            f"id: <code>{pack['id']}</code>\n"
            f"price: ${pack.get('price'):.2f}\n"
            f"stock: <b>{pack_stock_count(pack)}</b>\n"
            f"type: {pack.get('stock_type')}",
            kb_admin_pack(cat_id, pack),
        )
        return

    if data.startswith("ad:addstock:"):
        _, _, cat_id, pack_id = data.split(":", 3)
        _wait[uid] = {"action": "add_stock", "cat_id": cat_id, "pack_id": pack_id}
        bot.answer_callback_query(c.id)
        edit(
            "🔑 ផ្ញើ stock:\n• Text: មួយ key ក្នុងមួយបន្ទាត់\n• ឬ Document file",
            types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("⬅️", callback_data=f"ad:pack:{cat_id}:{pack_id}")
            ),
        )
        return

    if data.startswith("ad:price:"):
        _, _, cat_id, pack_id = data.split(":", 3)
        _wait[uid] = {"action": "set_price", "cat_id": cat_id, "pack_id": pack_id}
        bot.answer_callback_query(c.id)
        edit(
            "ផ្ញើតម្លៃថ្មី (ឧ. 2.10):",
            types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("⬅️", callback_data=f"ad:pack:{cat_id}:{pack_id}")
            ),
        )
        return

    if data.startswith("ad:renamepack:"):
        _, _, cat_id, pack_id = data.split(":", 3)
        _wait[uid] = {"action": "rename_pack", "cat_id": cat_id, "pack_id": pack_id}
        bot.answer_callback_query(c.id)
        edit("ផ្ញើឈ្មោះ pack ថ្មី:", types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("⬅️", callback_data=f"ad:pack:{cat_id}:{pack_id}")
        ))
        return

    if data.startswith("ad:togglepack:"):
        _, _, cat_id, pack_id = data.split(":", 3)
        _, pack = find_pack(store, cat_id, pack_id)
        if pack:
            pack["enabled"] = not pack.get("enabled", True)
            save_store(store)
            bot.answer_callback_query(c.id, "OK")
            c.data = f"ad:pack:{cat_id}:{pack_id}"
            handle_admin_cb(c)
        return

    if data.startswith("ad:stocktype:"):
        _, _, cat_id, pack_id = data.split(":", 3)
        _, pack = find_pack(store, cat_id, pack_id)
        if pack:
            pack["stock_type"] = "file" if pack.get("stock_type") != "file" else "text"
            save_store(store)
            bot.answer_callback_query(c.id, pack["stock_type"])
            c.data = f"ad:pack:{cat_id}:{pack_id}"
            handle_admin_cb(c)
        return

    if data.startswith("ad:delpack:"):
        _, _, cat_id, pack_id = data.split(":", 3)
        cat = find_cat(store, cat_id)
        if cat:
            cat["packs"] = [p for p in (cat.get("packs") or []) if p.get("id") != pack_id]
            save_store(store)
            bot.answer_callback_query(c.id, "Deleted")
            c.data = f"ad:cat:{cat_id}"
            handle_admin_cb(c)
        return

    bot.answer_callback_query(c.id)


# ─── Admin text/document wizard ───────────────────────────────────────────
@bot.message_handler(commands=["setvideo"])
def cmd_setvideo(msg):
    if not is_admin(msg.from_user.id):
        return
    if not msg.reply_to_message or not msg.reply_to_message.video:
        bot.reply_to(msg, "Reply to a video with /setvideo")
        return
    store = load_store()
    store["welcome_video"] = msg.reply_to_message.video.file_id
    save_store(store)
    bot.reply_to(msg, "✅ Welcome video set")


@bot.message_handler(content_types=["text", "document"])
def on_wizard(msg):
    uid = msg.from_user.id
    if uid not in _wait or not is_admin(uid):
        return
    if msg.text and msg.text.startswith("/"):
        return

    st = _wait.get(uid) or {}
    action = st.get("action")
    store = load_store()

    if action == "broadcast":
        _wait.pop(uid, None)
        text = msg.text or ""
        users = load_users()
        ok = fail = 0
        bot.reply_to(msg, f"📢 កំពុងផ្ញើទៅ {len(users)} users…")
        for u in users:
            try:
                bot.send_message(int(u), text)
                ok += 1
                time.sleep(0.04)
            except Exception:
                fail += 1
        bot.send_message(msg.chat.id, f"✅ Broadcast រួច · ok={ok} fail={fail}", reply_markup=kb_admin_home())
        return

    if action == "set_emoji_multi":
        _wait.pop(uid, None)
        report = _apply_setemojis_from_message(msg)
        if not report:
            bot.reply_to(msg, "រកមិនឃើញ custom_emoji ក្នុងសារ — ផ្ញើ premium emoji")
        else:
            bot.reply_to(msg, "✅ កំណត់:\n" + "\n".join(report))
        bot.send_message(msg.chat.id, "✨ Emoji Premium", reply_markup=kb_emoji_menu())
        return

    if action == "set_emoji":
        key = st.get("key")  # unicode char
        _wait.pop(uid, None)
        if msg.text and msg.text.strip().lower() == "/clear":
            EMOJI_MAP[key] = None
            save_emoji()
            load_emoji()
            bot.reply_to(msg, f"✅ cleared {key}")
            bot.send_message(msg.chat.id, "✨ Emoji Premium", reply_markup=kb_emoji_menu())
            return
        cid = None
        for ent in (msg.entities or []):
            if ent.type == "custom_emoji" and getattr(ent, "custom_emoji_id", None):
                cid = str(ent.custom_emoji_id)
                break
        if not cid and msg.text and msg.text.strip().isdigit():
            cid = msg.text.strip()
        if not cid:
            bot.reply_to(msg, "ផ្ញើ Premium emoji ឬ custom_emoji_id លេខ")
            return
        if not _valid_emoji_id(cid):
            bot.reply_to(msg, "id មិនត្រឹមត្រូវ")
            return
        EMOJI_MAP[key] = cid
        save_emoji()
        load_emoji()
        bot.reply_to(msg, f"✅ {key} → <code>{esc(cid)}</code>")
        # preview single
        try:
            bot.send_message(
                msg.chat.id,
                key,
                entities=[_MessageEntity(type="custom_emoji", offset=0, length=len(key.encode("utf-16-le"))//2, custom_emoji_id=cid)],
            )
        except Exception as ex:
            bot.send_message(msg.chat.id, f"preview err: {esc(ex)}")
        bot.send_message(msg.chat.id, "✨ Emoji Premium", reply_markup=kb_emoji_menu())
        return

    if action == "set_support":
        _wait.pop(uid, None)
        s = load_settings()
        s["support_text"] = msg.text or ""
        save_settings(s)
        bot.reply_to(msg, "✅ Support text updated")
        return

    if action == "set_welcome":
        _wait.pop(uid, None)
        store["welcome_text"] = msg.text or store.get("welcome_text")
        save_store(store)
        bot.reply_to(msg, "✅ Welcome updated")
        return

    if action == "new_cat":
        _wait.pop(uid, None)
        name = (msg.text or "").strip()
        if not name:
            bot.reply_to(msg, "Empty")
            return
        cid = slugify(name) + "_" + uuid.uuid4().hex[:4]
        store.setdefault("categories", []).append(
            {"id": cid, "name": name, "icon": "📦", "enabled": True, "packs": []}
        )
        save_store(store)
        bot.reply_to(msg, f"✅ Category <b>{esc(name)}</b> · id <code>{cid}</code>")
        bot.send_message(msg.chat.id, "📦 Products", reply_markup=kb_admin_products(store))
        return

    if action == "rename_cat":
        cat_id = st.get("cat_id")
        _wait.pop(uid, None)
        cat = find_cat(store, cat_id)
        if cat and msg.text:
            cat["name"] = msg.text.strip()
            save_store(store)
            bot.reply_to(msg, "✅ Renamed")
        return

    if action == "icon_cat":
        cat_id = st.get("cat_id")
        _wait.pop(uid, None)
        cat = find_cat(store, cat_id)
        if cat and msg.text:
            cat["icon"] = msg.text.strip()[:4]
            save_store(store)
            bot.reply_to(msg, f"✅ Icon {cat['icon']}")
        return

    if action == "new_pack":
        cat_id = st.get("cat_id")
        _wait.pop(uid, None)
        cat = find_cat(store, cat_id)
        if not cat:
            bot.reply_to(msg, "Category gone")
            return
        raw = (msg.text or "").strip()
        if "|" in raw:
            name, price_s = [x.strip() for x in raw.split("|", 1)]
        else:
            parts = raw.rsplit(" ", 1)
            name, price_s = (parts[0], parts[1]) if len(parts) == 2 else (raw, "1")
        try:
            price = float(price_s.replace("$", ""))
        except ValueError:
            bot.reply_to(msg, "តម្លៃមិនត្រឹមត្រូវ")
            return
        pid = slugify(name) + "_" + uuid.uuid4().hex[:4]
        cat.setdefault("packs", []).append(
            {"id": pid, "name": name, "price": price, "stock": [], "stock_type": "text", "enabled": True}
        )
        save_store(store)
        bot.reply_to(msg, f"✅ Pack <b>{esc(name)}</b> ${price:.2f} · <code>{pid}</code>")
        return

    if action == "set_price":
        cat_id, pack_id = st.get("cat_id"), st.get("pack_id")
        _wait.pop(uid, None)
        _, pack = find_pack(store, cat_id, pack_id)
        try:
            price = float((msg.text or "").replace("$", "").strip())
        except ValueError:
            bot.reply_to(msg, "Invalid")
            return
        if pack:
            pack["price"] = price
            save_store(store)
            bot.reply_to(msg, f"✅ ${price:.2f}")
        return

    if action == "rename_pack":
        cat_id, pack_id = st.get("cat_id"), st.get("pack_id")
        _wait.pop(uid, None)
        _, pack = find_pack(store, cat_id, pack_id)
        if pack and msg.text:
            pack["name"] = msg.text.strip()
            save_store(store)
            bot.reply_to(msg, "✅ Pack renamed")
        return

    if action == "add_stock":
        cat_id, pack_id = st.get("cat_id"), st.get("pack_id")
        # keep wait until done once
        _wait.pop(uid, None)
        _, pack = find_pack(store, cat_id, pack_id)
        if not pack:
            bot.reply_to(msg, "Pack gone")
            return
        stock = list(pack.get("stock") or [])
        added = 0
        if msg.document:
            stock.append(
                {
                    "file_id": msg.document.file_id,
                    "type": "document",
                    "name": msg.document.file_name,
                }
            )
            pack["stock_type"] = "file"
            added = 1
        elif msg.text:
            lines = [ln.strip() for ln in msg.text.splitlines() if ln.strip()]
            stock.extend(lines)
            pack["stock_type"] = "text"
            added = len(lines)
        pack["stock"] = stock
        save_store(store)
        bot.reply_to(msg, f"✅ Added {added} · total stock <b>{len(stock)}</b>")
        return


def main():
    print(f"[KaiKeyBot] {BOT_NAME} admins={ADMIN_IDS}")
    load_store()
    load_emoji()
    port = os.getenv("PORT")
    if port:
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *a):
                pass

        threading.Thread(
            target=lambda: HTTPServer(("0.0.0.0", int(port)), H).serve_forever(),
            daemon=True,
        ).start()
    bot.infinity_polling(timeout=60, long_polling_timeout=50)


if __name__ == "__main__":
    main()
