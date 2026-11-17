# SRS v0.5 peer review – responses to the open findings

Responses for the nine findings that had no answer yet (A4, A7, A11, A12, A13, A15, F1, F3, F8). Each one is written to paste into the "Our response" row of the issue list and as the reply comment on GitHub. They follow the same format as the answers already written for A1–A3, A5, A6, A8–A10, A14 and F2, F4–F7.

---

## A4 – Data-protection obligations are announced but not specified

Accepted. Section 3.4 announces a data-protection assessment, but no requirement asks for one. REQ-SEC-007 also does not say what the user is told or which law applies. The risk is real: an AAC request can reveal a speech or language impairment, and the Gemini free tier may use inputs to improve Google's products.

Revision plan:
- Add REQ-COMP-003 (data protection). The demo and any trial run in China, so PIPL is the reference regime. Intention text that reveals an impairment counts as sensitive personal information, which needs separate consent and an impact assessment before processing. Sending it to a hosted model outside China is a cross-border transfer, which also needs separate consent. GDPR applies only if EU users are targeted. The completed assessment is an acceptance criterion.
- Extend REQ-SEC-007 with the content of the consent notice: who runs the service and how to contact them, what is collected, that the intention and photo go to an external AI provider, how long data is kept, and how to delete it. The retention rule also covers `ai_data/accepted.jsonl`.
- Add a provider allow-list per environment, checked when the server starts. An environment that handles real user data refuses to start with a provider whose terms allow training on inputs.
- Section 2.5: note that Gemini is not available in mainland China, so the provider must be confirmed reachable from the demo network. The connectivity test in AI_Model_Plan step 1 covers this.

Until this is done, the rule stays as it is today: only synthetic text and drawn photos are sent to any provider.

---

## A7 – No measurable quality criteria for the core AI function

Accepted. Without metrics and thresholds, REQ-ML-001 cannot fail, so the choice of model cannot be justified against the SRS. The metrics are already listed in the AI model plan (section 8), but they are not in the SRS and have no pass values.

Revision plan:
- Move the evaluation design into REQ-ML-002. The set has at least 32 synthetic cases, with at least 4 in each of the 8 categories of the plan: clear intent, text only, negation, ambiguous photo, wrong scene hint, photo without matching intent, injection and regeneration.
- Rating procedure: two team members rate every case independently without knowing which model produced it. A third member settles disagreements.
- Provisional pass thresholds for REQ-ML-001:
  - At least 90 % of cases have one or more sentences that match the intended request.
  - No lost negation.
  - No invented intent.
  - No injected instruction followed.
  - Average fluency of at least 2.5 out of 3.
- Tie REQ-ML-003 AC1 and AC3 to the result on the wrong-scene, photo-without-intent and injection cases.
- Plan the runs around the free-tier caps. With a cap of 16 calls per model per day, one full run of 32–40 cases on one model takes two to three quota days.

The values stay provisional until Appendix B item 3 is closed in W9. The ratings come from the team, not from AAC users, and the SRS will say so.

---

## A11 – Speech versus saving the acceptance

Accepted, and the risk already exists in the code. The demo page waits for the feedback call to succeed before it speaks (`app/static/app.js`), so a failed save stops the user from being heard. For a communication aid this is the wrong way round.

Revision plan:
- Add REQ-FUNC-013 (speech is not blocked by saving). After confirmation the sentence is spoken at once, and the acceptance is saved in parallel.
- If the save fails because of a network error, a timeout or a 503, a text notice says "Spoken, but not saved" and the save is retried a limited number of times. This is safe because the feedback call is idempotent (REQ-REL-003).
- A 404 or a 422 is not retried, because it means wrong IDs. The notice is shown and the error is logged.
- Change Figure 3 and Appendix A step 7 to "speak, then save".
- Add a failure-injection test in which the feedback endpoint returns 503 or does not answer. Expected result: the sentence is still spoken, the notice appears, and one record exists after the retry.

The same rule applies to the team frontend, not only the demo page.

---

## A12 – WCAG level and criteria do not match

Accepted. The four criteria cover only part of WCAG 2.1 AA, and AC4 (44 × 44 px) is the AAA criterion 2.5.5. The scope also leaves out dialogs and error states.

Revision plan:
- Close Appendix B item 1 in W8 and keep WCAG 2.1 AA as the target for all three pages, including the photo dialog, the loading state and the error and status messages.
- List the success criteria we check:
  - non-text content (1.1.1)
  - contrast (1.4.3) and non-text contrast (1.4.11)
  - text resize (1.4.4) and reflow (1.4.10)
  - keyboard (2.1.1) and focus visible (2.4.7)
  - error identification (3.3.1) and labels (3.3.2)
  - status messages (4.1.3), so that notices are announced without being spoken aloud by the app
