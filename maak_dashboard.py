import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
import re
import os

warnings.filterwarnings("ignore", category=UserWarning)

# --- CONFIGURATIE ---
PLOT_CONFIG = {'displayModeBar': False, 'staticPlot': False, 'scrollZoom': False, 'responsive': True}
HR_ZONES = {'Z1 Herstel': 135, 'Z2 Duur': 152, 'Z3 Tempo': 168, 'Z4 Drempel': 180, 'Z5 Max': 220}

# TDT ROCKETS DARK MODE THEMA
COLORS = {
    'primary': '#00e5ff',      
    'gold': '#facc15',         
    'bg': '#0b0914',           
    'card': '#1e1b4b',         
    'text': '#f8fafc',         
    'text_light': '#94a3b8',   
    'zwift': '#ff007f',        
    'bike_out': '#00e5ff',     
    'run': '#facc15',          
    'swim': '#3b82f6', 'padel': '#10b981', 'walk': '#a855f7', 
    'strength': '#ec4899', 'default': '#94a3b8', 'ref_gray': '#334155',
    'z1': '#a3e635', 'z2': '#facc15', 'z3': '#fb923c', 'z4': '#f87171', 'z5': '#ef4444'
}

YEAR_COLORS = ['#ff007f', '#00e5ff', '#facc15', '#a855f7', '#10b981']

# --- HELPERS ---
def solve_dates(date_str):
    if pd.isna(date_str) or str(date_str).strip() == "": return pd.NaT
    d_map = {'jan':1,'feb':2,'mrt':3,'apr':4,'mei':5,'jun':6,'jul':7,'aug':8,'sep':9,'okt':10,'nov':11,'dec':12}
    try:
        clean = re.sub(r'[^a-zA-Z0-9\s:]', '', str(date_str).lower())
        parts = clean.split()
        day, month_str, year = int(parts[0]), parts[1][:3], int(parts[2])
        return pd.Timestamp(year=year, month=d_map.get(month_str, 1), day=day, hour=12) 
    except: return pd.to_datetime(date_str, errors='coerce')

def determine_category(row):
    t = str(row['Activiteitstype']).lower().strip(); n = str(row['Naam']).lower().strip()
    if any(x in t for x in ['kracht', 'power', 'gym', 'fitness', 'weight']) or any(x in n for x in ['kracht', 'power', 'gym', 'fitness']): return 'Krachttraining'
    if 'virtu' in t or 'zwift' in n: return 'Zwift'
    if any(x in t for x in ['fiets', 'ride', 'cycle', 'gravel', 'mtb']): return 'Fiets'
    if any(x in t for x in ['run', 'loop', 'hardloop']): return 'Hardlopen'
    if 'zwem' in t: return 'Zwemmen'
    if any(x in t for x in ['wandel', 'hike', 'walk']): return 'Wandelen'
    if any(x in t for x in ['padel', 'tennis']): return 'Padel'
    return 'Overig'

def get_sport_style(cat):
    styles = {
        'Fiets': ('🚴', COLORS['bike_out']), 'Zwift': ('👾', COLORS['zwift']),
        'Hardlopen': ('🏃', COLORS['run']), 'Wandelen': ('🚶', COLORS['walk']),
        'Padel': ('🎾', COLORS['padel']), 'Zwemmen': ('🏊', COLORS['swim']),
        'Krachttraining': ('🏋️', COLORS['strength'])
    }
    return styles.get(cat, ('🏅', COLORS['default']))

def format_time(seconds):
    if pd.isna(seconds) or seconds <= 0: return '-'
    h, r = divmod(int(seconds), 3600); m, _ = divmod(r, 60)
    return f'{h}u {m:02d}m'

def determine_zone(hr):
    if pd.isna(hr) or hr == 0: return 'Onbekend'
    if hr < HR_ZONES['Z1 Herstel']: return 'Z1 Herstel'
    if hr < HR_ZONES['Z2 Duur']: return 'Z2 Duur'
    if hr < HR_ZONES['Z3 Tempo']: return 'Z3 Tempo'
    if hr < HR_ZONES['Z4 Drempel']: return 'Z4 Drempel'
    return 'Z5 Max'

def format_diff_html(cur, prev, unit=""):
    diff = cur - (prev if pd.notna(prev) else 0)
    color = '#10b981' if diff >= 0 else '#ef4444'
    sign = "▲" if diff >= 0 else "▼"
    return f'<span style="color:{color}; font-weight:700; font-size:0.85em;">{sign} {abs(diff):.1f} {unit}</span>'

