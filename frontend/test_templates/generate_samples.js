import fs from 'fs';
import path from 'path';
import PDFDocument from 'pdfkit';
import { Document, Packer, Paragraph, TextRun } from 'docx';

async function makePdf(dest) {
  return new Promise((resolve, reject) => {
    const doc = new PDFDocument();
    const stream = fs.createWriteStream(dest);
    doc.pipe(stream);
    doc.fontSize(16).text('Custom PDF Template', { underline: true });
    doc.moveDown();
    doc.fontSize(12).text('This PDF contains a JSON template embedded as plain text below.');
    doc.moveDown();
    const tpl = {
      id: 'pdf_template',
      name: 'PDF-embedded Template',
      criteria: [
        { id: 'steps', label: 'Steps', max: 10, weight: 2, detail: 'Number of steps' },
        { id: 'automation', label: 'Automation', max: 10, weight: 1, detail: 'Degree of automation' }
      ]
    };
    doc.fontSize(10).text('---BEGIN TEMPLATE (JSON)---');
    doc.font('Courier').text(JSON.stringify(tpl, null, 2));
    doc.font('Helvetica');
    doc.text('---END TEMPLATE---');
    doc.end();
    stream.on('finish', resolve);
    stream.on('error', reject);
  });
}

async function makeDocx(dest) {
  const doc = new Document({
    creator: 'Tool',
    title: 'Sample DOCX Template',
    sections: [
      {
        children: [
          new Paragraph({ children: [ new TextRun({ text: 'Custom DOCX Template', bold: true, size: 32 }) ] }),
          new Paragraph({ text: '' }),
          new Paragraph({ text: 'This DOCX contains a YAML template embedded as plain text below.' }),
          new Paragraph({ text: '' }),
          new Paragraph({ children: [ new TextRun({ text: '---BEGIN TEMPLATE (YAML)---' }) ] }),
          new Paragraph({ text: 'id: docx_template' }),
          new Paragraph({ text: 'name: DOCX-embedded Template' }),
          new Paragraph({ text: 'criteria:' }),
          new Paragraph({ text: '  - id: steps' }),
          new Paragraph({ text: '    label: Steps' }),
          new Paragraph({ text: '    max: 10' }),
          new Paragraph({ text: '    weight: 2' }),
          new Paragraph({ text: '  - id: automation' }),
          new Paragraph({ text: '    label: Automation' }),
          new Paragraph({ text: '    max: 10' }),
          new Paragraph({ text: '    weight: 1' }),
          new Paragraph({ children: [ new TextRun({ text: '---END TEMPLATE---' }) ] }),
        ],
      },
    ],
  });

  const buffer = await Packer.toBuffer(doc);
  await fs.promises.writeFile(dest, buffer);
}

async function run() {
  const outDir = path.join(process.cwd());
  const pdfPath = path.join(outDir, 'sample.pdf');
  const docxPath = path.join(outDir, 'sample.docx');
  console.log('Generating sample PDF ->', pdfPath);
  await makePdf(pdfPath);
  console.log('Generating sample DOCX ->', docxPath);
  await makeDocx(docxPath);
  console.log('Done.');
}

run().catch((e) => { console.error(e); process.exit(1); });
