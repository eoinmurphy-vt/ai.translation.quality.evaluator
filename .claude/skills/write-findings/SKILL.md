---
name: write-findings
description: Writes the findings for an AI translation quality evaluation (summary, root-cause themes, language assessments, recommended actions, decisions for the client) from reviewers' evaluation forms or raw-vs-final exports, and builds the HTML report with them. Use this whenever someone wants to analyse, review, summarise or write up a drop or batch of evaluation forms, asks what reviewers or translators said about the AI output, or wants conclusions or recommendations from the TER results, even if they don't say "findings" or "report".
---

# Write findings for an evaluation drop

The analysis method lives in `prompts/findings_prompt.md`. This skill runs the tool, applies that method,
and rebuilds the report, so the findings are the same whoever produces them.

## Names used below

- `<drop>`: a short id for file names, e.g. `drop3`.
- `<Drop name>`: the title used in the report, e.g. `Drop 3`.

Ask for the forms folder (or the raw and final exports) and the drop name if you don't have them.

## Steps

1. **Collect context.** In `data/`, look for a client context file (`*context*.md`) and the previous drop's
   findings (`*findings*.md`), and use them if they exist. Tell the user which ones you used.

2. **Run the tool** from the repository root:

   ```bash
   python evaluate.py forms "<forms folder>" -o output/<drop>.xlsx --json output/<drop>.json
   ```

   For exports, use `compare` or `table` with the same `-o` and `--json` options (see the README). If the
   tool reports a problem with an input file, tell the user what it says. Don't edit their forms.

3. **Write the findings.** Read `prompts/findings_prompt.md` from the line `You are a senior localization
   quality analyst` to the end, and follow it. Use `output/<drop>.json` as the results JSON, together with
   any context file and previous findings.

   Load the JSON with Python and count with code rather than by eye. Put helper scripts and dumps in
   `output/work/`, which git ignores, never elsewhere in the repository. Keep the per-row theme list the
   prompt asks for there too.

4. **Save** only the Markdown the prompt asks for to `data/<drop>_findings.md`. It holds client content, so
   it belongs in `data/`, which git ignores.

5. **Build the report**, writing the workbook, the JSON and the HTML report together so they match:

   ```bash
   python evaluate.py forms "<forms folder>" -o output/<drop>.xlsx --json output/<drop>.json --title "<Drop name> review" --notes data/<drop>_findings.md
   ```

   The HTML report is written next to the workbook, as `output/<drop>.html`.

6. **Check it.**
   - Compare each figure in the findings with the JSON (per-language totals and severity counts), and each
     theme count with your per-row theme list.
   - Check that every quoted example appears exactly in the JSON.
   - Read the `Findings check:` lines the tool prints in step 5. They catch a missing bottom line, a language
     without an assessment, or an assessment whose name doesn't match the data (the scorecard reads those
     names). Fix the findings and rebuild until no warnings remain.
   - Fix any mismatch before you report back.

7. **Report back to the user** (in the conversation, not in the findings file) with:
   - where the HTML report, workbook and findings are
   - the top three findings
   - the decisions the client needs to make
   - anything you were unsure of, such as a back-translation you couldn't confirm. Suggest a linguist
     checks those before the report is shared.

## Keep client data out of git

Everything in `data/` and `output/` is client content. Don't commit or push it, and don't copy it anywhere
else in the repository.