# --- LOGICA: STREAKS & RECORDS ---
def calculate_streaks(df):
    valid = df.dropna(subset=['Datum']).sort_values('Datum')
    if valid.empty: return {'cur_week':0, 'max_week':0, 'cur_day':0, 'max_day':0}
    
    valid['WeekStart'] = valid['Datum'].dt.to_period('W-MON').dt.start_time
    weeks = sorted(valid['WeekStart'].unique())
    days = sorted(valid['Datum'].dt.date.unique())
    
    def get_max_streak(items, delta):
        if not items: return 0
        cur = 1; mx = 1
        for i in range(1, len(items)):
            if (items[i] - items[i-1]) == delta:
                cur += 1
                mx = max(mx, cur)
            else: cur = 1
        return mx

    cur_wk = 0
    if weeks and (pd.Timestamp.now().to_period('W-MON').start_time - weeks[-1]).days <= 7:
        cur_wk = 1
        for i in range(len(weeks)-2, -1, -1):
            if (weeks[i+1]-weeks[i]).days == 7: cur_wk += 1
            else: break
            
    cur_d = 0
    if days and (datetime.now().date() - days[-1]).days <= 1:
        cur_d = 1
        for i in range(len(days)-2, -1, -1):
            if (days[i+1]-days[i]).days == 1: cur_d += 1
            else: break
            
    return {'cur_week':cur_wk, 'max_week':get_max_streak(weeks, timedelta(days=7)), 
            'cur_day':cur_d, 'max_day':get_max_streak(days, timedelta(days=1))}

def get_records(df):
    recs = []
    if df.empty: return recs
    runs = df[df['Categorie'] == 'Hardlopen']
    if not runs.empty:
        r5 = runs[runs['Afstand_km'] >= 4.9].sort_values('Gem_Snelheid', ascending=False).head(1)
        for _, r in r5.iterrows():
            recs.append({'icon': '🏃', 'label':'Snelste loop', 'val':f"{r['Gem_Snelheid']:.1f} km/u", 'date':r['Datum'].strftime('%d-%m-%y')})
    bikes = df[df['Categorie'].isin(['Fiets', 'Zwift'])]
    if not bikes.empty:
        b1 = bikes.sort_values('Afstand_km', ascending=False).head(1)
        for _, r in b1.iterrows():
            recs.append({'icon': '🚴', 'label':'Grootste rit', 'val':f"{r['Afstand_km']:.0f} km", 'date':r['Datum'].strftime('%d-%m-%y')})
    return recs

# --- UI GENERATORS ---
def generate_streaks_box(df):
    s = calculate_streaks(df)
    recs = get_records(df)
    rec_html = "".join([f'<div class="streak-sub">{r["icon"]} {r["label"]}: <b>{r["val"]}</b> <small>({r["date"]})</small></div>' for r in recs])
    return f"""<div class="streaks-section">
        <h3 class="box-title">🔥 MOTIVATIE & RECORDS</h3>
        <div style="display:flex; gap:30px; flex-wrap:wrap;">
            <div style="flex:1; min-width:140px;">
                <div class="streak-row"><span>Week Streak:</span><span style="color:var(--primary);">{s['cur_week']}</span></div>
                <div class="streak-sub">Record: {s['max_week']} wkn</div>
            </div>
            <div style="flex:1; min-width:140px;">
                <div class="streak-row"><span>Dag Streak:</span><span style="color:var(--primary);">{s['cur_day']}</span></div>
                <div class="streak-sub">Record: {s['max_day']} dgn</div>
            </div>
            <div style="flex:1.5; min-width:200px; border-left:1px solid rgba(255,255,255,0.1); padding-left:20px;">
                {rec_html}
            </div>
        </div>
    </div>"""

def create_ytd_chart(df, current_year):
    fig = go.Figure()
    years = sorted(df['Jaar'].unique(), reverse=True)[:3]
    for i, y in enumerate(years):
        df_y = df[df['Jaar'] == y].groupby('Day')['Afstand_km'].sum().reindex(range(1, 367), fill_value=0).cumsum()
        if y == datetime.now().year:
            df_y[datetime.now().timetuple().tm_yday+1:] = np.nan
        fig.add_trace(go.Scatter(x=list(range(1, 367)), y=df_y, name=str(y), line=dict(color=YEAR_COLORS[i%5], width=3 if y==current_year else 1.5)))
    fig.update_layout(template="plotly_dark", height=380, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                      margin=dict(t=20,b=20,l=0,r=10), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config=PLOT_CONFIG)

