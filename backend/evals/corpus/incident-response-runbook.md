# Incident Response Runbook

How Nandes Tech declares, runs, and closes production incidents. Security
incidents follow the reporting path in the IT security policy in addition to
this runbook.

## Severity levels

| Severity | Definition | Response time | Comms |
| --- | --- | --- | --- |
| SEV1 | Full outage or customer data at risk | 15 minutes | Status page + customer email |
| SEV2 | Major feature broken, no workaround | 30 minutes | Status page |
| SEV3 | Degraded performance or a workaround exists | 4 hours | Internal only |
| SEV4 | Cosmetic or low-impact bug | Next working day | Internal only |

## Declaring an incident

Anyone may declare an incident. Post `/incident declare` in `#eng-oncall` with
a one-line impact statement and a severity. When in doubt, declare the higher
severity; downgrading later is cheap.

## Roles

- **Incident commander** — owns the incident, makes decisions, is not hands
  on keyboard. Defaults to the primary on-call engineer until handed over.
- **Communications lead** — owns the status page and customer updates.
  Mandatory for SEV1 and SEV2.
- **Scribe** — records the timeline in the incident channel.

## On-call rotation

The rotation is weekly, handing over Wednesday at 10:00 WIB. Primary on-call
must acknowledge a page within 15 minutes; secondary is paged after 20 minutes
of no acknowledgement. On-call is compensated at IDR 1,500,000 per week plus
IDR 500,000 per night worked after 22:00.

## During an incident

The deploy freeze is automatic for the duration of any SEV1 or SEV2. Mitigate
first and find the root cause later: rolling back is always an acceptable first
action. Every change made during an incident is announced in the channel before
it is applied.

## Postmortems

SEV1 and SEV2 incidents require a written postmortem within five working days.
Postmortems are blameless and published to the whole company. Every action item
needs a named owner and a due date; action items from SEV1 postmortems are
reviewed weekly until closed.

SEV3 and SEV4 incidents do not require a postmortem unless the incident
commander requests one.
