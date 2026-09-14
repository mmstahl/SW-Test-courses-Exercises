-- Phone Configurator Simulator — Postgres schema.
-- Ported from the Google Apps Script version's Sheets (see
-- reference-appsscript-version/Phone_Configurator_Simulator_requirements.md §5).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS teachers (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Singleton settings row.
CREATE TABLE IF NOT EXISTS settings (
  id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  level INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 4),
  required_email_domain TEXT NOT NULL DEFAULT '',
  student_reset_enabled BOOLEAN NOT NULL DEFAULT false,
  discount_code_mode TEXT NOT NULL DEFAULT 'normal'
    CHECK (discount_code_mode IN ('normal', 'acceptAny', 'acceptNone')),
  allow_buy_with_partial_config BOOLEAN NOT NULL DEFAULT false,
  return_stays_available_when_empty BOOLEAN NOT NULL DEFAULT false,
  allow_discount_code_reuse BOOLEAN NOT NULL DEFAULT false,
  credit_basis TEXT NOT NULL DEFAULT 'paid' CHECK (credit_basis IN ('paid', 'base')),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS purchases (
  purchase_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_email TEXT NOT NULL,
  purchase_seq INTEGER NOT NULL,
  model TEXT NOT NULL DEFAULT '',
  storage TEXT NOT NULL DEFAULT '',
  color TEXT NOT NULL DEFAULT '',
  network TEXT NOT NULL DEFAULT '',
  accessory TEXT NOT NULL DEFAULT '',
  base_price NUMERIC(10, 2) NOT NULL,
  discount_code_used TEXT NOT NULL DEFAULT '',
  paid_price NUMERIC(10, 2) NOT NULL,
  credit_applied NUMERIC(10, 2) NOT NULL DEFAULT 0,
  requested_payment NUMERIC(10, 2) NOT NULL,
  code_generated TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'Bought' CHECK (status IN ('Bought', 'Returned')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_purchases_email ON purchases (student_email);

-- Codes are always looked up scoped to the owning student, so the natural
-- key is (student_email, code) rather than a synthetic id.
CREATE TABLE IF NOT EXISTS discount_codes (
  student_email TEXT NOT NULL,
  code TEXT NOT NULL,
  generated_by_purchase_id UUID NOT NULL REFERENCES purchases (purchase_id),
  status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Redeemed', 'Disabled')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (student_email, code)
);

CREATE TABLE IF NOT EXISTS store_credit (
  student_email TEXT PRIMARY KEY,
  balance NUMERIC(10, 2) NOT NULL DEFAULT 0
);

-- Append-only audit log. Never written inside the same transaction as the
-- action it records — see lib/actionLog.js for why.
CREATE TABLE IF NOT EXISTS action_log (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  student_email TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL CHECK (action IN ('CalculatePrice', 'Buy', 'Return', 'Reset')),
  parameters TEXT NOT NULL DEFAULT '',
  discount_code TEXT NOT NULL DEFAULT '',
  calculated_price NUMERIC(10, 2),
  credit_before NUMERIC(10, 2),
  credit_after NUMERIC(10, 2),
  result TEXT NOT NULL CHECK (result IN ('Success', 'Failed', 'Error')),
  message TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_action_log_email ON action_log (student_email);
CREATE INDEX IF NOT EXISTS idx_action_log_created_at ON action_log (created_at DESC);
