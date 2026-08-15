// Build the PROVA-MG thesis .docx from the extracted block list.
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  TableOfContents, PageBreak, ExternalHyperlink, LevelFormat, convertInchesToTwip,
} = require('docx');

const blocks = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const OUT = process.argv[3];

const SERIF = 'Times New Roman';
const DISPLAY = 'Georgia';
const MONO = 'Courier New';

const PAGE_W = 11906, MARGIN = 1440;          // A4, 1" margins
const USABLE = PAGE_W - 2 * MARGIN;           // 9026 dxa

const children = [];

// ---------------------------------------------------------------- inline runs
function toRuns(runs, opts = {}) {
  const out = [];
  for (const r of runs) {
    const text = r.text.replace(/\n/g, ' ');
    if (!text) continue;
    const base = {
      text,
      bold: r.bold || opts.bold,
      italics: r.italic || opts.italics,
      font: r.mono ? MONO : (opts.font || SERIF),
      size: r.mono ? (opts.size ? opts.size - 2 : 20) : opts.size,
      color: opts.color,
    };
    if (r.link) {
      out.push(new ExternalHyperlink({
        link: r.link,
        children: [new TextRun({ ...base, style: 'Hyperlink' })],
      }));
    } else {
      out.push(new TextRun(base));
    }
  }
  return out;
}

const indentOf = (n) => (n ? { left: 360 * n } : undefined);

// ---------------------------------------------------------------- paragraphs
function bodyPara(b) {
  const ind = b.indent || 0;
  switch (b.kind) {
    case 'label':
      return new Paragraph({
        children: toRuns(b.runs, { font: DISPLAY, size: 16, color: '8A7A5C', bold: true }),
        spacing: { before: 240, after: 60, line: 240 },
        indent: indentOf(ind),
      });
    case 'standfirst':
      return new Paragraph({
        children: toRuns(b.runs, { italics: true, color: '444444' }),
        spacing: { after: 160, line: 300 },
        indent: indentOf(ind),
        alignment: AlignmentType.JUSTIFIED,
      });
    case 'subtitle':
      return new Paragraph({
        children: toRuns(b.runs, { bold: true, size: 26, font: DISPLAY }),
        spacing: { after: 160 },
        indent: indentOf(ind),
      });
    case 'formula':
      return new Paragraph({
        children: toRuns(b.runs, { font: MONO, size: 21 }),
        alignment: AlignmentType.CENTER,
        spacing: { before: 180, after: 180, line: 260 },
        indent: indentOf(ind),
      });
    case 'listing':
      return new Paragraph({
        children: b.runs.length ? toRuns(b.runs, { font: MONO, size: 19 })
                                : [new TextRun({ text: ' ', font: MONO, size: 19 })],
        spacing: { before: 0, after: 0, line: 240 },
        indent: indentOf(ind + 1),
      });
    case 'bullet': {
      // the HTML builder prefixed these with "• " / "1. "
      const runs = b.runs.map((r) => ({ ...r }));
      let ordered = false;
      const m = runs[0].text.match(/^(•\s|(\d+)\.\s)/);
      if (m) {
        ordered = !!m[2];
        runs[0].text = runs[0].text.slice(m[0].length);
      }
      return new Paragraph({
        children: toRuns(runs),
        numbering: { reference: ordered ? 'numbers' : 'bullets', level: Math.min(ind, 2) },
        spacing: { after: 80, line: 300 },
        alignment: AlignmentType.JUSTIFIED,
      });
    }
    default:
      return new Paragraph({
        children: toRuns(b.runs),
        spacing: { after: 140, line: 360 },      // 1.5 line spacing
        indent: indentOf(ind),
        alignment: AlignmentType.JUSTIFIED,
      });
  }
}

function listPara(b) {
  return new Paragraph({
    children: toRuns(b.runs),
    numbering: {
      reference: b.ordered ? 'numbers' : 'bullets',
      level: Math.min(b.indent || 0, 2),
    },
    spacing: { after: 80, line: 300 },
  });
}

// ---------------------------------------------------------------- tables
function buildTable(b) {
  const cols = Math.max(...b.rows.map((r) => r.length));
  let widths;
  if (cols === 2) widths = [Math.round(USABLE * 0.32), USABLE - Math.round(USABLE * 0.32)];
  else {
    const w = Math.floor(USABLE / cols);
    widths = Array(cols).fill(w);
    widths[cols - 1] += USABLE - w * cols;
  }
  const rows = b.rows.map((cells) => new TableRow({
    tableHeader: cells.every((c) => c.header),
    children: cells.map((c, i) => {
      const span = cells.length < cols && i === cells.length - 1
        ? cols - cells.length + 1 : 1;
      let width = widths[i];
      if (span > 1) width = widths.slice(i).reduce((a, x) => a + x, 0);
      return new TableCell({
        columnSpan: span,
        width: { size: width, type: WidthType.DXA },
        shading: c.header
          ? { type: ShadingType.CLEAR, color: 'auto', fill: 'F2EDE2' }
          : undefined,
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [new Paragraph({
          children: toRuns(c.runs, { bold: c.header, size: 20 }),
          spacing: { after: 0, line: 260 },
        })],
      });
    }),
  }));
  return new Table({
    columnWidths: widths,
    width: { size: USABLE, type: WidthType.DXA },
    rows,
  });
}

