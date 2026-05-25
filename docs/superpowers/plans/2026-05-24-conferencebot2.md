# ConferenceBot2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular Telegram conference registration bot with full in-Telegram registration, Adventist Giving payment receipt flow, gender-based housing self-reservation, bilingual EN/UK support, and full admin tooling — deployed on Render with Supabase.

**Architecture:** Modular Python package: `config.py` (constants/env), `strings.py` (all EN/UK text), `db.py` (Supabase layer), four handler modules under `handlers/`, and `bot.py` as Flask webhook entry point. Flask runs sync; PTB v20 runs on a background asyncio loop bridged via `run_async()` helper — same proven pattern as the SYC conferencebot.

**Tech Stack:** Python 3.11+, python-telegram-bot==20.7, Flask, supabase-py>=2.0, pytest, pytest-mock, Render, Supabase (PostgreSQL)

---

### Task 1: GitHub Repo + Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `render.yaml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `handlers/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create GitHub repo**

```bash
cd /Users/ludwig/Projects/conferencebot2
gh repo create Yogurt43/conferencebot2 --public --source=. --remote=origin
```

Expected: repo created at https://github.com/Yogurt43/conferencebot2

- [ ] **Step 2: Create requirements.txt**

```
python-telegram-bot==20.7
supabase>=2.0.0
flask>=2.0.0
requests>=2.28.0
```

- [ ] **Step 3: Create requirements-dev.txt**

```
pytest>=7.0
pytest-mock>=3.10
pytest-asyncio>=0.21
```

- [ ] **Step 4: Create render.yaml**

```yaml
services:
  - type: web
    name: conferencebot2
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: python bot.py
    envVars:
      - key: BOT_TOKEN
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_KEY
        sync: false
      - key: SUPABASE_ANON_KEY
        sync: false
      - key: WEBHOOK_URL
        sync: false
      - key: GROUP_CHAT_ID
        sync: false
      - key: PAYMENT_LINK
        sync: false
```

- [ ] **Step 5: Create .env.example**

```
BOT_TOKEN=your_telegram_bot_token
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
SUPABASE_ANON_KEY=your_anon_key
WEBHOOK_URL=https://your-render-url.onrender.com
GROUP_CHAT_ID=-1001234567890
PAYMENT_LINK=https://adventistgiving.org/your-link
```

- [ ] **Step 6: Create .gitignore**

```
__pycache__/
*.pyc
*.pyo
.env
.pytest_cache/
*.egg-info/
dist/
.DS_Store
```

- [ ] **Step 7: Create handlers/__init__.py, tests/__init__.py, and tests/conftest.py**

```bash
touch handlers/__init__.py tests/__init__.py
```

Create `tests/conftest.py` — sets fake env vars before any module import so tests don't crash on missing keys:

```python
# tests/conftest.py
import os
os.environ.setdefault('BOT_TOKEN', 'test:token')
os.environ.setdefault('SUPABASE_URL', 'https://test.supabase.co')
os.environ.setdefault('SUPABASE_SERVICE_KEY', 'test_service_key')
os.environ.setdefault('SUPABASE_ANON_KEY', 'test_anon_key')
os.environ.setdefault('WEBHOOK_URL', 'https://test.example.com')
```

- [ ] **Step 8: Initial commit + push**

```bash
git add .
git commit -m "chore: project scaffold"
git push -u origin main
```

---

### Task 2: Database Schema

**Files:**
- Create: `schema.sql`

- [ ] **Step 1: Create schema.sql**

```sql
-- Participants
CREATE TABLE IF NOT EXISTS participants (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id       BIGINT UNIQUE NOT NULL,
  username      TEXT,
  full_name     TEXT,
  phone         TEXT,
  age           INTEGER,
  gender        TEXT CHECK (gender IN ('M', 'F')),
  lang          TEXT CHECK (lang IN ('en', 'uk')) DEFAULT 'en',
  status        TEXT CHECK (status IN (
                  'incomplete',
                  'pending_payment',
                  'pending_approval',
                  'approved',
                  'denied'
                )) DEFAULT 'incomplete',
  denial_reason TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- Payment receipts (Telegram file_id)
CREATE TABLE IF NOT EXISTS receipts (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participant_id UUID REFERENCES participants(id) ON DELETE CASCADE,
  file_id        TEXT NOT NULL,
  submitted_at   TIMESTAMPTZ DEFAULT now()
);

-- Housing units (admin-managed)
CREATE TABLE IF NOT EXISTS houses (
  id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name     TEXT NOT NULL UNIQUE,
  gender   TEXT CHECK (gender IN ('M', 'F')),
  capacity INTEGER NOT NULL,
  address  TEXT,
  notes    TEXT
);

-- One reservation per participant
CREATE TABLE IF NOT EXISTS house_reservations (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  house_id       UUID REFERENCES houses(id) ON DELETE CASCADE,
  participant_id UUID REFERENCES participants(id) ON DELETE CASCADE,
  reserved_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE (participant_id)
);

-- Q&A submissions
CREATE TABLE IF NOT EXISTS questions (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participant_id UUID REFERENCES participants(id) ON DELETE CASCADE,
  text           TEXT NOT NULL,
  submitted_at   TIMESTAMPTZ DEFAULT now()
);

-- Coordinator messages
CREATE TABLE IF NOT EXISTS messages (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participant_id UUID REFERENCES participants(id) ON DELETE CASCADE,
  text           TEXT NOT NULL,
  submitted_at   TIMESTAMPTZ DEFAULT now()
);

-- Bot-wide config (schedule, venue, feature toggles)
CREATE TABLE IF NOT EXISTS bot_settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL DEFAULT ''
);

-- Seed default settings
INSERT INTO bot_settings (key, value) VALUES
  ('schedule_text', ''),
  ('venue_text', ''),
  ('qa_channel_id', ''),
  ('coord_channel_id', ''),
  ('qa_paused', 'false'),
  ('messages_paused', 'false'),
  ('housing_paused', 'false'),
  ('registration_locked', 'false'),
  ('admin_ids', '')
ON CONFLICT (key) DO NOTHING;
```

- [ ] **Step 2: Run schema against Supabase**

In Supabase dashboard → SQL Editor → paste schema.sql contents → Run.

Verify: all 7 tables appear in Table Editor.

- [ ] **Step 3: Commit**

```bash
git add schema.sql
git commit -m "feat: database schema"
git push
```

---

### Task 3: config.py

**Files:**
- Create: `config.py`

- [ ] **Step 1: Write config.py**

```python
import os

# ─── Conference identity ───────────────────────────────────────────────────────
CONF_NAME = "CONFERENCE_NAME"   # ← replace this one line to rebrand

# ─── Telegram ─────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ["BOT_TOKEN"]
WEBHOOK_URL  = os.environ["WEBHOOK_URL"]
OWNER_ID     = 479515546
ADMIN_IDS    = [479515546, 426569764]   # expandable via /addadmin at runtime

# ─── Group for admin notifications (receipt alerts, Q&A forwards, etc.) ───────
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))

# ─── Supabase ─────────────────────────────────────────────────────────────────
SUPABASE_URL         = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SUPABASE_ANON_KEY    = os.environ["SUPABASE_ANON_KEY"]

# ─── Payment ──────────────────────────────────────────────────────────────────
PAYMENT_LINK = os.getenv("PAYMENT_LINK", "PAYMENT_LINK_PLACEHOLDER")

# ─── Feature flags (defaults — overridden at runtime via bot_settings) ────────
QA_RATE_LIMIT = 3   # max questions per participant
```

- [ ] **Step 2: Commit**

```bash
git add config.py
git commit -m "feat: config module"
git push
```

---

### Task 4: strings.py

**Files:**
- Create: `strings.py`
- Create: `tests/test_strings.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_strings.py
from strings import S

def test_both_languages_present():
    assert 'en' in S
    assert 'uk' in S

def test_all_keys_in_both_languages():
    en_keys = set(S['en'].keys())
    uk_keys = set(S['uk'].keys())
    missing_in_uk = en_keys - uk_keys
    missing_in_en = uk_keys - en_keys
    assert not missing_in_uk, f"Missing in UK: {missing_in_uk}"
    assert not missing_in_en, f"Missing in EN: {missing_in_en}"

def test_no_empty_strings():
    for lang in ('en', 'uk'):
        for key, val in S[lang].items():
            assert val.strip(), f"Empty string for [{lang}][{key}]"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/ludwig/Projects/conferencebot2
python -m pytest tests/test_strings.py -v
```

Expected: `ModuleNotFoundError: No module named 'strings'`

- [ ] **Step 3: Create strings.py**