def create_hr_chart(df_yr):
    if 'Hartslag' not in df_yr.columns or df_yr['Hartslag'].sum() == 0: return '<p style="padding:20px;">Geen hartslagdata beschikbaar.</p>'
    df_h = df_yr[df_yr['Hartslag'] > 0].copy()
    df_h['Zone'] = df_h['Hartslag'].apply(determine_zone)
    counts = df_h['Zone'].value_counts().reindex(HR_ZONES.keys(), fill_value=0)
    fig = px.bar(x=counts.index, y=counts.values, color=counts.index, 
                 color_discrete_map={'Z1 Herstel':COLORS['z1'],'Z2 Duur':COLORS['z2'],'Z3 Tempo':COLORS['z3'],'Z4 Drempel':COLORS['z4'],'Z5 Max':COLORS['z5']})
    fig.update_layout(template="plotly_dark", height=300, showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=10,b=10,l=0,r=0), xaxis_title="", yaxis_title="Aantal sessies")
    return fig.to_html(full_html=False, include_plotlyjs=False, config=PLOT_CONFIG)

def generate_sport_cards(df_yr, df_prev_comp):
    html = '<div class="sport-grid">'
    for cat in sorted(df_yr['Categorie'].unique()):
        df_s = df_yr[df_yr['Categorie'] == cat]
        df_p = df_prev_comp[df_prev_comp['Categorie'] == cat] if not df_prev_comp.empty else pd.DataFrame()
        icon, color = get_sport_style(cat)
        
        n=len(df_s); np=len(df_p); d=df_s['Afstand_km'].sum(); dp=df_p['Afstand_km'].sum() if not df_p.empty else 0
        t=df_s['Beweegtijd_sec'].sum(); tp=df_p['Beweegtijd_sec'].sum() if not df_p.empty else 0
        hr=df_s['Hartslag'].mean() if 'Hartslag' in df_s.columns else 0
        
        html += f"""<div class="sport-card" style="border-left:4px solid {color}">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:15px;">
                <div class="icon-circle" style="background:{color}20; color:{color};">{icon}</div>
                <h3 style="margin:0; font-size:16px; color:var(--text);">{cat}</h3>
            </div>
            <div class="stat-row"><span>Sessies</span><strong>{n} {format_diff_html(n,np)}</strong></div>
            <div class="stat-row"><span>Afstand</span><strong>{d:,.1f} km {format_diff_html(d,dp)}</strong></div>
            <div class="stat-row"><span>Tijd</span><strong>{format_time(t)}</strong></div>
            {f'<div class="stat-row"><span>Hartslag</span><strong class="secure-hr" data-hr="{hr:.0f}">❤️ ***</strong></div>' if hr > 40 else ''}
        </div>"""
    return html + '</div>'

def generate_yearly_gear(df_yr, df_all, all_time_mode=False):
    df_g = (df_all if all_time_mode else df_yr).copy()
    if 'Gear' not in df_g.columns: return '<p>Geen materiaal-kolom gevonden.</p>'
    
    # 🔥 CRUCIALE JOËL-FIX: Forceer Gear naar tekst voordat we gaan strippen
    df_g['Gear'] = df_g['Gear'].astype(str)
    df_g = df_g.dropna(subset=['Gear'])
    df_g = df_g[df_g['Gear'].str.strip() != 'nan']
    df_g = df_g[df_g['Gear'].str.strip() != '']
    
    if df_g.empty: return '<p style="color:var(--text_light); font-size:13px; padding:20px;">Geen materiaalgegevens bekend.</p>'
    
    html = '<div class="kpi-grid">'
    for g in sorted(df_g['Gear'].unique()):
        dy = df_g[df_g['Gear'] == g]
        ky = dy['Afstand_km'].sum()
        sy = dy['Beweegtijd_sec'].sum()
        html += f"""<div class="kpi-card">
            <div class="box-title">{g}</div>
            <div style="font-size:20px; font-weight:800; color:var(--text);">{ky:,.0f} km</div>
            <div class="sec-lbl">⏱️ {sy/3600:,.1f} uur totaal</div>
        </div>"""
    return html + '</div>'

