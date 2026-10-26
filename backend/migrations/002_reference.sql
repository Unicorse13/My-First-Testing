-- S-02-inspired versioned schedule setup. No official rates or UCC templates are supplied.
CREATE TABLE fee_schedules (
    id INTEGER PRIMARY KEY,
    municipality_id INTEGER NOT NULL REFERENCES municipalities(id),
    subcode TEXT NOT NULL CHECK(subcode IN ('building','electrical','elevator','fire_protection','plumbing')),
    use_group TEXT NOT NULL DEFAULT '' CHECK(subcode='building' OR use_group=''),
    effective_date TEXT NOT NULL,
    min_fee_cents INTEGER NOT NULL DEFAULT 0 CHECK(min_fee_cents>=0),
    max_fee_cents INTEGER CHECK(max_fee_cents IS NULL OR max_fee_cents>=min_fee_cents),
    ordinance_citation TEXT NOT NULL CHECK(length(ordinance_citation)>=3),
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','active')),
    copied_from_id INTEGER REFERENCES fee_schedules(id),
    created_at TEXT NOT NULL,
    activated_at TEXT,
    UNIQUE(municipality_id,subcode,use_group,effective_date)
);
CREATE TABLE fee_schedule_items (
    id INTEGER PRIMARY KEY,
    schedule_id INTEGER NOT NULL REFERENCES fee_schedules(id),
    position INTEGER NOT NULL CHECK(position>0),
    description TEXT NOT NULL CHECK(length(description)>=2),
    basis TEXT NOT NULL CHECK(basis IN ('fixed','per_unit')),
    amount_cents INTEGER NOT NULL CHECK(amount_cents>=0),
    minimum_cents INTEGER NOT NULL DEFAULT 0 CHECK(minimum_cents>=0),
    UNIQUE(schedule_id,position)
);
CREATE INDEX fee_schedule_effective ON fee_schedules(municipality_id,subcode,use_group,status,effective_date);
CREATE TRIGGER fee_schedule_active_immutable BEFORE UPDATE ON fee_schedules
WHEN OLD.status='active'
BEGIN SELECT RAISE(ABORT,'Activated fee schedules are immutable. Copy to a new effective date.'); END;
CREATE TRIGGER fee_schedule_active_delete BEFORE DELETE ON fee_schedules
WHEN OLD.status='active'
BEGIN SELECT RAISE(ABORT,'Activated fee schedules are retained.'); END;
CREATE TRIGGER fee_item_active_insert BEFORE INSERT ON fee_schedule_items
WHEN (SELECT status FROM fee_schedules WHERE id=NEW.schedule_id)='active'
BEGIN SELECT RAISE(ABORT,'Activated fee schedule items are immutable.'); END;
CREATE TRIGGER fee_item_active_update BEFORE UPDATE ON fee_schedule_items
WHEN (SELECT status FROM fee_schedules WHERE id=OLD.schedule_id)='active'
 OR (SELECT status FROM fee_schedules WHERE id=NEW.schedule_id)='active'
BEGIN SELECT RAISE(ABORT,'Activated fee schedule items are immutable.'); END;
CREATE TRIGGER fee_item_active_delete BEFORE DELETE ON fee_schedule_items
WHEN (SELECT status FROM fee_schedules WHERE id=OLD.schedule_id)='active'
BEGIN SELECT RAISE(ABORT,'Activated fee schedule items are immutable.'); END;
