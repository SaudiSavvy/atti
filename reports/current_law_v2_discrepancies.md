# ATTI current_law_v2: discrepancy matrix (AI review, provisional)

> AI-assisted analysis, **not** human verification. Excerpts are short quotations for identification; full texts stay in local, git-ignored files.

Rule: Strict corpus: a pair is excluded when the English adds, drops or changes a legal element of the Arabic (negation, condition, threshold, scope, the identity of a sanction, the legal basis) or reflects a different legal version. A pair is retained when only list labels/markup differ with content corresponding one-to-one and in order, or when a term differs but its referent is unambiguous and unchanged. Neither official text is corrected.

Categories: **SOURCE_ERROR** = an error in the wording of a published official text itself; **TRANSLATION_DIFFERENCE** = the English wording departs from the Arabic (substantive or terminological); **FORMATTING_ANOMALY** = list labels or markup differ in a published source; wording corresponds; **EXTRACTION_FAILURE** = ATTI's extraction does not reproduce the published text; **VERSION_MISMATCH** = the two texts represent different legal versions.

For 15, 64 and 108 the label differences were checked against the raw PDF text and the raw HTML list markup (<ol start>, nested <ol>); ATTI reproduces the published labels. No discrepancy among the flagged pairs is an extraction failure.

| Art. | Part | Flagged | Category | Arabic excerpt | English excerpt | BOE English (cross-check) | Disposition |
|---:|---:|---|---|---|---|---|---|
| 15 | 1 | yes | FORMATTING_ANOMALY | list labels 4. … 8. | list labels 1. … 5. | labels 1-5 | RETAINED (PROPOSED_PASS) |
| 40 | 3 | yes | VERSION_MISMATCH | غرامات يتسبب بها صاحب العمل | any penalties resulting from delays | BOE Arabic (pre-amendment) lacks the qualifier; BOE English 'the fines resulting from their delay' | EXCLUDED → 35 (VERSION_MISMATCH) |
| 63 | 5 | yes | TRANSLATION_DIFFERENCE | مادة محرمة شرعاً | legally prohibited substance | 'illegal substances' (same shift in the older BOE translation) | EXCLUDED → 56 (FAIL) |
| 64 | 5 | yes | FORMATTING_ANOMALY | list labels 1. 2. | list labels 7. 8. | n/a (article amended) | RETAINED (PROPOSED_PASS) |
| 66 | 5 | yes | TRANSLATION_DIFFERENCE | 2. الغرامة | 2. Penalty | '2. Fines.' | EXCLUDED → 71 (FAIL) |
| 81 | 5 | yes | TRANSLATION_DIFFERENCE | خطر جسيم | a danger in the workplace | 'a serious hazard' | EXCLUDED → 58 (FAIL) |
| 108 | 6 | yes | FORMATTING_ANOMALY | items 1-4; الفقرات 2 ، 3 ، 4 | items 1, 1, 2, 3; 'paragraphs 2, 3, and 4' | items 1-4 | RETAINED (PROPOSED_PASS) |
| 167 | 10 | yes | TRANSLATION_DIFFERENCE | في هذا الباب | in this Chapter | 'in this Part' | RETAINED (PROPOSED_PASS) |
| 189 | 12 | yes | TRANSLATION_DIFFERENCE | والأشخاص الذين يحملون إذناً خاصاً | individuals who do not hold a special permit | 'restricted to workers therein, persons authorized to inspect ..., and persons holding special permits' | EXCLUDED → 187 (FAIL) |
| 76 | 5 | no | TRANSLATION_DIFFERENCE | على أكثر من ذلك | agree otherwise | n/a (article amended) | EXCLUDED (FAIL) |
| 187 | 12 | no | TRANSLATION_DIFFERENCE | يسري عليها هذا الباب | subject to this Chapter | 'this Part' | RETAINED (PROPOSED_PASS) |

## Source-alignment limitations (retained pairs)

Semantic differences between the published Arabic and English texts of selected pairs. They are documented, not repaired; the pairs stay in the corpus under the research scope.