def generate_logbook(df):
    rows = ""
    for _, r in df.sort_values('Datum', ascending=False).head(25).iterrows():
        icon = get_sport_style(r['Categorie'])[0]
        rows += f"<tr><td>{r['Datum'].strftime('%d %b')}</td><td>{icon}</td><td>{r['Naam'][:35]}</td><td align='right'><b>{r['Afstand_km']:.1f}</b></td></tr>"
    return f'<div class="chart-box" style="padding:0;"><table class="log-table"><thead><tr><th>Datum</th><th></th><th>Activiteit</th><th align="right">KM</th></tr></thead><tbody>{rows}</tbody></table></div>'

# --- MAIN ENGINE ---
def genereer_dashboard():
    print("🚀 Start V71.0 (Full Joël Edition)...")
    try:
        if not os.path.exists('activities.csv'): return
        df = pd.read_csv('activities.csv')
        nm = {'Datum van activiteit':'Datum', 'Naam activiteit':'Naam', 'Activiteitstype':'Activiteitstype', 'Beweegtijd':'Beweegtijd_sec', 'Afstand':'Afstand_km', 'Gemiddelde hartslag':'Hartslag', 'Gemiddelde snelheid':'Gem_Snelheid', 'Uitrusting voor activiteit':'Gear', 'Calorieën':'Calorieën'}
        df = df.rename(columns={k:v for k,v in nm.items() if k in df.columns})
        
        for c in ['Afstand_km', 'Beweegtijd_sec', 'Gem_Snelheid', 'Calorieën']:
            if c in df.columns: df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        df['Datum'] = df['Datum'].apply(solve_dates); df = df.dropna(subset=['Datum'])
        df['Categorie'] = df.apply(determine_category, axis=1)
        df['Jaar'] = df['Datum'].dt.year; df['Day'] = df['Datum'].dt.dayofyear
        
        yr = datetime.now().year; df_yr = df[df['Jaar'] == yr]
        ytd_day = datetime.now().timetuple().tm_yday
        df_prev_comp = df[(df['Jaar'] == yr-1) & (df['Day'] <= ytd_day)]
        
        # --- TAB NAVIGATIE ---
        nav = f'<button class="nav-btn active" onclick="openTab(event,\'tab1\')">Overzicht</button>'
        nav += f'<button class="nav-btn" onclick="openTab(event,\'tab2\')">Materiaal</button>'
        nav += f'<button class="nav-btn" onclick="openTab(event,\'tab3\')">Logboek</button>'
        nav += f'<button class="nav-btn" onclick="openTab(event,\'tab4\')">Analyse</button>'

        # --- TAB 1: OVERZICHT ---
        sects = f'<div id="tab1" class="tab-content" style="display:block;">'
        sects += f"""<div class="kpi-grid">
            <div class="kpi-card"><div class="box-title">Sessies {yr}</div><div style="font-size:32px; font-weight:800;">{len(df_yr)}</div>{format_diff_html(len(df_yr), len(df_prev_comp))} vs vorig jaar</div>
            <div class="kpi-card"><div class="box-title">Afstand {yr}</div><div style="font-size:32px; font-weight:800;">{df_yr['Afstand_km'].sum():,.0f} <span style="font-size:14px;">km</span></div>{format_diff_html(df_yr['Afstand_km'].sum(), df_prev_comp['Afstand_km'].sum(), "km")}</div>
            <div class="kpi-card"><div class="box-title">Energie {yr}</div><div style="font-size:32px; font-weight:800;">{df_yr['Calorieën'].sum():,.0f} <span style="font-size:14px;">kcal</span></div><div class="sec-lbl">Totaal verbrand</div></div>
        </div>"""
        sects += generate_streaks_box(df)
        sects += f'<div class="sec-sub">Progressie</div><div class="chart-box full-width">{create_ytd_chart(df, yr)}</div>'
        sects += f'<div class="sec-sub">Details per Sport</div>{generate_sport_cards(df_yr, df_prev_comp)}'
        sects += '</div>'
        
        # --- TAB 2: MATERIAAL ---
        sects += f'<div id="tab2" class="tab-content">'
        sects += f'<div class="sec-sub">Materiaal {yr}</div>{generate_yearly_gear(df_yr, df)}'
        sects += f'<div class="sec-sub">All-time Materiaal</div>{generate_yearly_gear(df_yr, df, True)}'
        sects += '</div>'
        
        # --- TAB 3: LOGBOEK ---
        sects += f'<div id="tab3" class="tab-content">'
        sects += f'<div class="sec-sub">Laatste 25 Activiteiten</div>{generate_logbook(df)}'
        sects += '</div>'
        
        # --- TAB 4: ANALYSE ---
        sects += f'<div id="tab4" class="tab-content">'
        sects += f'<div class="sec-sub">Hartslagverdeling {yr}</div><div class="chart-box">{create_hr_chart(df_yr)}</div>'
        sects += '</div>'

        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>⚡ Sportoverzicht Joël</title><link rel="manifest" href="manifest.json"><link rel="icon" type="image/png" href="icon.png"><link rel="apple-touch-icon" href="icon.png">
        <style>
        :root{{--primary:#00e5ff;--bg:#0b0914;--card:#1e1b4b;--text:#f8fafc;--text_light:#94a3b8;}}
        * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
        body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--text);margin:0;padding:20px 0;line-height:1.4;}}
        .container{{width:94%; max-width:1200px; margin:0 auto;}}
        .header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:25px;}}
        .nav{{display:flex;gap:8px;margin-bottom:25px;overflow-x:auto;padding-bottom:10px;scrollbar-width:none;}}
        .nav::-webkit-scrollbar{{display:none;}}
        .nav-btn{{background:rgba(255,255,255,0.05);border:none;color:var(--text_light);padding:10px 20px;border-radius:25px;font-weight:700;font-size:13px;white-space:nowrap;cursor:pointer;transition:all 0.2s;}}
        .nav-btn.active{{background:var(--primary);color:var(--bg);box-shadow:0 4px 15px rgba(0,229,255,0.3);}}
        .tab-content {{ display:none; animation: fadeIn 0.3s ease; }}
        @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        .lock-btn {{ background:rgba(255,255,255,0.05); border:none; color:white; padding:10px; border-radius:50%; width:40px; height:40px; cursor:pointer; }}
        .kpi-grid, .sport-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 25px; }}
        .kpi-card, .sport-card, .chart-box, .streaks-section {{ background: var(--card); padding:20px; border-radius:16px; border:1px solid rgba(255,255,255,0.05); box-shadow:0 4px 10px rgba(0,0,0,0.3); width: 100%; }}
        .sec-sub{{font-size:13px;text-transform:uppercase;letter-spacing:1px;margin:35px 0 15px 0;border-bottom:2px solid rgba(255,255,255,0.05);padding-bottom:5px;color:var(--primary);font-weight:800; display:inline-block;}}
        .box-title{{font-size:11px;color:var(--text_light);text-transform:uppercase;margin-bottom:12px;letter-spacing:0.5px;font-weight:700}}
        .stat-row{{display:flex;justify-content:space-between;font-size:13px;margin-bottom:8px; color:var(--text_light);}}
        .log-table{{width:100%;border-collapse:collapse;font-size:12px;}} .log-table th{{text-align:left;padding:12px 10px;border-bottom:1px solid rgba(255,255,255,0.05);color:var(--text_light);}} .log-table td{{padding:12px 10px;border-bottom:1px solid rgba(255,255,255,0.02);}}
        .streak-row{{display:flex;justify-content:space-between;font-size:18px;font-weight:800;color:var(--text);}}
        .streak-sub{{font-size:11px;color:var(--text_light);margin-top:4px;}}
        .icon-circle{{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;margin-bottom:10px;}}
        </style></head><body><div class="container">
        <div class="header"><h1 style="font-size:28px;font-weight:800;letter-spacing:-1px;margin:0; background: -webkit-linear-gradient(45deg, #ff007f, #00e5ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">⚡ Sportoverzicht Joël</h1><button class="lock-btn" onclick="unlock()">❤️ 🔒</button></div>
        <div class="nav">{nav}</div>{sects}</div>
        <script>
        function openTab(e,n){{
            document.querySelectorAll('.tab-content').forEach(x=>x.style.display='none');
            document.querySelectorAll('.nav-btn').forEach(x=>x.classList.remove('active'));
            document.getElementById(n).style.display='block';
            e.currentTarget.classList.add('active');
            window.scrollTo({{top:0, behavior:'smooth'}});
            setTimeout(() => {{ window.dispatchEvent(new Event('resize')); }}, 50);
        }}
        function unlock(){{
            if(prompt("Wachtwoord:")==='Joël2026'){{
                document.querySelectorAll('.secure-hr').forEach(e => {{ e.innerHTML = '❤️ ' + e.getAttribute('data-hr'); }});
                document.querySelector('.lock-btn').style.display='none';
            }}
        }}
        </script></body></html>"""
        
        with open('dashboard.html', 'w', encoding='utf-8') as f: f.write(html)
        print("✅ Dashboard (V71.0) klaar!")
    except Exception as e: print(f"❌ Fout: {e}")

if __name__ == "__main__": genereer_dashboard()
