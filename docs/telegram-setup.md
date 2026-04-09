# Telegram Setup

## What you will see after provisioning

When provisioning completes successfully, the real Telegram group appears inside the **owner account** in the Telegram app:

- group name: `Дом`
- group type: private supergroup
- forum mode: enabled
- topics: `Сегодня`, `Неделя`, `Календарь`, `Покупки`, `Быт`, `Решения`, `Заметки`, `Шаблоны`, `Архив`, `Система`

How to verify it:

1. Open Telegram on the account whose phone is set in `HOMEGROUP_TELEGRAM_OWNER_PHONE`.
2. Search for `Дом`.
3. Open the group and confirm that forum topics are present.
4. Open topic `Система` and check the technical provisioning report.
5. Open topic `Шаблоны` and confirm that templates and instructions were published.

## Exact credentials and data needed from you

### Required secrets

- `HOMEGROUP_BOT_TOKEN`
  Bot token from BotFather for the main bot.
- `HOMEGROUP_TELEGRAM_API_ID`
  Telegram API ID from `my.telegram.org`.
- `HOMEGROUP_TELEGRAM_API_HASH`
  Telegram API hash from `my.telegram.org`.
- `HOMEGROUP_TELEGRAM_OWNER_PHONE`
  Phone number of the Telegram account that will own and create the group.
- `HOMEGROUP_TELEGRAM_SECOND_USER_USERNAME`
  Telegram username of the second participant to invite into the group.
- `HOMEGROUP_OPENROUTER_API_KEY`
  API key for OpenRouter.
- `HOMEGROUP_DOMAIN`
  Public domain or subdomain for HTTPS access.
- `HOMEGROUP_BASE_URL`
  Public base URL, for example `https://homegroup.example.com`.

### Strongly recommended values

- `HOMEGROUP_TELEGRAM_SECOND_USER_ID`
  Numeric Telegram user ID of the second participant.
  The current provisioning code mainly relies on username, but numeric ID is useful for app-level data binding and future tightening.
- `HOMEGROUP_WEBHOOK_SECRET`
  Secret string for webhook validation and safer deployment.
- `HOMEGROUP_BACKUP_PASSPHRASE`
  Secret used to protect backup operations and future encryption extensions.

## Manual actions still needed from you

### BotFather

You need to do these outside the repo:

1. Create the bot.
2. Copy the bot token.
3. Disable or correctly configure group privacy mode so the bot can read the intended group messages.
4. Optionally configure the bot menu button to point to the Mini App URL.
5. Optionally set the bot commands list to match the implemented commands.

### Telegram owner login

The first provisioning run needs an interactive Telegram login for the owner account:

1. Start `uv run homegroup provision`.
2. Telethon asks for the login code sent by Telegram.
3. If the owner account has 2FA password enabled, enter that password too.
4. After successful login, the provisioning session is stored locally for future runs.

Important:

- the SMS/login code is **not** stored in `.env`
- the 2FA password is **not** part of current config either
- these are entered interactively during the first provisioning run

## Minimal ready-to-run bundle from you

If you want me to finish the real Telegram bootstrap next, I need:

- bot token
- Telegram API ID
- Telegram API hash
- owner phone number
- second user username
- OpenRouter API key
- public domain/base URL

And operationally:

- working SSH access to the VPS
- confirmation code from Telegram during the first owner login
- 2FA password too, only if the owner account has it enabled

## What is not needed from you

You do **not** need to give me:

- chat ID
- topic IDs
- message IDs
- database IDs

Those are created and stored by the system during provisioning and runtime.
