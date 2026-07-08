> **Snapshot notice:** Markdown snapshot of `Marketing Role Research Notes_ Automated Copy Review.docx`, generated 2026-07-07 via `pandoc -f docx -t gfm`. The docx remains the authoritative source — don't hand-edit this file; regenerate it with the same command if the docx changes.

# **Marketing Role Research Notes: Automated Copy Review**

## **1. Persona & Domain Mapping**

- **Target User:** Marketing Lead / Content Manager

- **Core Responsibility:** Guarding brand integrity, managing editorial pipelines, and scaling multi-channel content production across internal teams and external freelancers.

- **Daily Context:** Juggling 5 to 10 active cross-channel campaigns simultaneously. They work primarily within content workspaces like Google Docs and Notion, migrating finalized assets into marketing automation hubs like HubSpot or Klaviyo.

## **2. Daily Workflows & Friction Points**

The table below maps the standard copywriting pipeline, isolating the exact operational drag occurring at the evaluation stage.

| **Stage**          | **Process**                                                                              | **Typical Tools**          | **Friction Level & Primary Driver**                                                                            |
| ------------------ | ---------------------------------------------------------------------------------------- | -------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **1. Briefing**    | Marketing Lead defines target audience, channel, goals, and core messaging requirements. | Notion, Jira, Asana        | **Low:** Strategic and highly structured.                                                                      |
| **2. Drafting**    | Internal copywriters or external freelancers write copy versions.                        | Google Docs                | **Low:** High-autonomy creative execution.                                                                     |
| **3. Review Loop** | **Marketing Lead manually evaluates drafts against 20-50 page static brand guidelines.** | **Google Docs (Comments)** | **Critical Bottleneck:** High-cognitive load checking mechanical drift, tone discrepancies, and CTA alignment. |
| **4. Approval**    | Stakeholders review finalized copy for regulatory or cross-functional alignment.         | Slack, Email               | **Medium:** Schedule dependencies.                                                                             |
| **5. Deployment**  | Copy versions are moved to execution platforms.                                          | HubSpot, Figma             | **Low:** Operational execution.                                                                                |

## **3. Deep Dive: Brand Voice Consistency & Copy Review Bottleneck**

### **The Core Problem**

Brand guidelines exist as static documentation (PDFs or static wiki pages). Writers must self-police against these rules asynchronously. Because style definitions like "professional but warm" are subjective, different writers interpret them inconsistently.

### **Core Micro-Decisions**

The Marketing Lead is forced to make the same micro-decisions repeatedly on every single block of copy:

- *Does this tone drift too formal, or does it cross the line into overly casual?*

- *Does the information hierarchy lead with the primary value proposition, or is the hook buried?*

- *Is the Call-to-Action (CTA) cadence appropriate for this channel, or is it premature?*

### **Quantifiable Operational Impact**

- **Time Allocation:** Marketing leads spend 20% to 30% of their total editing time policing mechanical voice and tone corrections rather than refining structural narrative or messaging strategy.

- **Review Velocity:** As manual review cycles drag on, the timeline from initial draft to deployment stretches by hours or days per asset, compounding content pipeline delay when managing multiple external vendors.

## **4. High-Level Agent Strategy & Integration**

****

[Writer Submits Draft]

│

▼

┌────────────────────────────────────────┐

│ Agent Evaluation Block (In-Doc) │

│ ──────────────────────────────────── │

│ 1. Check Brand Voice Guidelines │

│ 2. Audit Info Hierarchy & Hooks │

│ 3. Verify CTA Cadence Rules │

└────────────────────────────────────────┘

│

▼

[Inline Suggestions Generated]

│

▼

[Marketing Lead Strategic Sign-off Only]

### **Strategic Objective**

An agent that reviews copy drafts against brand voice, information hierarchy, and CTA guidelines—so the marketing lead only intervenes on strategic decisions, not mechanical corrections.

### **The Solution: Embedded Interception Agent**

To minimize workflow friction, the agent must be built as a **Google Docs Workspace Add-on**.

- **The Workflow Fit:** Copywriters draft inside Google Docs. Before notifying the Marketing Lead for review, the writer runs the agent.

- **Actionable Feedback:** The agent evaluates the document against an ingested brand voice vector model and a specific campaign brief. It generates inline comments flagging tone drift, structural issues, or weak CTAs, and suggests high-quality alternative rewrites inline.

- **The Result:** The Marketing Lead receives a pre-screened, mechanically compliant draft. Their role shifts from a line-by-line proofreader to a high-level, human-in-the-loop strategic approver.
