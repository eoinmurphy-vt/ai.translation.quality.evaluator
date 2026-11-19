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
- Shows every change in Excel: removed text in red strikethrough, added text in green underline
- Writes every rate as an Excel formula, so anyone can check the numbers
- Optionally writes an HTML report to share: charts, a scorecard, reviewer comments, every item with its
  changes highlighted, and your own written findings at the top

It runs on its own: Python plus one package. No AI tools or Claude Code are needed.

## What you need

- **Python 3.9 or later.** On Windows, install it from [python.org](https://www.python.org/downloads/)
  and tick *Add python.exe to PATH* during setup.
- **The openpyxl package**, installed with `pip install -r requirements.txt` (see below).
- Excel, or any spreadsheet app, to read the results.

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
| `--json FILE` | Also save all results as JSON, for dashboards or further processing |

`--html-output`, `--title` and `--notes` each turn on the HTML report, so `--html` isn't needed with them.

`python evaluate.py <mode> --help` lists every option.

## The workbook

| Tab | Contents |
|---|---|
| **Summary** | One row per language: segments, severity counts (forms), unchanged segments (exports), TER and character edit rate, plus a total row |
| **Segments** | Every segment: source, raw AI, final text, the changes highlighted, reviewer rating and comment (forms), and the edit counts |
| **Forms** | Forms mode only: each form's team, project, word count and overall comment |
| **About** | Inputs, date, and how the numbers are calculated |

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

- Headline counts: items or segments, severity totals, and how much of the text changed
- **TER by language**: every segment as a dot, with each language's overall TER marked
- **Scorecard**: one row per language, with an editing level from the rule of thumb above
- **Issue profile** (forms): items by severity and by category, and how the segments split by amount of
  editing. For export comparisons, the editing split is shown on its own.
- **Detail**: each form's overall comment, then every item (forms) or every edited segment (exports, most
  edited first) with its changes highlighted. A switch shows the raw and final text in full instead.
- **Method**: how the numbers are calculated, and which files were read

The tool can't write conclusions; those come from reading the reviewers' comments. Write your findings in a
Markdown file and pass it with `--notes`, and they appear at the top of the report under **Findings**:

```bash
python evaluate.py forms "data/Drop 2 forms" --title "Drop 2 review" --notes data/drop2_findings.md
```

The notes file supports headings (`#`, `##`), paragraphs, bullet and numbered lists, `**bold**`, `*italic*`,
`` `code` ``, `> quotes` and `[links](https://...)`. See `samples/findings_example.md`.

## Using a different form template

`config/form_layout.json` says where everything is on the form: the sheet name, the first data row, which
column holds the source, raw AI, corrected text, category, severity and comment, and which cells hold the
header fields. The defaults match the AI Human Evaluation Form. For another template, edit the file, or
copy it and run with `--layout my_layout.json`.

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
  cli.py                  Command-line options
config/form_layout.json   Where things are on the evaluation form
samples/                  Invented test files and an example findings file (make_samples.py recreates the data)
tests/                    Unit and end-to-end tests
data/                     Your input files (ignored by git)
output/                   Results (ignored by git)
```

### 📝 License

This project is licensed under the Apache 2.0 License. © 2026 Vistatec, Ltd.

```