| Art. | Category | Arabic excerpt | English excerpt | Finding | Origin |
|---:|---|---|---|---|---|
| 34 | TRANSLATION_DIFFERENCE | لا يغني عن رخصة العمل | The work permit ... shall not substitute for | Direction of substitution reversed: the Arabic says no permit from another authority replaces the work permit; the HRSD English says the work permit does not replace other authorities' permits. | independent audit (named in Task 12; the audit text was not available to the AI agent) and AI re-examination 2026-11-24 |
| 35 | TRANSLATION_DIFFERENCE | وأيًّا من الاشتراطات | or any other conditions | The Arabic joins the localization standards and the other conditions with 'and' (wa); the English uses 'or', which may widen the grounds for refusing renewal. The Arabic coordination is open to either reading; not resolved. | independent audit (named in Task 12; the audit text was not available to the AI agent) and AI re-examination 2026-11-24 |
| 108 | FORMATTING_ANOMALY | الفقرات 2 ، 3 ، 4 | items 1, 1, 2, 3 | English item labels 1, 1, 2, 3 (nested list markup) against its own cross-reference to paragraphs 2, 3 and 4; read by label, the cross-reference points to the wrong items. | AI review 2026-11-23 (Task 07), also named by the independent audit (Task 12) |

## Article 15: FORMATTING_ANOMALY, RETAINED

- Arabic PDF: <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf#page=8>
- Arabic HTML: <https://www.hrsd.gov.sa/%D8%A7%D9%84%D8%AA%D8%B9%D8%B1%D9%8A%D9%81%D8%A7%D8%AA/%D8%A7%D9%84%D8%A3%D8%AD%D9%83%D8%A7%D9%85-%D8%A7%D9%84%D8%B9%D8%A7%D9%85%D8%A9#heading-18>
- English HTML: <https://www.hrsd.gov.sa/en/%D8%A7%D9%84%D8%AA%D8%B9%D8%B1%D9%8A%D9%81%D8%A7%D8%AA/%D8%A7%D9%84%D8%A3%D8%AD%D9%83%D8%A7%D9%85-%D8%A7%D9%84%D8%B9%D8%A7%D9%85%D8%A9#heading-19>
- Finding: Five items correspond one-to-one and in order (establishment identity and address; licensed activity and registration; number of workers; responsible manager; other data). The Arabic labels 4-8 are printed in the PDF and encoded as <ol start="4"> in the Arabic HTML; nothing is lost or reassigned. Not an extraction failure (checked against raw PDF text and HTML).

## Article 40: VERSION_MISMATCH, EXCLUDED

- Arabic PDF: <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf#page=15>, <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf#page=16>
- Arabic HTML: <https://www.hrsd.gov.sa/%D8%AA%D9%88%D8%B8%D9%8A%D9%81-%D8%BA%D9%8A%D8%B1-%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A%D9%8A%D9%86#heading-9>
- English HTML: <https://www.hrsd.gov.sa/en/%D8%AA%D9%88%D8%B8%D9%8A%D9%81-%D8%BA%D9%8A%D8%B1-%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A%D9%8A%D9%86#heading-9>
- Finding: PDF footnote 21 (p. 15): the article was amended by Royal Decree M/44 (8/2/1446 AH). The amended Arabic limits the employer's liability to delay fines the employer caused; the HRSD English matches the earlier, unqualified wording. Of the 25 selected articles whose HRSD Arabic differs from the BOE Arabic, this is the only one whose English does not carry the change.

## Article 63: TRANSLATION_DIFFERENCE, EXCLUDED

- Arabic PDF: <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf#page=23>
- Arabic HTML: <https://www.hrsd.gov.sa/%D8%B9%D9%84%D8%A7%D9%82%D8%A7%D8%AA-%D8%A7%D9%84%D8%B9%D9%85%D9%84#heading-20>
- English HTML: <https://www.hrsd.gov.sa/en/%D8%B9%D9%84%D8%A7%D9%82%D8%A7%D8%AA-%D8%A7%D9%84%D8%B9%D9%85%D9%84#heading-19>
- Finding: The basis of the prohibition changes from Sharia to law, so the set of substances covered need not coincide. The same English article renders the closing Sharia penalties as 'Sharia', so the shift is not a house convention for the term. Terminological, but it changes the legal basis.

## Article 64: FORMATTING_ANOMALY, RETAINED

- Arabic PDF: <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf#page=23>
- Arabic HTML: <https://www.hrsd.gov.sa/%D8%B9%D9%84%D8%A7%D9%82%D8%A7%D8%AA-%D8%A7%D9%84%D8%B9%D9%85%D9%84>
- English HTML: <https://www.hrsd.gov.sa/en/%D8%B9%D9%84%D8%A7%D9%82%D8%A7%D8%AA-%D8%A7%D9%84%D8%B9%D9%85%D9%84>
- Finding: The two obligations (service certificate with its contents and prohibition on harmful content; return of deposited documents) correspond in order. The English HTML encodes the list as <ol start="7">, continuing an earlier article's numbering. Labels only; not an extraction failure.

