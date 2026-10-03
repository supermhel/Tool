"""Printable HTML generation: tickets, tender award reports, bidder debriefs.

PDF is produced client-side via the browser's print dialog (window.print()).
Endpoints serve this HTML, with auto-print triggered on load when asked.
"""

from datetime import datetime
from html import escape

_CSS = """
  @page { size: A4; margin: 18mm; }
  body { font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color:#1c2330; }
  .head { display:flex; justify-content:space-between; align-items:flex-start;
          border-bottom:2px solid #1c2330; padding-bottom:12px; }
  h1 { font-size:20px; margin:0; } h2 { font-size:15px; margin:22px 0 4px; }
  .meta { color:#6b7690; font-size:12px; margin-top:4px; }
  .badge { text-align:center; }
  .badge .g { font-size:42px; font-weight:800; line-height:1; }
  .badge .s { font-size:13px; color:#6b7690; }
  .scope { background:#f4f6fb; border:1px solid #e3e8f2; border-radius:8px;
           padding:10px 14px; margin:16px 0; font-size:12px; }
  table { width:100%; border-collapse:collapse; margin-top:8px; font-size:12px; }
  th { text-align:left; color:#6b7690; font-size:11px; text-transform:uppercase;
       border-bottom:1px solid #c9d2e3; padding:6px 8px; }
  td { padding:8px; border-bottom:1px solid #eef1f7; vertical-align:top; }
  td.num { text-align:right; white-space:nowrap; }
  .lbl { font-weight:600; }
  .det { font-weight:400; color:#6b7690; font-size:11px; margin-top:2px; }
  .flag { color:#c0392b; font-weight:600; }
  .notes { margin-top:16px; font-size:12px; }
  .letter { white-space:pre-wrap; font-size:13px; line-height:1.55; margin-top:14px; }
  footer { margin-top:20px; color:#9aa6bd; font-size:10px; border-top:1px solid #eef1f7; padding-top:8px;
           word-break:break-all; }
"""

_PRINT = "<script>window.onload = () => window.print();</script>"


def _grade_color(grade: str) -> str:
    return {"A": "#2c9e6b", "B": "#7aab2f", "C": "#d39235",
            "D": "#d36a35", "E": "#c0392b"}.get(grade, "#5b8cff")


def _fmt_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except Exception:  # noqa: BLE001
        return iso


def _page(title: str, body: str, auto_print: bool) -> str:
    return (f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
            f"<title>{escape(title)}</title><style>{_CSS}</style></head>"
            f"<body>{body}{_PRINT if auto_print else ''}</body></html>")


def render_ticket_html(ticket: dict, auto_print: bool = False) -> str:
    rows = ""
    for d in ticket.get("details", []):
        rows += f"""
        <tr>
          <td class="lbl">{escape(d['label'])}<div class="det">{escape(d.get('detail', ''))}</div></td>
          <td class="num">{d['value']:g} / {d['max']:g}</td>
          <td class="num">{d['weight']:g}</td>
          <td class="num">{d['contribution']:g}%</td>
        </tr>"""
    gc = _grade_color(ticket.get("grade", ""))
    tpl = f"{escape(ticket.get('template_name', ''))} v{ticket.get('template_version', 1)}"
    notes = (f'<div class="notes"><b>Notes:</b> {escape(ticket["notes"])}</div>'
             if ticket.get("notes") else "")
    seal = (f"<br>Integrity seal (sha256): {escape(ticket['hash'])}" if ticket.get("hash") else "")
    body = f"""
  <div class="head">
    <div>
      <h1>{tpl} — {escape(ticket.get('subject', ''))}</h1>
      <div class="meta">Ticket {escape(ticket.get('id', ''))} · generated {escape(_fmt_date(str(ticket.get('created_at', ''))))}</div>
    </div>
    <div class="badge"><div class="g" style="color:{gc}">{escape(ticket.get('grade', ''))}</div>
      <div class="s">{ticket.get('score', '')} / 100 · {escape(ticket.get('grade_label', ''))}</div></div>
  </div>
  <div class="scope"><b>Scope.</b> This report measures the criteria listed below
  for the template "{escape(ticket.get('template_name', ''))}". Dimensions outside this template
  are not covered by this score.</div>
  <table>
    <thead><tr><th>Criterion</th><th>Score</th><th>Weight</th><th>Attainment</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  {notes}
  <footer>Tool — evaluation platform. Score = weighted average of criterion attainment, normalised to 100.{seal}</footer>"""
    return _page(f"Ticket {ticket.get('id', '')}", body, auto_print)


