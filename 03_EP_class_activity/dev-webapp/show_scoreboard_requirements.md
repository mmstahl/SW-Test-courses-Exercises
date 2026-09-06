# Software Requirements Specification (SRS): Graphical Live Scoreboard (`show_scoreboard.py`)

## 1. Scope & Execution Mechanics
1.1 The program **shall** function as a standalone cross-platform GUI utility driven by Python's built-in `tkinter` runtime framework.
1.2 The program **shall** parse execution parameters via the command line interface using the following structural rules:
    * **Argument 1 (Mandatory):** The public Google Spreadsheet Alphanumeric Identifier String.
    * **Argument 2 (Optional):** An integer parsing candidate defining the base typographical font size for the student roster list display.
1.3 If the second argument is missing or invalid, the program **shall** automatically fall back to a default base font size value of **11**.

## 2. Background Data Ingestion Pipeline
2.1 The program **shall** execute all network operations asynchronously within an isolated background worker thread to prevent the main user interface layout thread from hanging or freezing.
2.2 The worker thread **shall** fetch remote data by compiling an HTTP GET link requesting a public CSV export targeting a sheet tab explicitly named `Scoreboard`:
    ```
    [https://docs.google.com/spreadsheets/d/](https://docs.google.com/spreadsheets/d/)<GOOGLE_SHEET_ID>/gviz/tq?tqx=out:csv&sheet=Scoreboard
    ```
2.3 The background sampling thread **shall** execute automatically on a recurring timer cycle looping precisely every 2000 milliseconds ($2\text{ seconds}$).
2.4 If a network dropout or timeout occurs, the processing loop **shall** fail silently, preserving the current state of active student records visible on-screen.

## 3. Dynamic Header Resolution & Row Filtering Logic
3.1 The data parser **shall** inspect the first row of the CSV file (Index 0) to resolve column positions dynamically by header strings (case-insensitive):
    * The column containing the student identifier **shall** be located by matching the token `"student name"`.
    * The column containing the student score metric **shall** be located by matching the token `"total score"`.
3.2 If the dynamic header mapping fails to locate the `"total score"` column, the parser **shall** fall back to checking the final column array element position in the row matrix.
3.3 The parser **shall** process student record rows starting from index 1 up to a hard operational row limit index boundary of **51**.
3.4 The script **shall** drop rows if the parsed name string matches an empty text block, a raw sequence of double quotes (`""`), or a literal string text value of `0`.

## 4. Sorting & Three-Column Layout Grid
4.1 The program **shall** sort the parsed student records globally in descending order based on their numerical total scores. The highest-scoring student **shall** occupy position number 1.
4.2 The window layout size **shall** initialize at dimensions measuring 1200 horizontal pixels by 580 vertical pixels ($1200 \times 580$) using a light presentation theme background color (`#ffffff`).
4.3 The app canvas **shall** divide student entries across a balanced three-table presentation grid containing a total of 7 structural columns:
    * **Column 1 & 2 (Table Left):** Positions 1 through 15 Student Names and Total Score Value Blocks.
    * **Column 3 (Spacer Left):** A visual buffer column (`#ffffff`) providing distinct separation.
    * **Column 4 & 5 (Table Center):** Positions 16 through 30 Student Names and Total Score Value Blocks.
    * **Column 6 (Spacer Right):** A secondary visual buffer column (`#ffffff`).
    * **Column 7 & 8 (Table Right):** Positions 31 through 45 Student Names and Total Score Value Blocks.
4.4 Individual entries **shall** be indexed sequentially using standard two-digit layout counts format (` 1. Name`, `16. Name`, `31. Name`).

## 5. Dynamic Cell Heatmap Color Gradients
5.1 Score box backgrounds and font colors **shall** adapt dynamically relative to the current maximum positive ($M_{pos}$) and absolute maximum negative ($M_{neg}$) scores calculated across the active student group:
5.2 **Zero Baseline State ($Score = 0$):**
    * Background Color **shall** match `#e0e0e0`. Font color **shall** match `#222222`.
5.3 **Positive Grade Scale ($Score > 0$):**
    * The cell color **shall** scale smoothly from a light pastel green (`#e8f5e9`) when approaching 0, up to a vivid emerald green (`#4caf50`) at the maximum positive boundary value.
    * The RGB values for a positive score calculation **shall** conform to:
      $$Ratio = \min\left(\frac{Score}{M_{pos}}, 1.0\right)$$
      $$R = \text{int}(232 - 156 \times Ratio)$$
      $$G = \text{int}(245 - 70 \times Ratio)$$
      $$B = \text{int}(233 - 153 \times Ratio)$$
    * The foreground font color for all positive cells **shall** remain a high-contrast dark forest green tone (`#0e3a10`).
5.4 **Negative Grade Scale ($Score < 0$):**
    * The cell color **shall** scale smoothly from a soft light rose red (`#ffebee`) when approaching 0, down to a deep warning crimson red (`#f44336`) at the maximum negative penalty layout boundary.
    * The RGB values for a negative score calculation **shall** conform to:
      $$Ratio = \min\left(\frac{|Score|}{M_{neg}}, 1.0\right)$$
      $$R = \text{int}(255 - 11 \times Ratio)$$
      $$G = \text{int}(235 - 168 \times Ratio)$$
      $$B = \text{int}(238 - 184 \times Ratio)$$
    * The foreground font color for all negative cells **shall** remain a high-contrast dark maroon tone (`#4a0d0d`).