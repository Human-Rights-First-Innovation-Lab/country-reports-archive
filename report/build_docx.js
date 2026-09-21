const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, ImageRun,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType, TabStopType,
  Header, Footer, PageNumber, LevelFormat, convertInchesToTwip,
} = require(path.join(__dirname, 'node_modules', 'docx'));

const INK = '12171D', MUTED = '5B6673', RULE = 'DDE3EA';
const S23 = '1163A0', S24 = 'A32C25', BAND = 'F4F6F8';
const SERIF = 'Georgia', SANS = 'Arial';

// US Letter, in DXA (1440 = 1 inch).
const PAGE = { size: { width: 12240, height: 15840 },
               margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } };
const CONTENT_W = 12240 - 2880;   // usable width between margins

const NONE = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const noBorders = { top: NONE, bottom: NONE, left: NONE, right: NONE,
                    insideHorizontal: NONE, insideVertical: NONE };

const img = (file, wIn, hIn) => new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 200, after: 120 },
  children: [new ImageRun({
    type: 'png',
    data: fs.readFileSync(path.join(__dirname, file)),
    transformation: { width: wIn * 96, height: hIn * 96 },
  })],
});

const h1 = (t) => new Paragraph({
  heading: HeadingLevel.HEADING_1, spacing: { before: 60, after: 160 },
  children: [new TextRun({ text: t, font: SERIF, size: 30, bold: true, color: INK })],
});
const h2 = (t) => new Paragraph({
  heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 110 },
  children: [new TextRun({ text: t, font: SANS, size: 23, bold: true, color: INK })],
});
const p = (runs, opts = {}) => new Paragraph({
  spacing: { after: opts.after ?? 180, line: 288 },
  children: (Array.isArray(runs) ? runs : [runs]).map(r =>
    typeof r === 'string'
      ? new TextRun({ text: r, font: SANS, size: 21, color: INK })
      : new TextRun({ font: SANS, size: 21, color: INK, ...r })),
});
const caption = (t) => new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { after: 300 },
  children: [new TextRun({ text: t, font: SANS, size: 17, italics: true, color: MUTED })],
});
const eyebrow = (t) => new Paragraph({
  spacing: { before: 480, after: 90 },
  children: [new TextRun({ text: t.toUpperCase(), font: SANS, size: 15,
                           bold: true, color: MUTED, characterSpacing: 40 })],
});
const rule = () => new Paragraph({
  spacing: { before: 60, after: 240 }, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE } },
  children: [new TextRun({ text: '' })],
});

/* ---------- key-figures band ---------- */
const figCell = (n, label) => new TableCell({
  width: { size: Math.floor(CONTENT_W / 4), type: WidthType.DXA },
  shading: { type: ShadingType.CLEAR, fill: BAND, color: 'auto' },
  margins: { top: 200, bottom: 200, left: 160, right: 160 },
  borders: noBorders,
  children: [
    new Paragraph({ spacing: { after: 60 },
      children: [new TextRun({ text: n, font: SERIF, size: 34, bold: true, color: S24 })] }),
    new Paragraph({ children: [new TextRun({ text: label, font: SANS, size: 16, color: MUTED })] }),
  ],
});

/* ---------- data table ---------- */
const COLS = [Math.floor(CONTENT_W * 0.40), Math.floor(CONTENT_W * 0.20),
              Math.floor(CONTENT_W * 0.20), Math.floor(CONTENT_W * 0.20)];
