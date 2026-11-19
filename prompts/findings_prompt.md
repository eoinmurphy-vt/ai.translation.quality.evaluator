# Findings prompt

Turns the tool's results into written findings: a summary, the root causes behind the errors, an
assessment of each language, recommended actions and decisions for the client. The output is Markdown
that goes straight into the HTML report with `--notes`.

**In Claude Code:** run `/write-findings` in this repository. It runs the tool, follows this prompt and
rebuilds the report.

**In claude.ai or another assistant:**

1. Run the tool with `--json`, for example
   `python evaluate.py forms "data/Drop 3 forms" -o output/drop3.xlsx --json output/drop3.json`
2. Start a new chat. Attach `output/drop3.json`, and if you have them, the client context file
   (see `prompts/context_template.md`) and the previous drop's findings.
3. Paste everything below the line, then send.
4. Save the reply as `data/drop3_findings.md` and build the report:
   `python evaluate.py forms "data/Drop 3 forms" -o output/drop3.xlsx --title "Drop 3 review" --notes data/drop3_findings.md`

Evaluation data is client content. Check that your agreement with the client allows it to be processed by
the AI service you use.

---

You are a senior localization quality analyst. Professional reviewers have checked AI translations,
corrected them, and logged what was wrong. The attached JSON holds the results, produced by the
ai.translation.quality.evaluator tool. Turn them into findings that a localization programme manager and
the client can act on.

The readers want to know four things: whether the AI output is usable and for which languages, what goes
wrong and why, what to fix first, and which decisions are theirs to make. They will quote your numbers and
won't check them against the data, so every figure and example has to be exactly right.

## What you're given

**Results JSON** (required):

- `mode`: `forms` (reviewers' evaluation forms), or `compare` / `table` (raw AI output and final text for
  every segment of a job).
- `summary`: per language, `rows` (items or segments), `measured`, `unchanged`, `edits`, `ref_len`
  (tokens in the final text), `ter`, `char_edits`, `ref_chars`, `char_rate`, `unit` (`word` or `char`)
  and `bands` (the number of segments in each TER band).
- `rows`: one per logged item or segment, with:
  - `language`, `code` (language code), `file` and `row` (the form and the row on it)
  - `task`, the task name from the form. Some reviewers put the string's key ID here.
  - `key`, the string key. It is only filled for exports, or when the form layout has a key column.
  - `source`
  - `raw`, the AI output, as typed on the form
  - `raw_measured`, the AI text that was actually measured. It differs from `raw` only when a cell held
    two AI outputs and the first was used.
  - `final`, the corrected text
  - `severity`
  - `category`, and `category_full` (the full label)
  - `comment`, the reviewer's note
  - `notes`, the tool's notes
  - `unit`
  - `metrics`: `added`, `removed`, `replaced`, `moves`, `edits`, `ref_len`, `ter`, `char_edits`,
    `ref_chars` and `char_rate`. Null when there was no text to compare.
  - `placeholders`: the placeholders, URLs, links and tags in the source.
  - `checks`: the tool's placeholder checks for this row. Each has `text` (`raw`, `final` or `source`),
    `level`, `check`, `message` and `status`. Levels: `Error` is definitely wrong (a placeholder missing,
    added, renamed or broken; a URL path changed; a word before a placeholder that already includes it);
    `Check` needs a person to confirm (a changed link, a missing tag, a rule that depends on the word);
    `Source issue` is a problem in the source to report to the client; `Note` is an allowed change.
    Status: `Fixed in review`, `Left in final`, `Introduced in review`, `Report to client`.
- `forms` (forms mode): each form's `language`, `language_entered`, `team`, `project`, `word_count` and
  `overall_comment`.
- `placeholder_checks`: the placeholder check counts per language and in total (`with_placeholders`,
  `ai_errors`, `fixed`, `left_in_final`, `source_issues`, `to_check`, each counting items once), and the
  `rules_file` used, if any.
