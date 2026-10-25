"""Local typography and small truthful UI visuals for the repair studio."""
import base64
from functools import lru_cache
from html import escape

import streamlit as st

from .common import ROOT


@lru_cache(maxsize=4)
def _font(name,modified):
    return base64.b64encode((ROOT/'assets/fonts'/name).read_bytes()).decode()


def apply_theme():
    fonts=[]
    for name,family,weight in (('Inter.woff2','Studio Inter','100 900'),('IBMPlexMono-Regular.woff2','Studio Mono','400')):
        path=ROOT/'assets/fonts'/name
        if path.exists():fonts.append("@font-face{font-family:'"+family+"';src:url(data:font/woff2;base64,"+_font(name,path.stat().st_mtime_ns)+") format('woff2');font-weight:"+weight+";font-style:normal;font-display:swap;}")
    st.html('<style>'+''.join(fonts)+(ROOT/'assets/studio.css').read_text()+'</style>')


def badge(text,kind='saved'):
    return f'<span class="studio-badge {escape(kind)}"><i class="studio-dot"></i>{escape(text)}</span>'


def topbar():
    icon='<svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 16V8h5v8h6V8h5M2 12h2m16 0h2M9 6v2m6 8v2" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    st.markdown('<div class="studio-topbar"><div class="studio-brand"><span class="studio-brand-icon">'+icon+'</span>RTLRefine<span class="studio-brand-sub">Repair studio</span></div><div class="studio-provider"><b>NVIDIA Nemotron</b> / Nebius Token Factory</div></div>',unsafe_allow_html=True)


def steps(record):
    done=[bool(record and record.get('original_discovery')),bool(record and record.get('pool_candidates') is not None),bool(record and record.get('final_check')),bool(record and record.get('accepted'))]
    parts=[]
    for i,title in enumerate(('Reproduce','Find a patch','Verify','Export')):
        if i:parts.append('<span class="studio-step-line"></span>')
        parts.append(f'<span class="studio-step {"is-done" if done[i] else ""}"><b>{i+1:02d}</b>{title}</span>')
    st.html('<div class="studio-steps">'+''.join(parts)+'</div>')


def waveform(before,after):
    """Discrete captured values only. Unknown/invalid oracle values remain gaps."""
    if not before or not before.get('rows'):return ''
    rows=before['rows'];patched={r['cycle']:r['actual'] for r in (after or {}).get('rows',[])}
    series=[('Expected','#8395a7',[r['expected'] for r in rows]),('Original','#ed929d',[r['actual'] for r in rows])]
    if after:series.append(('Checked','#7be2c0',[patched.get(r['cycle'],'?') for r in rows]))
    x0=90;width=650;cell=width/len(rows);height=40+len(series)*43
    parts=[f'<div class="studio-waveform-viewport" role="region" tabindex="0" aria-label="Captured signal samples"><svg class="studio-waveform" viewBox="0 0 760 {height}" role="img" aria-label="Captured expected, original and checked values for {escape(before["port"])}">']
    for i,row in enumerate(rows):
        x=x0+i*cell
        if row['expected']!='?' and not row['match']:parts.append(f'<rect x="{x:.2f}" y="20" width="{cell:.2f}" height="{height-30}" fill="#de7887" opacity=".055"/>')
        parts.append(f'<path d="M{x:.2f} 20V{height-10}" stroke="#293745" stroke-width=".6"/>')
        parts.append(f'<text x="{x+cell/2:.2f}" y="12" text-anchor="middle" fill="#8296a8">{row["cycle"]}</text>')
    for lane,(label,color,values) in enumerate(series):
        center=42+lane*43;parts.append(f'<text x="0" y="{center+4}" fill="{color}">{label}</text>')
        binary=all(v=='?' or int(v,16) in (0,1) for v in values)
        previous=None
        for i,value in enumerate(values):
            x=x0+i*cell
            if value=='?':
                parts.append(f'<text x="{x+cell/2:.2f}" y="{center+3}" text-anchor="middle" fill="#536779">?</text>');previous=None;continue
            integer=int(value,16)
            if binary:
                y=center-9 if integer else center+9
                if previous is not None:parts.append(f'<path d="M{x:.2f} {previous}V{y}" fill="none" stroke="{color}" stroke-width="1.7"/>')
                parts.append(f'<path d="M{x:.2f} {y}H{x+cell:.2f}" fill="none" stroke="{color}" stroke-width="1.7"><title>Cycle {rows[i]["cycle"]}: {label} {integer}</title></path>');previous=y
            else:
                parts.append(f'<path d="M{x+3:.2f} {center-10}H{x+cell-3:.2f}L{x+cell:.2f} {center}L{x+cell-3:.2f} {center+10}H{x+3:.2f}L{x:.2f} {center}Z" fill="none" stroke="{color}" stroke-width=".8"/><text x="{x+cell/2:.2f}" y="{center+3}" text-anchor="middle" fill="{color}">{escape(value)}</text>')
    parts.append('</svg></div>');return ''.join(parts)