## Article 66: TRANSLATION_DIFFERENCE, EXCLUDED

- Arabic PDF: <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf#page=24>
- Arabic HTML: <https://www.hrsd.gov.sa/%D8%B9%D9%84%D8%A7%D9%82%D8%A7%D8%AA-%D8%A7%D9%84%D8%B9%D9%85%D9%84#heading-25>
- English HTML: <https://www.hrsd.gov.sa/en/%D8%B9%D9%84%D8%A7%D9%82%D8%A7%D8%AA-%D8%A7%D9%84%D8%B9%D9%85%D9%84#heading-22>
- Finding: In a list of disciplinary penalties, item 2 'Penalty' no longer identifies the sanction (a monetary fine). The same HRSD English renders the word as 'fine' in Articles 70, 71 and 73.
- Replacement draws: 76 (rejected), 71

## Article 81: TRANSLATION_DIFFERENCE, EXCLUDED

- Arabic PDF: <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf#page=27>, <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf#page=28>
- Arabic HTML: <https://www.hrsd.gov.sa/%D8%B9%D9%84%D8%A7%D9%82%D8%A7%D8%AA-%D8%A7%D9%84%D8%B9%D9%85%D9%84#heading-44>
- English HTML: <https://www.hrsd.gov.sa/en/%D8%B9%D9%84%D8%A7%D9%82%D8%A7%D8%AA-%D8%A7%D9%84%D8%B9%D9%85%D9%84#heading-38>
- Finding: Case 6 lets the worker leave without notice only for a grave danger; the English drops the seriousness threshold, widening the right. Other six cases correspond.

## Article 108: FORMATTING_ANOMALY, RETAINED

- Arabic PDF: <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf#page=35>
- Arabic HTML: <https://www.hrsd.gov.sa/%D8%B4%D8%B1%D9%88%D8%B7-%D8%A7%D9%84%D8%B9%D9%85%D9%84-%D9%88%D8%B8%D8%B1%D9%88%D9%81%D9%87#heading-28>
- English HTML: <https://www.hrsd.gov.sa/en/%D8%B4%D8%B1%D9%88%D8%B7-%D8%A7%D9%84%D8%B9%D9%85%D9%84-%D9%88%D8%B8%D8%B1%D9%88%D9%81%D9%87#heading-27>
- Finding: The English HTML nests items 2-4 as a sub-list inside item 1, so they display and extract as 1-3. The four items correspond in order, and the English closing cross-reference to paragraphs 2, 3 and 4 matches the Arabic and the intended flat list. Labels only. Caveat: a reader resolving the cross-reference by the displayed labels would misread it.

## Article 167: TRANSLATION_DIFFERENCE, RETAINED

- Arabic PDF: <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf#page=50>
- Arabic HTML: <https://www.hrsd.gov.sa/%D8%AA%D8%B4%D8%BA%D9%8A%D9%84-%D8%A7%D9%84%D8%A3%D8%AD%D8%AF%D8%A7%D8%AB#heading-7>
- English HTML: <https://www.hrsd.gov.sa/en/%D8%AA%D8%B4%D8%BA%D9%8A%D9%84-%D8%A7%D9%84%D8%A3%D8%AD%D8%AF%D8%A7%D8%AB#heading-7>
- Finding: Terminology only: Part 10 has no chapters in either language, so 'this Chapter' can only refer to Part 10. The HRSD English uses 'Chapter' for the Arabic chapter unit elsewhere (e.g. Article 47) and 'this Part' in Article 168; the term is inconsistent but the referent is unchanged. Exemptions, minimum age 14 and the three programmes correspond.

## Article 189: TRANSLATION_DIFFERENCE, EXCLUDED

- Arabic PDF: <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf#page=56>
- Arabic HTML: <https://www.hrsd.gov.sa/%D8%A7%D9%84%D8%B9%D9%85%D9%84-%D9%81%D9%8A-%D8%A7%D9%84%D9%85%D9%86%D8%A7%D8%AC%D9%85-%D9%88%D8%A7%D9%84%D9%85%D8%AD%D8%A7%D8%AC%D8%B1#heading-5>
- English HTML: <https://www.hrsd.gov.sa/en/%D8%A7%D9%84%D8%B9%D9%85%D9%84-%D9%81%D9%8A-%D8%A7%D9%84%D9%85%D9%86%D8%A7%D8%AC%D9%85-%D9%88%D8%A7%D9%84%D9%85%D8%AD%D8%A7%D8%AC%D8%B1#heading-5>
- Finding: Substantive negation conflict. The Arabic (PDF and HTML identical, unchanged from the BOE Arabic) has no negation; read literally it lists permit holders among those barred. The HRSD English negates the permit condition. The older BOE English reads the three groups as those allowed in, which differs from both. No authoritative source resolves the discrepancy; neither text is corrected. Semantically non-equivalent.

