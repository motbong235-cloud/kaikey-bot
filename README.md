# Spider Mode VPN Bot

Telegram shop — **Mode / File Key / DNS**  
Brand: **Spider Mode VPN**

## User flow
`/start` → BUY NOW → Categories → Pack → Cart → **ABA QR** → auto Key/File

## Admin Panel
`/admin` or `/panel`

| Menu | Features |
|------|----------|
| **Products** | Create/edit/delete Category & Pack, icon, price, enable |
| **Stock** | View stock · add text keys or document files |
| **Orders** | Recent orders · Force deliver |
| **Users** | List users, order count, last seen · Export IDs |
| **Broadcast** | Message all users |
| **Emoji Premium** | custom_emoji_id / emoji per key |
| **Settings** | Maintenance, support text, welcome text/video |
| **Stats** | users, orders, revenue, stock left |

## Env (Render)
```
BOT_TOKEN=
ADMIN_IDS=
KHMER_API_KEY=
KHMER_PROFILE_KEY=
CHANNEL_ID=
BOT_NAME=Spider Mode VPN
```

## Deploy
```bash
pip install -r requirements.txt
python bot.py
```
Or connect repo on Render — `render.yaml` uses **starter** plan.

Suggested username: set in @BotFather
