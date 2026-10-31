"""Plain static HTML report: no JS, dependencies, remote assets, or HTML injection."""
import html
import json
from pathlib import Path


def render(result: dict) -> str:
    e = lambda s: html.escape(str(s), quote=True)
    rows = ''.join(
        '<tr><td><code>{}</code></td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
            *[e(s) for s in (x['id'], x['status'], x['field'],
                              json.dumps(x['observed']), x['source'])])
        for x in result['findings']
    )
    changes = ''.join(
        '<li><code>{}</code>: {}. Mapped tests: {}. Human review required.</li>'.format(
            e(c['control_id']), e(c['change']), e(', '.join(c['mapped_tests']) or 'none'))
        for c in result['standards_changes'])
    actions = ''.join(
        '<li><code>{}</code>: {}</li>'.format(e(a['control_id']), e(a['recommended_action']))
        for a in result['human_review_requests'])
    trace = ''.join('<li>{}: <code>{}</code></li>'.format(t['step'], e(t['tool'])) for t in result['trace'])
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Control Assurance Agent: Sample Run</title>
<style>body{{background:#fff;color:#111;font:17px/1.55 Georgia,serif;max-width:780px;margin:40px auto;padding:0 20px}}h1,h2,code,small{{font-family:monospace}}h1{{font-size:29px}}h2{{margin-top:32px;font-size:21px}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{border-bottom:1px solid #aaa;text-align:left;padding:9px 8px 9px 0}}small{{color:#444}}li{{margin:8px 0}}a{{color:#111}}@media(max-width:540px){{table{{display:block;overflow-x:auto}}}}</style></head><body>
<p><a href="/work/control-assurance-agent/">&larr; technical note</a></p>
<h1>Control Assurance Agent / example run</h1>
<p><strong>System:</strong> {e(result['system'])} (fictional). <strong>Mode:</strong> local read-only demonstration.</p>
<p><strong>Results:</strong> PASS {result['counts']['PASS']} / FAIL {result['counts']['FAIL']} / UNKNOWN {result['counts']['UNKNOWN']} / ERROR {result['counts']['ERROR']}</p>
<p><small>Generated from synthetic fixtures. Not a real organization, assurance opinion, or NIST compliance assessment.</small></p>
<h2>Control results</h2><table><thead><tr><th>ID</th><th>Result</th><th>Field</th><th>Observed</th><th>Evidence source</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Standards version comparison</h2><p>Local, fictional OSCAL-style samples. Changes may be editorial and require human interpretation.</p><ul>{changes}</ul>
<h2>Review queue (not executed)</h2><ul>{actions}</ul>
<h2>Tool-use trace</h2><ol>{trace}</ol>
<p><small>Each tool invocation in the JSON report also records input and output SHA-256 digests. No changes to system configuration were made.</small></p>
</body></html>'''


def write_outputs(result: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'report.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (directory / 'report.html').write_text(render(result), encoding='utf-8')
