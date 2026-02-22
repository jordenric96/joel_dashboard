import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime
import json
import os

# --- CONFIGURATIE ---
COLORS = {
    'primary': '#0f172a',
    'gold': '#d4af37',
    'bg': '#f8fafc',
    'card': '#ffffff',
    'text': '#1e293b',
    'text_light': '#64748b',
    'success': '#10b981',
    'danger': '#ef4444',
    'chart_main': '#3b82f6',
    'chart_sec': '#cbd5e1'
}

SPORT_CONFIG = {
    'Mountainbike': {'icon': '🚵', 'color': '#0ea5e9'},
    'Wandelen': {'icon': '🥾', 'color': '#10b981'},
    'Default': {'icon': '🏅', 'color': '#64748b'}
}

# --- HULPFUNCTIES ---

def format_time(seconds):
    if pd.isna(seconds) or seconds <= 0: return '-'
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f'{hours}u {minutes:02d}m'

def format_diff_html(current, previous, unit="", inverse=False):
    if pd.isna(previous): previous = 0
    diff = current - previous
    if diff == 0: return '<span class="diff-neutral">-</span>'
    is_good = (diff > 0) if not inverse else (diff < 0)
    color = COLORS['success'] if is_good else COLORS['danger']
    arrow = "▲" if diff > 0 else "▼"
    if unit == 'u': val_str = f"{abs(diff):.1f}"
    else: val_str = f"{abs(diff):.1f}" if isinstance(diff, float) else f"{abs(int(diff))}"
    bg = f"{color}15"
    return f'<span style="color:{color}; background:{bg}; padding:2px 8px; border-radius:6px; font-weight:700; font-size:0.85em;">{arrow} {val_str} {unit}</span>'

def get_sport_style(sport_name):
    for key, config in SPORT_CONFIG.items():
        if key.lower() in str(sport_name).lower():
            return config
    return SPORT_CONFIG['Default']

def robust_date_parser(date_series):
    dutch_month_mapping = {
        'jan': 'Jan', 'feb': 'Feb', 'mrt': 'Mar', 'apr': 'Apr', 
        'mei': 'May', 'jun': 'Jun', 'jul': 'Jul', 'aug': 'Aug', 
        'sep': 'Sep', 'okt': 'Oct', 'nov': 'Nov', 'dec': 'Dec'
    }
    date_series_str = date_series.astype(str).str.lower()
    for dutch, eng in dutch_month_mapping.items():
        date_series_str = date_series_str.str.replace(dutch, eng, regex=False)
    dates = pd.to_datetime(date_series_str, format='%d %b %Y, %H:%M:%S', errors='coerce')
    mask = dates.isna()
    if mask.any():
        dates[mask] = pd.to_datetime(date_series_str[mask], errors='coerce', dayfirst=True)
    return dates

# --- HTML GENERATOREN ---

def generate_kpi(title, value, icon="", diff=""):
    return f"""
    <div class="kpi-card">
        <div class="kpi-icon-box">{icon}</div>
        <div class="kpi-content">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{diff}</div>
        </div>
    </div>
    """

