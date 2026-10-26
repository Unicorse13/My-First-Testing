-- Financial records are append-only, except reconciliation confirmation.
CREATE TRIGGER payment_no_financial_update BEFORE UPDATE OF permit_id,amount_cents,method,reference,idempotency_key,request_hash,created_at ON payments BEGIN SELECT RAISE(ABORT,'Financial records are immutable'); END;
CREATE TRIGGER payment_no_delete BEFORE DELETE ON payments BEGIN SELECT RAISE(ABORT,'Financial records are immutable'); END;
CREATE TRIGGER payment_reconciliation_forward BEFORE UPDATE OF reconciled ON payments WHEN OLD.reconciled=1 AND NEW.reconciled=0 BEGIN SELECT RAISE(ABORT,'Reconciliation cannot be undone'); END;
CREATE TRIGGER review_tenant_insert BEFORE INSERT ON plan_reviews BEGIN
SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM users u JOIN permits p ON p.municipality_id=u.municipality_id WHERE p.id=NEW.permit_id AND u.id=NEW.reviewer_id AND u.role IN ('admin','reviewer')) THEN RAISE(ABORT,'Reviewer municipality or role mismatch') END;
END;
CREATE TRIGGER inspection_tenant_insert BEFORE INSERT ON inspections BEGIN
SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM users u JOIN permits p ON p.municipality_id=u.municipality_id WHERE p.id=NEW.permit_id AND u.id=NEW.inspector_id AND u.role='inspector') THEN RAISE(ABORT,'Inspector municipality or role mismatch') END;
END;
CREATE TRIGGER inspection_tenant_update BEFORE UPDATE OF permit_id,inspector_id ON inspections BEGIN
SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM users u JOIN permits p ON p.municipality_id=u.municipality_id WHERE p.id=NEW.permit_id AND u.id=NEW.inspector_id AND u.role='inspector') THEN RAISE(ABORT,'Inspector municipality or role mismatch') END;
END;
