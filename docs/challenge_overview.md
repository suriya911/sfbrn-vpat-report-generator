# Challenge Overview: Accessibility VPAT Review for Procurement of Software — AI-assisted first-pass VPAT/ACR accessibility review

## Project Objectives
- Automate first-pass review of vendor VPAT/ACR documents to produce faster, more consistent, and more accurate accessibility judgments during procurement.
- Enable non-specialists to conduct reliable accessibility reviews by codifying expert business logic into a standardized tool.
- Improve experience for staff, faculty, and students by reducing barriers introduced through inaccessible software purchases.
- Reduce time spent manually reviewing VPATs while flagging and prioritizing documents that require escalation to a manual reviewer.
- Leave room to grow into a widely shareable tool usable by procurement offices across the CSU system and nationally, with customizable, hard-coded rule sets.

## Current Workflow
- VPAT/ACR documents (PDFs) are requested from vendors during the ICT procurement review (security, accessibility, endpoint); accessibility standards referenced include WCAG, Section 508, and ADA.
- A first-pass procurement specialist (lower-training/non-specialist) reviews the VPAT and decides whether it passes or needs escalation; flagged items go to a trained specialist for a required manual review.
- Reviewers read long, variable-quality documents and make an educated, often subjective ("a feeling") judgment about accessibility and completeness.
- Manual artifacts include TAAP reports (documenting findings and help needed) and a recently mapped business process guide.
- Some ad-hoc experimentation done in personal Claude/ChatGPT accounts; an existing Python VPAT review tool has been built and refactored.

## Key Pain Points
- VPATs are long, ambiguous, and inconsistently filled out — hard to tell if gaps mean the product is accessible or the vendor didn't do the work.
- Reviews require tribal knowledge and specialist training that not every campus has available.
- Manual review is time-consuming and error-prone, requiring reviewers to locate and validate individual issues within the product.
- High volume of procurement reviews that could be accelerated through consistent, programmatic first-pass triage.
- Ad-hoc AI use in personal accounts lacks standardization, reliability, and codified rules.

## Ideal Solution Vision
- A standardized application (executable / Python) that ingests VPAT/ACR PDFs and outputs a summary, grading, and next steps — addressing inconsistent, subjective manual review.
- Example: upload a vendor ACR → tool returns a category classification (Good to go / Minor issues / Needs manual review / Needs temporary alternative access plan) with document-level detail on failing criteria to guide reviewers.
- Analysis guided by WCAG success criteria (publicly available via W3C); rule sets customizable and hard-coded for consistency, addressing the non-specialist usability need.
- Dashboard surface for escalation and prioritization, plus document-level analysis pinpointing failing items to feed manual reviews or alternative access plans.
- Extension path: build on existing codebase; deployable and affordable (e.g., Sonnet-tier model via AWS Bedrock) so it can scale across multiple campuses and be shared nationally without a rewrite.

## Data Availability
- Existing refactored Python VPAT review tool codebase (creator has approved sharing).
- Large repository of VPAT/ACR documents held at the Chancellor's Office (access permission to be obtained).
- Sample TAAP output reports documenting findings and help needed; recently mapped business process guide.
- Human resources: SFBRN ATI, ITS staff, campus accessibility partners, CSU ATI communities of practice, SME steering/feedback, and potential collaboration with the SPAN procurement accessibility initiative.
- Public standards reference: WCAG / W3C success criteria; general models already carry baseline WCAG knowledge.
- Known gap: no defined rubric exists yet for what "good" judgment looks like — steering and success criteria to be developed with SMEs.