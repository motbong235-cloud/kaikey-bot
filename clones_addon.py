# -*- coding: utf-8 -*-
"""KaiKey Bot Clone system — $9.99/month SaaS clones."""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

CLONE_PRICE = float(os.getenv("CLONE_PRICE", "9.99"))
SUPPORT_USER = os.getenv("SUPPORT_USER", "kairozen_support")

_clone_runners = {}


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def setup_clones(bot, types, *, data_dir: Path, admin_ids: set, kh_tz, wait: dict, notify_admins, now_kh, is_admin):
    """Wire clone handlers onto existing bot instance."""
    clones_file = Path(data_dir) / "clones.json"

    def load_clones():
        if not clones_file.exists():
            return {}
        try:
            return json.loads(clones_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_clones(data):
        clones_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def clone_is_active(c):
        if not c or c.get("status") == "suspended":
            return False
        if c.get("status") != "active":
            return False
        until = c.get("paid_until") or ""
        if not until:
            return True
        try:
            return datetime.strptime(until[:10], "%Y-%m-%d").date() >= datetime.now(kh_tz).date()
        except Exception:
            return True

    def mask_token(tok: str) -> str:
        t = (tok or "").strip()
        if len(t) < 12:
            return "***"
        return t[:8] + "…" + t[-4:]

    def extend_paid_until(days=30):
        d = datetime.now(kh_tz).date()
        return (d + timedelta(days=days)).isoformat()

    def stop_clone_runner(cid: str):
        info = _clone_runners.pop(cid, None)
        if not info:
            return
        info.get("stop", {}).update({"stop": True})
        b = info.get("bot")
        if b:
            try:
                b.stop_polling()
            except Exception:
                pass

    def start_clone_runner(cid: str, force=False):
        data = load_clones()
        c = data.get(cid)
        if not c or not clone_is_active(c):
            return False, "not active"
        token = (c.get("bot_token") or "").strip()
        if not token or ":" not in token:
            return False, "bad token"
        stop_clone_runner(cid)
        stop_flag = {"stop": False}
        shop = c.get("shop_name") or "Shop"
        owner = int(c.get("admin_id") or 0)
        paid_until = c.get("paid_until") or ""

        def _run():
            try:
                import telebot as tb

                b = tb.TeleBot(token, parse_mode="HTML")

                @b.message_handler(commands=["start", "menu"])
                def _st(m):
                    if stop_flag["stop"]:
                        return
                    b.send_message(
                        m.chat.id,
                        f"👋 Welcome to <b>{_esc(shop)}</b>!\n"
                        f"Powered by KaiKey · Support @{SUPPORT_USER}\n\n"
                        f"✅ Bot កំពុងដំណើរការ។\n"
                        f"Admin: /admin",
                    )

                @b.message_handler(commands=["admin"])
                def _ad(m):
                    if m.from_user.id != owner and m.from_user.id not in admin_ids:
                        return
                    b.send_message(
                        m.chat.id,
                        f"🛡 Clone Admin · <b>{_esc(shop)}</b>\n"
                        f"Status: active\n"
                        f"Paid until: <code>{_esc(paid_until)}</code>",
                    )

                _clone_runners[cid] = {"bot": b, "stop": stop_flag}
                b.infinity_polling(timeout=30, long_polling_timeout=25, skip_pending=True)
            except Exception as e:
                print(f"[clone {cid}] exit: {e}")
                try:
                    notify_admins(f"⚠️ Clone stop <code>{_esc(cid)}</code>\n{_esc(e)}")
                except Exception:
                    pass

        th = threading.Thread(target=_run, name=f"clone-{cid}", daemon=True)
        th.start()
        _clone_runners[cid] = {**_clone_runners.get(cid, {}), "thread": th, "stop": stop_flag}
        return True, "started"

    def start_all_active_clones():
        data = load_clones()
        n = 0
        for cid, c in data.items():
            if clone_is_active(c):
                ok, _ = start_clone_runner(cid)
                if ok:
                    n += 1
                time.sleep(0.25)
        print(f"[KaiKey] clone runners started: {n}")
        return n

    def kb_clones_admin():
        data = load_clones()
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("➕ បង្កើត Free (Admin)", callback_data="ad:clone_free", color="progress"))
        m.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="ad:clones", color="inactive"))
        items = sorted(data.items(), key=lambda x: x[1].get("created_at") or "", reverse=True)[:30]
        for cid, c in items:
            st = c.get("status") or "?"
            mark = "✅" if clone_is_active(c) else ("⏳" if st == "pending_payment" else "⛔")
            m.add(
                types.InlineKeyboardButton(
                    f"{mark} {c.get('shop_name') or cid} · {st}",
                    callback_data=f"ad:clone:{cid}",
                    color="active" if clone_is_active(c) else "danger",
                )
            )
        m.add(types.InlineKeyboardButton("⬅️ Admin", callback_data="ad:home", color="inactive"))
        return m

    def clones_admin_text():
        data = load_clones()
        active = sum(1 for c in data.values() if clone_is_active(c))
        pending = sum(1 for c in data.values() if c.get("status") == "pending_payment")
        return (
            f"🤖 <b>Bot Clones</b>\n"
            f"តម្លៃ: <b>${CLONE_PRICE:.2f}/month</b>\n"
            f"សរុប: <b>{len(data)}</b> · Active: <b>{active}</b> · Pending: <b>{pending}</b>\n"
            f"Support: @{SUPPORT_USER}"
        )

    def kb_clone_detail(cid):
        m = types.InlineKeyboardMarkup()
        m.add(
            types.InlineKeyboardButton("✅ Mark Paid +30d", callback_data=f"ad:clone_pay:{cid}", color="active"),
            types.InlineKeyboardButton("🎁 Free +30d", callback_data=f"ad:clone_freepay:{cid}", color="progress"),
        )
        m.add(
            types.InlineKeyboardButton("⏸ Suspend", callback_data=f"ad:clone_sus:{cid}", color="danger"),
            types.InlineKeyboardButton("▶️ Activate", callback_data=f"ad:clone_act:{cid}", color="active"),
        )
        m.add(
            types.InlineKeyboardButton("🗑 Delete", callback_data=f"ad:clone_del:{cid}", color="danger"),
            types.InlineKeyboardButton("🔄 Restart", callback_data=f"ad:clone_run:{cid}", color="progress"),
        )
        m.add(types.InlineKeyboardButton("⬅️ Clones", callback_data="ad:clones", color="inactive"))
        return m

    def handle_admin_clone_cb(c, data, uid, edit):
        """Return True if handled."""
        if data == "ad:clones":
            bot.answer_callback_query(c.id)
            edit(clones_admin_text(), kb_clones_admin())
            return True

        if data == "ad:clone_free":
            bot.answer_callback_query(c.id)
            wait[uid] = {"action": "admin_clone_free"}
            edit(
                "🎁 <b>បង្កើត Clone Free</b>\nផ្ញើ 3 បន្ទាត់:\n<code>ShopName\nBOT_TOKEN\nADMIN_ID</code>",
                types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("⬅️", callback_data="ad:clones", color="inactive")
                ),
            )
            return True

        if data.startswith("ad:clone:") and data.count(":") == 2:
            cid = data.split(":")[2]
            clones = load_clones()
            cl = clones.get(cid)
            if not cl:
                bot.answer_callback_query(c.id, "Not found", show_alert=True)
                return True
            bot.answer_callback_query(c.id)
            edit(
                f"🤖 <b>{_esc(cl.get('shop_name'))}</b>\n"
                f"ID: <code>{cid}</code>\n"
                f"Status: <b>{_esc(cl.get('status'))}</b>\n"
                f"Paid until: <code>{_esc(cl.get('paid_until') or '-')}</code>\n"
                f"Owner: <code>{cl.get('owner_id')}</code>\n"
                f"Admin: <code>{cl.get('admin_id')}</code>\n"
                f"Token: <code>{_esc(mask_token(cl.get('bot_token')))}</code>\n"
                f"Created: {_esc(cl.get('created_at'))}",
                kb_clone_detail(cid),
            )
            return True

        if data.startswith("ad:clone_pay:") or data.startswith("ad:clone_freepay:"):
            cid = data.split(":")[2]
            clones = load_clones()
            cl = clones.get(cid)
            if not cl:
                bot.answer_callback_query(c.id, "Gone", show_alert=True)
                return True
            cl["status"] = "active"
            cl["paid_until"] = extend_paid_until(30)
            if data.startswith("ad:clone_freepay:"):
                cl["free"] = True
                cl["price"] = 0
            save_clones(clones)
            start_clone_runner(cid)
            bot.answer_callback_query(c.id, "Paid +30d ✅")
            try:
                bot.send_message(
                    int(cl.get("owner_id")),
                    f"✅ Shop Bot <b>{_esc(cl.get('shop_name'))}</b> បាន Activate!\n"
                    f"Paid until: <code>{cl['paid_until']}</code>\n"
                    f"បើក bot របស់អ្នក រួច /start",
                )
            except Exception:
                pass
            edit(clones_admin_text(), kb_clones_admin())
            return True

        if data.startswith("ad:clone_sus:"):
            cid = data.split(":")[2]
            clones = load_clones()
            if cid in clones:
                clones[cid]["status"] = "suspended"
                save_clones(clones)
                stop_clone_runner(cid)
            bot.answer_callback_query(c.id, "Suspended")
            edit(clones_admin_text(), kb_clones_admin())
            return True

        if data.startswith("ad:clone_act:"):
            cid = data.split(":")[2]
            clones = load_clones()
            if cid in clones:
                clones[cid]["status"] = "active"
                if not clones[cid].get("paid_until"):
                    clones[cid]["paid_until"] = extend_paid_until(30)
                save_clones(clones)
                start_clone_runner(cid)
            bot.answer_callback_query(c.id, "Activated")
            edit(clones_admin_text(), kb_clones_admin())
            return True

        if data.startswith("ad:clone_del:"):
            cid = data.split(":")[2]
            clones = load_clones()
            stop_clone_runner(cid)
            clones.pop(cid, None)
            save_clones(clones)
            bot.answer_callback_query(c.id, "Deleted")
            edit(clones_admin_text(), kb_clones_admin())
            return True

        if data.startswith("ad:clone_run:"):
            cid = data.split(":")[2]
            ok, info = start_clone_runner(cid, force=True)
            bot.answer_callback_query(c.id, f"{ok} {info}"[:180], show_alert=True)
            return True

        return False

    # —— user entry ——
    @bot.message_handler(func=lambda m: m.text and "បង្កើត Shop Bot" in (m.text or ""))
    def msg_clone_entry(msg):
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("🚀 ចាប់ផ្តើមបង្កើត", callback_data="clone:start", color="active"))
        m.add(types.InlineKeyboardButton(f"💬 ទាក់ទង @{SUPPORT_USER}", url=f"https://t.me/{SUPPORT_USER}"))
        bot.send_message(
            msg.chat.id,
            f"🤖 <b>បង្កើត Shop Bot (Clone)</b>\n\n"
            f"តម្លៃ: <b>${CLONE_PRICE:.2f} / month</b>\n\n"
            f"ត្រូវការ:\n"
            f"1) Bot Token (@BotFather)\n"
            f"2) Admin Telegram ID\n"
            f"3) ឈ្មោះ Shop\n\n"
            f"បន្ទាប់ពីបំពេញ → ទាក់ទង <b>@{SUPPORT_USER}</b> ដើម្បីបង់ប្រាក់\n"
            f"Admin នឹង Activate ឲ្យ។",
            reply_markup=m,
        )

    @bot.callback_query_handler(func=lambda c: (c.data or "").startswith("clone:"))
    def handle_clone_user_cb(c):
        uid = c.from_user.id
        data = c.data or ""
        if data == "clone:start":
            wait[uid] = {"action": "clone_shop_name"}
            bot.answer_callback_query(c.id)
            bot.send_message(c.message.chat.id, "① ផ្ញើ <b>ឈ្មោះ Shop</b> (ឧ. Roma Key Store):")
            return
        bot.answer_callback_query(c.id)

    @bot.message_handler(func=lambda m: (wait.get(m.from_user.id) or {}).get("action", "").startswith("clone_"))
    def on_clone_wizard(msg):
        uid = msg.from_user.id
        st = wait.get(uid) or {}
        action = st.get("action")
        if action == "clone_shop_name":
            name = (msg.text or "").strip()
            if len(name) < 2:
                bot.reply_to(msg, "ឈ្មោះខ្លីពេក")
                return
            st["shop_name"] = name[:64]
            st["action"] = "clone_token"
            wait[uid] = st
            bot.reply_to(msg, "② ផ្ញើ <b>Bot Token</b> ពី @BotFather\n<code>123456:AA...</code>")
            return
        if action == "clone_token":
            tok = (msg.text or "").strip().replace(" ", "")
            if ":" not in tok or len(tok) < 30:
                bot.reply_to(msg, "Token មិនត្រឹមត្រូវ")
                return
            st["bot_token"] = tok
            st["action"] = "clone_admin"
            wait[uid] = st
            bot.reply_to(msg, "③ ផ្ញើ <b>Admin ID</b> (លេខ)\nឧ. <code>123456789</code>")
            return
        if action == "clone_admin":
            try:
                aid = int((msg.text or "").strip())
            except ValueError:
                bot.reply_to(msg, "Admin ID ត្រូវជាលេខ")
                return
            wait.pop(uid, None)
            cid = "c_" + uuid.uuid4().hex[:10]
            clones = load_clones()
            clones[cid] = {
                "id": cid,
                "shop_name": st.get("shop_name"),
                "bot_token": st.get("bot_token"),
                "admin_id": aid,
                "owner_id": uid,
                "status": "pending_payment",
                "paid_until": "",
                "created_at": now_kh(),
                "price": CLONE_PRICE,
            }
            save_clones(clones)
            m = types.InlineKeyboardMarkup()
            m.add(types.InlineKeyboardButton(f"💬 ទាក់ទង @{SUPPORT_USER}", url=f"https://t.me/{SUPPORT_USER}"))
            bot.send_message(
                msg.chat.id,
                f"✅ <b>បានបង្កើត Clone</b>\n"
                f"ID: <code>{cid}</code>\n"
                f"Shop: <b>{_esc(st.get('shop_name'))}</b>\n"
                f"Admin ID: <code>{aid}</code>\n"
                f"Token: <code>{_esc(mask_token(st.get('bot_token')))}</code>\n"
                f"Status: <b>pending_payment</b>\n\n"
                f"💵 តម្លៃ <b>${CLONE_PRICE:.2f}/month</b>\n"
                f"សូមទាក់ទង <b>@{SUPPORT_USER}</b> ដើម្បីបង់ប្រាក់។",
                reply_markup=m,
            )
            notify_admins(
                f"🤖 Clone ថ្មី pending pay\n"
                f"ID: <code>{cid}</code>\n"
                f"Shop: {_esc(st.get('shop_name'))}\n"
                f"Owner: <code>{uid}</code>\n"
                f"Admin: <code>{aid}</code>\n"
                f"Token: <code>{_esc(mask_token(st.get('bot_token')))}</code>"
            )

    @bot.message_handler(func=lambda m: (wait.get(m.from_user.id) or {}).get("action") == "admin_clone_free")
    def on_admin_clone_free(msg):
        if not is_admin(msg.from_user.id):
            return
        wait.pop(msg.from_user.id, None)
        parts = [ln.strip() for ln in (msg.text or "").splitlines() if ln.strip()]
        if len(parts) < 3:
            bot.reply_to(msg, "ត្រូវ 3 បន្ទាត់: ShopName / TOKEN / ADMIN_ID")
            return
        name, tok, aid_s = parts[0], parts[1], parts[2]
        try:
            aid = int(aid_s)
        except ValueError:
            bot.reply_to(msg, "Admin ID invalid")
            return
        if ":" not in tok:
            bot.reply_to(msg, "Token invalid")
            return
        cid = "c_" + uuid.uuid4().hex[:10]
        clones = load_clones()
        clones[cid] = {
            "id": cid,
            "shop_name": name[:64],
            "bot_token": tok.strip(),
            "admin_id": aid,
            "owner_id": msg.from_user.id,
            "status": "active",
            "paid_until": extend_paid_until(30),
            "created_at": now_kh(),
            "price": 0,
            "free": True,
        }
        save_clones(clones)
        ok, info = start_clone_runner(cid)
        bot.reply_to(msg, f"✅ Free clone <b>{_esc(name)}</b>\n<code>{cid}</code>\nrunner: {ok} {_esc(info)}")

    return {
        "start_all_active_clones": start_all_active_clones,
        "handle_admin_clone_cb": handle_admin_clone_cb,
        "kb_clones_admin": kb_clones_admin,
        "CLONE_PRICE": CLONE_PRICE,
        "SUPPORT_USER": SUPPORT_USER,
    }
