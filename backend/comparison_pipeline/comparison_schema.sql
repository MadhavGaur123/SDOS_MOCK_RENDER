-- ============================================================
-- HealIN v2 Schema  –  Optimised for PolicyBazaar-style comparison
-- ============================================================
-- Design principles:
--   1. Every comparable field gets its own typed column (not a JSONB blob)
--      so the display layer can just SELECT and render — no JSON drilling.
--   2. One row per policy×plan_variant.  Multi-variant policies (Standard /
--      Exclusive, Silver / Gold) get separate rows in policy_variants; the
--      parent policies table stores only insurer + document metadata.
--   3. Sub-limits and coverage features that are list-shaped (exclusions,
--      waiting periods, feature list) live in child tables with a FK to
--      policy_variants — normalised so the RAG pipeline can index them too.
--   4. All monetary amounts stored in INTEGER (rupees).  Ratios/percentages
--      stored as NUMERIC(6,2).
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ──────────────────────────────────────────────────────────────
-- 1. Insurers
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS insurers (
    insurer_id      BIGSERIAL PRIMARY KEY,
    insurer_name    TEXT UNIQUE NOT NULL,
    irdai_reg       TEXT,
    cin             TEXT,
    helpline        TEXT,
    website         TEXT,
    grievance_email TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ──────────────────────────────────────────────────────────────
-- 2. Policies  (one row per policy document)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS policies (
    policy_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    insurer_id      BIGINT NOT NULL REFERENCES insurers(insurer_id),
    policy_name     TEXT NOT NULL,
    policy_code     TEXT,
    version         TEXT,
    effective_date  DATE,
    policy_type     TEXT,          -- Individual / Family Floater / Individual+Family
    document_type   TEXT,          -- policy_wording / prospectus
    source_file     TEXT,
    extraction_date DATE,
    page_count      INT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_policy UNIQUE (insurer_id, policy_name, policy_code, version)
);

-- ──────────────────────────────────────────────────────────────
-- 3. Policy Variants  (one row per plan / variant within a policy)
--    This is the PRIMARY comparison unit.
--    e.g. Easy Health – Standard, Easy Health – Exclusive,
--         Super Surplus – Silver, Super Surplus – Gold
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS policy_variants (
    variant_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id       UUID NOT NULL REFERENCES policies(policy_id) ON DELETE CASCADE,

    -- ── Identity ──────────────────────────────────────────────
    variant_name    TEXT NOT NULL,          -- 'Standard', 'Exclusive', 'Silver', 'Gold', 'Base'

    -- ── Sum Insured ───────────────────────────────────────────
    si_min_inr      INTEGER,                -- minimum available SI in Rs.
    si_max_inr      INTEGER,                -- maximum available SI in Rs.
    si_options_text TEXT,                   -- human-readable e.g. "1L, 1.5L, 2L … 25L"

    -- ── Core Hospitalisation ──────────────────────────────────
    inpatient_covered           BOOLEAN DEFAULT true,
    inpatient_limit_text        TEXT,       -- "Up to sum insured" / specific cap
    pre_hosp_days               SMALLINT,   -- e.g. 30, 60
    post_hosp_days              SMALLINT,   -- e.g. 60, 90
    daycare_covered             BOOLEAN,
    domiciliary_covered         BOOLEAN,
    domiciliary_min_days        SMALLINT,   -- min days required for domiciliary
    organ_donor_covered         BOOLEAN,
    ayush_covered               BOOLEAN,
    ayush_limit_text            TEXT,

    -- ── Room Rent ─────────────────────────────────────────────
    room_rent_limit_text        TEXT,       -- plain-language limit
    room_rent_type              TEXT,       -- 'percentage_si' | 'fixed_per_day' | 'room_category' | 'no_limit'
    room_rent_pct_si            NUMERIC(5,2), -- if type=percentage_si
    room_rent_fixed_inr         INTEGER,    -- if type=fixed_per_day
    room_rent_category          TEXT,       -- e.g. "Single Private A/C Room"
    icu_covered                 BOOLEAN DEFAULT true,
    icu_limit_text              TEXT,

    -- ── Ambulance ─────────────────────────────────────────────
    ambulance_covered           BOOLEAN,
    ambulance_limit_inr         INTEGER,    -- per hospitalisation
    ambulance_annual_limit_inr  INTEGER,    -- overall annual/policy-period cap
    air_ambulance_covered       BOOLEAN,
    air_ambulance_limit_text    TEXT,

    -- ── Waiting Periods ───────────────────────────────────────
    initial_waiting_days        SMALLINT,   -- usually 30
    ped_waiting_months          SMALLINT,   -- pre-existing disease, usually 36
    specific_disease_waiting_months SMALLINT, -- usually 24
    ped_reducible               BOOLEAN,    -- via portability/migration

    -- ── Deductible / Co-pay ───────────────────────────────────
    has_deductible              BOOLEAN DEFAULT false,
    deductible_text             TEXT,       -- "Per hospitalisation as per schedule"
    has_copay                   BOOLEAN DEFAULT false,
    copay_text                  TEXT,

    -- ── Maternity ─────────────────────────────────────────────
    maternity_covered           BOOLEAN DEFAULT false,
    maternity_normal_inr        INTEGER,
    maternity_caesar_inr        INTEGER,
    maternity_waiting_months    SMALLINT,
    maternity_max_deliveries    SMALLINT,
    newborn_covered             BOOLEAN DEFAULT false,
    newborn_limit_inr           INTEGER,

    -- ── Critical Illness ──────────────────────────────────────
    critical_illness_covered    BOOLEAN DEFAULT false,
    critical_illness_limit_text TEXT,
    critical_illness_waiting_days SMALLINT,

    -- ── Mental Health ─────────────────────────────────────────
    mental_health_covered       BOOLEAN,

    -- ── OPD ───────────────────────────────────────────────────
    opd_covered                 BOOLEAN DEFAULT false,
    opd_limit_text              TEXT,

    -- ── Restoration / Recharge ───────────────────────────────
    restoration_covered         BOOLEAN DEFAULT false,
    restoration_pct             SMALLINT,   -- e.g. 100, 200
    restoration_frequency_text  TEXT,       -- "Once per policy period"
    restoration_same_illness    BOOLEAN,    -- can be used for same illness?
    restoration_limit_text      TEXT,

    -- ── Cumulative / No-Claim Bonus ───────────────────────────
    ncb_covered                 BOOLEAN DEFAULT false,
    ncb_rate_text               TEXT,       -- "10% per year"
    ncb_max_text                TEXT,       -- "up to 100%"
    ncb_on_claim                TEXT,       -- "reduces at same rate" / "reset to 0"

    -- ── Health Checkup ────────────────────────────────────────
    health_checkup_covered      BOOLEAN DEFAULT false,
    health_checkup_limit_text   TEXT,
    health_checkup_frequency    TEXT,       -- "Every 3 years" / "Every 4 claim-free years"

    -- ── Wellness ──────────────────────────────────────────────
    wellness_covered            BOOLEAN DEFAULT false,
    wellness_details_text       TEXT,

    -- ── International Cover ───────────────────────────────────
    international_covered       BOOLEAN DEFAULT false,
    international_details_text  TEXT,

    -- ── Moratorium ────────────────────────────────────────────
    moratorium_months           SMALLINT,   -- usually 60

    -- ── Policy Conditions ─────────────────────────────────────
    free_look_days              SMALLINT,
    grace_period_text           TEXT,       -- "15 days (monthly), 30 days (others)"
    renewal_guaranteed          BOOLEAN,
    portability_available       BOOLEAN,
    cancellation_by_holder_text TEXT,
    territorial_limit           TEXT,       -- "India only"

    -- ── Premium & Discounts ───────────────────────────────────
    premium_modes_text          TEXT,       -- "Monthly, Quarterly, Half-yearly, Annual, 2-year"
    family_discount_text        TEXT,
    long_term_discount_text     TEXT,
    other_discounts_text        TEXT,

    -- ── Claim Process ─────────────────────────────────────────
    cashless_available          BOOLEAN DEFAULT true,
    cashless_notice_planned     TEXT,       -- "48 hours before"
    cashless_notice_emergency   TEXT,       -- "24 hours after"
    cashless_helpline           TEXT,
    reimbursement_available     BOOLEAN DEFAULT true,
    reimbursement_submit_days   SMALLINT,   -- days from discharge to submit docs
    claim_settlement_days       SMALLINT,   -- IRDAI standard / insurer target

    -- ── Metadata ──────────────────────────────────────────────
    created_at  TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT uq_variant UNIQUE (policy_id, variant_name)
);

-- ──────────────────────────────────────────────────────────────
-- 4. Coverage Features  (list-type coverage items per variant)
--    e.g. "Daily Cash for Shared Accommodation", "Recovery Benefit"
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS variant_features (
    feature_id      BIGSERIAL PRIMARY KEY,
    variant_id      UUID NOT NULL REFERENCES policy_variants(variant_id) ON DELETE CASCADE,
    feature_type    TEXT NOT NULL,   -- hospitalization | ambulance | daycare | wellness | etc.
    feature_name    TEXT NOT NULL,
    is_covered      BOOLEAN NOT NULL DEFAULT true,
    limit_text      TEXT,
    details         TEXT,
    notes           TEXT,
    page_number     INT
);
CREATE INDEX IF NOT EXISTS idx_vfeatures_variant ON variant_features(variant_id);

-- ──────────────────────────────────────────────────────────────
-- 5. Sub-limits  (granular caps per variant)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS variant_sublimits (
    sublimit_id     BIGSERIAL PRIMARY KEY,
    variant_id      UUID NOT NULL REFERENCES policy_variants(variant_id) ON DELETE CASCADE,
    limit_category  TEXT NOT NULL,   -- room_rent | ambulance | disease_specific | hospitalization
    item_name       TEXT NOT NULL,
    limit_type      TEXT,            -- fixed_amount | percentage | room_category
    limit_inr       INTEGER,
    limit_pct       NUMERIC(6,2),
    applies_to      TEXT,            -- per_day | per_claim | per_year | per_delivery | per_block
    description     TEXT,
    page_number     INT
);
CREATE INDEX IF NOT EXISTS idx_vsublimits_variant ON variant_sublimits(variant_id);

-- ──────────────────────────────────────────────────────────────
-- 6. Waiting Periods  (detailed, per variant)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS variant_waiting_periods (
    wp_id               BIGSERIAL PRIMARY KEY,
    variant_id          UUID NOT NULL REFERENCES policy_variants(variant_id) ON DELETE CASCADE,
    period_type         TEXT NOT NULL,  -- initial | pre_existing | specific_disease | maternity | critical_illness
    disease_or_procedure TEXT,
    duration_days       SMALLINT,
    can_be_reduced      BOOLEAN,
    reduction_conditions TEXT,
    page_number         INT
);
CREATE INDEX IF NOT EXISTS idx_vwp_variant ON variant_waiting_periods(variant_id);

-- ──────────────────────────────────────────────────────────────
-- 7. Exclusions  (per variant)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS variant_exclusions (
    exclusion_id        BIGSERIAL PRIMARY KEY,
    variant_id          UUID NOT NULL REFERENCES policy_variants(variant_id) ON DELETE CASCADE,
    exclusion_category  TEXT,           -- standard | specific
    exclusion_name      TEXT NOT NULL,
    description         TEXT,
    exception_conditions TEXT,
    page_number         INT
);
CREATE INDEX IF NOT EXISTS idx_vexcl_variant ON variant_exclusions(variant_id);

-- ──────────────────────────────────────────────────────────────
-- 8. Non-payable Items  (per policy, not per variant — same across variants)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS policy_non_payable (
    np_id       BIGSERIAL PRIMARY KEY,
    policy_id   UUID NOT NULL REFERENCES policies(policy_id) ON DELETE CASCADE,
    category    TEXT,   -- list_1 | subsumed_room | subsumed_procedure | subsumed_treatment
    item_name   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_np_policy ON policy_non_payable(policy_id);

-- ──────────────────────────────────────────────────────────────
-- 9. RAG chunks (unchanged from v1 — stays compatible)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS policy_chunks (
    chunk_uid    TEXT PRIMARY KEY,
    policy_id    UUID REFERENCES policies(policy_id) ON DELETE CASCADE,
    variant_id   UUID REFERENCES policy_variants(variant_id) ON DELETE SET NULL,
    source_section TEXT,
    chunk_text   TEXT NOT NULL,
    page_number  INT,
    metadata     JSONB DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chunks_policy  ON policy_chunks(policy_id);
CREATE INDEX IF NOT EXISTS idx_chunks_variant ON policy_chunks(variant_id);