def render_tender_report_html(doc: dict, res: dict, auto_print: bool = False) -> str:
    tpl = doc["template"]
    rank_rows = "".join(
        f'<tr><td class="num">{r["rank"]}</td><td class="lbl">{escape(r["name"])}</td>'
        f'<td class="num">{r["score"]:g}</td></tr>' for r in res["ranking"])
    sections = ""
    for b in res["bidders"]:
        rows = ""
        for c in b["criteria"]:
            evals = "<br>".join(
                f"<b>{escape(e)}</b> {s['value']:g}: {escape(s['justification'])}"
                for e, s in c["scores"].items())
            cons = ""
            if c["consensus"]:
                cons = (f"<br><b>Consensus {c['consensus']['value']:g}:</b> "
                        f"{escape(c['consensus']['justification'])}")
            flag = ' <span class="flag">(divergent)</span>' if c["flagged"] else ""
            rows += (f'<tr><td class="lbl">{escape(c["label"])}{flag}'
                     f'<div class="det">{evals}{cons}</div></td>'
                     f'<td class="num">{c["effective"]:g} / {c["max"]:g}</td>'
                     f'<td class="num">{c["weight"]:g}</td></tr>')
        sections += (f"<h2>{escape(b['name'])} — {b['score']:g} / 100 ({escape(b['grade'])})</h2>"
                     f"<table><thead><tr><th>Criterion and evaluator justifications</th>"
                     f"<th>Final</th><th>Weight</th></tr></thead><tbody>{rows}</tbody></table>")
    body = f"""
  <div class="head"><div>
    <h1>Award report — {escape(doc['name'])}</h1>
    <div class="meta">Tender {escape(doc['id'])} · template {escape(tpl['name'])} v{tpl['version']} ·
    awarded {escape(_fmt_date(doc.get('awarded_at', '')))} · evaluators: {escape(', '.join(doc['evaluators']))}</div>
  </div></div>
  <div class="scope">Weights were fixed before scoring. Evaluators scored independently;
  criteria where scores differed by more than {doc['divergence_threshold'] * 100:g}% of the scale were
  reconciled by consensus with a written justification.</div>
  <h2>Ranking</h2>
  <table><thead><tr><th>Rank</th><th>Bidder</th><th>Score</th></tr></thead><tbody>{rank_rows}</tbody></table>
  {sections}
  <footer>Each bidder's result is sealed in a hash-chained ticket. Verify with GET /api/v1/tickets/verify.</footer>"""
    return _page(f"Award report {doc['name']}", body, auto_print)


def render_debrief_html(doc: dict, res: dict, bidder_id: str, auto_print: bool = False) -> str:
    b = next(x for x in res["bidders"] if x["bidder_id"] == bidder_id)
    rank = next(r["rank"] for r in res["ranking"] if r["name"] == b["name"])
    n = len(res["bidders"])
    top = max(x["score"] for x in res["bidders"])
    rows = ""
    for c in b["criteria"]:
        just = (c["consensus"]["justification"] if c["consensus"]
                else " ".join(s["justification"] for s in c["scores"].values()))
        rows += (f'<tr><td class="lbl">{escape(c["label"])}<div class="det">{escape(just)}</div></td>'
                 f'<td class="num">{c["effective"]:g} / {c["max"]:g}</td>'
                 f'<td class="num">{c["weight"]:g}</td></tr>')
    body = f"""
  <div class="head"><div>
    <h1>Debrief — {escape(b['name'])}</h1>
    <div class="meta">Tender: {escape(doc['name'])} · {escape(_fmt_date(doc.get('awarded_at', '')))}</div>
  </div></div>
  <div class="letter">Your tender was ranked {rank} of {n} with a score of {b['score']:g} / 100
(grade {escape(b['grade'])}). The highest score awarded in this procedure was {top:g} / 100.
Evaluation criteria and weights were those published for this procedure
(template "{escape(doc['template']['name'])}" v{doc['template']['version']}).
Reasons for each score follow.</div>
  <table><thead><tr><th>Criterion and reasons</th><th>Your score</th><th>Weight</th></tr></thead>
  <tbody>{rows}</tbody></table>
  <footer>Other bidders' identities and detailed scores are confidential and not disclosed.</footer>"""
    return _page(f"Debrief {b['name']}", body, auto_print)
