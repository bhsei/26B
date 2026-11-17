# Interest Discovery Proposal

Context-aware AAC Board · Team B - The Outliers  
Owner: Jiahui Chen · Draft 0.1 · 2026-10-28 · Status: proposal for team decision

This document proposes letting the sentence provider suggest things the user did not
ask for, so the app can help discover what the user likes in a given context. It
conflicts with the current SRS guardrails, so it needs a team decision before any
code. Nothing here is implemented.

## 1. The idea

Example: the user takes a photo of an empty cup in a café. They want water, but
selecting symbols is slow, so they select nothing or only "drink". The app offers
water, and also juice. The user had not thought of juice, likes the idea and picks
it. Next time in a café, juice appears earlier.

Two different things are mixed in this example:

1. **Open choice.** The user gives a photo but no clear wish. The app offers a short
   menu of options that fit the scene, and the user picks one.
2. **Alternative.** The user gives a clear wish ("water"). The app keeps it, and
   also offers one clearly marked option the user did not ask for ("juice instead?").

Over time, which options and alternatives the user accepts form a **preference
profile**. That profile is what "discovering interests" means in practice.

## 2. Conflict with the current requirements

| Item | Current text (short) | Conflict |
| --- | --- | --- |
| REQ-ML-003 | The provider shall never invent an intention from the photo or scene alone | Open choice builds options from the photo; alternatives add a wish the user did not express |
| SRS 3.6.4 Ethics | The product must not put words in the user's mouth | An alternative is a sentence the user did not intend |
| SRS A-4 | A photo alone cannot reliably reveal intent; symbols or text are always needed | Open choice starts from the photo only |
| System prompt (`src/ai/gemini_common.py`) | "Never add a wish that the person did not express" | Must change for the new modes |
| REQ-SEC-005 | No user accounts or ownership yet | A preference profile belongs to one person; without ownership, all profiles mix |
| REQ-SEC-007 | Consent and retention rules come before real users | Preferences are personal data, more sensitive than single sentences |

These rules exist because our users may not be able to correct a wrong sentence
quickly, and a spoken sentence speaks in their name. The design below keeps that
protection. The model may *offer* things, but every spoken sentence still rests on
the user's own choice (REQ-ML-005 is unchanged).

## 3. Proposed design

### 3.1 Open choice (no wish given)

- Trigger: a photo or scene hint, with no symbols and no intention. Today this
  returns an empty list.
- The model returns 3–4 short **options** (single words or short phrases: "Water",
  "Juice", "Coffee", "The bill"), not sentences.
- The UI shows them as symbols or buttons. Nothing is spoken.
- Picking an option sets it as the intention, and the normal flow generates the
  sentences. The final sentence is therefore still based on the user's selection,
  so REQ-ML-003 holds for everything that can be spoken.
- An "None of these" button always exists and goes back to the symbol board.

### 3.2 Alternative (wish given)

- Off by default, switched on per user (a setting, not a hidden behaviour).
- The model returns the usual faithful sentences, plus **at most one** alternative,
  in the same call.
- The alternative is visually separate and labelled "Something else?". It is
  phrased as the user's own request with "instead" ("Could I have some juice
  instead?"), so the listener hears it only if the user picks it.
- No alternative is generated when:
  - the wish is negative ("I do not want sugar"): an alternative could contradict
    it;
  - the wish is not food, drink or an activity choice (help, pain, toilet, stop);
  - the profile records a restriction (for example "no sugar", an allergy). This
    needs the restriction list in section 4.
- The faithful sentences come first and are never replaced by the alternative.

### 3.3 Preference profile

- Signal: an accepted option or alternative counts as a "like" for that item in that
  scene type; a shown and ignored one counts as a weak "no".
- Use 1: order the open-choice options (liked items first).
- Use 2: feed the retrieval examples (`src/ai/retrieval.py`), so liked items appear
  in the prompt.
- Keep one slot for something new, so the profile does not repeat the same items
  forever (explore vs. exploit).
- The user or carer can see and clear the profile.

### 3.4 Cost

Both modes use the same single call as today. The schema gets one more field, so
output grows by about 10–20 tokens. No extra requests, so the free-tier quota is
not affected (see `docs/design/AI_Model_Plan.md`, section 4.2).

## 4. Changes needed

