# Backup and Disaster-Recovery Exercise

Production promotion requires evidence from a real recovery exercise, not merely a configured backup job.

## Backup/restore gate

- Create encrypted database and object-storage backups.
- Record checksum, size, retention, location, and key owner.
- Restore into an isolated environment.
- Run integrity checks, sample clinical/financial queries, and attachment downloads.
- Record recovery point and elapsed recovery time.
- Confirm audit and identity data are preserved.

## Disaster-recovery gate

- Simulate loss of the primary application and database services.
- Restore service using documented runbooks and approved personnel.
- Verify DNS/TLS, workers, queues, storage, PACS, payments, notifications, and provider callbacks.
- Test rollback and data reconciliation.
- Record RTO/RPO achieved, unresolved risks, and approval.

Use the `backup_restore` and `disaster_recovery` release-acceptance gates for the signed evidence.
