# AI Translation Quality Evaluation

Measures how much reviewers had to change AI translations, language by language, and produces an Excel
workbook you can share. It uses Translation Edit Rate (TER), the standard measure of post-editing effort,
and keeps the reviewers' severity and category ratings alongside it.

- Reads the AI Human Evaluation Forms reviewers fill in, and measures every segment they logged
- Compares a raw AI export with the final export from Lokalise (or any TMS) to give a job-level TER,
  including the share of segments nobody had to change
- Reads JSON, CSV, Excel and XLIFF exports, and treats placeholders such as `{{name}}`, `%s` and HTML tags
  as single units
- Measures Japanese, Chinese and Thai per character, because they don't put spaces between words
- Checks that every placeholder, URL, link and tag in the source survives translation, plus your client's
  own placeholder rules (for example, no preposition before a placeholder that already includes one)
- Shows every change in Excel: removed text in red strikethrough, added text in green underline
- Writes every rate as an Excel formula, so anyone can check the numbers
- Optionally writes an HTML report to share: charts, a scorecard, reviewer comments, every item with its
  changes highlighted, and your own written findings at the top

The measurements, workbook and HTML report need only Python and one package. Only the optional written
findings use Claude.

## What you need

- **Python 3.9 or later.** On Windows, install it from [python.org](https://www.python.org/downloads/)
  and tick *Add python.exe to PATH* during setup.
- **The openpyxl package**, installed with `pip install -r requirements.txt` (see [Quick start](#quick-start)).
- Excel, or any spreadsheet app, to read the results.
- **Optional: Claude**, to write the findings: the bottom line, root causes, language assessments and
  recommendations at the top of the HTML report. In Claude Code it's `/write-findings`; a claude.ai account
  also works. Without Claude you still get the full workbook and HTML report, just without written findings.
  See [Writing the findings with Claude](#writing-the-findings-with-claude).

## Quick start

```bash
git clone https://github.com/eoinmurphy-vt/ai.translation.quality.evaluator.git
cd ai.translation.quality.evaluator
pip install -r requirements.txt
python evaluate.py selftest
python evaluate.py forms samples/forms --html
```

The workbook and the HTML report are saved in `output/`. Open the workbook on the **Summary** tab, or open
the `.html` file in any browser. The files in `samples/` are invented, so you can try every mode before using
real data.

## Three ways to measure

### 1. Evaluation forms: `forms`

```bash
python evaluate.py forms "data/Drop 2 forms"
```

Point it at a folder of forms or at individual `.xlsx`/`.xlsm` files. Each form's language comes from its
file name (`..._es_US.xlsm`, `..._zh-CN.xlsm`, `..._DE.xlsm`, `..._ro_RO_2.xlsm`), or from the
*Language* field on the form when the file name has none. Rows without both raw and corrected text, such
as general comments, are listed but not measured.

> Forms list only the segments reviewers chose to log, usually the problem ones. TER from forms shows how
> heavily those segments were rewritten. It doesn't measure the AI's quality across the whole job; use
> `compare` for that.

### 2. Raw AI vs final export: `compare` (job-level TER)

```bash
python evaluate.py compare --raw data/de_raw.json --final data/de_final.json --lang de-DE --source data/en.json
```

1. Export the language straight after AI pre-translation, before anyone edits it.
2. Export it again after review sign-off, in the same format.
3. Run `compare`. Segments are matched by key. Keys found in only one file are listed with a note.

| Export format | What is read |
|---|---|
| JSON | key → text, flat or nested (nested keys are joined with `::`) |
| CSV / Excel | key in the first column and text in the second, or name the column with `--text-column de` |
| XLIFF 1.2 / 2.0 | target text, keyed by `resname` or `id`; the source text is read too |

`--source` is optional and only adds the source text to the workbook. `--unit word` or `--unit char`
overrides the automatic choice.

### 3. A prepared sheet: `table`

```bash
python evaluate.py table data/pairs.xlsx
```

One row per segment, with any number of languages. Column names are matched loosely (case and spaces
don't matter):

| Column | Also accepted | Required |
|---|---|---|
| `key` | `key_id`, `id`, `string_id` | Yes |
| `language` | `locale`, `lang` | Yes |
| `raw` | `raw_ai`, `mt`, `ai_output` | Yes |
| `final` | `corrected`, `post_edited`, `reviewed` | Yes |
| `source` | `en`, `source_text` | No |

### Options for every mode

| Option | What it does |
|---|---|
| `-o`, `--output FILE` | Where to save the workbook (default: `output/TER_<mode>_<date>.xlsx`) |
| `--html` | Also write an HTML report, with the same name as the workbook |
| `--html-output FILE` | Write the HTML report to this file instead |
| `--title TEXT` | Title of the HTML report, e.g. `"Drop 2 review"` |
| `--notes FILE` | Markdown file with your written findings, shown at the top of the HTML report |
| `--no-ai-note` | Hide the "drafted with AI, AI can make mistakes" note. Use only when a person wrote the findings |
| `--json FILE` | Also save all results as JSON, for dashboards or further processing |
| `--rules FILE` | Client placeholder rules (default: `data/placeholder_rules.json`, if it exists). See [Placeholder checks](#placeholder-checks) |

`--html-output`, `--title` and `--notes` each turn on the HTML report, so `--html` isn't needed with them.

`python evaluate.py <mode> --help` lists every option.

## The workbook

| Tab | Contents |
|---|---|
| **Summary** | One row per language: segments, severity counts (forms), unchanged segments (exports), TER and character edit rate, plus a total row |
| **Segments** | Every segment: source, raw AI, final text, the changes highlighted, reviewer rating and comment (forms), and the edit counts |
| **Forms** | Forms mode only: each form's team, project, word count and overall comment |
| **Placeholder checks** | One line per placeholder, URL, link or tag problem: where it is, the level, what's wrong and whether review fixed it |
| **About** | Inputs, date, and how the numbers are calculated |

The Summary and Segments tabs also count placeholder errors in the raw AI output, errors left in the final
text, and source issues.

As a rule of thumb for TER:

| TER | Editing needed |
|---|---|
| Under 10% | Light |
| 10–30% | Moderate |
| 30–50% | Heavy |
| Over 50% | Close to a retranslation |

TER can go over 100% when the reviewer's version is much shorter than the AI's.

## The HTML report

One self-contained `.html` file that opens in any browser and needs no internet connection, so it can be
emailed or put on SharePoint as it is. It contains:

- **Headline counts**: items or segments, severity totals, and how much of the text changed. With findings,
  their bottom line is shown here too.
- **Findings** (when you pass `--notes`), with a note that they were drafted with AI and AI can make mistakes
- **TER by language**: every segment as a dot, with each language's overall TER marked. Below it, *Reading
  these numbers* gives the caveats for this data: languages resting on one or two segments, languages that
  also logged Minor items or left severity blank, and languages measured per character.
- **Scorecard**: one row per language. With findings, it shows each language's assessment and evidence
  rating. Without them, it shows the TER band for the logged segments, labelled as an edit level, not a
  verdict.
- **Issue profile** (forms): items by severity and by category, and how the segments split by amount of
  editing. For export comparisons, the editing split is shown on its own.
- **Placeholder checks**: per language, how many items have placeholders, URLs, links or tags, errors in
  the AI output, how many review fixed, errors left in the final text and source issues, then a list of
  every problem found, the ones left in the final text first
- **Detail**: each language's assessment (with findings), each form's overall comment, then every item
  (forms) or every edited segment (exports, most edited first) with its changes highlighted and any
  placeholder check results. A switch shows the raw and final text in full instead.
- **Form check** (forms): which header fields each form is missing, items without a severity, category or
  comment, a locale code typed into the team field, Minor items, cells holding two AI outputs, and the
  content each form covers
- **Method**: how the numbers are calculated, and which files were read

Every chart and table lists languages in the same order: highest TER first.

The figures, charts, caveats, form check and placeholder checks are calculated directly from the data,
without AI. The
conclusions come from reading the reviewers' comments. Write your findings in a Markdown file and pass it
with `--notes`, and they appear at the top of the report under **Findings**:

```bash
python evaluate.py forms "data/Drop 2 forms" --title "Drop 2 review" --notes data/drop2_findings.md
```

The notes file supports headings (`#`, `##`), paragraphs, bullet and numbered lists, `**bold**`, `*italic*`,
`` `code` ``, `> quotes` and `[links](https://...)`. Three conventions link it to the rest of the report:

- **`# Bottom line`**: one or two sentences, shown at the top of the report.
- **`# Language assessments`**: lines like
  `- **Japanese**: Not usable as-is (evidence: strong, 10 items). Reason.` fill the scorecard and each
  language section. Use the language names exactly as the report shows them. Statuses are *Not usable
  as-is*, *Needs targeted fixes*, *Usable with light edits*, *Good* or *Can't assess*.
- **Theme headings** ending in `(Critical)`, `(Major)`, `(Minor)` or `(Decision needed)` get a coloured tag.

After building the report, the tool prints `Findings check:` lines if the bottom line is missing, a
language has no assessment, or an assessment's name doesn't match a language. See
`samples/findings_example.md` for a complete example.

## Writing the findings with Claude

`prompts/findings_prompt.md` holds the analysis method: how to read every item, trace each error to its
root cause, group causes into themes, assess each language and recommend actions. It also sets the rules
that keep conclusions honest (exact counts, what form-based TER can and can't show, glossing every
example) and the output format the report expects. The tool itself still needs no AI; only this step uses
Claude.

**With Claude Code** (recommended): open this folder in Claude Code and ask, for example, *"write up the
Drop 3 forms in data/Drop 3"*, or type `/write-findings`. The skill in `.claude/skills/write-findings/`:

1. runs the tool
2. follows the prompt and checks the numbers against the results
3. saves `data/<drop>_findings.md`
4. rebuilds the HTML report with the findings at the top

**With claude.ai**: run the tool with `--json output/<drop>.json`, start a new chat, attach the JSON, paste
everything below the line in `prompts/findings_prompt.md`, and save the reply as `data/<drop>_findings.md`.
Then build the report with `--notes`.

To keep conclusions consistent between drops:

- **Record decisions in a context file.** Copy `prompts/context_template.md` to `data/<client>_context.md`
  and record product names, what each placeholder means, style rules and decisions the client has made.
  Both routes use it. Rules the tool can check go in `data/placeholder_rules.json` (see
  [Placeholder checks](#placeholder-checks)).
- **Compare with the last drop.** Give the previous drop's findings as well, and the new findings will say
  what changed.

AI can make mistakes. The report says so next to the findings (and next to the bottom line), but read the
findings yourself before you share them, and have a linguist check any example where the exact meaning
matters.
Evaluation data is client content, so check that your agreement with the client allows it to be processed
by the AI service you use.

## Placeholder checks

Every run checks each segment's placeholders, URLs, links and tags, without AI:

| Check | Level | What it flags |
|---|---|---|
| Placeholders | Error | A placeholder missing, added, renamed or appearing a different number of times than in the source |
| Broken placeholder | Error | Braces that don't match, such as `{{name}` or `{name}}`, or a name that isn't valid, such as a translated one |
| URL path | Error | Text after a URL placeholder that was changed, e.g. `{{baseUrl}}/login` translated |
| Link | Check | A link target or URL that differs from the source |
| Tags | Check | An HTML tag missing or added |
| Client rules | Error or Check | A word before (or a suffix after) a placeholder that already includes it, as set in the rules file |
| Source issue | Source issue | The same client rules broken in the source: report these to the client |

`{{name}}`, Lokalise's on-screen `1:name` and Lokalise's `[%1$s:name]` count as the same placeholder, so
the way text was pasted doesn't cause false errors. Each problem gets a status: *Fixed in review*, *Left in
final* (still wrong after review: fix before release), *Introduced in review* or *Report to client*.

On forms, only the logged items are checked. With full exports (`compare` or `table`), every string is
checked, which is where the checks pay off.

**Client rules.** Some placeholders already include words: a "to" phrase that becomes "to France" in
English and "nach Frankreich" in German, or a name that includes its article. Typing a preposition or an
article before them doubles it. Rules for these go in a JSON file. Copy
`config/placeholder_rules.example.json` to `data/placeholder_rules.json` and edit it. The tool reads that
file automatically, or the one you pass with `--rules`. Each rule gives:

- `placeholders`: a regular expression for the placeholder names it covers
- `not_before`: for each language code, the words that must not come right before them
- `no_suffix_after`: languages where letters stuck after them are wrong (Turkish case endings)
- `level`: `Error`, or `Check` when the word is sometimes right
- `replaces` (optional): a placeholder that may stand in for another, reported as a note rather than an
  error

The source is checked against the `source_language` list, and problems there are reported as source
issues. Have a linguist confirm each language's word list. Client rules name the client's placeholders, so
keep them in `data/`, which git ignores.

## Using a different form template

`config/form_layout.json` says where everything is on the form: the sheet name, the first data row, which
column holds the source, raw AI, corrected text, category, severity and comment, and which cells hold the
header fields. The defaults match the AI Human Evaluation Form. For another template, edit the file, or
copy it and run with `--layout my_layout.json`.

The same file has `language_overrides`, which replaces a language code after it is read. For example,
`"ja-US": "ja"` shows a form named `..._JP_US.xlsm` as *Japanese* rather than *Japanese (US)*. Add an entry
whenever a file name gives a language an odd label.

## How it's calculated

- **TER** = (tokens added + removed + replaced + phrase moves) ÷ tokens in the final text, using the
  shift-aware algorithm from tercom and sacreBLEU (phrases up to 10 tokens, moved up to 50 positions).
  Case is ignored. `python evaluate.py selftest` checks it against the published reference example
  (Snover et al., 2006: 4 edits over 13 words).
- **Tokens** are words and punctuation marks. Languages written without spaces (Japanese, Chinese, Thai,
  Lao, Khmer, Burmese) are measured per character. Numbers such as `10,000` count as one token.
- **Placeholders and tags** count as one token each. `{{name}}` and Lokalise's on-screen form `1:name`
  are treated as the same, so differences in how text was pasted aren't counted as edits.
- **Character edit rate** = character-level edit distance (spaces ignored) ÷ characters in the final
  text. It doesn't depend on word boundaries, so use it to compare languages measured in different units.

TER counts edits, not their importance: fixing a wrong amount counts the same as fixing a comma. Read it
alongside the reviewers' severity ratings and comments.

## Keeping client data out of GitHub

Evaluation forms, exports, workbooks and HTML reports contain client content. Put input files and findings
notes in `data/`; results go to `output/`. Git ignores both folders, and also ignores `.xlsx`, `.xlsm`,
`.csv`, `.json`, `.html` and XLIFF files anywhere except `samples/` and `config/`. Check `git status` before
every commit.

## Tests

```bash
python -m unittest discover -s tests
```

## Project layout

```
evaluate.py               Command-line entry point
translation_quality/      The tool
  ter.py                  TER algorithm
  text.py                 Tokens, placeholders, per-segment measures, change highlighting
  languages.py            Language codes from file names and form fields
  readers.py              Reading forms, exports and tables
  stats.py                Per-language totals and editing levels
  excel.py                Writing the workbook
  html_report.py          Writing the HTML report
  checks.py               Placeholder, URL, link and tag checks, and client placeholder rules
  cli.py                  Command-line options
config/form_layout.json   Where things are on the evaluation form
config/placeholder_rules.example.json   Example client placeholder rules (copy to data/)
prompts/                  The findings prompt and the client context template
.claude/skills/           The Claude Code skill that writes findings (/write-findings)
samples/                  Invented test files and an example findings file (make_samples.py recreates the data)
tests/                    Unit and end-to-end tests
data/                     Your input files (ignored by git)
output/                   Results (ignored by git)
```

### 📝 License

This project is licensed under the Apache 2.0 License. © 2026 Vistatec, Ltd.

---
