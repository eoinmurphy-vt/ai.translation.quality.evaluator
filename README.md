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
python evaluate.py forms samples/forms
```

The workbook is saved in `output/`. Open it and start on the **Summary** tab. The files in `samples/` are
invented, so you can try every mode before using real data.

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
| `--json FILE` | Also save all results as JSON, for dashboards or further processing |

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

Evaluation forms, exports and results contain client content. Put input files in `data/`; results go to
`output/`. Git ignores both folders, and also ignores `.xlsx`, `.xlsm`, `.csv`, `.json` and XLIFF files
anywhere except `samples/` and `config/`. Check `git status` before every commit.

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
  excel.py                Writing the workbook
  cli.py                  Command-line options
config/form_layout.json   Where things are on the evaluation form
samples/                  Invented test files (make_samples.py recreates them)
tests/                    Unit and end-to-end tests
data/                     Your input files (ignored by git)
output/                   Results (ignored by git)
```

## Licence

No licence has been chosen yet. Add a `LICENSE` file before sharing this outside the company.
