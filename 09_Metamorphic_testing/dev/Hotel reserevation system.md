# Software Requirements Specification: Hotel Reservation CLI System & Metamorphic Testing Workshop

## 1. Overview & Purpose
This system is a command-line interface (CLI) hotel reservation query tool built as an educational testbed for teaching **Metamorphic Testing**. 

The application evaluates hotel availability across a database of 100 hotels for specified date ranges and room requirements. To simulate the **Oracle Problem**, the underlying database is generated dynamically in-memory using a fixed random seed—preventing students from calculating expected results via direct database inspection or reading external files.

---

## 2. Bug Configuration Panel
At the top of the script, a dedicated configuration panel controls bug activation and threshold parameters:

# ==============================================================================
# BUG CONFIGURATION PANEL
# ==============================================================================
ACTIVATE_BUGS = True  # Master switch (True = Enable premeditated bugs, False = Flawless execution)


# Bug A: Date Shift Offset (Shifts query window forward or backward)
BUG_A_DAY_OFFSET = 7  # Must be positive integer (e.g., 0 , 3)

# Bug B: Non-Monotonic Total Capacity Threshold
# Note to teacher: Don't set the threshold to something too large. Remember: some hotels have only 20 rooms. Setting this at or close to 20 or 40 will trigger only when they test boundary values. Too low will trigger all the time. 
BUG_B_TOTAL_ROOMS_THRESHOLD = 6  # Positive integer (triggered when single + double + suite >= threshold)

# Bug C3: Parameter Rotation Threshold
# Note to teacher: Don't set the threshold to something too large. Remember: some hotels have only 20 rooms. But too low will trigger all the time. 
BUG_C_ROOM_THRESHOLD = 4  # Triggered when single > threshold OR double > threshold OR suite > threshold


---

## 3. Data Architecture & Generation Rules

### 3.1 Hotel Database Setup

* **Hotel Count:** Exactly 100 hotels (IDs: `1` to `100`).
* **Hotel Capacity:** Each hotel has $N$ total rooms, where $N \in [20, 40]$ (randomly chosen per hotel).
* **Room Distribution:**
* Room categories: `single`, `double`, `suite`.
* Every hotel **must** have at least 5 rooms of each type (`singles >= 5`, `doubles >= 5`, `suites >= 5`).
* The remaining $N - 15$ rooms are allocated randomly among the three room categories.



### 3.2 Date Range & Availability Mapping

* **Valid CLI Search Window:** October 1, 2026 (`01/10/26`) to September 30, 2028 (`30/09/28`).
* **Extended Data Generation Window:** October 1, 2026 to October 31, 2028.
* *Note:* The extra month (October 2028) is generated in-memory to prevent out-of-bounds array errors when `BUG_A_DAY_OFFSET` shifts dates forward, but CLI inputs beyond September 30, 2028 remain invalid during parsing.


* **Baseline Generation Algorithm:**
1. Generate random free room counts per room type per day for a 4-month baseline window: **October 2026 through January 2027**.
2. Map these 4 baseline months across the full timeline up to October 31, 2028:
* **31-day months** (Jan, Mar, May, Jul, Aug, Oct) mirror 31-day baseline patterns.
* **30-day months** (Apr, Jun, Sep, Nov) mirror 30-day baseline patterns.
* **February** (28 days) mirrors any baseline month using its first 28 days.




* **Encrypted / In-Memory Requirement:** The data must be generated in-memory at runtime using a fixed pseudo-random generator seed (e.g., `random.seed(42)`). No external unencrypted `.sql` or `.csv` files may be used.

---

## 4. CLI Parameters & Input Validation

### 4.1 Interface Syntax

```bash
python hotel_search.py <check_in> <check_out> [--single X] [--double Y] [--suite Z]

```

### 4.2 Parameter Specifications

