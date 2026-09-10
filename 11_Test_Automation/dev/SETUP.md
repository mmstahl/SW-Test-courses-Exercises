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

## 2. Set the teacher password

The default password is `teacher123` (see `DEFAULT_TEACHER_PASSWORD` in `Code.js`).
Go to `.../exec?role=teacher`, unlock with the default, then use the **Change Teacher
Password** section immediately.

## 3. Student and teacher URLs

* Students: `.../exec`
* Teacher: `.../exec?role=teacher`

## 4. Sheets

The three data sheets (`Purchases`, `DiscountCodes`, `StoreCredit`) are created
automatically, with headers, the first time any server function runs — no manual
setup needed. They're added as new tabs in whichever spreadsheet this script is
bound to.

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