def generate_sport_cards(df_cur, df_prev):
    html = '<div class="sport-grid">'
    sports = sorted(df_cur['Activiteitstype'].unique())
    
    for sport in sports:
        df_s_cur = df_cur[df_cur['Activiteitstype'] == sport]
        if df_prev is not None and not df_prev.empty:
            df_s_prev = df_prev[df_prev['Activiteitstype'] == sport]
            prev_count = len(df_s_prev)
            prev_dist = df_s_prev['Afstand_km'].sum()
        else:
            prev_count = 0; prev_dist = 0
            
        style = get_sport_style(sport)
        count = len(df_s_cur)
        dist = df_s_cur['Afstand_km'].sum()
        time = df_s_cur['Beweegtijd_sec'].sum()
        avg_hr = df_s_cur['Gemiddelde_Hartslag'].mean()
        
        diff_count = format_diff_html(count, prev_count)
        diff_dist = format_diff_html(dist, prev_dist, "km")
        
        dist_html = f"""<div class="stat-col"><div class="label">Afstand</div><div class="val">{dist:,.0f} <small>km</small></div><div class="sub">{diff_dist}</div></div>"""

        extra_stat = ""
        if 'Mountainbike' in sport:
            real_rides = df_s_cur[df_s_cur['Afstand_km'] > 5]
            max_spd = real_rides['Gemiddelde_Snelheid_km_u'].max() if not real_rides.empty else 0
            if max_spd > 0: extra_stat = f'<div class="stat-row"><span>Snelste rit (gem)</span> <strong>{max_spd:.1f} km/u</strong></div>'
        else:
            max_dst = df_s_cur['Afstand_km'].max()
            if max_dst > 0: extra_stat = f'<div class="stat-row"><span>Langste</span> <strong>{max_dst:.1f} km</strong></div>'
        
        hr_html = f'<div class="stat-row"><span>Gem. Hartslag</span> <strong class="hr-blur">{avg_hr:.0f} bpm</strong></div>' if pd.notna(avg_hr) else ""

        html += f"""
        <div class="sport-card">
            <div class="sport-header">
                <div class="sport-icon-circle" style="background:{style['color']}20; color:{style['color']}">{style['icon']}</div>
                <h3>{sport}</h3>
            </div>
            <div class="sport-body">
                <div class="stat-main">
                    <div class="stat-col"><div class="label">Sessies</div><div class="val">{count}</div><div class="sub">{diff_count}</div></div>
                    <div class="stat-divider"></div>
                    {dist_html}
                </div>
                <div class="sport-details">
                    <div class="stat-row"><span>Tijd</span> <strong>{format_time(time)}</strong></div>
                    {extra_stat}
                    {hr_html}
                </div>
            </div>
        </div>
        """
    html += '</div>'
    return html

def generate_hall_of_fame(df):
    html = '<div class="hof-grid">'
    sports = sorted(df['Activiteitstype'].unique())
    
    for sport in sports:
        df_s = df[(df['Activiteitstype'] == sport) & (df['Afstand_km'] > 1.0)]
        if df_s.empty: continue
        
        style = get_sport_style(sport)
        records = []
        
        idx_dist = df_s['Afstand_km'].idxmax()
        if pd.notna(idx_dist):
            row = df_s.loc[idx_dist]
            records.append({'label': 'Langste Afstand', 'val': f"{row['Afstand_km']:.1f} km", 'date': row['Datum'], 'icon': '📏', 'class': ''})
        
        if 'Mountainbike' in sport:
            df_speed = df_s[df_s['Gemiddelde_Snelheid_km_u'] > 10]
            if not df_speed.empty:
                idx = df_speed['Gemiddelde_Snelheid_km_u'].idxmax()
                row = df_speed.loc[idx]
                records.append({'label': 'Hoogste Gem. Snelheid', 'val': f"{row['Gemiddelde_Snelheid_km_u']:.1f} km/u", 'date': row['Datum'], 'icon': '🚀', 'class': 'rocket'})
        elif 'Wandelen' in sport:
             df_speed = df_s[(df_s['Gemiddelde_Snelheid_km_u'] > 3) & (df_s['Gemiddelde_Snelheid_km_u'] < 10)]
             if not df_speed.empty:
                idx = df_speed['Gemiddelde_Snelheid_km_u'].idxmax()
                row = df_speed.loc[idx]
                pace_sec = 3600 / row['Gemiddelde_Snelheid_km_u']
                pace = f"{int(pace_sec//60)}:{int(pace_sec%60):02d} /km"
                records.append({'label': 'Snelste Tempo', 'val': pace, 'date': row['Datum'], 'icon': '⚡', 'class': ''})

        idx_time = df_s['Beweegtijd_sec'].idxmax()
        if pd.notna(idx_time):
             row = df_s.loc[idx_time]
             records.append({'label': 'Langste Duur', 'val': format_time(row['Beweegtijd_sec']), 'date': row['Datum'], 'icon': '⏱️', 'class': ''})
        
        if not records: continue

        rec_html = ""
        for r in records:
            icon_class = r.get('class', '')
            rec_html += f"""
            <div class="hof-record">
                <div class="hof-icon {icon_class}" style="color:{style['color']}">{r['icon']}</div>
                <div class="hof-data">
                    <div class="hof-label">{r['label']}</div>
                    <div class="hof-val">{r['val']}</div>
                    <div class="hof-date">{r['date'].strftime('%d %b %Y')}</div>
                </div>
            </div>"""
        html += f"""<div class="hof-card"><div class="hof-header"><h3 style="color:{style['color']}">{style['icon']} {sport}</h3></div><div class="hof-body">{rec_html}</div></div>"""
    html += "</div>"
    return html

