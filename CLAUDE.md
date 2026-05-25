# WeAre Conference Bot — Project Context

## What This Is
A Telegram bot for managing conference registrations, payment receipt verification, gender-based housing reservations, and participant Q&A. Built for the "WeAre" conference.

## Tech Stack
- **Python 3.11+** with `python-telegram-bot` v20+ (async, webhook mode)
- **Flask** — webhook receiver (sync bridge to PTB's async loop via `run_async`)
- **Supabase** (Postgres) — all persistent state
- **Render** — deployment (web service, auto-deploy from GitHub main branch)

## Architecture
- `bot.py` — Flask app + PTB Application, handler registration, webhook endpoint
- `config.py` — env vars, owner/admin IDs, feature flags
- `db.py` — all Supabase calls (ORM-like interface)
- `strings.py` — all user-facing text, EN + UK, via `t(lang, key, **kwargs)`
- `utils.py` — validate_age (10–99), format_house_button, get_lang, is_admin
- `handlers/registration.py` — ConversationHandler for registration flow
- `handlers/housing.py` — post-approval house selection
- `handlers/admin.py` — all admin/owner commands + inline approval/deny flow
- `handlers/info.py` — schedule, venue, Q&A, coordinator messages

## Registration Flow (ConversationHandler)
LANG → NAME → AGE → GENDER → HOUSING_PREF → PHONE → PAYMENT_STEP → RECEIPT → END

- **HOUSING_PREF**: records `needs_housing` boolean (preference only, not selection)
- Denied users re-enter at RECEIPT (or HOUSING_PREF if needs_housing is NULL)
- On receipt upload: notifies admin group with photo + Approve/Deny inline buttons

## Housing Flow (post-approval, main menu)
Menu → "Do you need housing?" (menu_housing_yes / menu_housing_no callbacks)
→ Yes → house list filtered by participant gender → select → confirm → reserved

**Important**: registration uses `housing_yes`/`housing_no` callbacks; main menu uses
`menu_housing_yes`/`menu_housing_no` — different to avoid ConversationHandler collision.

## Admin Deny Flow
1. Admin clicks ❌ Deny on receipt notification in group
2. `cb_admin_deny_start` stores target in `_deny_pending` (memory + Supabase for restart survival)
3. Admin types reason as plain text in group → `handle_setting_input` processes it
4. User receives denial notification; admin sees updated caption

**Critical**: info.py's `handle_text_input` is registered in PTB group=1, admin's
`handle_setting_input` is in group=0 — this ensures admin text is processed first.
Bot must have privacy mode DISABLED in BotFather to receive plain group messages.

## Owners vs Admins
- `OWNER_IDS = {479515546, 426569764}` — both are owners (full access)
- `OWNER_ID = 479515546` — primary, used as fallback notify chat if GROUP_CHAT_ID unset
- `ADMIN_IDS = [479515546, 426569764]` — expandable via `/addadmin` at runtime
- `_require_owner` checks against `OWNER_IDS`; `_require_admin` checks `is_admin()`
- `/help` shows owner-only section only to owners

## Houses
Houses are managed directly in Supabase (no bot commands for add/remove).
Schema: `id, name, gender (M|F), capacity` — address and notes columns removed.

Current houses (added via SQL):
- **Female (Timber Village)**: Hemlock, Madrona, Cedar, Spruce
- **Male (Cascade Village)**: Lassen, Rainier, Hood, Bachelor

## Q&A and Coordinator Messages
Both forward to `coord_channel_id` from `bot_settings` table (set once in Supabase).
Falls back to `GROUP_CHAT_ID` env var if not set.

## Key Commands
- `/help` — lists all commands (owner section hidden from non-owners)
- `/pending` — show registrations awaiting review
- `/participants` — all participants with status
- `/listhouses` — house occupancy
- `/moveresident <id> <house>` — reassign someone's house
- `/testsetup` — (owner only) deletes caller's own participant record for re-testing
- `/broadcast <msg>` — send to all approved participants
- `/setschedule`, `/setvenue` — set info text
- `/pause`/`/resume` `<housing|qa|messages>` — toggle features

## Supabase Schema Notes
Tables: `participants`, `receipts`, `houses`, `house_reservations`, `questions`, `messages`, `bot_settings`

`participants` has `needs_housing BOOLEAN DEFAULT NULL` — added via migration:
```sql
ALTER TABLE participants ADD COLUMN IF NOT EXISTS needs_housing BOOLEAN DEFAULT NULL;
```

`houses` no longer has `address` or `notes` columns:
```sql
ALTER TABLE houses DROP COLUMN IF EXISTS address;
ALTER TABLE houses DROP COLUMN IF EXISTS notes;
```

## Deployment
- GitHub: `https://github.com/Yogurt43/weare-conference-bot.git` (main branch)
- Render auto-deploys on push — webhook has been flaky; use Manual Deploy if commit doesn't trigger
- Render env vars: `BOT_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, `WEBHOOK_URL`, `GROUP_CHAT_ID`, `PAYMENT_LINK`

## Known Gotchas
- PTB handler groups: info text handler is group=1, admin text handler is group=0 — do not change this order or deny flow breaks
- ConversationHandler is `persistent=False` — state lost on bot restart; users mid-flow may need to `/start` again
- `validate_age` accepts 10–99 only (2-digit numbers)
- Privacy mode must be OFF in BotFather for bot to receive plain text in groups
- `housing_yes`/`housing_no` callback data is used by ConversationHandler HOUSING_PREF state; main menu uses `menu_housing_yes`/`menu_housing_no` — never reuse the former outside the ConversationHandler
