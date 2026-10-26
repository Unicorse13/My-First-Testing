CREATE TABLE status_overrides(
 municipality_id INTEGER NOT NULL REFERENCES municipalities(id),
 code TEXT NOT NULL REFERENCES statuses(code),
 label TEXT NOT NULL,
 next_statuses TEXT NOT NULL CHECK(json_valid(next_statuses)),
 PRIMARY KEY(municipality_id,code)
);
ALTER TABLE permits ADD COLUMN use_group TEXT NOT NULL DEFAULT '';
ALTER TABLE permits ADD COLUMN assessed_schedule_id INTEGER REFERENCES fee_schedules(id);
INSERT OR IGNORE INTO permit_types VALUES('elevator','Elevator (configure fee schedule)',0,0);
INSERT OR IGNORE INTO permit_types VALUES('fire_protection','Fire Protection (configure fee schedule)',0,0);