```python
# strings.py
from config import CONF_NAME

S = {
    'en': {
        # ── General ──────────────────────────────────────────────────────────
        'choose_lang':          '🌐 Please choose your language:',
        'error_generic':        '❌ Something went wrong. Please try again.',
        'not_approved':         '⏳ Your registration is still under review.',
        'no_permission':        '🚫 You do not have permission to use this command.',
        'btn_back':             '⬅️ Back',
        'cancelled':            '✅ Cancelled.',

        # ── Main menu ────────────────────────────────────────────────────────
        'main_menu':            f'🏠 Welcome to {CONF_NAME}! What would you like to do?',
        'btn_housing':          '🏡 Housing',
        'btn_schedule':         '📅 Schedule',
        'btn_venue':            '📍 Venue',
        'btn_qa':               '❓ Ask a Question',
        'btn_coordinator':      '📨 Message Coordinators',

        # ── Registration ─────────────────────────────────────────────────────
        'welcome_new':          f'👋 Welcome to {CONF_NAME}!\n\nLet\'s get you registered. This will only take a minute.',
        'already_pending':      f'⏳ Your registration for {CONF_NAME} is under review. We\'ll notify you once it\'s approved!',
        'already_approved':     f'✅ You\'re already registered for {CONF_NAME}!',
        'denied_resubmit':      '❌ Your registration was denied.\n\n*Reason:* {reason}\n\nYou may upload a new payment receipt to reapply.',
        'enter_name':           '📝 Please enter your *full name*:',
        'enter_age':            '🔢 Please enter your *age*:',
        'invalid_age':          '❌ Please enter a valid age (a number between 10 and 99).',
        'choose_gender':        '👤 Please select your gender:',
        'btn_male':             '♂️ Male',
        'btn_female':           '♀️ Female',
        'share_phone':          '📱 Please share your phone number so we can contact you:',
        'btn_share_phone':      '📲 Share Phone Number',
        'payment_instructions': (
            f'💳 *Payment*\n\n'
            f'Please complete your registration payment at the link below:\n\n'
            f'{{payment_link}}\n\n'
            f'Once you\'ve paid, come back and send your *payment receipt* (photo or screenshot).'
        ),
        'upload_receipt':       '📎 Please upload your *payment receipt* (photo or screenshot):',
        'receipt_submitted':    (
            '✅ Your receipt has been received!\n\n'
            'Our team will review it and notify you once your registration is approved. '
            'This usually takes 1–2 business days.'
        ),
        'approved_welcome':     (
            f'🎉 *You\'re registered for {CONF_NAME}!*\n\n'
            'Your registration has been approved. Use the menu below to access all features.'
        ),
        'denied_notification':  '❌ *Registration Update*\n\nYour registration was not approved.\n\n*Reason:* {reason}\n\nPlease contact the organizers if you have questions.',

        # ── Housing ──────────────────────────────────────────────────────────
        'housing_paused':       '⏸ Housing reservations are not available right now.',
        'housing_prompt':       '🏡 Do you need local housing for the conference?',
        'btn_housing_yes':      '✅ Yes, I need housing',
        'btn_housing_no':       '❌ No, I have my own',
        'no_housing_needed':    '👍 Got it! You\'re all set without housing.',
        'no_houses_available':  '😔 No housing is available for your group right now. Please contact the organizers.',
        'housing_list_header':  '🏠 Available houses — tap one to reserve:',
        'house_full_label':     '{name} — FULL',
        'house_spots_label':    '{name} — {taken}/{capacity} spots taken',
        'house_full_msg':       '😔 That house is full. Please choose another.',
        'house_confirm':        '🏡 Reserve a spot at *{name}*?\n\nAddress: {address}',
        'btn_confirm_yes':      '✅ Yes, reserve',
        'btn_confirm_no':       '❌ Cancel',
        'house_reserved':       '✅ You\'re reserved at *{name}*!\n\nAddress: {address}\n\n{notes}',
        'current_reservation':  '🏡 Your current reservation: *{name}*\n\nAddress: {address}\n\nWould you like to cancel it?',
        'btn_cancel_reservation': '❌ Cancel Reservation',
        'reservation_cancelled': '✅ Your reservation has been cancelled. You can reserve a new spot anytime.',

        # ── Schedule ─────────────────────────────────────────────────────────
        'no_schedule':          '📅 The schedule hasn\'t been posted yet. Check back soon!',

        # ── Venue ────────────────────────────────────────────────────────────
        'no_venue':             '📍 Venue information hasn\'t been posted yet. Check back soon!',

        # ── Q&A ──────────────────────────────────────────────────────────────
        'qa_paused':            '⏸ Q&A submissions are paused right now.',
        'qa_prompt':            '❓ Type your question for the speakers:',
        'qa_submitted':         '✅ Your question has been submitted!',
        'qa_rate_limited':      '❌ You\'ve reached the question limit ({limit} questions max).',

        # ── Coordinator messages ──────────────────────────────────────────────
        'messages_paused':      '⏸ Coordinator messaging is paused right now.',
        'coordinator_prompt':   '📨 Type your message to the coordinators:',
        'coordinator_submitted':'✅ Your message has been sent to the coordinators!',

        # ── Admin ─────────────────────────────────────────────────────────────
        'admin_no_pending':     '✅ No registrations pending review.',
        'admin_pending_header': '📋 *Pending registrations ({count}):*\n\n',
        'admin_pending_entry':  '👤 *{name}* | {age}y | {gender} | @{username}\n',
        'admin_approved':       '✅ {name} has been approved and notified.',
        'admin_denied':         '❌ {name} has been denied and notified.',
        'admin_deny_prompt':    'Enter the reason for denial (will be sent to the user):',
        'admin_no_participants':'No participants found.',
        'admin_broadcast_sent': '📢 Broadcast sent to {count} approved participants.',
        'admin_house_added':    '✅ House *{name}* added ({gender}, capacity {capacity}).',
        'admin_house_exists':   '❌ A house named *{name}* already exists.',
        'admin_house_removed':  '✅ House *{name}* removed.',
        'admin_house_not_found':'❌ No house found with name *{name}*.',
        'admin_house_occupied': '⚠️ House *{name}* has {count} reservation(s). Remove anyway? Reply /confirmremove {name}',
        'admin_houses_list':    '🏠 *Houses:*\n\n{list}',
        'admin_resident_moved': '✅ {user} moved to *{house}*.',
        'admin_user_not_found': '❌ No user found with that ID.',
        'admin_feature_paused': '⏸ Feature *{feature}* paused.',
        'admin_feature_resumed':'▶️ Feature *{feature}* resumed.',
        'admin_schedule_set':   '✅ Schedule updated.',
        'admin_venue_set':      '✅ Venue info updated.',
        'admin_added':          '✅ Admin {chat_id} added.',
        'admin_user_removed':   '✅ User removed.',
        'admin_nuke_confirm1':  '⚠️ This will delete ALL participant data. Type /nuke2 to confirm.',
        'admin_nuke_confirm2':  '🔴 FINAL WARNING: all data will be wiped. Type /nuke3 to proceed.',
        'admin_nuked':          '💥 All participant data has been deleted.',
        'admin_set_prompt':     'Send the new {field} text now:',
        'admin_status':         (
            '📊 *Bot Status*\n\n'
            '👥 Total participants: {total}\n'
            '✅ Approved: {approved}\n'
            '⏳ Pending review: {pending}\n'
            '❌ Denied: {denied}\n'
            '🏠 Housing reserved: {housed}'
        ),
    },

    'uk': {
        # ── General ──────────────────────────────────────────────────────────
        'choose_lang':          '🌐 Будь ласка, оберіть мову:',
        'error_generic':        '❌ Щось пішло не так. Будь ласка, спробуйте ще раз.',
        'not_approved':         '⏳ Ваша реєстрація ще на розгляді.',
        'no_permission':        '🚫 У вас немає дозволу використовувати цю команду.',
        'btn_back':             '⬅️ Назад',
        'cancelled':            '✅ Скасовано.',

        # ── Main menu ────────────────────────────────────────────────────────
        'main_menu':            f'🏠 Ласкаво просимо до {CONF_NAME}! Що бажаєте зробити?',
        'btn_housing':          '🏡 Житло',
        'btn_schedule':         '📅 Розклад',
        'btn_venue':            '📍 Місце проведення',
        'btn_qa':               '❓ Запитати доповідача',
        'btn_coordinator':      '📨 Написати координаторам',

        # ── Registration ─────────────────────────────────────────────────────
        'welcome_new':          f'👋 Ласкаво просимо до {CONF_NAME}!\n\nДавайте зареєструємо вас. Це займе лише хвилину.',
        'already_pending':      f'⏳ Ваша реєстрація на {CONF_NAME} на розгляді. Ми повідомимо вас, коли її схвалять!',
        'already_approved':     f'✅ Ви вже зареєстровані на {CONF_NAME}!',
        'denied_resubmit':      '❌ Вашу реєстрацію було відхилено.\n\n*Причина:* {reason}\n\nВи можете завантажити новий чек для повторної подачі.',
        'enter_name':           "📝 Будь ласка, введіть ваше *повне ім'я*:",
        'enter_age':            '🔢 Будь ласка, введіть ваш *вік*:',
        'invalid_age':          '❌ Будь ласка, введіть коректний вік (число від 10 до 99).',
        'choose_gender':        '👤 Будь ласка, оберіть вашу стать:',
        'btn_male':             '♂️ Чоловік',
        'btn_female':           '♀️ Жінка',
        'share_phone':          '📱 Будь ласка, поділіться своїм номером телефону, щоб ми могли зв\'язатися з вами:',
        'btn_share_phone':      '📲 Поділитися номером телефону',
        'payment_instructions': (
            f'💳 *Оплата*\n\n'
            f'Будь ласка, здійсніть оплату реєстраційного внеску за посиланням нижче:\n\n'
            f'{{payment_link}}\n\n'
            f'Після оплати поверніться сюди та надішліть *квитанцію про оплату* (фото або скриншот).'
        ),
        'upload_receipt':       '📎 Будь ласка, завантажте *квитанцію про оплату* (фото або скриншот):',
        'receipt_submitted':    (
            '✅ Вашу квитанцію отримано!\n\n'
            'Наша команда перевірить її та повідомить вас після схвалення реєстрації. '
            'Зазвичай це займає 1–2 робочі дні.'
        ),
        'approved_welcome':     (
            f'🎉 *Вітаємо! Ви зареєстровані на {CONF_NAME}!*\n\n'
            'Вашу реєстрацію схвалено. Використовуйте меню нижче для доступу до всіх функцій.'
        ),
        'denied_notification':  '❌ *Оновлення реєстрації*\n\nВашу реєстрацію не схвалено.\n\n*Причина:* {reason}\n\nЗверніться до організаторів, якщо у вас є запитання.',

        # ── Housing ──────────────────────────────────────────────────────────
        'housing_paused':       '⏸ Бронювання житла наразі недоступне.',
        'housing_prompt':       '🏡 Чи потребуєте ви проживання під час конференції?',
        'btn_housing_yes':      '✅ Так, потребую',
        'btn_housing_no':       '❌ Ні, маю своє',
        'no_housing_needed':    '👍 Зрозуміло! Все влаштовано без проживання.',
        'no_houses_available':  '😔 На жаль, проживання для вашої групи наразі недоступне. Зверніться до організаторів.',
        'housing_list_header':  '🏠 Доступне житло — натисніть, щоб забронювати:',
        'house_full_label':     '{name} — ЗАЙНЯТИЙ',
        'house_spots_label':    '{name} — {taken}/{capacity} місць зайнято',
        'house_full_msg':       '😔 Цей будинок заповнений. Будь ласка, оберіть інший.',
        'house_confirm':        '🏡 Забронювати місце в *{name}*?\n\nАдреса: {address}',
        'btn_confirm_yes':      '✅ Так, бронюю',
        'btn_confirm_no':       '❌ Скасувати',
        'house_reserved':       '✅ Ви заброньовані в *{name}*!\n\nАдреса: {address}\n\n{notes}',
        'current_reservation':  '🏡 Ваше поточне бронювання: *{name}*\n\nАдреса: {address}\n\nБажаєте скасувати?',
        'btn_cancel_reservation': '❌ Скасувати бронювання',
        'reservation_cancelled': '✅ Ваше бронювання скасовано. Ви можете забронювати нове місце будь-коли.',

        # ── Schedule ─────────────────────────────────────────────────────────
        'no_schedule':          '📅 Розклад ще не опубліковано. Перевірте пізніше!',

        # ── Venue ────────────────────────────────────────────────────────────
        'no_venue':             '📍 Інформація про місце проведення ще не опублікована. Перевірте пізніше!',

        # ── Q&A ──────────────────────────────────────────────────────────────
        'qa_paused':            '⏸ Прийом запитань наразі призупинено.',
        'qa_prompt':            '❓ Введіть ваше запитання для доповідачів:',
        'qa_submitted':         '✅ Ваше запитання надіслано!',
        'qa_rate_limited':      '❌ Ви досягли ліміту запитань (максимум {limit}).',

        # ── Coordinator messages ──────────────────────────────────────────────
        'messages_paused':      '⏸ Зв\'язок з координаторами наразі призупинено.',
        'coordinator_prompt':   '📨 Введіть повідомлення для координаторів:',
        'coordinator_submitted':'✅ Ваше повідомлення надіслано координаторам!',

        # ── Admin ─────────────────────────────────────────────────────────────
        'admin_no_pending':     '✅ Немає реєстрацій на розгляді.',
        'admin_pending_header': '📋 *Очікують розгляду ({count}):*\n\n',
        'admin_pending_entry':  '👤 *{name}* | {age}р | {gender} | @{username}\n',
        'admin_approved':       '✅ {name} схвалено та повідомлено.',
        'admin_denied':         '❌ {name} відхилено та повідомлено.',
        'admin_deny_prompt':    'Введіть причину відхилення (буде надіслана користувачу):',
        'admin_no_participants':'Учасників не знайдено.',
        'admin_broadcast_sent': '📢 Повідомлення надіслано {count} схваленим учасникам.',
        'admin_house_added':    '✅ Будинок *{name}* додано ({gender}, місткість {capacity}).',
        'admin_house_exists':   '❌ Будинок з назвою *{name}* вже існує.',
        'admin_house_removed':  '✅ Будинок *{name}* видалено.',
        'admin_house_not_found':'❌ Будинок з назвою *{name}* не знайдено.',
        'admin_house_occupied': '⚠️ У будинку *{name}* є {count} бронювань. Видалити? Відповідь /confirmremove {name}',
        'admin_houses_list':    '🏠 *Будинки:*\n\n{list}',
        'admin_resident_moved': '✅ {user} переміщено до *{house}*.',
        'admin_user_not_found': '❌ Користувача з таким ID не знайдено.',
        'admin_feature_paused': '⏸ Функцію *{feature}* призупинено.',
        'admin_feature_resumed':'▶️ Функцію *{feature}* відновлено.',
        'admin_schedule_set':   '✅ Розклад оновлено.',
        'admin_venue_set':      '✅ Інформацію про місце оновлено.',
        'admin_added':          '✅ Адміністратора {chat_id} додано.',
        'admin_user_removed':   '✅ Користувача видалено.',
        'admin_nuke_confirm1':  '⚠️ Це видалить УСІ дані учасників. Введіть /nuke2 для підтвердження.',
        'admin_nuke_confirm2':  '🔴 ОСТАТОЧНЕ ПОПЕРЕДЖЕННЯ: всі дані будуть видалені. Введіть /nuke3 для продовження.',
        'admin_nuked':          '💥 Усі дані учасників видалено.',
        'admin_set_prompt':     'Надішліть новий текст для {field}:',
        'admin_status':         (
            '📊 *Статус бота*\n\n'
            '👥 Всього учасників: {total}\n'
            '✅ Схвалено: {approved}\n'
            '⏳ На розгляді: {pending}\n'
            '❌ Відхилено: {denied}\n'
            '🏠 Забронювали житло: {housed}'
        ),
    }
}


def t(lang: str, key: str, **kwargs) -> str:
    """Get a translated string. Falls back to 'en' if lang not found."""
    text = S.get(lang, S['en']).get(key, S['en'].get(key, f'[{key}]'))
    return text.format(**kwargs) if kwargs else text
```

