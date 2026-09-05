-- A number to text when a call needs the customer.
--
-- Escalation could reach nobody on the deployment as shipped: it wanted a
-- SendGrid key, whose free tier ended in May 2025, or a WhatsApp sender, which
-- needs Meta Business verification. SMS needs neither - it goes out from the
-- Twilio number that already places the calls - so the profile gains somewhere
-- to put the number.
--
-- Nullable, and it falls back to `phone` and then to the WhatsApp number in
-- app/services/notify.py, so an existing account needs no migration of its own.

alter table public.profiles
    add column if not exists escalation_sms text;