## Article 76: TRANSLATION_DIFFERENCE, EXCLUDED

- Arabic PDF: <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf#page=26>
- Arabic HTML: <https://www.hrsd.gov.sa/%D8%B9%D9%84%D8%A7%D9%82%D8%A7%D8%AA-%D8%A7%D9%84%D8%B9%D9%85%D9%84#heading-38>
- English HTML: <https://www.hrsd.gov.sa/en/%D8%B9%D9%84%D8%A7%D9%82%D8%A7%D8%AA-%D8%A7%D9%84%D8%B9%D9%85%D9%84#heading-32>
- Finding: Not one of the 9 flagged pairs: first replacement draw for Article 66, rejected on review. The Arabic allows the parties to agree only on a larger payment; 'otherwise' also admits a smaller one.

## Article 187: TRANSLATION_DIFFERENCE, RETAINED

- Arabic PDF: <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf#page=56>
- Arabic HTML: <https://www.hrsd.gov.sa/%D8%A7%D9%84%D8%B9%D9%85%D9%84-%D9%81%D9%8A-%D8%A7%D9%84%D9%85%D9%86%D8%A7%D8%AC%D9%85-%D9%88%D8%A7%D9%84%D9%85%D8%AD%D8%A7%D8%AC%D8%B1#heading-3>
- English HTML: <https://www.hrsd.gov.sa/en/%D8%A7%D9%84%D8%B9%D9%85%D9%84-%D9%81%D9%8A-%D8%A7%D9%84%D9%85%D9%86%D8%A7%D8%AC%D9%85-%D9%88%D8%A7%D9%84%D9%85%D8%AD%D8%A7%D8%AC%D8%B1#heading-3>
- Finding: Not one of the 9 flagged pairs: replacement for Article 189. Same terminology pattern as 167; Part 12 has no chapters, so the referent is unchanged. Otherwise corresponds.

## Article 34: TRANSLATION_DIFFERENCE, RETAINED (source-alignment limitation)

- Arabic PDF: <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf#page=15>
- Arabic HTML: <https://www.hrsd.gov.sa/%D8%AA%D9%88%D8%B8%D9%8A%D9%81-%D8%BA%D9%8A%D8%B1-%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A%D9%8A%D9%86>
- English HTML: <https://www.hrsd.gov.sa/en/%D8%AA%D9%88%D8%B8%D9%8A%D9%81-%D8%BA%D9%8A%D8%B1-%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A%D9%8A%D9%86>
- Finding: Direction of substitution reversed: the Arabic says no permit from another authority replaces the work permit; the HRSD English says the work permit does not replace other authorities' permits.

## Article 35: TRANSLATION_DIFFERENCE, RETAINED (source-alignment limitation)

- Arabic PDF: <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf#page=15>
- Arabic HTML: <https://www.hrsd.gov.sa/%D8%AA%D9%88%D8%B8%D9%8A%D9%81-%D8%BA%D9%8A%D8%B1-%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A%D9%8A%D9%86>
- English HTML: <https://www.hrsd.gov.sa/en/%D8%AA%D9%88%D8%B8%D9%8A%D9%81-%D8%BA%D9%8A%D8%B1-%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A%D9%8A%D9%86>
- Finding: The Arabic joins the localization standards and the other conditions with 'and' (wa); the English uses 'or', which may widen the grounds for refusing renewal. The Arabic coordination is open to either reading; not resolved.

## Article 108: FORMATTING_ANOMALY, RETAINED (source-alignment limitation)

- Arabic PDF: <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf#page=35>
- Arabic HTML: <https://www.hrsd.gov.sa/%D8%B4%D8%B1%D9%88%D8%B7-%D8%A7%D9%84%D8%B9%D9%85%D9%84-%D9%88%D8%B8%D8%B1%D9%88%D9%81%D9%87>
- English HTML: <https://www.hrsd.gov.sa/en/%D8%B4%D8%B1%D9%88%D8%B7-%D8%A7%D9%84%D8%B9%D9%85%D9%84-%D9%88%D8%B8%D8%B1%D9%88%D9%81%D9%87>
- Finding: English item labels 1, 1, 2, 3 (nested list markup) against its own cross-reference to paragraphs 2, 3 and 4; read by label, the cross-reference points to the wrong items.
