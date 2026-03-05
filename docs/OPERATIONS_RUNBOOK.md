# Operations Runbook

## Monitoring
Track:
- API response times (especially scan lookup)
- Error rate by endpoint
- DB file growth and free disk space
- Failed login attempts
- Alert feed backlog by severity/category
- Export job run success/failure rate

## Routine Tasks
- Daily: DB backup verification
- Weekly: audit log review for abnormal edits
- Weekly: protocol expiration alert checks
- Monthly: user/role review and stale session cleanup
- Monthly: billing period run, statement export, and period close
- Daily: review facility request queue and SLA summary
- Weekly: review pending export jobs and delivery status
- Daily: review unresolved high-severity alert notifications
- Daily: review quarantine overdue and necropsy pending queues

## Incident Response
1. Identify impacted endpoint and users.
2. Capture logs and DB snapshot.
3. Disable public scan route if abuse suspected.
4. Revoke active sessions if account compromise is possible.
5. Apply patch and rerun CI suite.

## Data Recovery
- Restore DB from latest backup.
- Run smoke checks:
  - login
  - cage search
  - scan lookup
  - audit endpoint
  - billing statement export
  - request list/status update
  - export-job run path
  - alert feed and acknowledgment path
  - quarantine and mortality workflows