- [ ] **Step 4: Install dev dependencies and run tests**

```bash
pip install -r requirements-dev.txt
python -m pytest tests/test_strings.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add strings.py tests/test_strings.py
git commit -m "feat: bilingual strings module with tests"
git push
```

---

### Task 5: db.py — Supabase Query Layer

**Files:**
- Create: `db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_db.py
import pytest
from unittest.mock import MagicMock
import db  # conftest.py sets env vars before this import

@pytest.fixture
def mock_sb(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(db, 'sb', mock)
    return mock

def test_get_participant_returns_none_when_not_found(mock_sb):
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    result = db.get_participant(99999)
    assert result is None

def test_get_participant_returns_data(mock_sb):
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {'chat_id': 123, 'full_name': 'Test User', 'status': 'approved'}
    ]
    result = db.get_participant(123)
    assert result['chat_id'] == 123
    assert result['status'] == 'approved'

def test_upsert_participant(mock_sb):
    mock_sb.table.return_value.upsert.return_value.execute.return_value.data = [
        {'chat_id': 123, 'lang': 'uk'}
    ]
    result = db.upsert_participant({'chat_id': 123, 'lang': 'uk'})
    assert result['lang'] == 'uk'

def test_get_houses_for_gender(mock_sb):
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {'id': 'abc', 'name': 'Test House', 'gender': 'M', 'capacity': 12}
    ]
    result = db.get_houses_for_gender('M')
    assert len(result) == 1
    assert result[0]['gender'] == 'M'

def test_get_setting(mock_sb):
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {'key': 'schedule_text', 'value': 'Day 1: ...'}
    ]
    result = db.get_setting('schedule_text')
    assert result == 'Day 1: ...'

def test_get_setting_returns_empty_when_not_found(mock_sb):
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    result = db.get_setting('missing_key')
    assert result == ''
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_db.py -v
```

