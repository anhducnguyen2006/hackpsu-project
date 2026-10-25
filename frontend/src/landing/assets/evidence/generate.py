"""Regenerate the local evidence artwork after editing researchEvidence.ts.
Run from any directory: python3 path/to/landing/assets/evidence/generate.py.
Uses only the Python standard library; no network requests.
"""
from pathlib import Path
import json, textwrap, html
base = Path(__file__).resolve().parents[2]
data = (base / 'researchEvidence.ts').read_text()
rows = json.loads(data.split('export const RESEARCH_EVIDENCE: ResearchEvidence[] = ', 1)[1].strip().removesuffix(';'))
colors={'discussion':('#222225','#efeff0'),'forum':('#1c1e20','#eeeef0'),'study':('#29292c','#f4f4f3'),'note':('#353535','#f5f4f1'),'reporting':('#262627','#f3f2ed'),'technical':('#181b1e','#e9edef')}
esc=lambda s:html.escape(s,quote=True)
for i,r in enumerate(rows):
 bg,fg=colors[r['category']]
 serif=r['category'] in ('reporting','study')
 font='Georgia, serif' if serif else 'Arial, sans-serif'
 titlelines=textwrap.wrap(r['headline'],width=23 if serif else 24)
 titley=134 if len(titlelines)>2 else 150
 title=''.join(f'<tspan x="48" y="{titley+n*59}">{esc(t)}</tspan>' for n,t in enumerate(titlelines))
 bodyy=titley+(len(titlelines)-1)*59+64
 body=''.join(f'<tspan x="48" y="{bodyy+n*39}">{esc(t)}</tspan>' for n,t in enumerate(textwrap.wrap(r['summary'],width=43)))
 marker={'discussion':'Research discussion','forum':'Workflow discussion','study':'Research note','note':'Field notes','reporting':'Research reporting','technical':'Data workflow'}[r['category']]
 svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="780" height="510" viewBox="0 0 780 510" role="img" aria-labelledby="title desc">
<title id="title">{esc(r['headline'])}</title><desc id="desc">{esc(r['summary'])} Editorial paraphrase of {esc(r['source'])}. Verified 25 Oct 2026.</desc>
<rect width="780" height="510" rx="28" fill="{bg}"/>
<rect x="48" y="47" width="7" height="27" rx="2" fill="#a6a6a8"/>
<text x="72" y="69" font-family="Arial, sans-serif" font-size="28" fill="#bcbcc1">{marker}</text>
<text font-family="{font}" font-size="54" font-weight="{400 if serif else 600}" letter-spacing="-1.3" fill="{fg}">{title}</text>
<text font-family="Arial, sans-serif" font-size="31" fill="#c7c7cb">{body}</text>
<text x="48" y="429" font-family="Arial, sans-serif" font-size="27" fill="{fg}">{esc(r['source'])}</text>
<text x="48" y="475" font-family="Arial, sans-serif" font-size="23" fill="#a9a9af">Editorial summary · Verified 25 Oct 2026</text>
<path d="M694 72h28v28m-28 0 28-28" fill="none" stroke="#aaaab0" stroke-width="3"/>
</svg>'''
 (base/'assets/evidence'/f"{r['id']}.svg").write_text(svg)
print(f'Created {len(rows)} assets from {len(set(r["url"] for r in rows))} verified original URLs')