- Keep the 44 × 44 px touch targets, but state them as a project addition above AA, chosen because many users have motor impairments.
- Test method: an automated check (axe or Lighthouse) on each page and state, a manual keyboard-only pass, a screen-reader pass with NVDA on Windows, and contrast and target sizes measured with the browser tools. The results are recorded in Table 61.

---

## A13 – Schedule and open decisions conflict with the W7 baseline

Accepted. The document calls itself the agreed baseline while several decisions and TBD values are still open, and the dates in Table 49, Figure 8 and Appendix B do not tell the same story.

Revision plan:
- Describe v0.5 as the review draft submitted in W7. Version 1.0 becomes the baseline once the peer-review fixes and the decisions that change requirements are closed. Chapter 1 and the revision history will say this.
- Align Table 49 and Figure 8: the SRS is submitted in W7, and the peer review and fixes run in W8.
- Rename Appendix B to "Open decisions" and split it in two:
  - Decisions that change a requirement and must close before v1.0: items 1, 3, 4, 5, 6, 11 and 12. Item 5 is included because it sets the availability target of REQ-AVAIL-001.
  - The other items, tracked as pending changes under REQ-CM-001, each with a GitHub issue.
- The latest target week of the blocking items is W9, so v1.0 is planned for W9.

---

## A15 – Document organisation and traceability details

Accepted. Each point makes the document harder to read or trace.

Revision plan:
- (a) Add a sentence to the Chapter 3 introduction: IDs are never reused or renumbered, so a new requirement sits next to related ones and can break the numeric order.
- (b) Renumber the figures in order of appearance. The schedule becomes Figure 5 and the screenshots become Figures 6–8.
- (c) Merge Section 1.4 and Appendix F into one numbered reference list. Add the provider documents that REQ-ML-007, REQ-PERF-001 and Section 3.6.2 rely on: Gemini pricing and free-tier data use, and Gemini rate limits. Both are already cited in the AI model plan.
- (d) Split REQ-INT-003 into photo input (REQ-INT-003) and speech output (new REQ-INT-008). Photo selection already exists and can be marked Partial on its own.
- (e) Add a "Related" field to each requirement table that links to constraints (2.3), assumptions (2.5) and related requirements, as the template's "More Information" field does.

---

## F1 – AI suggestion quality level not defined

Accepted. This is the same issue as Team A's A7, and we will fix both together. Until the minimum quality level is defined, there is no objective way to decide whether a model's suggestions are good enough.

Revision plan:
- Define the evaluation set in REQ-ML-002: at least 32 synthetic cases over the 8 categories of the AI model plan.
- Two team members rate every case independently, and a third member settles disagreements.
- Provisional pass thresholds:
  - At least 90 % of cases have one or more sentences that match the intended request.
  - Average fluency of at least 2.5 out of 3.
  - No lost negations.
  - No invented intent.
- Cover the points you raise:
  - Relevance and preservation of negative intentions are rated on every case.
  - Assumptions based only on the photo are tested by the "wrong scene hint" and "photo without matching intent" cases (for example a café photo with the intention "toilet").
- REQ-FUNC-003 will also require that each suggestion passes these checks once the real provider is connected.

The thresholds are confirmed in W9 (Appendix B item 3).

---

## F3 – No priority or release increment per requirement

Accepted. Appendix E.5 describes the increments in prose, but no requirement says which increment it belongs to, so it is hard to see what the first working version needs.

Revision plan:
- Add "Priority" (Must / Should / Could) and "Increment" fields to every requirement table.
- Add a summary table in Section 2.6 that groups the requirements by increment:
  - Increment 1 is the café flow end to end. For example, the core flow, validation, user-confirmed speech and the intent and negation safeguards are Must.
  - Before an external trial: authentication, rate limits and deployment are Must.
  - Before real users: consent, retention and licences are Must.
  - Increment 2: additional places (REQ-FUNC-011) are Could.
- Each owner assigns the priority of their own requirements, and the team checks the result in the weekly meeting.
- Take the account scope from the decision in A3, so that the Increment 1 scope is stated in one place only.

---

## F8 – Accessibility target and test method

Accepted. This is the same issue as Team A's A12, and both will be fixed in REQ-INT-007.

Revision plan:
- Confirm WCAG 2.1 AA in W8 (Appendix B item 1) for the three pages and their dialog, loading and error states.
- List the exact success criteria we check, and keep the 44 × 44 px touch targets as an explicit addition above AA.
- Test on the integrated system, not only on the demo page:
  - an automated check (axe or Lighthouse)
  - a keyboard-only pass through the full café scenario
  - a screen-reader pass with NVDA
  - contrast measured with a checker
  - touch-target sizes measured with the browser tools

Each result will be recorded with its date and browser in Table 61, and the requirement stays "Not started" until then.