Expected: `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Install supabase and create db.py**

```bash
pip install supabase
```

```python
# db.py
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ─── Participants ──────────────────────────────────────────────────────────────

def get_participant(chat_id: int) -> dict | None:
    res = sb.table('participants').select('*').eq('chat_id', chat_id).execute()
    return res.data[0] if res.data else None

def upsert_participant(data: dict) -> dict:
    res = sb.table('participants').upsert(data, on_conflict='chat_id').execute()
    return res.data[0]

def update_participant(chat_id: int, data: dict) -> dict:
    res = sb.table('participants').update(data).eq('chat_id', chat_id).execute()
    return res.data[0]

def get_participants_by_status(status: str) -> list[dict]:
    res = sb.table('participants').select('*').eq('status', status).execute()
    return res.data

def get_all_participants() -> list[dict]:
    res = sb.table('participants').select('*').order('created_at').execute()
    return res.data

def delete_participant(chat_id: int) -> None:
    sb.table('participants').delete().eq('chat_id', chat_id).execute()

def delete_all_participants() -> None:
    # Delete reservations, receipts, questions, messages first (FK cascade handles it)
    sb.table('participants').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()

def count_participants_by_status() -> dict:
    all_p = get_all_participants()
    counts = {'total': len(all_p), 'approved': 0, 'pending': 0, 'denied': 0}
    for p in all_p:
        if p['status'] == 'approved':
            counts['approved'] += 1
        elif p['status'] in ('pending_payment', 'pending_approval'):
            counts['pending'] += 1
        elif p['status'] == 'denied':
            counts['denied'] += 1
    return counts


# ─── Receipts ─────────────────────────────────────────────────────────────────

def save_receipt(participant_id: str, file_id: str) -> dict:
    res = sb.table('receipts').insert({
        'participant_id': participant_id,
        'file_id': file_id
    }).execute()
    return res.data[0]

def get_latest_receipt(participant_id: str) -> dict | None:
    res = (sb.table('receipts')
             .select('*')
             .eq('participant_id', participant_id)
             .order('submitted_at', desc=True)
             .limit(1)
             .execute())
    return res.data[0] if res.data else None


# ─── Houses ───────────────────────────────────────────────────────────────────

def get_houses_for_gender(gender: str) -> list[dict]:
    res = sb.table('houses').select('*').eq('gender', gender).execute()
    return res.data

def get_all_houses() -> list[dict]:
    res = sb.table('houses').select('*').order('name').execute()
    return res.data

def get_house_by_name(name: str) -> dict | None:
    res = sb.table('houses').select('*').eq('name', name).execute()
    return res.data[0] if res.data else None

def get_house_by_id(house_id: str) -> dict | None:
    res = sb.table('houses').select('*').eq('id', house_id).execute()
    return res.data[0] if res.data else None

def add_house(name: str, gender: str, capacity: int, address: str = '', notes: str = '') -> dict:
    res = sb.table('houses').insert({
        'name': name, 'gender': gender, 'capacity': capacity,
        'address': address, 'notes': notes
    }).execute()
    return res.data[0]

def remove_house(house_id: str) -> None:
    sb.table('houses').delete().eq('id', house_id).execute()


# ─── House Reservations ────────────────────────────────────────────────────────

def get_reservation(participant_id: str) -> dict | None:
    res = (sb.table('house_reservations')
             .select('*, houses(*)')
             .eq('participant_id', participant_id)
             .execute())
    return res.data[0] if res.data else None

def get_house_occupancy(house_id: str) -> int:
    res = sb.table('house_reservations').select('id').eq('house_id', house_id).execute()
    return len(res.data)

def get_house_reservation_count(house_id: str) -> int:
    return get_house_occupancy(house_id)

def create_reservation(house_id: str, participant_id: str) -> dict:
    res = sb.table('house_reservations').insert({
        'house_id': house_id,
        'participant_id': participant_id
    }).execute()
    return res.data[0]

def delete_reservation(participant_id: str) -> None:
    sb.table('house_reservations').delete().eq('participant_id', participant_id).execute()

def move_reservation(participant_id: str, new_house_id: str) -> dict:
    res = (sb.table('house_reservations')
             .update({'house_id': new_house_id})
             .eq('participant_id', participant_id)
             .execute())
    return res.data[0]

def count_housed_participants() -> int:
    res = sb.table('house_reservations').select('id').execute()
    return len(res.data)


# ─── Q&A ──────────────────────────────────────────────────────────────────────

def count_questions_by_participant(participant_id: str) -> int:
    res = sb.table('questions').select('id').eq('participant_id', participant_id).execute()
    return len(res.data)

def save_question(participant_id: str, text: str) -> dict:
    res = sb.table('questions').insert({
        'participant_id': participant_id, 'text': text
    }).execute()
    return res.data[0]


# ─── Coordinator messages ──────────────────────────────────────────────────────

def save_message(participant_id: str, text: str) -> dict:
    res = sb.table('messages').insert({
        'participant_id': participant_id, 'text': text
    }).execute()
    return res.data[0]


# ─── Bot settings ─────────────────────────────────────────────────────────────

def get_setting(key: str) -> str:
    res = sb.table('bot_settings').select('value').eq('key', key).execute()
    return res.data[0]['value'] if res.data else ''

def set_setting(key: str, value: str) -> None:
    sb.table('bot_settings').upsert({'key': key, 'value': value}).execute()

def is_paused(feature: str) -> bool:
    return get_setting(f'{feature}_paused') == 'true'

def get_admin_ids_from_db() -> list[int]:
    """Returns runtime admin IDs stored in bot_settings (in addition to ADMIN_IDS in config)."""
    raw = get_setting('admin_ids')
    if not raw:
        return []
    return [int(x) for x in raw.split(',') if x.strip().isdigit()]
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_db.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: db layer with tests"
git push
```

---

### Task 6: utils.py — Pure Helper Functions

**Files:**
- Create: `utils.py`
- Create: `tests/test_utils.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_utils.py
from utils import validate_age, format_house_button, get_lang, is_admin

def test_validate_age_valid():
    assert validate_age('25') == 25
    assert validate_age('10') == 10
    assert validate_age('99') == 99

def test_validate_age_invalid():
    assert validate_age('abc') is None
    assert validate_age('9') is None
    assert validate_age('100') is None
    assert validate_age('') is None
    assert validate_age('-1') is None

def test_format_house_button_available():
    house = {'name': 'Дім Сонця', 'capacity': 12}
    label = format_house_button(house, taken=4)
    assert 'Дім Сонця' in label
    assert '4/12' in label

def test_format_house_button_full():
    house = {'name': 'Дім Сонця', 'capacity': 12}
    label = format_house_button(house, taken=12)
    assert 'FULL' in label or 'ЗАЙНЯТИЙ' in label or label.endswith('— 12/12 spots taken')

def test_get_lang_defaults_to_en():
    participant = {'lang': None}
    assert get_lang(participant) == 'en'

def test_get_lang_returns_stored():
    participant = {'lang': 'uk'}
    assert get_lang(participant) == 'uk'

def test_is_admin_owner():
    assert is_admin(479515546) is True

def test_is_admin_known_admin():
    assert is_admin(426569764) is True

def test_is_admin_random_user():
    assert is_admin(99999999) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_utils.py -v
```

Expected: `ModuleNotFoundError: No module named 'utils'`

- [ ] **Step 3: Create utils.py**

```python
# utils.py
import db
from config import ADMIN_IDS, OWNER_ID


def validate_age(text: str) -> int | None:
    """Return integer age if valid (10–99), else None."""
    try:
        age = int(text.strip())
        return age if 10 <= age <= 99 else None
    except (ValueError, AttributeError):
        return None


def format_house_button(house: dict, taken: int) -> str:
    """Format a house's inline button label."""
    name = house['name']
    cap = house['capacity']
    if taken >= cap:
        return f"{name} — FULL / ЗАЙНЯТИЙ"
    return f"{name} — {taken}/{cap} spots taken"


def get_lang(participant: dict | None) -> str:
    """Return participant's language, defaulting to 'en'."""
    if not participant:
        return 'en'
    return participant.get('lang') or 'en'