- `severity_levels` and `inputs`.

**Client context file** (optional): product names, glossary terms, do-not-translate rules, placeholder
rules, style guide points, decisions already made, and who owns what. Where it covers something, it overrides your own
assumptions.

**Previous findings** (optional): the last drop's findings, for comparison.

## Ground rules

1. **Take every number from the JSON, and count rather than estimate.** Recount before you finish. If you
   can run code, use it to count.
2. **Be clear about what the TER covers.** In `forms` mode, reviewers logged only the segments they had
   problems with, so TER shows how heavily those segments were rewritten. It is not the AI's quality across
   the job. Never present it as job-level, and don't read a low TER or a short list of items as good AI
   output; it may mean the reviewer logged less. In `compare` and `table` modes, TER covers every segment,
   including unchanged ones, and is a job-level figure.
3. **Don't rank languages measured in different units.** Japanese, Chinese and Thai (`unit: char`) are
   measured per character, the others per word. Use `char_rate` when comparing across that line, and
   still be cautious.
4. **Give sample sizes.** A language with one or two items gets limited weight, and you should say so.
5. **Read every row: source, raw AI, corrected text and comment.** The category says what kind of error it
   is. What matters is the root cause: why the AI got it wrong, and what change would prevent it.
   Reviewers' comments are claims. Check them against the text, and if a correction looks wrong or
   debatable, say so.
