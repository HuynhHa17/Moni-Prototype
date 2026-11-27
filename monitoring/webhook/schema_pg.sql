CREATE TABLE IF NOT EXISTS episodes (
    id                BIGSERIAL PRIMARY KEY,
    fingerprint       TEXT        NOT NULL,
    starts_at         TIMESTAMPTZ NOT NULL,
    alertname         TEXT        NOT NULL,
    host              TEXT,
    service           TEXT,
    severity          TEXT,
    labels_json       JSONB       NOT NULL,
    annotations_json  JSONB,
    status            TEXT        NOT NULL CHECK (status IN ('firing', 'resolved')),
    ends_at           TIMESTAMPTZ,
    missing_firing    INTEGER     NOT NULL DEFAULT 0 CHECK (missing_firing IN (0, 1)),
    first_received_at TIMESTAMPTZ NOT NULL,
    last_received_at  TIMESTAMPTZ NOT NULL,
    UNIQUE (fingerprint, starts_at)
);

CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL   PRIMARY KEY,
    episode_id  BIGINT      NOT NULL REFERENCES episodes (id),
    status      TEXT        NOT NULL CHECK (status IN ('firing', 'resolved')),
    ends_at     TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL,
    group_key   TEXT,
    outcome     TEXT        NOT NULL CHECK (outcome IN (
                    'new', 'repeat', 'resolve',
                    'resolved_repeat', 'resolved_without_firing', 'late_firing'))
);

CREATE INDEX IF NOT EXISTS idx_events_episode   ON events (episode_id);
CREATE INDEX IF NOT EXISTS idx_episodes_status  ON episodes (status);
CREATE INDEX IF NOT EXISTS idx_episodes_host    ON episodes (host, starts_at);