def is_admin(chat_id: int) -> bool:
    """True if chat_id is owner, in static ADMIN_IDS, or in runtime DB admin list."""
    if chat_id == OWNER_ID or chat_id in ADMIN_IDS:
        return True
    try:
        return chat_id in db.get_admin_ids_from_db()
    except Exception:
        return False


def is_owner(chat_id: int) -> bool:
    """True only for the owner."""
    return chat_id == OWNER_ID
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_utils.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add utils.py tests/test_utils.py
git commit -m "feat: utils helpers with tests"
git push
```

---

### Task 7: Registration Handler

**Files:**
- Create: `handlers/registration.py`

- [ ] **Step 1: Create handlers/registration.py**

```python
# handlers/registration.py
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.constants import ParseMode

import db
import utils
from strings import t
from config import PAYMENT_LINK, GROUP_CHAT_ID

# Conversation states
LANG, NAME, AGE, GENDER, PHONE, PAYMENT_STEP, RECEIPT = range(7)


def _lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧 English", callback_data='lang_en'),
         InlineKeyboardButton("🇺🇦 Українська", callback_data='lang_uk')]
    ])


def _gender_keyboard(lang: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, 'btn_male'), callback_data='gender_M'),
         InlineKeyboardButton(t(lang, 'btn_female'), callback_data='gender_F')]
    ])


def _phone_keyboard(lang: str):
    btn = KeyboardButton(t(lang, 'btn_share_phone'), request_contact=True)
    return ReplyKeyboardMarkup([[btn]], one_time_keyboard=True, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    participant = db.get_participant(chat_id)

    if participant:
        lang = utils.get_lang(participant)
        status = participant['status']

        if status == 'approved':
            await _show_main_menu(update, lang)
            return ConversationHandler.END

        if status in ('pending_payment', 'pending_approval'):
            await update.message.reply_text(t(lang, 'already_pending'))
            return ConversationHandler.END

        if status == 'denied':
            await update.message.reply_text(
                t(lang, 'denied_resubmit', reason=participant.get('denial_reason', '—')),
                parse_mode=ParseMode.MARKDOWN
            )
            # Jump straight to receipt upload — they don't redo the whole form
            db.update_participant(chat_id, {'status': 'pending_payment'})
            return RECEIPT

    # New user — start language selection
    await update.message.reply_text(
        t('en', 'choose_lang'),
        reply_markup=_lang_keyboard()
    )
    return LANG


async def handle_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.data.replace('lang_', '')
    chat_id = update.effective_chat.id
    username = update.effective_user.username or ''

    db.upsert_participant({'chat_id': chat_id, 'username': username, 'lang': lang, 'status': 'incomplete'})
    context.user_data['lang'] = lang

    await query.edit_message_text(t(lang, 'welcome_new'), parse_mode=ParseMode.MARKDOWN)
    await query.message.reply_text(t(lang, 'enter_name'), parse_mode=ParseMode.MARKDOWN)
    return NAME


async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _get_lang(update, context)
    name = update.message.text.strip()
    context.user_data['full_name'] = name
    db.update_participant(update.effective_chat.id, {'full_name': name})

    await update.message.reply_text(t(lang, 'enter_age'), parse_mode=ParseMode.MARKDOWN)
    return AGE


async def handle_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _get_lang(update, context)
    age = utils.validate_age(update.message.text)

    if age is None:
        await update.message.reply_text(t(lang, 'invalid_age'))
        return AGE

    context.user_data['age'] = age
    db.update_participant(update.effective_chat.id, {'age': age})

    await update.message.reply_text(t(lang, 'choose_gender'), reply_markup=_gender_keyboard(lang))
    return GENDER


async def handle_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _get_lang(update, context)
    gender = query.data.replace('gender_', '')
    context.user_data['gender'] = gender

    db.update_participant(update.effective_chat.id, {'gender': gender})

    await query.edit_message_text(t(lang, 'choose_gender') + f" ✅")
    await query.message.reply_text(
        t(lang, 'share_phone'),
        reply_markup=_phone_keyboard(lang)
    )
    return PHONE


async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _get_lang(update, context)

    if not update.message.contact:
        await update.message.reply_text(t(lang, 'share_phone'), reply_markup=_phone_keyboard(lang))
        return PHONE

    phone = update.message.contact.phone_number
    db.update_participant(update.effective_chat.id, {'phone': phone, 'status': 'pending_payment'})

    await update.message.reply_text(
        t(lang, 'payment_instructions', payment_link=PAYMENT_LINK),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.MARKDOWN
    )
    await update.message.reply_text(t(lang, 'upload_receipt'), parse_mode=ParseMode.MARKDOWN)
    return RECEIPT


async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _get_lang(update, context)
    chat_id = update.effective_chat.id

    # Accept photo or document
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text(t(lang, 'upload_receipt'), parse_mode=ParseMode.MARKDOWN)
        return RECEIPT

    participant = db.get_participant(chat_id)
    db.save_receipt(participant['id'], file_id)
    db.update_participant(chat_id, {'status': 'pending_approval'})

    await update.message.reply_text(t(lang, 'receipt_submitted'))

    # Notify admin group
    if GROUP_CHAT_ID:
        name = participant.get('full_name', 'Unknown')
        age = participant.get('age', '?')
        gender = participant.get('gender', '?')
        username = participant.get('username', '')
        uname_str = f"@{username}" if username else f"ID: {chat_id}"
        admin_text = (
            f"📥 *New registration pending review*\n\n"
            f"👤 {name} | {age}y | {gender}\n"
            f"📱 {uname_str}\n"
            f"🆔 `{chat_id}`\n\n"
            f"Use `/approve {chat_id}` or `/deny {chat_id} <reason>`\n"
            f"Use `/viewreceipt {chat_id}` to see the receipt."
        )
        await context.bot.send_message(GROUP_CHAT_ID, admin_text, parse_mode=ParseMode.MARKDOWN)

    return ConversationHandler.END


def _get_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Get lang from user_data cache or DB."""
    lang = context.user_data.get('lang')
    if not lang:
        p = db.get_participant(update.effective_chat.id)
        lang = utils.get_lang(p)
        context.user_data['lang'] = lang
    return lang


async def _show_main_menu(update: Update, lang: str):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, 'btn_housing'), callback_data='menu_housing')],
        [InlineKeyboardButton(t(lang, 'btn_schedule'), callback_data='menu_schedule'),
         InlineKeyboardButton(t(lang, 'btn_venue'), callback_data='menu_venue')],
        [InlineKeyboardButton(t(lang, 'btn_qa'), callback_data='menu_qa')],
        [InlineKeyboardButton(t(lang, 'btn_coordinator'), callback_data='menu_coordinator')],
    ])
    await update.message.reply_text(
        t(lang, 'main_menu'),
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu to approved participants."""
    chat_id = update.effective_chat.id
    participant = db.get_participant(chat_id)
    if not participant or participant['status'] != 'approved':
        lang = utils.get_lang(participant)
        await update.message.reply_text(t(lang, 'not_approved'))
        return
    lang = utils.get_lang(participant)
    await _show_main_menu(update, lang)


def build_registration_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LANG:         [CallbackQueryHandler(handle_lang, pattern='^lang_')],
            NAME:         [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name)],
            AGE:          [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_age)],
            GENDER:       [CallbackQueryHandler(handle_gender, pattern='^gender_')],
            PHONE:        [MessageHandler(filters.CONTACT, handle_phone)],
            PAYMENT_STEP: [],  # user just reads the message and sends receipt
            RECEIPT:      [MessageHandler(filters.PHOTO | filters.Document.ALL, handle_receipt)],
        },
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True,
        name='registration',
        persistent=False,
    )
```

- [ ] **Step 2: Commit**

```bash
git add handlers/registration.py
git commit -m "feat: registration conversation handler"
git push
```

---

### Task 8: Housing Handler

**Files:**
- Create: `handlers/housing.py`

- [ ] **Step 1: Create handlers/housing.py**

```python
# handlers/housing.py
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode

import db
import utils
from strings import t


async def handle_housing_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    participant = db.get_participant(chat_id)
    lang = utils.get_lang(participant)

    if db.is_paused('housing'):
        await query.edit_message_text(t(lang, 'housing_paused'))
        return

    # Check if already reserved
    reservation = db.get_reservation(participant['id'])
    if reservation:
        house = reservation['houses']
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t(lang, 'btn_cancel_reservation'), callback_data='housing_cancel')]
        ])
        await query.edit_message_text(
            t(lang, 'current_reservation', name=house['name'], address=house.get('address', '—')),
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, 'btn_housing_yes'), callback_data='housing_yes')],
        [InlineKeyboardButton(t(lang, 'btn_housing_no'), callback_data='housing_no')],
    ])
    await query.edit_message_text(t(lang, 'housing_prompt'), reply_markup=keyboard)


