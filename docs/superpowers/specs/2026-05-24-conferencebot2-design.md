# ConferenceBot2 — Design Spec
**Date:** 2026-05-24  
**Status:** Approved for implementation

---

## Overview

A Telegram bot for a large Slavic youth conference (different organization from SYC). Handles the full conference registration lifecycle — from first contact through payment verification, housing reservation, and event-day info. Built as a clean modular rewrite, not a fork of the SYC bot.

**Stack:** Python, python-telegram-bot, Supabase (PostgreSQL), Flask (webhook), Render (hosting)  
**Languages:** English + Ukrainian (user selects at `/start`, stored per participant)  
**Conference name:** `CONF_NAME` constant — single-line swap when confirmed

---

## Project Structure

```
conferencebot2/
├── bot.py              # Flask webhook entry point, app init, handler registration
├── config.py           # All env vars, CONF_NAME, constants (OWNER_ID, ADMIN_IDS, etc.)
├── strings.py          # All EN/UK user-facing text as a dict — zero hardcoded strings elsewhere
├── db.py               # All Supabase queries — one function per operation
├── handlers/
│   ├── registration.py # Full registration ConversationHandler (multi-step)
│   ├── housing.py      # Housing reservation flow
│   ├── info.py         # Schedule, venue, Q&A, coordinator messages
│   └── admin.py        # All admin commands
├── requirements.txt
├── render.yaml
└── schema.sql
```

---

## Configuration (`config.py`)

```python
CONF_NAME = "CONFERENCE_NAME"          # Replace this one line to rebrand
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
OWNER_ID = 479515546
ADMIN_IDS = [479515546, 426569764]     # Expandable list
PAYMENT_LINK = os.getenv("PAYMENT_LINK", "PAYMENT_LINK_PLACEHOLDER")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")   # Admin notification channel
```

Access levels:
- **Owner** (`OWNER_ID`): all commands including destructive ones (`/nuke`, `/removeuser`)
- **Admin** (`ADMIN_IDS` list, expandable at runtime): registration review, housing management, broadcasts
- **Participant** (approved status): full menu access
- **Unregistered**: registration flow only

---

## Data Model (`schema.sql`)

```sql
-- Core participant record
CREATE TABLE participants (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id       BIGINT UNIQUE NOT NULL,
  username      TEXT,
  full_name     TEXT,
  phone         TEXT,
  age           INTEGER,
  gender        TEXT CHECK (gender IN ('M', 'F')),
  lang          TEXT CHECK (lang IN ('en', 'uk')) DEFAULT 'en',
  status        TEXT CHECK (status IN (
                  'incomplete',        -- started but not finished registration
                  'pending_payment',   -- shown payment link, not yet uploaded receipt
                  'pending_approval',  -- receipt uploaded, awaiting admin review
                  'approved',          -- fully registered
                  'denied'             -- registration denied
                )) DEFAULT 'incomplete',
  denial_reason TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- Payment receipts (stored as Telegram file_id)
CREATE TABLE receipts (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participant_id UUID REFERENCES participants(id) ON DELETE CASCADE,
  file_id        TEXT NOT NULL,   -- Telegram file_id (photo or document)
  submitted_at   TIMESTAMPTZ DEFAULT now()
);

-- Available housing units (admin-managed)
CREATE TABLE houses (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  gender      TEXT CHECK (gender IN ('M', 'F')),
  capacity    INTEGER NOT NULL,
  address     TEXT,
  notes       TEXT
);

-- One row per reservation (unique per participant)
CREATE TABLE house_reservations (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  house_id       UUID REFERENCES houses(id) ON DELETE CASCADE,
  participant_id UUID REFERENCES participants(id) ON DELETE CASCADE,
  reserved_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE (participant_id)  -- one reservation per person
);

-- Q&A and coordinator messages
CREATE TABLE questions (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participant_id UUID REFERENCES participants(id) ON DELETE CASCADE,
  text           TEXT NOT NULL,
  submitted_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE messages (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participant_id UUID REFERENCES participants(id) ON DELETE CASCADE,
  text           TEXT NOT NULL,
  submitted_at   TIMESTAMPTZ DEFAULT now()
);

-- Bot-wide config: schedule, venue, feature toggles
CREATE TABLE bot_settings (
  key   TEXT PRIMARY KEY,
  value TEXT
);
```

---

## Registration Flow (`handlers/registration.py`)

Full ConversationHandler with these states:

```
LANG_SELECT → NAME → AGE → GENDER → PHONE → PAYMENT → RECEIPT
```

**Step-by-step:**

