# CogniCare App Flow

This document explains the end-to-end user journey inside the CogniCare app, how a user navigates between screens, and what each page is designed to help with.

---

## 1. Overall navigation model

The application uses a left sidebar for the main journey and a top bar for quick actions.

Main navigation items:
1. Import Records
2. Care Assessment
3. Hospital Matches
4. Decision Evidence
5. Compare Pathways
6. Care Journey
7. Caregiver Copilot

The app also includes an emergency shortcut from the header, which opens an emergency-care view.

The flow is structured like a decision support journey:

Import patient documents -> assess patient and policy fit -> review ranked hospitals -> understand recommendation -> compare options -> review care journey -> ask caregiver questions.

---

## 2. Entry point: Import Records

Page: Import Records

Purpose:
- Upload medical, policy, or care-related files.
- Build a unified synthetic care record from multiple sources.
- Track ingestion progress through a document-processing pipeline.

How the user navigates:
- User clicks the sidebar item labelled “Import Records”.
- The app opens the ingestion page.
- User drops files or browses to upload them.
- Background processing moves through stages such as validation, classification, extraction, patient matching, and record update.

What this page helps with:
- Consolidates patient data before decision-making.
- Prepares the system with the correct patient and care information.
- Reduces manual data entry and helps align records with the selected patient.

---

## 3. Assessment stage: Care Assessment

Page: Care Assessment

Purpose:
- Select the patient, policy, hospital, care specialty, and service requirement.
- Configure the care requirement before comparing hospital options.
- Trigger a compatibility calculation.

How the user navigates:
- User selects a patient from the patient dropdown.
- Chooses a policy and starting hospital.
- Enters the required specialty and service.
- Optionally marks emergency capability as required.
- Clicks “Calculate compatibility”.

What this page helps with:
- Defines the decision context in one place.
- Brings together patient needs, insurance rules, and operational constraints.
- Produces the base inputs for hospital ranking and pathway analysis.

This page is the decision setup step. It does not provide the final recommendation yet; it prepares the data used by the matching engine.

---

## 4. Matching stage: Hospital Matches

Page: Hospital Matches

Purpose:
- Rank hospitals based on compatibility with the patient, policy, and required care.
- Show a map view with hospital placement and scoring.
- Help the user choose a hospital to study in more detail.

How the user navigates:
- After calculation, the app moves to the Hospital Matches page automatically.
- A ranked list of hospitals appears with scores and explanations.
- The user can click any hospital card to inspect it further.
- The map highlights the location of each hospital and marks the best current match.

What this page helps with:
- Makes the recommendation understandable and actionable.
- Shows which hospitals best satisfy policy and clinical conditions.
- Provides spatial context for access and emergency coverage.

This is the main decision screen where the user sees a prioritized shortlist of hospital options.

---

## 5. Explanation stage: Decision Evidence

Page: Decision Evidence

Purpose:
- Explain why a hospital was recommended.
- Show score breakdown and evidence behind the match.
- Identify which conditions passed, failed, or need attention.

How the user navigates:
- User clicks a hospital card from Hospital Matches.
- The app opens the detailed decision evidence page.
- The system displays the hospital score, matched and failed conditions, and warning messages.

What this page helps with:
- Builds trust in the recommendation.
- Makes the AI/model output transparent.
- Enables clinical review before final decision-making.

This page is where the system explains itself rather than just presenting a ranking.

---

## 6. Comparison stage: Compare Pathways

Page: Compare Pathways

Purpose:
- Compare multiple hospitals side-by-side using the same care requirement.
- Review differences in score, policy fit, costs, insurance coverage, and patient payment.
- Support decision trade-offs across options.

How the user navigates:
- User selects the Compare Pathways page from the sidebar.
- Chooses two to four hospitals.
- Clicks “Compare selected pathways”.
- The app displays a visual comparison chart and detailed data table.

What this page helps with:
- Identifies relative strengths and weaknesses across hospitals.
- Helps compare operational, financial, and policy-related differences.
- Supports final selection when more than one hospital is viable.

This page helps evaluate the best option among top candidates rather than choosing only one hospital in isolation.

---

## 7. Planning stage: Care Journey

Page: Care Journey

Purpose:
- Display the patient’s care timeline and relevant care events.
- Present the treatment journey and milestones.
- Support planning and follow-up care.

How the user navigates:
- User selects Care Journey from the sidebar.
- The app loads events related to the selected patient.
- A timeline displays events, status, and types of care occurrences.

What this page helps with:
- Gives context beyond hospital matching.
- Shows how the patient’s treatment has progressed over time.
- Helps caregivers monitor the continuity of care.

This page shifts the app from “recommendation” to “care coordination and planning”.

---

## 8. Support stage: Caregiver Copilot

Page: Caregiver Copilot

Purpose:
- Answer questions using patient, policy, hospital, and journey data.
- Give the caregiver a decision-support assistant for contextual guidance.
- Explain the logic behind a hospital recommendation or policy impact.

How the user navigates:
- User opens the Caregiver Copilot page from the sidebar.
- Enters a question such as “Why was this hospital recommended?”
- Clicks “Ask Copilot”.
- The AI returns an answer with supporting evidence items.

What this page helps with:
- Replaces guesswork with contextual explanation.
- Helps caregivers ask follow-up questions quickly.
- Supports informed communication with patients and care teams.

This page is the assistant layer on top of the final recommendation.

---

## 9. Emergency access path

Page: Emergency Care

Purpose:
- Identify nearby hospitals that are emergency-capable.
- Support urgent decision-making when time-critical care is needed.

How the user navigates:
- User clicks the “Emergency care” button in the top bar.
- The application fetches emergency-ranked hospitals.
- A map and list show nearby emergency-capable providers.

What this page helps with:
- Ensures urgent patient access is considered.
- Highlights hospitals suitable for emergency treatment.
- Provides a backup or alternative care view outside the standard recommendation flow.

---

## 10. Full user journey summary

A typical user experience looks like this:

1. Upload records to build the patient profile.
2. Select the patient and define the care requirement.
3. Calculate compatibility.
4. Review ranked hospital matches.
5. Open a hospital’s evidence page to understand the recommendation.
6. Compare alternative hospitals when needed.
7. Review the patient care journey and timeline.
8. Ask the caregiver copilot clarifying questions.
9. Use the Emergency Care option when urgent access matters.

This creates a complete clinical decision-support flow: data intake -> requirement definition -> recommendation -> explanation -> comparison -> planning -> assisted decision-making.

---

## 11. Why this flow matters

The app is designed to support a caregiver or clinical decision maker in a structured, explainable, and practical way:

- It keeps the workflow guided and sequential.
- It reduces decision risk by showing evidence.
- It helps compare not just hospitals but also policy and financial implications.
- It adds context from the patient journey and caregiver questions.

This makes the app useful for real-world care navigation, not just a simple hospital list.