async def handle_housing_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    participant = db.get_participant(update.effective_chat.id)
    lang = utils.get_lang(participant)
    await query.edit_message_text(t(lang, 'no_housing_needed'))


async def handle_housing_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    participant = db.get_participant(chat_id)
    lang = utils.get_lang(participant)
    gender = participant.get('gender', 'M')

    houses = db.get_houses_for_gender(gender)
    if not houses:
        await query.edit_message_text(t(lang, 'no_houses_available'))
        return

    buttons = []
    for house in houses:
        taken = db.get_house_occupancy(house['id'])
        label = utils.format_house_button(house, taken)
        buttons.append([InlineKeyboardButton(label, callback_data=f"house_{house['id']}")])

    await query.edit_message_text(
        t(lang, 'housing_list_header'),
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def handle_house_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    participant = db.get_participant(chat_id)
    lang = utils.get_lang(participant)

    house_id = query.data.replace('house_', '')
    house = db.get_house_by_id(house_id)
    if not house:
        await query.edit_message_text(t(lang, 'error_generic'))
        return

    taken = db.get_house_occupancy(house_id)
    if taken >= house['capacity']:
        await query.edit_message_text(t(lang, 'house_full_msg'))
        return

    context.user_data['pending_house_id'] = house_id

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, 'btn_confirm_yes'), callback_data=f'houseconfirm_{house_id}')],
        [InlineKeyboardButton(t(lang, 'btn_confirm_no'), callback_data='menu_housing')],
    ])
    await query.edit_message_text(
        t(lang, 'house_confirm', name=house['name'], address=house.get('address', '—')),
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_house_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    participant = db.get_participant(chat_id)
    lang = utils.get_lang(participant)

    house_id = query.data.replace('houseconfirm_', '')
    house = db.get_house_by_id(house_id)

    # Double-check capacity (race condition guard)
    taken = db.get_house_occupancy(house_id)
    if taken >= house['capacity']:
        await query.edit_message_text(t(lang, 'house_full_msg'))
        return

    db.create_reservation(house_id, participant['id'])
    notes = house.get('notes') or ''
    await query.edit_message_text(
        t(lang, 'house_reserved',
          name=house['name'],
          address=house.get('address', '—'),
          notes=notes),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_cancel_reservation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    participant = db.get_participant(update.effective_chat.id)
    lang = utils.get_lang(participant)

    db.delete_reservation(participant['id'])
    await query.edit_message_text(t(lang, 'reservation_cancelled'))


def get_housing_handlers() -> list:
    return [
        CallbackQueryHandler(handle_housing_menu,      pattern='^menu_housing$'),
        CallbackQueryHandler(handle_housing_no,        pattern='^housing_no$'),
        CallbackQueryHandler(handle_housing_yes,       pattern='^housing_yes$'),
        CallbackQueryHandler(handle_house_select,      pattern='^house_[0-9a-f-]+$'),
        CallbackQueryHandler(handle_house_confirm,     pattern='^houseconfirm_[0-9a-f-]+$'),
        CallbackQueryHandler(handle_cancel_reservation,pattern='^housing_cancel$'),
    ]
```

- [ ] **Step 2: Commit**

```bash
git add handlers/housing.py
git commit -m "feat: housing reservation handler"
git push
```

---

### Task 9: Info Handler (Schedule, Venue, Q&A, Coordinators)

**Files:**
- Create: `handlers/info.py`

- [ ] **Step 1: Create handlers/info.py**

```python
# handlers/info.py
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

import db
import utils
from strings import t
from config import QA_RATE_LIMIT, GROUP_CHAT_ID

# In-memory state for "expecting message" (keyed by chat_id)
_awaiting_qa: set[int] = set()
_awaiting_msg: set[int] = set()


async def handle_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    participant = db.get_participant(update.effective_chat.id)
    lang = utils.get_lang(participant)
    text = db.get_setting('schedule_text')
    await query.edit_message_text(text or t(lang, 'no_schedule'), parse_mode=ParseMode.MARKDOWN)


async def handle_venue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    participant = db.get_participant(update.effective_chat.id)
    lang = utils.get_lang(participant)
    text = db.get_setting('venue_text')
    await query.edit_message_text(text or t(lang, 'no_venue'), parse_mode=ParseMode.MARKDOWN)


async def handle_qa_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    participant = db.get_participant(chat_id)
    lang = utils.get_lang(participant)

    if db.is_paused('qa'):
        await query.edit_message_text(t(lang, 'qa_paused'))
        return

    count = db.count_questions_by_participant(participant['id'])
    if count >= QA_RATE_LIMIT:
        await query.edit_message_text(t(lang, 'qa_rate_limited', limit=QA_RATE_LIMIT))
        return

    _awaiting_qa.add(chat_id)
    await query.edit_message_text(t(lang, 'qa_prompt'))


async def handle_coordinator_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    participant = db.get_participant(chat_id)
    lang = utils.get_lang(participant)

    if db.is_paused('messages'):
        await query.edit_message_text(t(lang, 'messages_paused'))
        return

    _awaiting_msg.add(chat_id)
    await query.edit_message_text(t(lang, 'coordinator_prompt'))


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catches free-text from users who are in QA or coordinator message flow."""
    chat_id = update.effective_chat.id
    participant = db.get_participant(chat_id)
    lang = utils.get_lang(participant)
    text = update.message.text.strip()

    if chat_id in _awaiting_qa:
        _awaiting_qa.discard(chat_id)
        db.save_question(participant['id'], text)
        await update.message.reply_text(t(lang, 'qa_submitted'))
        # Forward to admin group
        if GROUP_CHAT_ID:
            name = participant.get('full_name', 'Unknown')
            await context.bot.send_message(
                GROUP_CHAT_ID,
                f"❓ *Question from {name}*\n\n{text}",
                parse_mode=ParseMode.MARKDOWN
            )
        return

    if chat_id in _awaiting_msg:
        _awaiting_msg.discard(chat_id)
        db.save_message(participant['id'], text)
        await update.message.reply_text(t(lang, 'coordinator_submitted'))
        # Forward to coordinator channel
        coord_channel = db.get_setting('coord_channel_id')
        target = int(coord_channel) if coord_channel else GROUP_CHAT_ID
        if target:
            name = participant.get('full_name', 'Unknown')
            await context.bot.send_message(
                target,
                f"📨 *Message from {name}*\n\n{text}",
                parse_mode=ParseMode.MARKDOWN
            )
        return


def get_info_handlers() -> list:
    return [
        CallbackQueryHandler(handle_schedule,          pattern='^menu_schedule$'),
        CallbackQueryHandler(handle_venue,             pattern='^menu_venue$'),
        CallbackQueryHandler(handle_qa_start,          pattern='^menu_qa$'),
        CallbackQueryHandler(handle_coordinator_start, pattern='^menu_coordinator$'),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input),
    ]
```

- [ ] **Step 2: Commit**

```bash
git add handlers/info.py
git commit -m "feat: info handler (schedule, venue, Q&A, coordinators)"
git push
```

---

### Task 10: Admin Handler

**Files:**
- Create: `handlers/admin.py`

- [ ] **Step 1: Create handlers/admin.py**

```python
# handlers/admin.py
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from telegram.constants import ParseMode

import db
import utils
from strings import t
from config import OWNER_ID, GROUP_CHAT_ID

# State for deny flow
_deny_pending: dict[int, int] = {}   # admin_chat_id → target_chat_id
# State for setschedule/setvenue
_setting_field: dict[int, str] = {}  # admin_chat_id → field name
# Nuke confirmation steps
_nuke_step: dict[int, int] = {}      # admin_chat_id → step (1 or 2)
# Confirmremove pending
_remove_pending: dict[int, str] = {} # admin_chat_id → house_name


def _require_admin(func):
    """Decorator: block non-admins from commands."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not utils.is_admin(chat_id):
            await update.message.reply_text(t('en', 'no_permission'))
            return
        return await func(update, context)
    return wrapper


def _require_owner(func):
    """Decorator: block non-owners from commands."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.id != OWNER_ID:
            await update.message.reply_text(t('en', 'no_permission'))
            return
        return await func(update, context)
    return wrapper


# ─── Registration review ───────────────────────────────────────────────────────

@_require_admin
async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = db.get_participants_by_status('pending_approval')
    if not pending:
        await update.message.reply_text(t('en', 'admin_no_pending'))
        return

    text = t('en', 'admin_pending_header', count=len(pending))
    for p in pending:
        uname = p.get('username') or '—'
        gender_label = 'M' if p.get('gender') == 'M' else 'F'
        text += t('en', 'admin_pending_entry',
                  name=p.get('full_name', '?'),
                  age=p.get('age', '?'),
                  gender=gender_label,
                  username=uname)
        text += f"`/approve {p['chat_id']}` | `/deny {p['chat_id']} reason` | `/viewreceipt {p['chat_id']}`\n\n"

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


@_require_admin
async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /approve <chat_id>")
        return
    target_id = int(context.args[0])
    participant = db.get_participant(target_id)
    if not participant:
        await update.message.reply_text(t('en', 'admin_user_not_found'))
        return
    db.update_participant(target_id, {'status': 'approved'})
    lang = utils.get_lang(participant)
    await context.bot.send_message(target_id, t(lang, 'approved_welcome'), parse_mode=ParseMode.MARKDOWN)
    await update.message.reply_text(t('en', 'admin_approved', name=participant.get('full_name', str(target_id))))


@_require_admin
async def cmd_deny(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /deny <chat_id> <reason>")
        return
    target_id = int(context.args[0])
    reason = ' '.join(context.args[1:])
    participant = db.get_participant(target_id)
    if not participant:
        await update.message.reply_text(t('en', 'admin_user_not_found'))
        return
    db.update_participant(target_id, {'status': 'denied', 'denial_reason': reason})
    lang = utils.get_lang(participant)
    await context.bot.send_message(
        target_id,
        t(lang, 'denied_notification', reason=reason),
        parse_mode=ParseMode.MARKDOWN
    )
    await update.message.reply_text(t('en', 'admin_denied', name=participant.get('full_name', str(target_id))))


@_require_admin
async def cmd_viewreceipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /viewreceipt <chat_id>")
        return
    target_id = int(context.args[0])
    participant = db.get_participant(target_id)
    if not participant:
        await update.message.reply_text(t('en', 'admin_user_not_found'))
        return
    receipt = db.get_latest_receipt(participant['id'])
    if not receipt:
        await update.message.reply_text("No receipt found for this user.")
        return
    await context.bot.send_photo(update.effective_chat.id, receipt['file_id'],
                                  caption=f"Receipt for {participant.get('full_name', target_id)}")


@_require_admin
async def cmd_participants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_p = db.get_all_participants()
    if not all_p:
        await update.message.reply_text(t('en', 'admin_no_participants'))
        return
    lines = []
    for p in all_p:
        status = p.get('status', '')
        icon = {'approved': '✅', 'pending_approval': '⏳', 'pending_payment': '💳',
                'denied': '❌', 'incomplete': '🔘'}.get(status, '❓')
        name = p.get('full_name', '?')
        uname = f"@{p['username']}" if p.get('username') else f"ID:{p['chat_id']}"
        lines.append(f"{icon} {name} ({uname})")
    await update.message.reply_text('\n'.join(lines))


# ─── Housing management ────────────────────────────────────────────────────────

@_require_admin
async def cmd_addhouse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Usage: /addhouse <name> <M|F> <capacity> [address]
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("Usage: /addhouse <name> <M|F> <capacity> [address]")
        return
    name = args[0]
    gender = args[1].upper()
    if gender not in ('M', 'F'):
        await update.message.reply_text("Gender must be M or F.")
        return
    try:
        capacity = int(args[2])
    except ValueError:
        await update.message.reply_text("Capacity must be a number.")
        return
    address = ' '.join(args[3:]) if len(args) > 3 else ''

    if db.get_house_by_name(name):
        await update.message.reply_text(t('en', 'admin_house_exists', name=name), parse_mode=ParseMode.MARKDOWN)
        return

    db.add_house(name, gender, capacity, address)
    await update.message.reply_text(
        t('en', 'admin_house_added', name=name, gender=gender, capacity=capacity),
        parse_mode=ParseMode.MARKDOWN
    )


@_require_admin
async def cmd_removehouse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /removehouse <name>")
        return
    name = ' '.join(context.args)
    house = db.get_house_by_name(name)
    if not house:
        await update.message.reply_text(t('en', 'admin_house_not_found', name=name), parse_mode=ParseMode.MARKDOWN)
        return
    count = db.get_house_reservation_count(house['id'])
    if count > 0:
        _remove_pending[update.effective_chat.id] = name
        await update.message.reply_text(
            t('en', 'admin_house_occupied', name=name, count=count),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    db.remove_house(house['id'])
    await update.message.reply_text(t('en', 'admin_house_removed', name=name), parse_mode=ParseMode.MARKDOWN)


@_require_admin
async def cmd_confirmremove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_chat.id
    name = _remove_pending.pop(admin_id, None)
    if not name:
        await update.message.reply_text("No pending house removal.")
        return
    house = db.get_house_by_name(name)
    if house:
        db.remove_house(house['id'])
    await update.message.reply_text(t('en', 'admin_house_removed', name=name), parse_mode=ParseMode.MARKDOWN)


@_require_admin
async def cmd_listhouses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    houses = db.get_all_houses()
    if not houses:
        await update.message.reply_text("No houses configured.")
        return
    lines = []
    for h in houses:
        taken = db.get_house_occupancy(h['id'])
        gender_label = '♂️' if h['gender'] == 'M' else '♀️'
        lines.append(f"{gender_label} *{h['name']}* — {taken}/{h['capacity']} | {h.get('address', '—')}")
    await update.message.reply_text(
        t('en', 'admin_houses_list', list='\n'.join(lines)),
        parse_mode=ParseMode.MARKDOWN
    )


@_require_admin
async def cmd_moveresident(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Usage: /moveresident <chat_id> <house_name>
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /moveresident <chat_id> <house_name>")
        return
    target_id = int(context.args[0])
    house_name = ' '.join(context.args[1:])

    participant = db.get_participant(target_id)
    if not participant:
        await update.message.reply_text(t('en', 'admin_user_not_found'))
        return

    house = db.get_house_by_name(house_name)
    if not house:
        await update.message.reply_text(t('en', 'admin_house_not_found', name=house_name), parse_mode=ParseMode.MARKDOWN)
        return

    existing = db.get_reservation(participant['id'])
    if existing:
        db.move_reservation(participant['id'], house['id'])
    else:
        db.create_reservation(house['id'], participant['id'])

    name = participant.get('full_name', str(target_id))
    await update.message.reply_text(
        t('en', 'admin_resident_moved', user=name, house=house_name),
        parse_mode=ParseMode.MARKDOWN
    )


# ─── Bot management ────────────────────────────────────────────────────────────

@_require_admin
async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    text = ' '.join(context.args)
    approved = db.get_participants_by_status('approved')
    count = 0
    for p in approved:
        try:
            lang = utils.get_lang(p)
            await context.bot.send_message(p['chat_id'], text)
            count += 1
        except Exception:
            pass
    await update.message.reply_text(t('en', 'admin_broadcast_sent', count=count))


@_require_admin
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    counts = db.count_participants_by_status()
    housed = db.count_housed_participants()
    await update.message.reply_text(
        t('en', 'admin_status',
          total=counts['total'],
          approved=counts['approved'],
          pending=counts['pending'],
          denied=counts['denied'],
          housed=housed),
        parse_mode=ParseMode.MARKDOWN
    )


@_require_admin
async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /pause <housing|qa|messages>")
        return
    feature = context.args[0]
    db.set_setting(f'{feature}_paused', 'true')
    await update.message.reply_text(t('en', 'admin_feature_paused', feature=feature))


@_require_admin
async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /resume <housing|qa|messages>")
        return
    feature = context.args[0]
    db.set_setting(f'{feature}_paused', 'false')
    await update.message.reply_text(t('en', 'admin_feature_resumed', feature=feature))


@_require_admin
async def cmd_setschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _setting_field[update.effective_chat.id] = 'schedule'
    await update.message.reply_text(t('en', 'admin_set_prompt', field='schedule'))


@_require_admin
async def cmd_setvenue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _setting_field[update.effective_chat.id] = 'venue'
    await update.message.reply_text(t('en', 'admin_set_prompt', field='venue'))


async def handle_setting_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_chat.id
    field = _setting_field.pop(admin_id, None)
    if not field:
        return  # not in a setting flow — handled by info handler
    text = update.message.text
    if field == 'schedule':
        db.set_setting('schedule_text', text)
        await update.message.reply_text(t('en', 'admin_schedule_set'))
    elif field == 'venue':
        db.set_setting('venue_text', text)
        await update.message.reply_text(t('en', 'admin_venue_set'))


@_require_owner
async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /addadmin <chat_id>")
        return
    new_id = int(context.args[0])
    existing = db.get_admin_ids_from_db()
    if new_id not in existing:
        existing.append(new_id)
        db.set_setting('admin_ids', ','.join(str(x) for x in existing))
    await update.message.reply_text(t('en', 'admin_added', chat_id=new_id))


@_require_owner
async def cmd_removeuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /removeuser <chat_id>")
        return
    target_id = int(context.args[0])
    db.delete_participant(target_id)
    await update.message.reply_text(t('en', 'admin_user_removed'))


@_require_owner
async def cmd_nuke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _nuke_step[update.effective_chat.id] = 1
    await update.message.reply_text(t('en', 'admin_nuke_confirm1'))


@_require_owner
async def cmd_nuke2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _nuke_step.get(update.effective_chat.id) != 1:
        return
    _nuke_step[update.effective_chat.id] = 2
    await update.message.reply_text(t('en', 'admin_nuke_confirm2'))


@_require_owner
async def cmd_nuke3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _nuke_step.get(update.effective_chat.id) != 2:
        return
    _nuke_step.pop(update.effective_chat.id, None)
    db.delete_all_participants()
    await update.message.reply_text(t('en', 'admin_nuked'))


def get_admin_handlers() -> list:
    return [
        CommandHandler('pending',       cmd_pending),
        CommandHandler('approve',       cmd_approve),
        CommandHandler('deny',          cmd_deny),
        CommandHandler('viewreceipt',   cmd_viewreceipt),
        CommandHandler('participants',  cmd_participants),
        CommandHandler('addhouse',      cmd_addhouse),
        CommandHandler('removehouse',   cmd_removehouse),
        CommandHandler('confirmremove', cmd_confirmremove),
        CommandHandler('listhouses',    cmd_listhouses),
        CommandHandler('moveresident',  cmd_moveresident),
        CommandHandler('broadcast',     cmd_broadcast),
        CommandHandler('status',        cmd_status),
        CommandHandler('pause',         cmd_pause),
        CommandHandler('resume',        cmd_resume),
        CommandHandler('setschedule',   cmd_setschedule),
        CommandHandler('setvenue',      cmd_setvenue),
        CommandHandler('addadmin',      cmd_addadmin),
        CommandHandler('removeuser',    cmd_removeuser),
        CommandHandler('nuke',          cmd_nuke),
        CommandHandler('nuke2',         cmd_nuke2),
        CommandHandler('nuke3',         cmd_nuke3),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_setting_input),
    ]
```

- [ ] **Step 2: Commit**

```bash
git add handlers/admin.py
git commit -m "feat: admin handler"
git push
```

---

### Task 11: bot.py — Flask Webhook Entry Point

**Files:**
- Create: `bot.py`

- [ ] **Step 1: Create bot.py**

```python
# bot.py
import asyncio
import threading
import logging
import json

from flask import Flask, request, abort
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config import BOT_TOKEN, WEBHOOK_URL
from handlers.registration import build_registration_handler, menu_command
from handlers.housing import get_housing_handlers
from handlers.info import get_info_handlers
from handlers.admin import get_admin_handlers

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Flask app ────────────────────────────────────────────────────────────────
flask_app = Flask(__name__)

# ─── Async loop in background thread ─────────────────────────────────────────
loop = asyncio.new_event_loop()

def _start_loop(lp):
    asyncio.set_event_loop(lp)
    lp.run_forever()

threading.Thread(target=_start_loop, args=(loop,), daemon=True).start()


def run_async(coro):
    """Submit a coroutine to the background loop and wait for the result."""
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=60)


# ─── PTB Application ──────────────────────────────────────────────────────────
ptb_app = Application.builder().token(BOT_TOKEN).build()

# Register handlers
ptb_app.add_handler(build_registration_handler())
ptb_app.add_handler(CommandHandler('menu', menu_command))

for handler in get_housing_handlers():
    ptb_app.add_handler(handler)

for handler in get_info_handlers():
    ptb_app.add_handler(handler)

for handler in get_admin_handlers():
    ptb_app.add_handler(handler)

# Initialize PTB
run_async(ptb_app.initialize())

# Register webhook
WEBHOOK_SECRET = BOT_TOKEN.split(':')[0]  # use token prefix as secret
run_async(ptb_app.bot.set_webhook(
    url=f"{WEBHOOK_URL}/webhook",
    secret_token=WEBHOOK_SECRET,
    allowed_updates=['message', 'callback_query'],
))
logger.info(f"Webhook set to {WEBHOOK_URL}/webhook")


# ─── Webhook endpoint ─────────────────────────────────────────────────────────
@flask_app.route('/webhook', methods=['POST'])
def webhook():
    secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    if secret != WEBHOOK_SECRET:
        abort(403)
    data = request.get_json(force=True)
    update = Update.de_json(data, ptb_app.bot)
    run_async(ptb_app.process_update(update))
    return 'ok', 200


@flask_app.route('/health', methods=['GET'])
def health():
    return 'ok', 200


if __name__ == '__main__':
    flask_app.run(host='0.0.0.0', port=8080)
```

- [ ] **Step 2: Install all dependencies**

```bash
pip install -r requirements.txt
```

- [ ] **Step 3: Smoke-test import (no .env needed yet)**

```bash
python -c "import ast, sys; ast.parse(open('bot.py').read()); print('Syntax OK')"
python -c "import ast, sys; ast.parse(open('handlers/registration.py').read()); print('Syntax OK')"
python -c "import ast, sys; ast.parse(open('handlers/housing.py').read()); print('Syntax OK')"
python -c "import ast, sys; ast.parse(open('handlers/info.py').read()); print('Syntax OK')"
python -c "import ast, sys; ast.parse(open('handlers/admin.py').read()); print('Syntax OK')"
```

Expected: `Syntax OK` for each.

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS (strings, db mocks, utils).

- [ ] **Step 5: Commit**

```bash
git add bot.py
git commit -m "feat: Flask webhook entry point and handler wiring"
git push
```

---

### Task 12: Environment Setup + Render Deploy

**Files:**
- Create: `.env` (local only, gitignored)

- [ ] **Step 1: Create local .env for testing**

Create `/Users/ludwig/Projects/conferencebot2/.env`:

```
BOT_TOKEN=8516640247:AAEadqO01_2Px_CD68FUbGfHzHYs9VMU0Gc
SUPABASE_URL=https://wtgbmcmrfaelvdtwdbwt.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0Z2JtY21yZmFlbHZkdHdkYnd0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTY1MzY4MywiZXhwIjoyMDk1MjI5NjgzfQ.hWu7msVmfdJetR6l8BKvIt6479rBzmPuhYxbWpgGh8U
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0Z2JtY21yZmFlbHZkdHdkYnd0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk2NTM2ODMsImV4cCI6MjA5NTIyOTY4M30.5y-DTZ-Z-3UqCuRCaKNAyfpNsLzIv6RX9UgpeWg9Mds
WEBHOOK_URL=https://conferencebot2.onrender.com
GROUP_CHAT_ID=0
PAYMENT_LINK=PAYMENT_LINK_PLACEHOLDER
```

- [ ] **Step 2: Test local startup with env**

```bash
cd /Users/ludwig/Projects/conferencebot2
export $(cat .env | xargs) && python bot.py
```

Expected: Flask starts on port 8080, webhook registration logged. (Webhook call will fail since Render URL isn't live yet — that's OK.)

- [ ] **Step 3: Deploy to Render**

1. Go to https://render.com → New → Web Service
2. Connect GitHub repo `Yogurt43/conferencebot2`
3. Set:
   - **Runtime:** Python
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `python bot.py`
4. Add all environment variables from `.env` above
5. Set `WEBHOOK_URL` to the Render-assigned URL (e.g. `https://conferencebot2.onrender.com`)
6. Deploy

- [ ] **Step 4: Verify deployment**

```bash
curl https://conferencebot2.onrender.com/health
```

Expected: `ok`

- [ ] **Step 5: Test bot end-to-end**

Open Telegram → find the bot → send `/start` → confirm language selection appears.

- [ ] **Step 6: Final commit + tag**

```bash
git tag v0.1.0
git push --tags
```

---

## Summary

| Task | What it delivers |
|------|-----------------|
| 1 | GitHub repo, folder structure, Render config |
| 2 | Supabase schema (7 tables) |
| 3 | `config.py` — all env vars and constants |
| 4 | `strings.py` — complete EN/UK string dictionary + tests |
| 5 | `db.py` — Supabase query layer + tests |
| 6 | `utils.py` — pure helpers + tests |
| 7 | Registration ConversationHandler (lang→name→age→gender→phone→payment→receipt) |
| 8 | Housing reservation handler (browse, reserve, cancel, capacity guard) |
| 9 | Info handler (schedule, venue, Q&A, coordinators) |
| 10 | Admin handler (review queue, housing mgmt, broadcasts, toggles, nuke) |
| 11 | `bot.py` — Flask webhook, PTB wiring |
| 12 | Render deploy + end-to-end smoke test |
