# Product Requirements Document (PRD)

**Project Name:** "Bug Roulette" — Software Testing Classroom Web Application  
**Document Version:** 1.2 (Product Focus)  
**Target Audience:** Software Testing Course Faculty & Students  

---

## 1. Executive Summary & Pedagogical Goals

### 1.1 Objective
"Bug Roulette" is a realistic, web-based user registration application designed for university-level Software Testing courses. On their first visit, each student is secretly and randomly assigned a distinct "Application Variant." While the interface appears identical on the surface, each variant is seeded with a specific defect representing a fundamental **Software Testing Type**.

### 1.2 Learning Outcomes
*   **Broaden Testing Perspective:** Move students beyond basic functional testing toward multi-dimensional testing (Security, Accessibility, Usability, Performance, Metamorphic, Localization, etc.).
*   **Encourage Independent Discovery:** Prevent students from copying peer bug reports, as adjacent classmates will encounter completely different failure modes.
*   **Practice Black-Box Methodologies:** Force students to use structured black-box heuristics, browser tools, metamorphic relations, and input variation to isolate and document root causes.

### 1.3 Operational Context & Student Deliverables
*   **External Bug Tracking:** The application itself **does not** contain a built-in bug reporting form. Students will log discovered defects in an external tool chosen by the instructor (e.g., Jira, GitHub Issues, Trello, or Google Forms).
*   **Deliverable:** Students submit formal bug reports externally, detailing steps to reproduce, expected vs. actual behavior, severity, and identifying the overarching **Testing Type** demonstrated by their variant.

---

## 2. Core User Flow (The Baseline App)

The application models a standard two-page onboarding flow:

1.  **Registration Page:**
    *   **Form Fields:** First Name, Last Name, Email Address, Password, Confirm Password, Country (Dropdown), and **Account Tier / License Count** (Numeric slider or input for team seats).
    *   **Form Actions:** "Submit Account" button and "Reset Form" button.
    *   **Expected Client Behavior:** Basic validation (required fields, matching passwords, standard email formatting, linear pricing calculations).
2.  **Dashboard Page:**
    *   A welcome screen displaying a success confirmation: *"Welcome aboard, [First Name]!"* along with a summary of their submitted profile data, assigned country, and selected account tier details.

---

## 3. Variant Assignment & Engine Behavior

1.  **Initial Load & Persistence:** When a student accesses the site for the first time, the application randomly assigns them an integer ID (`0` through `9`). This assignment persists across reloads and navigations within the same browser session.
2.  **Stealth Execution:** The student is given no visual indication that they are running a variant. The core application workflow looks normal until the specific testing scenario is triggered.
3.  **Variant Behaviors:**
    *   **UI/Visual Defects** alter visual rendering, viewport layout, or DOM interaction directly on the page.
    *   **Data/Process Defects** alter form processing, validation rules, metamorphic calculations, delays, or response handling when the form is submitted.

---

## 4. The Variant Matrix (The 10 Testing Types)

*Variant `0` serves as the control group ("Golden Path") to verify baseline application behavior.*

| Variant ID | Testing Type Category | Seeded Product Defect Description | Metamorphic / Oracle Expected Finding |
| :---: | :--- | :--- | :--- |
| **0** | **Control / Golden Path** | **No Defect:** Application behaves flawlessly end-to-end. | Baseline confirmation; zero defects found. |
| **1** | **Negative Testing** | **Unhandled Invalid Input:** Inputting special characters (`<script>`, `'`, `"`) or malformed data bypasses validation and causes a raw, unhandled server crash page with a stack trace. | System fails gracefully on unexpected inputs instead of showing clean error messages. |
| **2** | **Boundary Value Testing** | **Off-by-One Field Rules:** The stated requirement is *"Password must be 8–16 characters."* The app accepts 9–15 characters, but throws a validation error on **exactly 8** and **exactly 16** characters. | Boundaries (min/max limits) are miscalculated by the system. |
| **3** | **Performance / Latency** | **Uncommunicated System Delays:** Processing the registration takes an artificial 6 seconds, during which the UI provides zero loading feedback and leaves buttons active. | Lack of response feedback leads to user frustration and multiple unintended submissions. |
| **4** | **Security Testing** | **Sensitive Data Leakage:** On successful registration, the application redirects to the dashboard with the user's password visible in plain text in the address bar URL. | Confidential user credentials are exposed via GET query parameters. |
| **5** | **Accessibility (a11y)** | **Navigation & Assistive Obstacles:** Form inputs lack proper screen reader labels, keyboard `Tab` navigation order is scrambled, and primary buttons fail WCAG color contrast standards. | Application is unusable for screen readers or keyboard-only navigation. |
| **6** | **Usability Testing** | **Deceptive Visual Hierarchy:** The "Reset Form" button is styled as a prominent primary action, while the "Submit Account" button is styled as a muted, secondary gray action that looks disabled. | Visual styling misleads users into accidentally clearing their form data. |
| **7** | **Responsive Testing** | **Viewport Occlusion:** On mobile screen sizes (screen width under 600px), a fixed footer banner completely overlaps and blocks physical clicks to the submission button. | Layout breaks on small viewports, blocking critical user conversion paths. |
| **8** | **Localization (L10n)** | **Character Encoding Corruption:** Entering non-ASCII or Right-to-Left (e.g., Hebrew) names causes the system to display mangled text (`???` or broken glyphs) on the dashboard. | System fails to support international character sets and RTL languages. |
| **9** | **Metamorphic Testing** | **Violation of Monotonicity Relation:** Calculating team license pricing breaks the metamorphic relation $f(x_2) \ge f(x_1)$ for $x_2 > x_1$. Selecting 5 seats calculates a total of $50, but selecting 10 seats calculates a total of $30 (without any bulk discount notice), violating expected numerical properties. | Testing via Metamorphic Relations: Increasing input quantity $x$ yields an illogical reduction in total output cost $f(x)$ without explicit business rules. |

---

## 5. Support, Hints, & Instructor Controls

To support classroom dynamics, the app includes two distinct hidden key-combo mechanisms active from the moment the site is launched:

### 5.1 Student Hint Banner (`Ctrl + Shift + H` / `Cmd + Shift + H`)
*   **Availability:** Enabled from the start of the exercise.
*   **Purpose:** Students can toggle this shortcut at any point if they get stuck or need orientation on what dimension to explore.
*   **Behavior:** Toggles a clean, floating banner at the bottom corner of the screen.
*   **Content:**
    > 🕵️ **Exercise Hint:** Your assigned instance focuses on **[Name of Testing Type]**.  
    > *Focus your exploration on how the application handles this specific dimension!*
*   **Note:** Read-only for students; contains no controls to modify or reset the assigned variant.

### 5.2 Instructor Admin Panel (`Ctrl + Shift + A` / `Cmd + Shift + A`)
*   **Availability:** Restricted shortcut for faculty/TAs.
*   **Purpose:** Allows instructors to inspect, verify, or override a student's assigned variant during lab sessions, grading reviews, or live lectures.
*   **Behavior:** Opens a modal dialog with administrative controls.
*   **Panel Options:**
    *   **Current Instance Inspection:** Displays Variant ID, Category, and internal bug details.
    *   `[Reset Variant]`: Clears `localStorage` and assigns a new random variant.
    *   `[Force Variant Dropdown v]`: Instantly switches the active machine to any specific variant (0–9) for live demonstrations.