def generate_gear_section(df):
    if 'Uitrusting voor activiteit' not in df.columns:
        return "<p style='text-align:center; color:#999'>Geen uitrusting data gevonden.</p>"
    
    df_gear = df.copy()
    df_gear['Uitrusting voor activiteit'] = df_gear['Uitrusting voor activiteit'].fillna('').astype(str)
    
    df_gear = df_gear[
        (df_gear['Uitrusting voor activiteit'].str.strip() != '') & 
        (df_gear['Uitrusting voor activiteit'].str.lower() != 'nan')
    ]

    if df_gear.empty:
         return "<p style='text-align:center; color:#999'>Nog geen uitrusting gebruikt.</p>"

    gear_stats = df_gear.groupby('Uitrusting voor activiteit').agg(
        Aantal=('Activiteitstype', 'count'),
        Afstand=('Afstand_km', 'sum'),
        Laatste_Gebruik=('Datum', 'max'),
        Type=('Activiteitstype', lambda x: x.mode()[0] if not x.mode().empty else 'Onbekend')
    ).reset_index()
    
    gear_stats = gear_stats.sort_values('Afstand', ascending=False)
    
    html = '<div class="kpi-grid">'
    for _, row in gear_stats.iterrows():
        gear_name = row['Uitrusting voor activiteit']
        icon = '🚲' if 'Mountainbike' in str(row['Type']) else '🥾'
        
        max_dist = 10000 if icon == '🚲' else 1000
        pct = min(100, (row['Afstand'] / max_dist) * 100)
        color = COLORS['success'] if pct < 50 else (COLORS['gold'] if pct < 80 else COLORS['danger'])
        
        html += f"""
        <div class="kpi-card" style="display:block;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-size:24px;">{icon}</span>
                    <div style="font-weight:700; color:{COLORS['text']}">{gear_name}</div>
                </div>
                <div style="font-size:12px; color:{COLORS['text_light']}">{row['Laatste_Gebruik'].strftime('%d-%m-%y')}</div>
            </div>
            <div style="font-size:20px; font-weight:700; margin-bottom:5px;">{row['Afstand']:,.0f} km</div>
            <div style="background:#e2e8f0; height:6px; border-radius:3px; overflow:hidden;">
                <div style="width:{pct}%; background:{color}; height:100%;"></div>
            </div>
            <div style="font-size:11px; color:{COLORS['text_light']}; margin-top:4px;">{row['Aantal']}x gebruikt</div>
        </div>
        """
    html += '</div>'
    return html

def genereer_manifest():
    manifest = {
        "name": "Sport Joël",
        "short_name": "Sport",
        "start_url": "./dashboard.html",
        "display": "standalone",
        "background_color": "#f8fafc",
        "theme_color": "#0f172a",
        "icons": [{"src": "icon.png", "sizes": "512x512", "type": "image/png"}]
    }
    with open('manifest.json', 'w') as f: json.dump(manifest, f)

