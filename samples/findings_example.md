# Bottom line

German output is usable after light edits; Japanese isn't usable as-is where amounts appear. Describe the
amount placeholders before the next drop.

# Summary

1. **Japanese misreads amount placeholders.** `Pay {{amount}} {{currencyCode}}` was translated as a number of
   items, the only Critical item in the sample.
2. **German edits are mostly about address and terms.** Two of four items switch to informal *du*, and one uses
   the glossary term for rewards.
3. **Headings are translated too literally** in both languages.

# What's going wrong

## 1. Amount placeholders read as counts (Critical)

*Languages: Japanese (1 item)*

- Source: Pay {{amount}} {{currencyCode}} today
- AI (ja-JP): 今日 {{amount}} 個の {{currencyCode}} を支払う ("pay {{amount}} pieces of {{currencyCode}} today")
- Corrected: 本日 {{amount}} {{currencyCode}} をお支払い ("pay {{amount}} {{currencyCode}} today")

**Fix:** Describe each currency placeholder in the TMS, for example "ISO currency code, always follows an
amount" (Both).

## 2. Formal address instead of informal (Major)

*Languages: German (Germany) (2 items)*

**Fix:** Add the informal-address rule to the AI instructions (Loc team).

# Language assessments

- **German (Germany)**: Usable with light edits (evidence: moderate, 4 items). Edits were for address, a
  glossary term and one business-day term.
- **Japanese**: Not usable as-is (evidence: moderate, 3 items). One amount was misread as a count, and both
  headings needed rewriting.

# Recommended actions

1. **Describe currency placeholders** (Both). Theme 1.
2. **Add the informal-address rule** (Loc team). Theme 2.

> Sample findings for testing. All content is invented.
