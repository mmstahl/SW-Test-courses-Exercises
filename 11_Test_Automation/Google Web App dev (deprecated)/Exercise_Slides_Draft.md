# Data-Driven & Keyword-Driven Testing — Slide Draft

*Text draft for review before building the actual deck. `[NOTES]` = speaker notes only (not shown to students; strip before sharing the file itself, not just before presenting).*

---

## SLIDE 1 — Title
**From Manual to Automated: Data-Driven & Keyword-Driven Testing**
Phone Configurator Simulator

---

## PHASE 1 — THE TRAP

### SLIDE 2 — Today's Task
The app is set to **Level 1**.

Your task: test it for **all-triplets coverage**.

Go to `.../exec`. Test manually, in the browser. Start now.

[NOTES] Don't explain why, don't mention automation, don't hint at time pressure. Let them start clicking. Set Level 1 on the teacher page before this slide. If anyone asks "how many tests is that," redirect: "you tell me, at the debrief."

### SLIDE 3 — Debrief
- How many tests did you run?
- How long did each one take, start to finish (select all 5 parameters → confirm price)?
- How many test cases does full all-triplets coverage actually require, for these 5 parameters?

[NOTES] Students designed all-triplets suites in a prior lesson — this is them recalling/reapplying that, not new material. If your own reference number is ~70 or whatever you've computed, don't reveal it yet; let them state their own count first.

### SLIDE 4 — Do the Math
**(time per test) × (number of triplet tests) = ?**

[NOTES] Let them compute this live, out loud if possible. This is the moment the exercise is built around — don't rush it.

### SLIDE 5 — So... How Long, Really?
*(reveal the computed total — hours? a full day?)*

Is this a plan you'd actually run before every release?

[NOTES] Let the absurdity land in silence for a beat. If nobody says "we need to automate this" within ~30 seconds, prompt: "What would you change about *how* we ran these tests?"

---

## PHASE 2 — AUTOMATE IT

### SLIDE 6 — We Need Another Way
Two flavors of automation:
- **Through the UI** — a browser driver clicks buttons for you.
- **Under the UI** — talk to the server directly, no browser at all.

Today: under the UI.

### SLIDE 7 — Meet REST Client
- A VS Code extension.
- Write HTTP requests as plain text, in `.http` files, next to your code.
- No GUI tool in between — you write the request yourself.
- `###` separates requests · `@name = value` defines a variable · `GET`/`POST` + headers + (optional) a JSON body.

[NOTES] Live install + a one-line demo request against a public API works well here before touching our app.

### SLIDE 8 — Talking to the Simulator, Under the UI
The app exposes the same actions the UI uses, through one URL:
- `GET .../exec?action=...` for read-only calls
- `POST .../exec` with a JSON body for anything that changes data

Start here: `GET .../exec?action=getUiConfig`

[NOTES] Deliberately bare — one example, not a walkthrough. Let them discover `calculate`/`buy` and the response shape themselves by reading what comes back. Do not hand out `requests.http`.

### SLIDE 9 — Your Assignment
1. Before writing any code: research **data-driven testing**. What does the term actually mean?
2. Take your all-triplets suite from Phase 1.
3. Write a script that runs the *entire* suite automatically over HTTP, and reports pass/fail per row.

### SLIDE 10 — What "Data-Driven" Should Actually Look Like
- Your test **logic** shouldn't know or care which row it's running.
- Your test **data** (the triplet suite) lives in its own file — not hardcoded into the script.

[NOTES] The thing to look for in review: did they actually separate data from logic, or write 70 near-identical copy-pasted requests with a different `for` loop wrapper? That's the real pass/fail signal for this phase, more than "did it run."

---

## PHASE 3 — THE NON-PROGRAMMER PROBLEM

### SLIDE 11 — New Persona
The company just hired a team of manual testers.

They're sharp. They are **not** programmers — not even with AI's help.

They still need to write and run tests against this app.

### SLIDE 12 — How Would You Solve This?
*(open discussion, no reveal)*

### SLIDE 13 — Go Research: Keyword-Driven Testing
What is it? How does it solve the problem on the last slide?

Come back with: a proposed list of keywords for testing *this* app.

### SLIDE 14 — Propose Your Keywords
Individually or in your team: what keywords would a non-programmer tester need to test this app?

Think about every user-visible action, and every check they'd want to make.

[NOTES — instructor reference keyword list, not for students]
Actions: `EnterEmail`, `SelectModel`, `SelectStorage`, `SelectColor`, `SelectNetwork`, `SelectAccessory`, `EnterDiscountCode`, `ClickCalculatePrice`, `ClickBuy`, `ClickReturn` (Refund/StoreCredit), `ClickReset`.
Checks: `VerifyTotalPrice`, `VerifyDiscountMessage`, `VerifyStoreCredit`, `VerifyGeneratedCode` / `VerifyNoCodeMessage`, `VerifyReturnMessage`, `VerifyBuyEnabled`/`Disabled`, `VerifyReturnEnabled`/`Disabled`.
Use this to steer, not to hand over. The point of the class discussion is convergence on shared *names* — watch for teams landing on different verbs for the same action (`SelectModel` vs `ChooseModel`) and push the room to resolve it, since that's exactly what has to converge for Slide 17 to work at all.

### SLIDE 15 — Class Discussion
Compare lists. Where do you agree? Where do you diverge, and why?

Converge on **one shared set of keyword names** for the whole class.

[NOTES] Explicitly out of scope for this agreement: parameters, argument order, how a test script is written, pass/fail signaling. Only the names. Say this out loud — it's the setup for what's coming.

### SLIDE 16 — Now Build It
In your team: build a keyword-driven test **engine** that understands the agreed keyword names.

Everything else — file format, syntax, how a keyword is invoked — is your team's own design decision.

### SLIDE 17 — Swap and Report
Exchange engines with another team.

Using only the agreed keyword names (and your own judgment about how to invoke them), write a few tests against your peers' engine.

Report: what worked immediately, what didn't, and why.

[NOTES] This is where the un-agreed parameter/signature differences bite — expected, not a bug in the exercise. Debrief afterward: this is exactly what happens between real teams without an interface contract, and it's the point.

### SLIDE 18 — Wrap-Up
- What made data-driven testing valuable?
- What made keyword-driven testing valuable — and for whom?
- What broke in the peer exchange? What would you add to the class agreement next time to prevent it?
