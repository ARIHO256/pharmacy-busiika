def log_action(user, action, meta=None):
    """Record legacy and unified audit events without breaking business flows.

    ``AuditLog`` remains for the original dashboard contract.  The governance
    event is the durable, append-only audit stream used by compliance views and
    future interoperability exports.
    """

    actor = user
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None

    legacy_entry = None
    try:
        from .models import AuditLog

        legacy_entry = AuditLog.objects.create(
            user=actor, action=action, meta=meta or {}
        )
    except Exception:
        # Audit helpers must never make the requested administrative action fail.
        legacy_entry = None

    try:
        from governance.services import audit

        audit(
            actor=actor,
            action=action,
            resource=legacy_entry,
            resource_type="AdministrativeAction" if legacy_entry is None else "",
            purpose="administration",
            metadata=meta or {},
        )
    except Exception:
        pass

    return legacy_entry
