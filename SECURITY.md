# Security policy

## Supported versions

Only the latest release and the `main` branch receive security fixes during the alpha
stage.

## Reporting a vulnerability

Do not open a public issue for a vulnerability or exposed secret. Use GitHub's private
security-advisory reporting for this repository. If that channel is unavailable, contact
the maintainer through the verified profile linked from the repository owner account.
Include affected version, reproduction steps, impact and any suggested mitigation.

This project has no live plant connector in v0.1. Treat any fork that adds network,
historian, OPC UA or actuator interfaces as a new security boundary requiring threat
modelling, least privilege, secret management and an independent safety review.
