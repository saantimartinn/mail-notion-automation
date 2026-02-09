# Mail → Notion Automation

Production-style automation service that ingests emails from a Gmail inbox and creates structured records in a Notion database.

This repository contains a **refactored and anonymized version** of a real production system.  
The original codebase cannot be shared for confidentiality reasons.

## What it does

- Connects to Gmail via IMAP
- Detects new emails using UID-based state tracking
- Filters and parses structured data from email bodies
- Creates entries in a Notion database
- Prevents duplicate processing (idempotent design)
- Stores execution logs and state in Google Cloud Storage
- Exposes an HTTP endpoint for remote execution (Cloud Run–ready)

## Key technical points

- Stateless service with external state (GCS)
- Secrets loaded from Google Secret Manager (ADC)
- Dockerized, Cloud Run–friendly
- DRY_RUN mode for safe testing
- Designed for production operation and observability

## Disclaimer

This is a **refactored technical example** for demonstration and portfolio purposes only.  
It does not contain real credentials, data, or confidential business logic.