const cell = (text, i, opts = {}) => new TableCell({
  width: { size: COLS[i], type: WidthType.DXA },
  margins: { top: 90, bottom: 90, left: 120, right: 120 },
  borders: { ...noBorders, bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE } },
  shading: opts.head ? { type: ShadingType.CLEAR, fill: BAND, color: 'auto' } : undefined,
  children: [new Paragraph({
    alignment: i === 0 ? AlignmentType.LEFT : AlignmentType.RIGHT,
    children: [new TextRun({ text, font: SANS, size: 19,
      bold: !!opts.head, color: opts.down ? S24 : (opts.head ? MUTED : INK) })],
  })],
});
const tableRows = [
  ['Reports', '193', '194', '+1'],
  ['Total characters', '11,153,732', '3,810,680', '−65.8%'],
  ['Median report length', '52,875', '18,187', '−65.6%'],
  ['Outline headings', '30', '17', '−43.3%'],
  ['Distinct named sources', '1,211', '506', '−58.2%'],
  ['Named source mentions', '3,476', '1,328', '−61.8%'],
  ['Quantitative claims', '3,676', '1,372', '−62.7%'],
];

const doc = new Document({
  creator: 'Human Rights First',
  title: 'The 2024 Contraction',
  description: 'Comparison of the 2023 and 2024 State Department Country Reports on Human Rights Practices',
  numbering: { config: [{
    reference: 'bullets', levels: [{
      level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: convertInchesToTwip(0.3), hanging: convertInchesToTwip(0.18) } } },
    }],
  }] },
  sections: [{
    properties: { page: PAGE },
    headers: { default: new Header({ children: [new Paragraph({
      spacing: { after: 0 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE } },
      children: [new TextRun({ text: 'Human Rights First  ·  Research note',
                               font: SANS, size: 15, color: MUTED })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({
      alignment: AlignmentType.RIGHT,
      children: [new TextRun({ children: ['Page ', PageNumber.CURRENT, ' of ', PageNumber.TOTAL_PAGES],
                               font: SANS, size: 15, color: MUTED })] })] }) },
    children: [
      /* ---------------- masthead ---------------- */
      new Paragraph({ spacing: { before: 240, after: 120 },
        children: [new TextRun({ text: 'COUNTRY REPORTS ON HUMAN RIGHTS PRACTICES',
          font: SANS, size: 16, bold: true, color: MUTED, characterSpacing: 50 })] }),
      new Paragraph({ spacing: { after: 160 },
        children: [new TextRun({ text: 'Every country report got shorter',
          font: SERIF, size: 46, bold: true, color: INK })] }),
      new Paragraph({ spacing: { after: 300, line: 300 },
        children: [new TextRun({
          text: "The State Department's 2024 Country Reports on Human Rights Practices are two-thirds shorter than the 2023 edition, cite half as many organisations, and follow a rewritten outline. Not one of 192 countries gained text.",
          font: SERIF, size: 24, color: '39424D' })] }),
      new Paragraph({ spacing: { before: 120, after: 360 },
        children: [new TextRun({
          text: 'Editions compared: 2023 → 2024   ·   389 reports analysed   ·   Prepared 15 September 2026',
          font: SANS, size: 17, color: MUTED })] }),

      new Table({ columnWidths: COLS.map(() => Math.floor(CONTENT_W / 4)),
        width: { size: CONTENT_W, type: WidthType.DXA }, borders: noBorders,
        rows: [new TableRow({ children: [
          figCell('−65.8%', 'Total text, 11.15M → 3.81M characters'),
          figCell('0 of 192', 'Countries whose report grew'),
          figCell('−58%', 'Distinct organisations cited'),
          figCell('−62.7%', 'Quantitative claims'),
        ] })] }),
      new Paragraph({ spacing: { after: 120 }, children: [new TextRun('')] }),

      /* ---------------- 01 scale ---------------- */
      eyebrow('01 — Scale'),
      h1('A uniform cut, not a set of country decisions'),
      p("The 2024 reports were released on 12 August 2025. Measured against the prior edition, the median country report fell from roughly 52,900 characters to 18,200 — a 65.6% reduction, closely tracking the 65.8% drop across the corpus as a whole."),
      p("The more telling number is the spread. If editors had made country-by-country judgements about what still warranted reporting, the reductions would vary widely — some countries trimmed lightly, others heavily, a few expanded. That is not what happened. Every one of the 192 countries present in both editions lands between −49% and −94%, and 147 of them sit inside a single 20-point band."),
      img('chart1_distribution.png', 6.3, 2.54),
      caption('Distribution of change in report length, 2023 → 2024. 192 countries present in both editions.'),
      p("No country appears to the right of −49%. The concentration in two adjacent bands is the signature of an editorial rule applied across the corpus, rather than 192 separate assessments."),

      /* ---------------- 02 outliers ---------------- */
      eyebrow('02 — Outliers'),
      h1('Israel and the West Bank and Gaza fell furthest'),
      p("One report is a clear outlier. The combined Israel, West Bank and Gaza report — by far the longest in the 2023 edition at 150,886 characters — was reduced to 8,762, a 94.2% cut. It is the only country outside the band that contains every other report, and it went from the longest report in the corpus to a below-median one."),
      img('chart2_reductions.png', 6.3, 3.06),
      caption('The ten largest reductions. For comparison, the smallest were Norway (−49.3%), Grenada (−50.5%) and Liberia (−50.7%).'),

      /* ---------------- 03 sources ---------------- */
      eyebrow('03 — Evidence base'),
      h1('Half the organisations disappeared from the reporting'),
      p("The reports attribute claims to outside bodies in prose — there are no footnotes. Counting those attributions, the number of distinct named organisations fell from 1,211 to 506, and total named mentions from 3,476 to 1,328."),
      p("The decline is not evenly distributed. UNHCR, the most-cited body in both editions, fell from 669 mentions across 137 countries to 288 across 93. The International Committee of the Red Cross fell from 66 mentions to 9; the Council of Europe from 64 to 7; Transparency International from 25 to 3. Thirty-three organisations cited at least three times in 2023 vanish entirely, among them the OSCE, UNESCO and the Organization of American States."),
      img('chart3_sources.png', 6.3, 4.11),
      caption('Mentions of frequently cited organisations, both editions.'),
      p([{ text: 'One exception stands out. ', bold: true },
         { text: "The International Labor Organization barely moves — 93 mentions to 83, across 79 countries then 75 — while comparable bodies lose half or more of their presence. Labour-rights sourcing survived the cut almost intact while refugee, civil-liberties and anti-corruption sourcing did not. The 2024 outline retains a dedicated Worker Rights subsection, and the topics whose sourcing collapsed are largely those whose dedicated sections were removed. That relationship is worth testing directly before drawing conclusions from it." }]),

      /* ---------------- 04 structure ---------------- */
      eyebrow('04 — Structure'),
      h1('The outline was rewritten, not trimmed'),
      p("The 2023 edition organised each report under seven thematic sections. The 2024 edition uses three. Only two headings survive in recognisable form across the two editions — a 96% change in the outline."),
      p("This matters for anyone comparing the editions: the sections do not correspond, so a section-by-section diff produces confident-looking numbers that mean nothing. Several distinct 2023 sections have no 2024 counterpart at all, including Corruption in Government, Freedom to Participate in the Political Process, and Denial of Fair Public Trial."),
      h2('2023 edition — seven sections'),
      ...['Respect for the Integrity of the Person','Respect for Civil Liberties',
          'Freedom to Participate in the Political Process','Corruption in Government',
          'Governmental Posture Towards International Bodies','Discrimination and Societal Abuses',
          'Worker Rights'].map(t => new Paragraph({
        numbering: { reference: 'bullets', level: 0 }, spacing: { after: 60 },
        children: [new TextRun({ text: t, font: SANS, size: 20, color: INK })] })),
      h2('2024 edition — three sections'),
      ...['Life','Liberty','Security of the Person'].map(t => new Paragraph({
        numbering: { reference: 'bullets', level: 0 }, spacing: { after: 60 },
        children: [new TextRun({ text: t, font: SANS, size: 20, color: INK })] })),
      new Paragraph({ spacing: { before: 160, after: 200 },
        children: [new TextRun({
          text: 'Subsections were also reorganised: 30 distinct headings in 2023 against 17 in 2024. Instances of Transnational Repression is the only 2024 subsection that is not universal — it appears in 52 of 195 reports.',
          font: SANS, size: 19, italics: true, color: MUTED })] }),

      /* ---------------- 05 coverage ---------------- */
      eyebrow('05 — Coverage'),
      h1('Country coverage held steady'),
      p("Unlike length and sourcing, the number of countries covered did not fall: 193 reports in 2023 against 194 in 2024. The Cook Islands and Niue were added. No country was dropped."),
      p("Quantitative claims fell roughly in line with overall length, from 3,676 to 1,372 (−62.7%). Percentages remain the most common figure in both editions — 1,917 instances in 2023, 689 in 2024."),
      new Table({ columnWidths: COLS, width: { size: CONTENT_W, type: WidthType.DXA },
        borders: noBorders,
        rows: [
          new TableRow({ tableHeader: true, children: [
            cell('Measure', 0, { head: true }), cell('2023', 1, { head: true }),
            cell('2024', 2, { head: true }), cell('Change', 3, { head: true })] }),
          ...tableRows.map(r => new TableRow({ children: [
            cell(r[0], 0), cell(r[1], 1), cell(r[2], 2),
            cell(r[3], 3, { down: r[3].startsWith('−') })] })),
        ] }),
      new Paragraph({ spacing: { after: 240 }, children: [new TextRun('')] }),

      /* ---------------- 06 method ---------------- */
      eyebrow('06 — Method'),
      h1('How these numbers were produced, and what they can bear'),
      p("All 389 reports were downloaded as published PDFs and parsed directly. Every figure above is reproducible from the archive, and each report is recorded with its source URL and SHA-256 checksum."),
      p([{ text: 'The reports contain no footnotes or bibliography. ', bold: true },
         { text: 'Sources appear only as inline prose — "according to UNICEF", "the KNCHR reported 82 cases". Source counts are therefore inferred from sentence structure, not read off a citation list. Every extracted row retains the verbatim sentence it came from, and rows are graded by confidence. The organisation-level counts quoted here are drawn from the high-confidence tier: a fixed list of known bodies matched by name.' }]),
      p("Extraction is deliberately conservative. An ambiguous four-digit figure — “2000 refugees” — is discarded rather than risk recording a year as a quantity. Real counts are lost this way; corrupted ones are not introduced. Counts of source mentions should be read as a consistent index applied identically to both editions, not as an exhaustive census."),
      p("Length is measured in characters of extracted body text, excluding running headers and page furniture. It is a proxy for detail, not a measure of quality or coverage."),
      h2('Two caveats to carry'),
      new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 100 },
        children: [
          new TextRun({ text: 'North Macedonia 2024 is missing. ', font: SANS, size: 20, bold: true, color: INK }),
          new TextRun({ text: 'The report exists, but state.gov blocks automated retrieval of that one file. It is excluded from every figure here rather than estimated.', font: SANS, size: 20, color: INK })] }),
      new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 240 },
        children: [
          new TextRun({ text: 'Low-frequency source names are unreliable. ', font: SANS, size: 20, bold: true, color: INK }),
          new TextRun({ text: 'Entries appearing only a handful of times can be truncated phrases rather than real organisations. Only sources with substantial counts are quoted above.', font: SANS, size: 20, color: INK })] }),

      rule(),
      new Paragraph({ spacing: { after: 100 }, children: [new TextRun({
        text: 'Source: U.S. Department of State, Bureau of Democracy, Human Rights, and Labor — Country Reports on Human Rights Practices, 2023 and 2024 editions. The 2024 edition was released 12 August 2025.',
        font: SANS, size: 17, color: MUTED })] }),
      new Paragraph({ children: [new TextRun({
        text: 'Figures derived from the published PDFs by an archiving and comparison pipeline maintained by Human Rights First. The same pipeline will run against the 2025 edition on release.',
        font: SANS, size: 17, color: MUTED })] }),
    ],
  }],
});

Packer.toBuffer(doc).then(b => {
  const out = path.join(__dirname, 'Country-Reports-2023-2024-Comparison.docx');
  fs.writeFileSync(out, b);
  console.log('wrote', out, b.length, 'bytes');
});