1. `/start` — check if already registered. If approved → show main menu. If pending → show waiting message. Otherwise start flow.
2. **Language selection** — inline buttons: `English` / `Українська`. Stored immediately.
3. **Full name** — free text input.
4. **Age** — numeric input, validated (must be integer, reasonable range 10–99).
5. **Gender** — inline buttons: Male / Female (localized labels).
6. **Phone** — Telegram contact share button (same pattern as SYC bot). Stored as-is.
7. **Payment** — show `PAYMENT_LINK`, instructions to complete payment and return with receipt. Status → `pending_payment`.
8. **Receipt upload** — user sends photo or document. `file_id` stored in `receipts` table. Status → `pending_approval`. User sees: *"Your registration is under review. You'll be notified once approved."* Admin channel pinged.

**Receipt resubmission (denied users):**
- If status is `denied`, `/start` shows denial reason and offers to resubmit receipt (skips all form steps, jumps to RECEIPT state).

---

## Housing Flow (`handlers/housing.py`)

Accessible from main menu for approved participants only.

1. **"Do you need local housing?"** — Yes / No inline buttons.
2. **No** → acknowledge, return to menu.
3. **Yes** → query houses filtered by participant's gender, with occupancy count.
4. Display as inline buttons: `"Дім Сонця — 4/12 spots taken"` (full houses shown as disabled/greyed label).
5. User taps a house → confirm dialog → reservation created.
6. **Already reserved** → show current reservation with option to cancel.
7. **Cancel reservation** → confirmation dialog → remove row from `house_reservations`.

**House full:** Button label updated to `"Дім Сонця — FULL"`, tapping it shows a message (no reservation created).

---

## Info Features (`handlers/info.py`)

All content stored in `bot_settings` so admins can update without redeploying:

| Feature | bot_settings key | Description |
|---|---|---|
| Schedule | `schedule_text` | Displayed as formatted message |
| Venue | `venue_text` | Address + map link |
| Q&A | `qa_channel_id` | Questions forwarded here |
| Coordinators | `coord_channel_id` | Messages forwarded here |

**Q&A:** Rate-limited (max 3 questions per participant). Forwarded to admin channel.  
**Coordinator messages:** Free-form, forwarded to coordinator channel.

---

## Admin Tools (`handlers/admin.py`)

### Registration management
| Command | Access | Description |
|---|---|---|
| `/pending` | Admin | Paginated list of `pending_approval` participants. Each entry has View Receipt / ✅ Approve / ❌ Deny buttons |
| `/approve <chat_id>` | Admin | Approve a participant, notify them |
| `/deny <chat_id> <reason>` | Admin | Deny with reason, notify them in their language |
| `/participants` | Admin | Full list with status indicators (✅ approved, ⏳ pending, 🚫 denied) |

### Housing management
| Command | Access | Description |
|---|---|---|
| `/addhouse <name> <M\|F> <capacity>` | Admin | Add a new house |
| `/removehouse <name>` | Admin | Remove a house (warns if occupied) |
| `/listhouses` | Admin | Show all houses with occupancy |
| `/moveresident <chat_id> <house_name>` | Admin | Move a participant to a different house |

### Bot management
| Command | Access | Description |
|---|---|---|
| `/broadcast <message>` | Admin | Send to all approved participants |
| `/status` | Admin | Stats: counts by status, house occupancy totals |
| `/pause <feature>` | Admin | Disable a feature (housing, qa, messages) |
| `/resume <feature>` | Admin | Re-enable a feature |
| `/setschedule` | Admin | Update schedule text (follows with text input) |
| `/setvenue` | Admin | Update venue text |
| `/addadmin <chat_id>` | Owner | Add to ADMIN_IDS at runtime (stored in bot_settings) |
| `/removeuser <chat_id>` | Owner | Hard delete one participant |
| `/nuke` | Owner | Wipe all participant data (2 confirmations) |

---

## Deployment

**Render:** Web service, Python, webhook mode (same as SYC bot).  
**Environment variables on Render:**
```
BOT_TOKEN
SUPABASE_URL
SUPABASE_SERVICE_KEY
SUPABASE_ANON_KEY
PAYMENT_LINK
GROUP_CHAT_ID
WEBHOOK_URL   (set to Render public URL)
```

**render.yaml** mirrors SYC bot config with updated service name.

---

## Out of Scope (v1)

- Web dashboard for receipt review (planned v2)
- Google Sheets integration (not needed — housing is self-service)
- Ticket management (removed)
- Anonymous Slido Q&A link (can be added to info menu trivially if needed)
