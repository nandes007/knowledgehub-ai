# Engineering Onboarding

Your first two weeks as an engineer at Nandes Tech. Your onboarding buddy is
assigned before your start date and is not your manager.

## Day one checklist

1. Collect your laptop from IT and enrol it in the endpoint agent.
2. Set up 1Password and add a hardware key or authenticator app to email,
   GitHub, and the VPN.
3. Accept the GitHub organisation invitation to `nandes-tech`.
4. Join `#eng-general`, `#eng-oncall`, and your team channel in Slack.
5. Read the IT security policy and confirm in the onboarding ticket.

## Week one goals

- Run the platform locally using `make dev` and the `.env.example` template.
- Ship one documentation fix or small bug fix to production.
- Pair with your buddy on at least two code reviews.
- Attend the Thursday architecture forum.

## Week two goals

- Take a scheduled shadow shift on the on-call rotation (observer only).
- Pick up a first ticket from the team backlog, sized at one day or less.
- Present a five-minute "what I learned" at Friday demo.

## Repositories

| Repository | Purpose |
| --- | --- |
| `platform-api` | Core backend services and the public API |
| `platform-web` | Customer-facing web application |
| `infra` | Terraform, Kubernetes manifests, and CI pipelines |
| `data-pipelines` | Batch ingestion and the warehouse models |

## Environments

There are three environments: `local`, `staging`, and `production`. Staging is
reset from a scrubbed production snapshot every Sunday at 02:00 WIB. Never
point local development at production credentials.

## Code review expectations

Every change needs one approving review, and two for changes to `infra` or to
authentication code. Reviews are expected within one working day. Pull requests
should stay under 400 changed lines where possible.

## Deployment

`platform-api` and `platform-web` deploy on merge to `main` via GitHub Actions.
Deploys are frozen from 16:00 WIB on Friday until Monday morning, and during
declared incidents.
