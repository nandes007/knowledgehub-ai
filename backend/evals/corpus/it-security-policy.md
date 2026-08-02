# IT Security Policy

This policy is mandatory for everyone with a Nandes Tech account, including
contractors. Violations are handled under the disciplinary process in the
employee handbook.

## Passwords and MFA

Passwords must be at least 14 characters and unique per service. Everyone uses
1Password; storing credentials in browsers, spreadsheets, or code is
prohibited.

Multi-factor authentication is mandatory on email, 1Password, GitHub, AWS, and
the VPN. Hardware keys or authenticator apps only. SMS-based codes are not
accepted as a second factor.

## Device requirements

Company laptops must have full-disk encryption enabled, the screen lock set to
five minutes, and the managed endpoint agent running. Personal devices may
access email and chat only, never source code or customer data.

## VPN and public networks

Connect to the company VPN before using any public or untrusted network,
including cafés, hotels, and airports. Working from public spaces is otherwise
governed by the remote work policy, which also requires a privacy screen.

## Customer data handling

Customer data may only be processed inside approved systems: the production
AWS account, the data warehouse, and the support tool. Exporting customer data
to a personal drive, a spreadsheet, or an unapproved AI tool is prohibited.

Production database access is read-only by default and requires a ticket with a
stated purpose and an expiry date. Standing production write access is granted
to on-call engineers only for the duration of their rotation.

## Reporting an incident

Report suspected security incidents — phishing, lost devices, leaked
credentials — to security@nandes.tech immediately, and always within one hour
of noticing. Do not investigate on your own and do not delete evidence. A lost
or stolen laptop must also be reported to your manager the same day.

## Offboarding

Accounts are disabled within one hour of the offboarding ticket being filed.
Access reviews run quarterly for all production systems.

## Third-party tools

New SaaS tools that touch customer data require a security review before
purchase. Free tiers are not exempt. Requests go through the security review
form and take up to ten working days.
