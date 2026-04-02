# After Action Report — Portfolio Exercise
**Inspired By:** Upwork — Vertex AI Agent Builder "Second Brain" (Strategic Land Promotion)
**Date:** March 29, 2026
**Status:** Not submitted — pivoting to portfolio build

---

## Decision

Prerequisites for freelance work are not yet satisfied. This job brief is being repurposed as a portfolio exercise. The use case (RAG agent over business documents with external API extensions) maps directly to the GCP/Vertex AI consulting positioning being built toward and is worth demonstrating in a production-grade context.

---

## Portfolio Framing

The UK land promotion domain is incidental. The pattern is what matters:

- Drive-grounded Vertex AI agent with structured instructions and source attribution
- Persistent session memory backed by Firestore
- External API extension via Cloud Function (OpenAPI spec)
- Authenticated access layer

This is the infrastructure pattern early-stage AI startups need before they have the headcount to build it themselves. The portfolio artifact should be framed around that pattern, not the specific domain.

---

## Scoped Build Plan

Deliberately narrowed to what is cleanly demonstrable. Do not build all 14 scope items from the original brief.

### Phase A — Core Agent (Start here)
- [ ] GCP project setup, billing, IAM, region locked to us-central1 (or europe-west2 to mirror brief)
- [ ] Vertex AI Agent Builder agent initialized
- [ ] Google Drive data store connected and verified — indexing PDFs, Sheets, images
- [ ] Web search grounding enabled
- [ ] Agent instructions written for a generic "business document analyst" use case (domain-agnostic framing)
- [ ] Source attribution enabled — all responses cite original files
- [ ] Basic prompt/response testing documented

### Phase B — Integrations
- [ ] Gmail connector via OAuth 2.0 + Domain-Wide Delegation (service account, Workspace Admin scopes)
- [ ] Firestore session metadata store — session ID keyed documents with display name and timestamps
- [ ] Stale session validation logic — cross-reference Firestore records against active Vertex AI sessions

### Phase C — External Extension
- [ ] Cloud Function wrapping Google Maps Elevation API
- [ ] OpenAPI spec registered as Agent Builder extension
- [ ] Agent able to accept coordinates and return elevation/topography data in response

### Phase D — Documentation & Write-up (Do not skip)
- [ ] Architecture diagram — agent, data stores, Cloud Function extension, auth layer
- [ ] README covering: what it does, how to deploy, key design decisions and tradeoffs
- [ ] Blog post or LinkedIn write-up framing the pattern for AI startup infrastructure use case
- [ ] Add to InfraPortal or publish as standalone repo under rodmen07

---

## What to Leave Out

The following items from the original brief are out of scope for the portfolio build. They require too much custom UI work relative to the consulting signal they send:

- Conversation management sidebar (rename, folders)
- Watchdog alerts pipeline
- Workspace Sidebar Add-on
- Docs/Sheets export
- Imagen and Mermaid generation
- Voice-to-text interface

---

## Key Technical Notes to Carry Forward

- **Gemini model:** Use 2.5 Pro — 3.1 Pro does not exist
- **Memory Bank:** Native cross-session memory is limited; Firestore is the reliable path
- **Planning constraint data:** Does not come from Google APIs — sourced from GIS portals (domain-specific, not relevant to portfolio framing)
- **Low-code boundary:** Agent instructions and grounding stay in Agent Designer console; custom code lives in discrete Cloud Functions only
- **TTL risk:** Vertex AI sessions expire — build stale session validation into Firestore layer from day one

---

## Prerequisites to Satisfy Before Freelance Work

- [ ] Review Smoothstack employment contract — moonlighting clause and IP assignment
- [ ] LLC formation — RM Cloud Consulting LLC (Texas)
- [ ] Business banking — Mercury
- [ ] E&O insurance
- [ ] Contract templates
- [ ] Upwork profile live with GCP/Vertex AI positioning

---

## Notes

- This build can be positioned as an InfraPortal v0.4 AI consulting feature or as a standalone repo — decide before starting
- Document architecture decisions and tradeoffs throughout; that content doubles as LinkedIn and blog material
- Long-term: this pattern is directly reusable for any client needing a document-grounded internal agent on GCP
