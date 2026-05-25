# tests/conftest.py
import os
os.environ.setdefault('BOT_TOKEN', 'test:token')
os.environ.setdefault('SUPABASE_URL', 'https://test.supabase.co')
os.environ.setdefault('SUPABASE_SERVICE_KEY', 'test_service_key')
os.environ.setdefault('SUPABASE_ANON_KEY', 'test_anon_key')
os.environ.setdefault('WEBHOOK_URL', 'https://test.example.com')
