# Managed Hosting MVP Blueprint

## Product concept

Build a managed hosting and deployment service for non-technical founders, creators, and small businesses who want an application online without operating infrastructure themselves.

The initial offer is simple: you handle deployment, hosting, maintenance, and support while the customer focuses on their product.

## Core value proposition

"Launch faster. Stay online. Stop worrying about infrastructure."

## Primary target customer

- founders launching a first product
- freelancers shipping client work
- small teams without a DevOps hire
- creators who want a polished web app without managing servers

## Problem being solved

These customers want reliable hosting and deployment support, but they do not want to learn cloud infrastructure, manage DNS, monitor uptime, or troubleshoot deployments.

## MVP scope

The first version should be intentionally narrow.

### MVP features

1. Marketing landing page
   - clear positioning
   - one strong call to action
   - consultation signup form

2. Consultation intake flow
   - project type
   - app or site description
   - launch timeline
   - budget range

3. Client dashboard
   - project status
   - onboarding checklist
   - deployment status
   - support requests

4. Basic managed service workflow
   - deployment setup
   - domain configuration
   - monitoring placeholder
   - maintenance request queue

## Why this fits the existing Portfolio repo

The existing Portfolio repository already contains several building blocks that map directly to this product:

- [Portfolio/infraportal](../infraportal) for the public-facing portal and client dashboard experience
- [Portfolio/auth-service](../auth-service) for authentication and role-based access
- [Portfolio/projects-service](../projects-service) for project, milestone, and deliverable tracking
- [Portfolio/services.yaml](../services.yaml) for the deployment and service inventory model

This means the product can be launched as a service layer on top of existing infrastructure patterns rather than as a brand-new stack.

## Suggested product structure

### Public experience

- home page with product positioning
- explain the service clearly
- show what is included
- collect consultation signups

### Customer experience

- login and dashboard
- onboarding checklist
- project view with current status
- request support
- review deployment and maintenance activity

## MVP user stories

### Visitor
- I can understand what this service offers in under 10 seconds.
- I can book a consultation without friction.

### Client
- I can see my active projects and their status.
- I can understand what onboarding steps are still pending.
- I can request help without emailing someone manually.

## Recommended implementation plan

### Phase 1 - Brand and landing page

- create a new branded landing experience in the existing frontend
- add a consultation form
- add a simple success state and follow-up flow
- connect the form to email or a lightweight CRM workflow

### Phase 2 - Client portal basics

- reuse the existing auth flow
- add a dashboard shell
- add project cards and status view
- add an onboarding checklist

### Phase 3 - Managed service workflow

- add deployment status and maintenance status views
- add support request entries
- add basic service health indicators
- create a simple recurring maintenance workflow

## Suggested first-week execution plan

1. Rebrand the existing portal experience around the hosting service offer.
2. Replace the default content with service-focused messaging.
3. Add a consultation signup form.
4. Add a simple dashboard route for signed-in users.
5. Add a mock project onboarding workflow using the existing project-service model.

## Technical approach

Use the existing repo as the foundation:

- frontend: React + Vite via [Portfolio/infraportal](../infraportal)
- authentication: existing auth-service patterns
- data model: project-oriented records similar to [Portfolio/projects-service](../projects-service)
- deployment: continue using the same deployment model already documented in [Portfolio/services.yaml](../services.yaml)

## Pricing direction

Start with a simple offer structure:

- Launch Setup
  - one app or site deployment
  - domain and SSL setup
  - basic monitoring

- Managed Maintenance
  - ongoing updates and support
  - monthly check-ins
  - backup and health monitoring

- Concierge Support
  - higher-touch support for growth and scaling

## Success criteria

The MVP is successful if it can:

- attract consultation requests
- create a credible professional experience
- demonstrate a clear path from signup to onboarding
- show that the service can be delivered with the current repo foundation

## Recommended next action

Implement the landing page and consultation flow first, then expand into the client dashboard once demand is validated.

## Implementation status

### Phase 1 - Brand and landing page

- Done: landing experience rebranded around the managed-hosting offer.
- Done: consultation form with a success state on the landing page.
- Done: consultation requests persist locally and carry a `new` -> `reviewed` -> `accepted` status.
- Done: route-addressable consultation review page at `#/admin/consultations` to triage incoming requests through intake to onboarding.
- Done: admin-side "Send to CRM" sync that pushes a consultation into the contacts-service as a lead, using the admin token (public form stays local, keeping the trust boundary correct).
- Next: add a public intake endpoint so landing-page submissions create leads server-side without exposing admin credentials, then expand the client dashboard (Phase 2).

### Phase 2 - Client portal basics

- Done: client dashboard reuses the existing auth flow and projects-service data.
- Done: managed service snapshot on the client dashboard.
- Done: launch onboarding checklist on the client dashboard so clients can see completed and pending steps, with progress saved per project.
- Next: add a maintenance and support request queue (Phase 3).

### Phase 3 - Managed service workflow

- Done: support and maintenance request queue on the client dashboard so clients can log requests, track status, and withdraw open ones without email.
- Next: surface request status transitions for the team (admin-side queue) and add basic service health indicators.