def genereer_dashboard(csv_input='activities.csv', html_output='dashboard.html'):
    print("🚀 Start Generatie V12 (Herstel Joël + Rocket CSS + Koersverloop 23/24)...")
    try:
        df = pd.read_csv(csv_input)
    except:
        print("❌ CSV niet gevonden.")
        return

    # Slim zoeken naar verschillende mogelijke namen voor de kolommen
    rename_mapping = {
        'Datum van activiteit': 'Datum', 'Activity Date': 'Datum',
        'Naam activiteit': 'Naam', 'Activity Name': 'Naam',
        'Activiteitstype': 'Activiteitstype', 'Activity Type': 'Activiteitstype',
        'Beweegtijd': 'Beweegtijd_sec', 'Moving Time': 'Beweegtijd_sec',
        'Afstand': 'Afstand_km', 'Distance': 'Afstand_km',
        'Totale stijging': 'Hoogte_m', 'Hoogtewinst': 'Hoogte_m', 'Hoogteverschil': 'Hoogte_m', 'Elevation Gain': 'Hoogte_m',
        'Gemiddelde hartslag': 'Gemiddelde_Hartslag', 'Average Heart Rate': 'Gemiddelde_Hartslag',
        'Gemiddelde snelheid': 'Gemiddelde_Snelheid_km_u', 'Average Speed': 'Gemiddelde_Snelheid_km_u',
        'Max. snelheid': 'Max_Snelheid_km_u', 'Max Speed': 'Max_Snelheid_km_u',
        'Uitrusting voor activiteit': 'Uitrusting voor activiteit', 'Activity Gear': 'Uitrusting voor activiteit'
    }
    
    df = df.rename(columns=lambda x: rename_mapping.get(x.strip(), x))

    # --- VEILIGHEIDSCHECK ONTBREKENDE DATA ---
    vereiste_kolommen = ['Hoogte_m', 'Gemiddelde_Hartslag', 'Gemiddelde_Snelheid_km_u', 'Beweegtijd_sec', 'Afstand_km']
    for col in vereiste_kolommen:
        if col not in df.columns:
            df[col] = 0.0

    cols = ['Afstand_km', 'Hoogte_m', 'Gemiddelde_Snelheid_km_u', 'Gemiddelde_Hartslag', 'Max_Snelheid_km_u']
    for c in cols:
        if c in df.columns and df[c].dtype == object:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '.'), errors='coerce')
            
    for col in vereiste_kolommen:
        df[col] = df[col].fillna(0)
    # -----------------------------------------

    if df['Gemiddelde_Snelheid_km_u'].mean() < 8: 
        df['Gemiddelde_Snelheid_km_u'] *= 3.6
        if 'Max_Snelheid_km_u' in df.columns: df['Max_Snelheid_km_u'] *= 3.6

    # --- FILTER MTB & WANDELEN ---
    mask_exclude = df['Activiteitstype'].str.contains('Virtuele|Virtueel|Zwift|Hardloop|Run', case=False, na=False)
    df = df[~mask_exclude]

    if 'Naam' in df.columns:
        mask_mtb = df['Naam'].str.contains('rit|ochtend|fiets|mountainbike|mtb', case=False, na=False) | \
                   df['Activiteitstype'].str.contains('fiets|ride|mountainbike|mtb', case=False, na=False)
    else:
        mask_mtb = df['Activiteitstype'].str.contains('fiets|ride|mountainbike|mtb', case=False, na=False)

    df.loc[mask_mtb, 'Activiteitstype'] = 'Mountainbike'
    
    if 'Uitrusting voor activiteit' not in df.columns:
        df['Uitrusting voor activiteit'] = ''
    df.loc[mask_mtb, 'Uitrusting voor activiteit'] = 'Emtb trek'

    mask_wandel = df['Activiteitstype'].str.contains('wandel|hike|walk', case=False, na=False)
    df.loc[mask_wandel, 'Activiteitstype'] = 'Wandelen'

    df = df[df['Activiteitstype'].isin(['Mountainbike', 'Wandelen'])]
    # -------------------------------------

    if 'Datum' not in df.columns:
        print("❌ Geen Datum kolom gevonden, kan niet verder.")
        return

    df['Datum'] = robust_date_parser(df['Datum'])
    df['Jaar'] = df['Datum'].dt.year
    df['DagVanJaar'] = df['Datum'].dt.dayofyear
    
    now = datetime.now()
    huidig_jaar = now.year
    max_datum = df['Datum'].max()
    
    if pd.isna(max_datum):
        print("❌ Geen geldige data over na het filteren van de ritten.")
        return
        
    ytd_day = max_datum.dayofyear if max_datum.year == huidig_jaar else 366

    genereer_manifest()

    nav_html = ""
    sections_html = ""
    jaren = sorted(df['Jaar'].dropna().unique(), reverse=True)
    alle_jaren = list(df['Jaar'].dropna().unique())
    
    for jaar in jaren:
        is_cur = (jaar == max_datum.year)
        df_j = df[df['Jaar'] == jaar]
        
        prev = jaar - 1
        df_prev_all = df[df['Jaar'] == prev]
        df_prev_ytd = df_prev_all[df_prev_all['DagVanJaar'] <= ytd_day] if is_cur else df_prev_all
        
        sc = {'n': len(df_j), 'km': df_j['Afstand_km'].sum(), 'h': df_j['Hoogte_m'].sum(), 't': df_j['Beweegtijd_sec'].sum()}
        sp = {'n': len(df_prev_ytd), 'km': df_prev_ytd['Afstand_km'].sum(), 'h': df_prev_ytd['Hoogte_m'].sum(), 't': df_prev_ytd['Beweegtijd_sec'].sum()}
        
        time_diff_hours = (sc['t'] - sp['t']) / 3600
        
        kpis = f"""<div class="kpi-grid">
            {generate_kpi("Sessies", sc['n'], "🔥", format_diff_html(sc['n'], sp['n']))}
            {generate_kpi("Afstand", f"{sc['km']:,.0f} km", "📏", format_diff_html(sc['km'], sp['km'], "km"))}
            {generate_kpi("Hoogtemeters", f"{sc['h']:,.0f} m", "⛰️", format_diff_html(sc['h'], sp['h'], "m"))}
            {generate_kpi("Tijd", format_time(sc['t']), "⏱️", format_diff_html(time_diff_hours, 0, "u"))}
        </div>"""
        
        # --- KOERSVERLOOP: Toon actieve jaar dik, 2023/2024 en andere jaren als vergelijking ---
        fig = px.line(title=f"Koersverloop {int(jaar)}")
        
        # Voeg EERST de vergelijkingsjaren toe (zoals 2023 en 2024) zodat ze op de achtergrond staan
        jaren_om_te_tonen = set([prev, 2023, 2024]) 
        for y in sorted(jaren_om_te_tonen):
            if y in alle_jaren and y != jaar:
                df_y = df[df['Jaar'] == y].sort_values('DagVanJaar')[['DagVanJaar', 'Afstand_km']].copy()
                df_y['Cum'] = df_y['Afstand_km'].cumsum()
                if not df_y.empty:
                    fig.add_scatter(x=df_y['DagVanJaar'], y=df_y['Cum'], name=f"{int(y)}", line_color=COLORS['chart_sec'], line_dash='dot', line_width=1.5)
        
        # Voeg DAARNA het huidige (actieve) jaar toe (dikke blauwe lijn)
        df_cum = df_j.sort_values('DagVanJaar')[['DagVanJaar', 'Afstand_km']].copy()
        df_cum['Cum'] = df_cum['Afstand_km'].cumsum()
        fig.add_scatter(x=df_cum['DagVanJaar'], y=df_cum['Cum'], name=f"{int(jaar)}", line_color=COLORS['chart_main'], line_width=3)
        
        fig.update_layout(template='plotly_white', margin=dict(t=40,l=20,r=20,b=20), height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", y=1.1, x=0))

        nav_html += f'<button class="nav-btn {"active" if is_cur else ""}" onclick="openTab(event, \'view-{int(jaar)}\')">{int(jaar)}</button>'
        
        sections_html += f"""
        <div id="view-{int(jaar)}" class="tab-content" style="display: {'block' if is_cur else 'none'};">
            <h2 class="section-title">Overzicht {int(jaar)}</h2>
            {kpis}
            <h3 class="section-subtitle">Per Sport</h3>
            {generate_sport_cards(df_j, df_prev_ytd)}
            <h3 class="section-subtitle">Analyse</h3>
            <div class="chart-box full-width">{fig.to_html(full_html=False, include_plotlyjs='cdn')}</div>
        </div>
        """

    nav_html += '<button class="nav-btn" onclick="openTab(event, \'view-Total\')">Totaal</button>'
    tk_n = len(df); tk_km = df['Afstand_km'].sum(); tk_time = df['Beweegtijd_sec'].sum()
    sections_html += f"""<div id="view-Total" class="tab-content" style="display:none;">
        <h2 class="section-title">Carrière</h2>
        <div class="kpi-grid">
            {generate_kpi("Totaal Sessies", tk_n, "🏆")}
            {generate_kpi("Totaal Km", f"{tk_km:,.0f} km", "🌍")}
            {generate_kpi("Totaal Tijd", format_time(tk_time), "⏱️")}
        </div>
        {generate_sport_cards(df, None)}
    </div>"""

    nav_html += '<button class="nav-btn" onclick="openTab(event, \'view-Garage\')">Garage</button>'
    sections_html += f"""<div id="view-Garage" class="tab-content" style="display:none;">
        <h2 class="section-title">De Garage</h2>
        {generate_gear_section(df)}
    </div>"""

    nav_html += '<button class="nav-btn" onclick="openTab(event, \'view-HOF\')">Records</button>'
    sections_html += f"""<div id="view-HOF" class="tab-content" style="display:none;">
        <h2 class="section-title">Eregalerij</h2>
        {generate_hall_of_fame(df)}
    </div>"""

    opt = "".join([f'<option value="{s}">{s}</option>' for s in sorted(df['Activiteitstype'].unique())])
    rows = ""
    for _, row in df.sort_values('Datum', ascending=False).iterrows():
        st = get_sport_style(row['Activiteitstype'])
        hr = f"{row['Gemiddelde_Hartslag']:.0f}" if pd.notna(row['Gemiddelde_Hartslag']) and row['Gemiddelde_Hartslag'] > 0 else "-"
        rows += f"""<tr data-sport="{row['Activiteitstype']}"><td><div style="width:8px;height:8px;border-radius:50%;background:{st['color']}"></div></td>
        <td>{row['Datum'].strftime('%d-%m-%y')}</td><td>{row['Activiteitstype']}</td><td>{row['Naam']}</td>
        <td class="num">{row['Afstand_km']:.1f}</td><td class="num hr-blur">{hr}</td></tr>"""

    detail_html = f"""<div class="detail-section"><div class="detail-header"><h3>Logboek</h3>
    <select id="sf" onchange="filterTable()"><option value="ALL">Alles</option>{opt}</select></div>
    <div style="overflow-x:auto"><table id="dt"><thead><tr><th></th><th>Datum</th><th>Sport</th><th>Naam</th><th class="num">Km</th><th class="num">❤️</th></tr></thead>
    <tbody>{rows}</tbody></table></div></div>"""

    html = f"""
    <!DOCTYPE html>
    <html lang="nl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        <link rel="manifest" href="manifest.json">
        <link rel="apple-touch-icon" href="icon.png">
        <title>Sportoverzicht Joël</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{ --primary: {COLORS['primary']}; --gold: {COLORS['gold']}; --bg: {COLORS['bg']}; --card: {COLORS['card']}; --text: {COLORS['text']}; }}
            body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 20px; padding-bottom: 80px; -webkit-tap-highlight-color: transparent; }}
            .container {{ max-width: 1000px; margin: 0 auto; }}
            
            h1 {{ margin: 0; font-size: 26px; font-weight: 700; color: var(--primary); letter-spacing:-0.5px; display:flex; align-items:center; gap:10px; }}
            h1::after {{ content:''; display:block; width:50px; height:3px; background:var(--gold); margin-left:15px; border-radius:2px; opacity:0.6; }}
            
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; padding-top: 10px; }}
            .lock-btn {{ background: white; border: 1px solid #cbd5e1; padding: 8px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; cursor: pointer; color: #64748b; transition:0.2s; }}
            .lock-btn:hover {{ border-color:var(--gold); color:var(--primary); }}
            
            .nav {{ display: flex; gap: 10px; overflow-x: auto; padding-bottom: 5px; margin-bottom: 25px; scrollbar-width: none; }}
            .nav::-webkit-scrollbar {{ display: none; }}
            .nav-btn {{ flex: 0 0 auto; background: white; border: 1px solid #e2e8f0; padding: 8px 18px; border-radius: 20px; font-size: 14px; font-weight: 600; color: #64748b; cursor: pointer; transition: 0.2s; }}
            .nav-btn.active {{ background: var(--primary); color: white; border-color: var(--primary); box-shadow: 0 4px 10px rgba(15, 23, 42, 0.2); }}
            
            .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 30px; }}
            .sport-grid, .hof-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 30px; }}
            
            .kpi-card, .sport-card, .hof-card, .chart-box, .detail-section {{ background: var(--card); border-radius: 16px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02); border:1px solid #f1f5f9; }}
            
            .sport-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }}
            .sport-icon-circle {{ width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 20px; }}
            .sport-header h3 {{ margin:0; font-size:18px; font-weight:700; color:var(--text); }}
            
            .stat-main {{ display: flex; margin-bottom: 16px; }}
            .stat-col {{ flex: 1; }} 
            .stat-divider {{ width: 1px; background: #e2e8f0; margin: 0 15px; }}
            .label {{ font-size: 11px; text-transform: uppercase; color: #94a3b8; font-weight: 700; }}
            .val {{ font-size: 22px; font-weight: 700; color:var(--primary); }}
            .sub {{ font-size: 12px; margin-top: 2px; }}
            
            .sport-details {{ background: #f8fafc; padding: 12px; border-radius: 12px; font-size: 13px; }}
            .stat-row {{ display: flex; justify-content: space-between; margin-bottom: 6px; color:#64748b; }}
            .stat-row strong {{ color:var(--text); }}
            
            .hof-header {{ border-bottom: 1px solid #f1f5f9; padding-bottom: 10px; margin-bottom: 10px; font-weight: 700; }}
            .hof-record {{ display: flex; gap: 12px; margin-bottom: 12px; align-items:center; }}
            .hof-icon {{ font-size:18px; width:24px; text-align:center; }}
            .hof-data {{ flex: 1; }}
            .hof-val {{ font-weight: 700; font-size: 15px; color: var(--primary); }}
            .hof-label {{ font-size:11px; text-transform:uppercase; color:#94a3b8; font-weight:600; }}
            .hof-date {{ font-size:11px; color:#94a3b8; }}

            .detail-header {{ display: flex; justify-content: space-between; margin-bottom: 15px; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
            th {{ text-align: left; color: #94a3b8; font-size: 11px; text-transform: uppercase; padding: 12px 10px; font-weight:700; }}
            td {{ padding: 14px 10px; border-bottom: 1px solid #f1f5f9; }}
            .num {{ text-align: right; font-weight:600; }}
            .hr-blur {{ filter: blur(5px); transition: 0.3s; background: #e2e8f0; border-radius: 4px; color: transparent; user-select: none; }}
            
            .full-width {{ grid-column: 1 / -1; }}
            .section-title {{ font-size: 18px; font-weight: 700; margin-bottom: 20px; color: var(--primary); }}
            .section-subtitle {{ font-size: 13px; font-weight: 700; color: #94a3b8; text-transform: uppercase; margin: 30px 0 15px 0; letter-spacing:0.5px; }}

            /* ROCKET CSS HERSTELD */
            .rocket {{ display: inline-block; animation: fly 1.5s ease-in-out infinite alternate; transform-origin: center; }}
            @keyframes fly {{
                0% {{ transform: translateY(0px) rotate(0deg) scale(1); }}
                100% {{ transform: translateY(-4px) rotate(15deg) scale(1.1); }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Sportoverzicht Joël</h1>
                <button class="lock-btn" onclick="unlock()">❤️ Hartslag 🔒</button>
            </div>
            
            <div class="nav">{nav_html}</div>
            
            {sections_html}
            {detail_html}
        </div>
        
        <script>
            function openTab(evt, name) {{
                document.querySelectorAll('.tab-content').forEach(x => x.style.display = 'none');
                document.querySelectorAll('.nav-btn').forEach(x => x.classList.remove('active'));
                document.getElementById(name).style.display = 'block';
                evt.currentTarget.classList.add('active');
            }}
            function filterTable() {{
                var val = document.getElementById('sf').value;
                document.querySelectorAll('#dt tbody tr').forEach(tr => {{
                    tr.style.display = (val === 'ALL' || tr.dataset.sport === val) ? '' : 'none';
                }});
            }}
            function unlock() {{
                var p = prompt("Wachtwoord (Tip: Niet Gust):");
                if(p === 'Nala') {{
                    document.querySelectorAll('.hr-blur').forEach(e => {{
                        e.style.filter = 'none'; e.style.color = 'inherit'; e.style.background = 'transparent';
                    }});
                    document.querySelector('.lock-btn').style.display = 'none';
                }}
            }}
        </script>
    </body>
    </html>
    """
    
    with open(html_output, 'w', encoding='utf-8') as f:
        f.write(html)
    print("✅ Dashboard succesvol gegenereerd voor Joël (met Rocket & Koersverloop)!")

if __name__ == "__main__":
    genereer_dashboard()