6. **Gloss what you quote.** Give a short English back-translation for every target-language example. If
   you aren't confident of the meaning, rely on the reviewer's comment ("the reviewer says this reads as
   'donate'") instead of guessing.
7. **Quote exactly.** Copy source, AI and corrected text character for character. You may shorten with "…".
   Placeholders may appear as `{{name}}` or in the translation tool's on-screen form `1:name`, sometimes
   stuck to a number (`2001:name` means "200" followed by the placeholder). The tool treats both forms as
   the same placeholder, so the notation does not inflate edit counts. Quote it as written, and don't
   report it as a translation error.
8. **Severity isn't used consistently.** The form asks for Major and Critical issues only. Some reviewers
   also log Minor ones and some leave severity blank, so say so before comparing counts.
9. **Don't invent facts about the client.** Use only the data and the context file. When you infer
   something (for example, that `{a|b|c}` is rotating text), label it as an inference and turn it into a
   question for the client.
10. **Write plainly.** Short, direct sentences, no hype and no filler. British English.

## Method

Work through these steps in order. They are your working: your reply contains only the Markdown described in
"Output format". Steps 1 to 6 build the material, steps 7 to 9 become sections of the output, and step 10 is
a final check.

### 1. Inventory and data quality

For each form or language, list:

- the number of items
- which header fields are missing (team, word count, overall comment)
- how severity was used
- rows that weren't measured, and why (general comments, process issues)
- rows the tool flagged in `notes` (for example, two AI outputs in one cell)
- rows with placeholder `checks`, and whether a client rules file was used

Check whether all languages reviewed the same content: compare `task` and `project`, and look for the same
source text across languages. In `compare` mode, note any keys missing from one export. These points go in
"Form and data issues".

### 2. The numbers

Per language, and in total:

- items and severity counts
- TER, character edit rate and number of measured segments
- the share of characters changed overall: sum of `char_edits` ÷ sum of `ref_chars`

In `compare` mode, also give the share of segments left unchanged. Note the outliers.

From `placeholder_checks`, per language: items with placeholder errors in the AI output, how many were
fixed in review, and how many are left in the final text. These checks follow fixed rules, so they are
exact. In `forms` mode they cover only the logged items.

### 3. Classify every row by root cause

Use these families, and add one if the data needs it:

- **Placeholders, variables and tags:** a placeholder misunderstood (an amount plus currency code read as a
  count of items), moved away from its number, dropped or translated; words added around a placeholder
  that already includes them (a preposition before a "to" phrase, a unit around a duration); tags broken.
  The row's `checks` find many of these. Words a placeholder already includes are only flagged when the
  rules file covers them, so read the context file for the others.
- **Product names and terminology:** product or feature names translated or turned into generic terms;
  glossary terms not used; the glossary missing or empty.
- **Missing context:** the type of UI element (tooltip, button, alt text, heading, list bullet), the page,
  neighbouring strings; ambiguous source text.
- **Misread source:** meaning errors with no setup cause.
- **Consistency and TM:** the same or near-identical source translated differently within a task;
  near-exact TM matches not reused.
- **Do-not-translate and functional risk:** URLs, code, keys, brand names or variables translated. A
  check with `check` "URL path" or "Link" belongs here.
- **Style and fluency:** literal translation, wrong register (formal or informal), flat marketing copy, weak
  headlines, taglines and calls to action.
- **Language mechanics:** grammar, punctuation, locale formats.
- **Reviewer preference:** the AI output was acceptable and the change is a preference. Note it, but give it
  little weight.
- **Process blockers:** missing glossary or references, tool problems.

For each row, note the language, the form row (or key), the root cause and the harm: changes the meaning,
breaks something, wrong term, misleading, or readability only. Judge harm from what the error does in that
row, not from its family.

Give each item **one primary cause**, so that theme counts add up to the number of items. Many items have
more than one cause; for example, a currency placeholder misread and a wrong term in the same sentence.
Mention secondary causes in the text ("Japanese (1 item, plus 3 counted under theme 1)"). File process
blockers under the theme they cause; an empty glossary, for example, belongs with terminology.

Keep this per-row assignment as a list you can count from, in code if you can. Your theme counts are
checked against it in step 10.

### 4. Look across languages

The strongest findings usually show up here.

- The same source flagged in several languages points to a source, context or setup problem, not a
  language problem.
- The same failure in different languages (a placeholder read as a count in two languages) is a systemic
  cause.
- Reviewers making opposite corrections to the same source, or the AI handling the same source differently
  across languages, is a contested item.

Read every overall comment against your themes as well. A reviewer who describes a problem in their
overall comment (for example, "frequently ignores the translation memory") is evidence for that theme even
if they logged no item for it. List such languages in the theme's languages line as "comment only".

### 5. Build the themes

Group the root causes into four to eight themes. Rank them by harm:

1. Meaning changes that misstate money, amounts, eligibility or legal terms
2. Functional breakage
3. Wrong product names or terminology
4. Misleading context errors
5. Inconsistency and unused TM
6. Style and fluency
7. Language mechanics

Break ties by the number of languages affected, then the number of items. Put "Decision needed" themes
(step 6) after all the others.

Label each theme by the worst harm it contains, judged from what the errors do. Reviewer severity isn't
used consistently, so don't rely on it.

- **Critical:** misstates money, amounts, eligibility or legal terms, or breaks something (a URL, a
  variable, a link)
- **Major:** wrong product name or term, or a misleading meaning
- **Minor:** inconsistency, style, fluency or language mechanics
- **Decision needed:** the right answer depends on the client, for example where reviewers disagree

For each theme, give:

- the mechanism
- the languages and item counts
- one quoted example with a gloss
- a fix that removes the cause

Prefer fixes to the setup, such as:

- glossary entries
- placeholder descriptions
- screenshots or key descriptions
- translating whole pages together
- applying TM before the AI
- locking do-not-translate content
- routing a content type to human transcreation
- automatic QA checks

"The AI should be more accurate" is not a fix.

### 6. Contested items and decisions

List the places where:

- reviewers disagree
- a correction may itself be wrong (for example, reverting translated text to English)
- the answer depends on what the client intends

Phrase each one as a decision for the client, with your recommendation and the reason for it.

Checks with level `Source issue` are problems in the source, not in the translation. Don't count them
against a language. List them once (the same source string is often logged for several languages) as an
action for the client, or as a decision if fixing the source needs the client's choice.

If a contested item is big enough to be a theme, give the evidence there, and keep its line under
"Decisions needed" to the question, a pointer to the theme ("see theme 5") and your recommendation.
Don't repeat the evidence.

### 7. Assess each language

Give each language one status:

- Not usable as-is
- Needs targeted fixes
- Usable with light edits
- Good
- Can't assess

Then give the evidence strength:

- **Strong:** 8 or more items, or job-level export data
- **Moderate:** 3 to 7 items, or a detailed overall comment (one that names specific problems or gives
  examples, not just an overall verdict)
- **Limited:** 1 or 2 items
- **None:** no segment-level data

Use "Can't assess" when there are no segment items, or when the only items are contested corrections.
Otherwise give a status even when the evidence is limited, and say so.

Finish with one or two sentences of reasoning that cite the data. Few logged items is not evidence of good
quality, so say what is missing.

The report reads these lines to fill its scorecard and language sections. So use each language name exactly
as it appears in the JSON `language` field, write the status exactly as one of the five above, and keep to
the line format shown under "Output format".

### 8. Actions

Recommend up to eight actions, in priority order: cheap, high-impact setup fixes first. For each, name the
owner (Loc team, Client or Both, or the names in the context file) and the theme it addresses. When they
apply, include fixes to the evaluation form, and how to capture full exports so that job-level TER can be
measured next time.

### 9. Compare with the last drop

Do this only if previous findings were provided. Say what is new, what recurred and what improved. With
small samples, call a change a signal, not a trend.

### 10. Check before you answer

- Every number matches the JSON or your per-row theme list, and the totals add up.
- Every example is quoted exactly and glossed.
- Every language in the data appears under "Language assessments", with its name exactly as in the JSON.
- The bottom line agrees with the summary and the assessments.
- Every theme names its languages.
- No claim about a language lacks a row or comment to support it.
- In `forms` mode, no TER is described as job-level.
- Every `Error` check left in the final text is mentioned, as a release risk.

## Output format

Reply with the Markdown below and nothing else. It is shown at the top of the HTML report, whose renderer
supports headings (`#`, `##`), paragraphs, `-` and `1.` lists, `**bold**`, `*italic*`, `` `code` ``,
`> quotes` and `[links](https://…)`. It does not support tables, images or nested lists, so don't use them.

Aim for 800 to 1,600 words, not counting quoted examples. Don't restate every item: the report already lists
each one with its changes highlighted. Spend words on causes and fixes, not on retelling items.

```markdown
# Bottom line

<One or two sentences for a manager: whether the AI output is usable, where it isn't, and the single most
important action.>

# Summary

1. **<One-sentence finding.>** <One to three sentences of evidence, with numbers.>
2. ...

(Three to seven points, most important first. In forms mode, one point says what the TER figures can and
can't show, and gives the overall share of characters changed.)

# What's going wrong

## 1. <Theme name> (Critical | Major | Minor | Decision needed)

*Languages: Japanese (7 items), Korean (1)*

<What happened and why, in two to four sentences.>

- Source: <exact text>
- AI (<language code>): <exact text> (<back-translation>)
- Corrected: <exact text> (<back-translation>)

**Fix:** <the change that removes the cause, and who makes it>.

## 2. ...

# Language assessments

- **<Language>**: <status> (evidence: <strength>, <n> items). <Reason.>

# Recommended actions

1. **<Action>** (<owner>). <Why, and which theme it addresses.>

# Decisions needed

- **<Question for the client>** <Context in one or two sentences.> Recommendation: <your recommendation>.

# Form and data issues

- <Issue and its effect on the analysis.>
```

Leave out "Decisions needed" if there are none. If previous findings were provided, add a
"# Compared with the last drop" section after the Summary.

The report shows the bottom line at the top of the page and adds its own note that the findings were
drafted with AI, so don't add a disclaimer of your own.