| Area | Change |
| --- | --- |
| Provider output | `GeneratedSentences` gets `options` (open choice) and `alternative` (0 or 1), each validated like sentences |
| API (`docs/API.md`) | Each suggestion gets `kind`: `faithful`, `alternative` or `option`. New version of the contract |
| Database | `suggestions.kind` column (migration). Preference counts need a `user_id`, so they depend on REQ-SEC-005 |
| Restrictions | Small per-user list (allergies, "no sugar") that blocks alternatives. Sensitive data, needs REQ-SEC-007 first |
| Frontend | Separate area for the alternative; option buttons for open choice; setting to switch alternatives on; profile view |
| Prompt | New rules for the two modes, with the "never add a wish" rule kept for faithful sentences |
| Standalone prototype | Can be tried first in `src/ai/` with a `kind` field in `ai_data/accepted.jsonl`, no backend change |

## 5. Risks

| # | Risk | Mitigation |
| --- | --- | --- |
| R-1 | The user picks the alternative by mistake and says something they did not mean | Separate area, label, confirmation before speech (REQ-ML-005). Measure mistaken picks |
| R-2 | Nudging: the app steers the user's choices (also toward what the model "thinks" fits a café) | Off by default, at most one alternative, faithful sentences first, easy to switch off |
| R-3 | Health and diet: an alternative breaks a medical or diet rule | No alternative after a negation or for listed restrictions; drink and food alternatives only after the restriction list exists |
| R-4 | A carer or another person uses the board, so the profile describes the wrong person | Profile per user account only (REQ-SEC-005); visible and clearable |
| R-5 | Privacy: a preference profile is personal data | Synthetic data only until consent and retention rules exist (REQ-SEC-007) |
| R-6 | The profile locks in on a few items | Keep one slot for new items (3.3) |
| R-7 | "Likes" are hard to measure: an accepted alternative may only mean it was easier to tap | Evaluate with scenarios where the intended item is known (section 6) |

## 6. Evaluation

With synthetic scenarios only, where the intended item is written down before the
run:

- **Open choice:** how often the intended item is among the options; how often the
  user (or a team member playing the user) needs "None of these".
- **Alternative:** acceptance rate of the alternative; rate of alternatives picked
  when the scenario says the user wanted the original item (mistaken picks, R-1);
  number of alternatives produced after a negation (must be 0).
- **Effort:** taps or seconds from photo to confirmed sentence, compared with the
  current flow. This is the benefit we hope for; it is not shown yet.

Pass thresholds would go to SRS open issue 8, like the other AI targets.

## 7. Proposed SRS changes (after team agreement)

- **REQ-ML-003:** keep it for every sentence that can be spoken; add that options in
  open-choice mode are not sentences and need the user's selection.
- **New REQ-ML-007 Open choice:** with a scene and no wish, the system may offer up to
  four options; nothing is spoken until the user picks one and confirms a sentence.
- **New REQ-ML-008 Alternative suggestion:** when enabled, at most one alternative,
  labelled, never after a negation or against a listed restriction.
- **New REQ-ML-009 Preference profile:** per user, visible and clearable; depends on
  REQ-SEC-005 and REQ-SEC-007.
- **2.5 Assumptions:** add that A-4 still holds for spoken sentences.
- **1.2 Scope table:** add "interest discovery" as Increment 2 or as out of scope,
  depending on the decision.

The SRS milestone is Week 7, so the team should decide this week whether these go
into the SRS now or are left as a later extension.

## 8. Suggested plan

1. Team decision on the questions below (this week, before the SRS milestone).
2. If accepted: update the SRS (section 7) and record it in the Revision History.
3. Prototype open choice in `src/ai/` (standalone, synthetic photos), then the
   alternative with the negation and restriction checks.
4. Backend and API changes after the real provider is connected and REQ-SEC-005 has
   a method.
5. Evaluation (section 6) before turning it on in any demo.

Open choice alone is the smaller and safer first step: it needs no profile and no
user accounts, and it fixes a real gap (a photo with no wish returns nothing today).

## 9. Questions for the team

1. Do we want this at all, or does it go against the product idea in SRS 1.2
   ("the user stays in control")?
2. If yes: only open choice, or also alternatives?
3. In the SRS for Week 7, or a later extension (Increment 2)?
4. Who owns the frontend part (separate area, options, setting, profile view)?
5. Can we show it at the Week 16 demo without user accounts, using one synthetic
   user only?
