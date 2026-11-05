# ModeKey Bot — Mode / File Key / DNS shop + full Admin Panel

## User flow
`/start` → BUY NOW → Categories → Pack → Cart → ABA QR → auto Key/File

## Admin Panel
Command: `/admin` or `/panel`

| Menu | Features |
|------|----------|
| **Products** | បង្កើត/កែ/លុប Category & Pack, icon, បិទ-បើក, តម្លៃ |
| **Stock** | មើលស្តុកទាំងអស់ · បន្ថែម key (text) ឬ file |
| **Orders** | order ថ្មី · Force deliver |
| **Users** | បញ្ជី user, orders count, last seen · Export IDs |
| **Broadcast** | ផ្ញើសារទៅគ្រប់ user |
| **Emoji Premium** | setup custom_emoji_id / emoji តាម key |
| **Settings** | maintenance, support text, welcome text/video |
| **Stats** | users, orders, revenue, stock |

## Env (Render)
```
BOT_TOKEN=
ADMIN_IDS=123456789
KHMER_API_KEY=
KHMER_PROFILE_KEY=
CHANNEL_ID=
BOT_NAME=ModeKey Store
```

## Deploy
```bash
pip install -r requirements.txt
python bot.py
```
Or push + Render with `render.yaml` (starter).

## Quick stock
Admin → Products → Category → Pack → 🔑 បន្ថែម Stock  
ឬ wizard បន្ទាប់ពីចុច button។
