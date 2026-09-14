# Setup & Deployment

## 1. Deploy the web app

In the Apps Script editor (script.google.com, this project) or via `clasp`:

1. **Deploy → New deployment → type: Web app**
2. **Execute as:** Me
3. **Who has access:** Anyone
4. Deploy, copy the `.../exec` URL.

This must be **Anyone** (not "Anyone with Google account") — the whole point is that
students never sign in. See `Phone_Configurator_Simulator_requirements.md` §3/§7 for why.

The existing `@HEAD` deployment found by `clasp deployments` is a dev/test
deployment tied to your own editor session — it is **not** guaranteed to honor the
`Anyone, anonymous` access setting. Create a real versioned deployment as above for
actual use (by students, ChromeDriver, or curl/REST Client).

## 2. Set up the Teachers allowlist

Same mechanism as the 10_Combinatorial_testing reference app: create a sheet tab
named exactly **`Teachers`** in the bound spreadsheet, with a header in row 1 and
one teacher/TA email per row starting at row 2 (column A). `doGet` only serves
`teacher.html` to a visitor whose signed-in Google account
(`Session.getActiveUser().getEmail()`) is on this list — everyone else transparently
gets the student page, no error, no hint a teacher mode exists.

This sheet is **not** created automatically (matching the reference app) — add it
yourself before trying `.../exec?role=teacher`.

**Unverified assumption, worth checking on first use:** `Session.getActiveUser()`
reliably identifies the reference app's users under a single deployment; this app's
deployment is configured identically. If, once deployed, you visit
`.../exec?role=teacher` while signed into an allowlisted account and still land on
the student page, that assumption didn't hold here and this needs revisiting (see
`Phone_Configurator_Simulator_requirements.md` §7 for the reasoning either way).

## 3. Student and teacher URLs

* Students: `.../exec`
* Teacher: `.../exec?role=teacher` (while signed into an allowlisted Google account)

## 4. Sheets

The four data sheets (`Purchases`, `DiscountCodes`, `StoreCredit`, `ActionLog`) are
created automatically, with headers, the first time any server function runs — no
manual setup needed. `Teachers` (step 2 above) is the one exception — create it
yourself. All are added as tabs in whichever spreadsheet this script is bound to.

## 5. Testing

* **ChromeDriver/Selenium:** point at `.../exec`. Expect a redirect to a
  `googleusercontent.com` sandbox domain before the page's elements are available —
  wait for that before locating elements.
* **"Under the UI" HTTP testing:** see `requests.http` for a worked example of every
  action (curl equivalents are in the comments above each request).

## 6. Redeploying after a code change

`clasp push` updates the project's saved code (and the `@HEAD` deployment
immediately), but an existing **versioned** deployment (the one from step 1) keeps
serving whatever code existed when it was created. To publish changes to students,
create a **new version** of that deployment (Deploy → Manage deployments → edit →
new version) rather than a brand-new deployment, so the `.../exec` URL stays the same.