1. **`check_in`** (Position 1, Required):
* Format: `d/mm/yy` or `dd/mm/yy` (e.g., `1/10/26` or `01/10/26`).
* Valid years: `26`, `27`, `28`.
* Must be a valid calendar date between `01/10/26` and `30/09/28`.


2. **`check_out`** (Position 2, Required):
* Same format and date range rules as `check_in`.
* Must be chronologically strictly greater than `check_in`.


3. **Room Flags** (Optional):
* `--single X`: Non-negative integer (Default = `0`).
* `--double Y`: Non-negative integer (Default = `0`).
* `--suite Z`: Non-negative integer (Default = `0`).



---

## 5. Core Search Logic & Premeditated Bugs

### 5.1 Correct Logic (`ACTIVATE_BUGS = False`)

1. Determine the stay duration: night dates from `check_in` up to `check_out - 1 day`.
2. A hotel can accommodate the request if and only if, for **every single night** in the stay duration:
* $\text{Free Singles} \ge X$
* $\text{Free Doubles} \ge Y$
* $\text{Free Suites} \ge Z$


3. **Output:** Output only a single integer representing the number of available hotels.

---

### 5.2 Premeditated Bug Logic (`ACTIVATE_BUGS = True`)

#### Bug A: Date Shift Bug

* **Trigger:** Active whenever `ACTIVATE_BUGS = True`.
* **Behavior:** Shift both `check_in` and `check_out` by `BUG_A_DAY_OFFSET` days before querying the database.
* Example: If `BUG_A_DAY_OFFSET = 7` and user requests Oct 10–12, the system actually queries Oct 17–19.
* Safety handling: If the shifted `check_in` or `check_out` exceeds October 31, 2028, cap it at the dataset boundary. 


* **Target Metamorphic Relation (MR):** **Sub-Period Inclusion / Overlap Invariance**.
* *Property:* If a hotel is free for a 10-day period ($T_1 \to T_2$), it must be free for any sub-period ($T_{sub1} \to T_{sub2}$) within that interval.



#### Bug B: Non-Monotonic Capacity Bug

* **Trigger:** Active when requested $(X + Y + Z) \ge \text{BUG\_B\_TOTAL\_ROOMS\_THRESHOLD}$.
* **Behavior:** When triggered, invert or distort the check such that hotels with **fewer** available rooms are improperly qualified (e.g., evaluating `free_rooms >= (requested_rooms % BUG_B_TOTAL_ROOMS_THRESHOLD)` or inverting the comparison logic).
* **Target Metamorphic Relation (MR):** **Quantity Monotonicity**.
* *Property:* Requesting more rooms of any category should never increase the count of available hotels ($Count(\text{Rooms } N+1) \le Count(\text{Rooms } N)$).



#### Bug C3: Parameter Rotation Bug

* **Trigger:** Active when $X > \text{BUG\_C\_ROOM\_THRESHOLD}$ OR $Y > \text{BUG\_C\_ROOM\_THRESHOLD}$ OR $Z > \text{BUG\_C\_ROOM\_THRESHOLD}$.
* **Behavior:** Rotate room parameters prior to availability calculation:

$$\text{Effective Singles} = Z \quad (\text{Suite input})$$


$$\text{Effective Doubles} = X \quad (\text{Single input})$$


$$\text{Effective Suites} = Y \quad (\text{Double input})$$


* **Target Metamorphic Relation (MR):** **Category Zero-Invariance & Monotonicity**.
* *Property:* Requesting 5 singles with 0 suites should return $\le$ hotels than requesting 4 singles with 0 suites. Under Bug C3, 5 singles converts to requesting 5 doubles, causing non-monotonic spikes in available hotels.



---

## 6. Workshop Gamification Summary

| Feature | Design Target |
| --- | --- |
| **Duration** | 30 minutes total (5m setup, 15m game, 10m debrief). |
| **Goal for Students** | Find contradictions between multiple test runs to prove a bug exists. |
| **Score System** | 100 points for a valid Metamorphic Relation defined; 250 points for catching a bug using an MR. |

```

```