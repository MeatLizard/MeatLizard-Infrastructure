# shared_lib/audit.py
from sqlalchemy.orm import Session
from shared_lib.db import AuditLog

def log_audit_event(
    db: Session,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    old_values: dict,
    new_values: dict,
):
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_values=old_values,
        new_values=new_values,
    )
    db.add(audit_log)
    db.commit()
