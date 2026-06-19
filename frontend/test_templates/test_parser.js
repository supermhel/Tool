import fs from 'fs/promises';
import path from 'path';
import YAML from 'js-yaml';

function parseCsv(text) {
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  if (lines.length === 0) return null;
  const hasHeader = /id|label|max|weight/i.test(lines[0]);
  const rows = lines.map((line) => {
    const cols = [];
    let cur = '', inQ = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') { inQ = !inQ; continue; }
      if (ch === ',' && !inQ) { cols.push(cur); cur = ''; continue; }
      cur += ch;
    }
    cols.push(cur);
    return cols.map((c) => c.trim());
  });

  const result = { id: `csv-${Date.now()}`, name: 'Uploaded CSV template', criteria: [], scope: { covered: [], excluded: [] } };
  if (hasHeader) {
    const headers = rows[0].map((h) => h.toLowerCase());
    for (let i = 1; i < rows.length; i++) {
      const r = rows[i];
      if (r.length === 0) continue;
      const obj = {};
      headers.forEach((h, j) => { obj[h] = r[j]; });
      const c = {
        id: obj.id || `c${i}`,
        label: obj.label || obj.name || `Criterion ${i}`,
        max: Number(obj.max) || 10,
        weight: Number(obj.weight) || 1,
        detail: obj.detail || "",
      };
      result.criteria.push(c);
    }
  } else {
    rows.forEach((r, i) => {
      const c = {
        id: r[0] || `c${i}`,
        label: r[1] || `Criterion ${i}`,
        max: Number(r[2]) || 10,
        weight: Number(r[3]) || 1,
        detail: r[4] || "",
      };
      result.criteria.push(c);
    });
  }
  return result;
}

async function tryParse(file) {
  const p = path.join(process.cwd(), 'test_templates', file);
  const txt = await fs.readFile(p, 'utf8');
  let tpl = null;
  try {
    if (file.endsWith('.json')) tpl = JSON.parse(txt);
    else if (file.endsWith('.yaml') || file.endsWith('.yml')) tpl = YAML.load(txt);
    else if (file.endsWith('.csv')) tpl = parseCsv(txt);
    else {
      try { tpl = JSON.parse(txt); }
      catch { try { tpl = YAML.load(txt); } catch { tpl = parseCsv(txt); } }
    }
    console.log(`Parsed ${file}: id=${tpl.id} name=${tpl.name} criteria=${tpl.criteria.length}`);
  } catch (e) {
    console.error(`Failed ${file}:`, e.message || e);
  }
}

async function run() {
  console.log('Starting parser tests...');
  await tryParse('sample.json');
  await tryParse('sample.yaml');
  await tryParse('sample.csv');
  console.log('Parser tests completed.');
}

run().catch((e) => { console.error(e); process.exit(1); });