const HR = () => new Paragraph({
  text: '',
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: 'C8BFA8', space: 1 } },
  spacing: { before: 120, after: 240 },
});

// ---------------------------------------------------------------- assemble
const HEADING = {
  h1: HeadingLevel.HEADING_1,
  h2: HeadingLevel.HEADING_2,
  h3: HeadingLevel.HEADING_3,
  h4: HeadingLevel.HEADING_4,
  h5: HeadingLevel.HEADING_5,
};

let coverDone = false;
let tocInserted = false;

blocks.forEach((b, idx) => {
  if (idx === 0 && b.type === 'h1') {
    children.push(new Paragraph({
      children: [new TextRun({ text: b.text, bold: true, font: DISPLAY, size: 44 })],
      alignment: AlignmentType.CENTER,
      spacing: { before: 1200, after: 400 },
    }));
    coverDone = true;
    return;
  }

  if (b.type === 'table' && !tocInserted && coverDone) {
    children.push(buildTable(b));
    children.push(new Paragraph({ children: [new PageBreak()] }));
    children.push(new Paragraph({
      children: [new TextRun({ text: 'Table of Contents', bold: true, font: DISPLAY, size: 32 })],
      spacing: { after: 240 },
    }));
    children.push(new TableOfContents('Contents', {
      hyperlink: true,
      headingStyleRange: '1-3',
    }));
    children.push(new Paragraph({ children: [new PageBreak()] }));
    tocInserted = true;
    return;
  }

  switch (b.type) {
    case 'h1':
      children.push(new Paragraph({
        text: b.text,
        heading: HeadingLevel.HEADING_1,
        pageBreakBefore: true,
        spacing: { before: 0, after: 260 },
      }));
      break;
    case 'h2': case 'h3': case 'h4': case 'h5':
      children.push(new Paragraph({
        text: b.text,
        heading: HEADING[b.type],
        spacing: { before: 260, after: 140 },
      }));
      break;
    case 'p': children.push(bodyPara(b)); break;
    case 'li': children.push(listPara(b)); break;
    case 'table': children.push(buildTable(b)); break;
    case 'hr': children.push(HR()); break;
  }
});

const doc = new Document({
  creator: 'PROVA-MG',
  title: 'PROVA-MG: A Probabilistic Routing Framework for Low-Resource Malagasy Speech Recognition',
  description: 'Doctoral methodology note — merged working document',
  styles: {
    // an explicit Normal keeps consumers that don't fall back to docDefaults happy
    paragraphStyles: [{
      id: 'Normal',
      name: 'Normal',
      quickFormat: true,
      run: { font: SERIF, size: 24 },
      paragraph: { spacing: { line: 360 } },
    }],
    default: {
      document: { run: { font: SERIF, size: 24 }, paragraph: { spacing: { line: 360 } } },
      heading1: {
        run: { font: DISPLAY, size: 34, bold: true, color: '1A1A1A' },
        paragraph: { spacing: { before: 300, after: 200 }, outlineLevel: 0 },
      },
      heading2: {
        run: { font: DISPLAY, size: 27, bold: true, color: '1A1A1A' },
        paragraph: { spacing: { before: 280, after: 140 }, outlineLevel: 1 },
      },
      heading3: {
        run: { font: DISPLAY, size: 23, bold: true, color: '2A2A2A' },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 2 },
      },
      heading4: {
        run: { font: SERIF, size: 22, bold: true, italics: true, color: '2A2A2A' },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 3 },
      },
    },
  },
  numbering: {
    config: [
      {
        reference: 'bullets',
        levels: [0, 1, 2].map((level) => ({
          level,
          format: LevelFormat.BULLET,
          text: ['•', '◦', '▪'][level],
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720 + 360 * level, hanging: 360 } } },
        })),
      },
      {
        reference: 'numbers',
        levels: [0, 1, 2].map((level) => ({
          level,
          format: [LevelFormat.DECIMAL, LevelFormat.LOWER_LETTER, LevelFormat.LOWER_ROMAN][level],
          text: [`%1.`, `%2.`, `%3.`][level],
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720 + 360 * level, hanging: 360 } } },
        })),
      },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: 16838 },
        margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN },
      },
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log('wrote', OUT, buf.length, 'bytes;', children.length, 'blocks');
});
