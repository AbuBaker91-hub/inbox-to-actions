-- inbox-to-actions project tables (core tables come from aiforge-core)

CREATE TABLE IF NOT EXISTS emails (
    id          serial PRIMARY KEY,
    message_id  text UNIQUE NOT NULL,
    subject     text NOT NULL DEFAULT '',
    sender      text NOT NULL DEFAULT '',
    received_at timestamptz,
    body_text   text NOT NULL DEFAULT '',
    status      text NOT NULL DEFAULT 'new'  -- new | written | review | skipped | error
);

CREATE TABLE IF NOT EXISTS attachments (
    id       serial PRIMARY KEY,
    email_id integer NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    filename text NOT NULL,
    text     text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS extractions (
    id             serial PRIMARY KEY,
    email_id       integer NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    category       text NOT NULL,
    confidence     double precision NOT NULL DEFAULT 0,
    payload_json   jsonb NOT NULL DEFAULT '{}'::jsonb,
    prompt_version text NOT NULL DEFAULT '',
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS review_queue (
    id            serial PRIMARY KEY,
    extraction_id integer NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
    reason        text NOT NULL,
    status        text NOT NULL DEFAULT 'pending',  -- pending | approved | rejected
    decided_at    timestamptz
);

CREATE TABLE IF NOT EXISTS contacts (
    id              serial PRIMARY KEY,
    email           text UNIQUE NOT NULL,
    name            text,
    phone           text,
    source_email_id integer REFERENCES emails(id)
);

CREATE TABLE IF NOT EXISTS deals (
    id             serial PRIMARY KEY,
    contact_id     integer REFERENCES contacts(id),
    reference      text UNIQUE NOT NULL,
    amount         numeric,
    stage          text NOT NULL DEFAULT 'new',
    key_dates_json jsonb
);

CREATE TABLE IF NOT EXISTS activities (
    id         serial PRIMARY KEY,
    contact_id integer REFERENCES contacts(id),
    deal_id    integer REFERENCES deals(id),
    kind       text NOT NULL,
    note       text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now()
);
