"""Printable HTML generation for tickets.

PDF is produced client-side via the browser's print dialog (window.print()).
The /export?format=pdf endpoint serves this HTML with auto-print triggered on load.
"""

from datetime import datetime
from html import escape


def _grade_color(grade: str) -> str:
    return {
        "A": "#2c9e6b", "B": "#7aab2f", "C": "#d39235",
        "D": "#d36a35", "E": "#c0392b",
    }.get(grade, "#5b8cff")


def render_ticket_html(ticket: dict, auto_print: bool = False) -> str:
    """Return a self-contained printable HTML page for a ticket.

    When `auto_print=True`, triggers window.print() on load (used for the
    browser-side PDF export flow).
    """
    created = ticket.get("created_at", "")
    try:
        created = datetime.fromisoformat(created).strftime("%d/%m/%Y %H:%M")
    except Exception:  # noqa: BLE001
        pass

    rows = ""
    for d in ticket.get("details", []):
        rows += f"""
        <tr>
          <td class="lbl">{escape(d['label'])}<div class="det">{escape(d['detail'])}</div></td>
          <td class="num">{d['value']:g} / {d['max']:g}</td>
          <td class="num">{d['weight']:g}</td>
          <td class="num">{d['contribution']:g}%</td>
        </tr>"""

    gc = _grade_color(ticket.get("grade", ""))
    print_script = "<script>window.onload = () => window.print();</script>" if auto_print else ""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Ticket {escape(ticket.get('id',''))}</title>
<style>
  @page {{ size: A4; margin: 18mm; }}
  body {{ font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color:#1c2330; }}
  .head {{ display:flex; justify-content:space-between; align-items:flex-start;
           border-bottom:2px solid #1c2330; padding-bottom:12px; }}
  h1 {{ font-size:20px; margin:0; }}
  .meta {{ color:#6b7690; font-size:12px; margin-top:4px; }}
  .badge {{ text-align:center; }}
  .badge .g {{ font-size:42px; font-weight:800; color:{gc}; line-height:1; }}
  .badge .s {{ font-size:13px; color:#6b7690; }}
  .scope {{ background:#f4f6fb; border:1px solid #e3e8f2; border-radius:8px;
            padding:10px 14px; margin:16px 0; font-size:12px; }}
  table {{ width:100%; border-collapse:collapse; margin-top:8px; font-size:12px; }}
  th {{ text-align:left; color:#6b7690; font-size:11px; text-transform:uppercase;
        border-bottom:1px solid #c9d2e3; padding:6px 8px; }}
  td {{ padding:8px; border-bottom:1px solid #eef1f7; vertical-align:top; }}
  td.num {{ text-align:right; white-space:nowrap; }}
  .lbl {{ font-weight:600; }}
  .det {{ font-weight:400; color:#6b7690; font-size:11px; margin-top:2px; }}
  .notes {{ margin-top:16px; font-size:12px; }}
  footer {{ margin-top:20px; color:#9aa6bd; font-size:10px; border-top:1px solid #eef1f7; padding-top:8px; }}
</style></head>
<body>
  <div class="head">
    <div>
      <h1>{escape(ticket.get('template_name',''))} — {escape(ticket.get('subject',''))}</h1>
      <div class="meta">Ticket {escape(ticket.get('id',''))} · generated {escape(str(created))}</div>
    </div>
    <div class="badge"><div class="g">{escape(ticket.get('grade',''))}</div>
      <div class="s">{ticket.get('score','')} / 100 · {escape(ticket.get('grade_label',''))}</div></div>
  </div>

  <div class="scope"><b>Scope.</b> This report measures the criteria listed below
  for the template "{escape(ticket.get('template_name',''))}". Dimensions outside this template
  are not covered by this score.</div>

  <table>
    <thead><tr><th>Criterion</th><th>Score</th><th>Weight</th><th>Attainment</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>

  {f'<div class="notes"><b>Notes:</b> {escape(ticket["notes"])}</div>' if ticket.get('notes') else ''}

  <footer>Tool — generic evaluation platform. Score = weighted average of criterion attainment, normalised to 100.</footer>
  {print_script}
</body></html>"""
