import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
import re

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
    
    'mountainbike': '#00e5ff', 
    'padel': '#10b981',        
    'walk': '#a855f7',         
    
    'default': '#94a3b8', 'ref_gray': '#334155',
    'z1': '#a3e635', 'z2': '#facc15', 'z3': '#fb923c', 'z4': '#f87171', 'z5': '#ef4444',
    'elevation': '#fb923c' # Kleur voor hoogtemeters
}

YEAR_COLORS = ['#00e5ff', '#10b981', '#a855f7', '#facc15', '#ff007f']

# --- DATUM FIX ---
def solve_dates(date_str):
    if pd.isna(date_str) or str(date_str).strip() == "": return pd.NaT
    d_map = {'jan':1,'feb':2,'mrt':3,'apr':4,'mei':5,'jun':6,'jul':7,'aug':8,'sep':9,'okt':10,'nov':11,'dec':12}
    try:
        clean = re.sub(r'[^a-zA-Z0-9\s:]', '', str(date_str).lower())
        parts = clean.split()
        day, month_str, year = int(parts[0]), parts[1][:3], int(parts[2])
        return pd.Timestamp(year=year, month=d_map.get(month_str, 1), day=day, hour=12) 
    except: return pd.to_datetime(date_str, errors='coerce')

# --- CATEGORIE LOGICA ---
def determine_category(row):
    t = str(row['Activiteitstype']).lower().strip()
    n = str(row['Naam']).lower().strip()
    
    # Alles met training is Padel
    if 'train' in t or 'train' in n or any(x in t for x in ['padel', 'tennis', 'squash', 'work', 'fit']): 
        return 'Padel'
    
    # Alles met fiets, rit, mtb, mountainbike is Mountainbike
    if any(x in t for x in ['fiets', 'rit', 'mtb', 'mountainbike', 'ride', 'cycle', 'gravel', 'velomobiel', 'e-bike']) or any(x in n for x in ['fiets', 'rit', 'mtb', 'mountainbike']): 
        return 'Mountainbike'
    
    # Wandelen blijft Wandelen
    if any(x in t for x in ['wandel', 'hike', 'walk']): 
        return 'Wandelen'
    
    return 'Overig'

def get_sport_style(cat):
    styles = {
        'Mountainbike': ('🚴', COLORS['mountainbike']),
        'Wandelen': ('🚶', COLORS['walk']), 
        'Padel': ('🎾', COLORS['padel']),
    }
    return styles.get(cat, ('🏅', COLORS['default']))

def determine_zone(hr):
    if pd.isna(hr) or hr == 0: return 'Onbekend'
    if hr < HR_ZONES['Z1 Herstel']: return 'Z1 Herstel'
    if hr < HR_ZONES['Z2 Duur']: return 'Z2 Duur'
    if hr < HR_ZONES['Z3 Tempo']: return 'Z3 Tempo'
    if hr < HR_ZONES['Z4 Drempel']: return 'Z4 Drempel'
    return 'Z5 Max'

# --- HELPERS ---
def format_time(seconds):
    if pd.isna(seconds) or seconds <= 0: return '-'
    h, r = divmod(int(seconds), 3600); m, _ = divmod(r, 60)
    return f'{h}u {m:02d}m'

def format_diff_html(cur, prev, unit=""):
    if pd.isna(prev) and cur == 0: return '<span style="color:#64748b">-</span>'
    diff = cur - (prev if pd.notna(prev) else 0)
    color = '#10b981' if diff >= 0 else '#ef4444'
    arrow = "▲" if diff >= 0 else "▼"
    return f'<span style="color:{color}; font-weight:700; font-size:0.85em; font-family: monospace;">{arrow} {abs(diff):.1f} {unit}</span>'

# --- UI GENERATORS ---
def create_ytd_chart(df, current_year):
    fig = go.Figure()
    years_to_plot = sorted(df['Jaar'].unique(), reverse=True)[:5]
    
    for i, y in enumerate(years_to_plot):
        df_y = df[df['Jaar'] == y].groupby('Day')['Afstand_km'].sum().reset_index()
        if df_y.empty: continue
        
        all_days = pd.DataFrame({'Day': range(1, 367)})
        df_y = pd.merge(all_days, df_y, on='Day', how='left').fillna(0)
        df_y['Cum_Afstand'] = df_y['Afstand_km'].cumsum()
        
        if y == datetime.now().year:
            current_day = datetime.now().timetuple().tm_yday
            df_y.loc[df_y['Day'] > current_day, 'Cum_Afstand'] = np.nan
            
        color = YEAR_COLORS[i % len(YEAR_COLORS)]
        width = 4 if y == current_year else 2
        
        fig.add_trace(go.Scatter(
            x=df_y['Day'], y=df_y['Cum_Afstand'], 
            mode='lines', name=str(y), 
            line=dict(color=color, width=width),
            hovertemplate=f"<b>{y}</b><br>Dag %{{x}}<br>%{{y:.0f}} km<extra></extra>"
        ))
        
    fig.update_layout(
        title='📈 Aantal km\'s', 
        template='plotly_dark', 
        margin=dict(t=50, b=60, l=0, r=10),
        height=380, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(title="", showgrid=False, fixedrange=True), 
        yaxis=dict(title="", showgrid=True, gridcolor='rgba(255,255,255,0.05)', fixedrange=True, side="right"), 
        legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"), 
        font=dict(color='#94a3b8')
    )
    return f'<div class="chart-box full-width">{fig.to_html(full_html=False, include_plotlyjs="cdn", config=PLOT_CONFIG)}</div>'

def calculate_streaks(df):
    valid = df.dropna(subset=['Datum']).sort_values('Datum')
    if valid.empty: return {}
    valid['WeekStart'] = valid['Datum'].dt.to_period('W-MON').dt.start_time
    weeks = sorted(valid['WeekStart'].unique()); days = sorted(valid['Datum'].dt.date.unique())
    cur_wk, max_wk, max_wk_dates = 0, 0, "-"
    if weeks:
        if (pd.Timestamp.now().to_period('W-MON').start_time - weeks[-1]).days <= 7:
            cur_wk = 1
            for i in range(len(weeks)-2, -1, -1):
                if (weeks[i+1]-weeks[i]).days == 7: cur_wk+=1
                else: break
        temp, start = 1, weeks[0]; max_wk, max_wk_dates = 1, f"({weeks[0].strftime('%d %b %y')})"
        for i in range(1, len(weeks)):
            if (weeks[i]-weeks[i-1]).days == 7: temp+=1
            else:
                if temp > max_wk: max_wk = temp; max_wk_dates = f"({start.strftime('%d %b %y')} - {(weeks[i-1]+timedelta(days=6)).strftime('%d %b %y')})"
                temp = 1; start = weeks[i]
        if temp > max_wk: max_wk = temp; max_wk_dates = f"({start.strftime('%d %b %y')} - {(weeks[-1]+timedelta(days=6)).strftime('%d %b %y')})"
    cur_d, max_d, max_d_dates = 0, 0, "-"
    if days:
        if (datetime.now().date() - days[-1]).days <= 1: cur_d = 1
        for i in range(len(days)-2, -1, -1):
            if (days[i+1]-days[i]).days == 1: cur_d+=1
            else: break
        temp, start = 1, days[0]; max_d, max_d_dates = 1, f"({days[0].strftime('%d %b')})"
        for i in range(1, len(days)):
            if (days[i]-days[i-1]).days == 1: temp+=1
            else:
                if temp > max_d: max_d = temp; max_d_dates = f"({start.strftime('%d %b')} - {days[i-1].strftime('%d %b %y')})"
                temp = 1; start = days[i]
        if temp > max_d: max_d = temp; max_d_dates = f"({start.strftime('%d %b')} - {days[-1].strftime('%d %b %y')})"
    return {'cur_week':cur_wk, 'max_week':max_wk, 'max_week_dates':max_wk_dates, 'cur_day':cur_d, 'max_day':max_d, 'max_day_dates':max_d_dates}

def generate_streaks_box(df):
    s = calculate_streaks(df)
    return f"""<div class="streaks-section">
        <h3 class="box-title">🔥 MOTIVATIE REEKSEN</h3>
        <div class="streaks-container" style="display:flex; gap:30px; flex-wrap:wrap;">
            <div style="flex:1; min-width:200px;">
                <div class="streak-row"><span class="label">Huidig Wekelijks:</span><span class="val" style="color:var(--primary);">{s.get('cur_week',0)} weken</span></div>
                <div class="streak-row"><span class="label">Record Wekelijks:</span><span class="val" style="color:var(--text);">{s.get('max_week',0)} weken</span></div>
                <div class="streak-sub">{s.get('max_week_dates','-')}</div>
            </div>
            <div style="flex:1; min-width:200px;">
                <div class="streak-row"><span class="label">Huidig Dagelijks:</span><span class="val" style="color:var(--primary);">{s.get('cur_day',0)} dagen</span></div>
                <div class="streak-row"><span class="label">Record Dagelijks:</span><span class="val" style="color:var(--text);">{s.get('max_day',0)} dagen</span></div>
                <div class="streak-sub">{s.get('max_day_dates','-')}</div>
            </div>
        </div>
    </div>"""

def create_monthly_charts(df_cur, df_prev, year):
    months = ['Jan','Feb','Mrt','Apr','Mei','Jun','Jul','Aug','Sep','Okt','Nov','Dec']
    def get_m(df, cats): return df[df['Categorie'].isin(cats)].groupby(df['Datum'].dt.month)['Afstand_km'].sum().reindex(range(1,13), fill_value=0)
    
    pt = get_m(df_prev, ['Mountainbike']); ct = get_m(df_cur, ['Mountainbike'])
    fb = go.Figure()
    fb.add_trace(go.Bar(x=months, y=pt, name=f"{year-1}", marker_color=COLORS['ref_gray']))
    fb.add_trace(go.Bar(x=months, y=ct, name=f"{year} MTB", marker_color=COLORS['mountainbike']))
    fb.update_layout(title='🚴 Mountainbike (km)', template='plotly_dark', barmode='group', margin=dict(t=50,b=60,l=10,r=10), height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"), xaxis=dict(fixedrange=True), yaxis=dict(fixedrange=True, gridcolor='rgba(255,255,255,0.05)'), font=dict(color='#94a3b8'))
    
    pp = get_m(df_prev, ['Wandelen']); cp = get_m(df_cur, ['Wandelen'])
    fw = go.Figure()
    fw.add_trace(go.Bar(x=months, y=pp, name=f"{year-1}", marker_color=COLORS['ref_gray']))
    fw.add_trace(go.Bar(x=months, y=cp, name=f"{year} Wandelen", marker_color=COLORS['walk']))
    fw.update_layout(title='🚶 Wandelen (km)', template='plotly_dark', barmode='group', margin=dict(t=50,b=60,l=10,r=10), height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"), xaxis=dict(fixedrange=True), yaxis=dict(fixedrange=True, gridcolor='rgba(255,255,255,0.05)'), font=dict(color='#94a3b8'))
    
    return f'<div class="chart-grid"><div class="chart-box">{fb.to_html(full_html=False, include_plotlyjs="cdn", config=PLOT_CONFIG)}</div><div class="chart-box">{fw.to_html(full_html=False, include_plotlyjs="cdn", config=PLOT_CONFIG)}</div></div>'

def create_elevation_chart(df_yr):
    # Het nieuwe "kotje" voor hoogtemeters
    if 'Hoogtemeters' not in df_yr.columns: return ""
    df_elev = df_yr[df_yr['Hoogtemeters'] > 0]
    if df_elev.empty: return ""
    
    counts = df_elev.groupby(df_elev['Datum'].dt.month)['Hoogtemeters'].sum().reindex(range(1,13), fill_value=0)
    months = ['Jan','Feb','Mrt','Apr','Mei','Jun','Jul','Aug','Sep','Okt','Nov','Dec']
    
    fig = go.Figure()
    fig.add_trace(go.Bar(x=months, y=counts, marker_color=COLORS['elevation'], text=counts.apply(lambda x: f"{x:.0f}m" if x > 0 else ""), textposition='auto'))
    fig.update_layout(title='⛰️ Hoogtemeters per maand', template='plotly_dark', margin=dict(t=50,b=40,l=10,r=10), height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis=dict(title='', fixedrange=True, gridcolor='rgba(255,255,255,0.05)'), xaxis=dict(fixedrange=True), font=dict(color='#94a3b8'))
    
    return f'<div class="chart-box">{fig.to_html(full_html=False, include_plotlyjs="cdn", config=PLOT_CONFIG)}</div>'

def create_heatmap(df_yr):
    df_hm = df_yr.copy(); df_hm['Uur'] = df_hm['Datum'].dt.hour; df_hm['Weekdag'] = df_hm['Datum'].dt.day_name()
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    nl_days = {'Monday':'Ma', 'Tuesday':'Di', 'Wednesday':'Wo', 'Thursday':'Do', 'Friday':'Vr', 'Saturday':'Za', 'Sunday':'Zo'}
    grouped = df_hm.groupby(['Weekdag', 'Uur']).size().reset_index(name='Aantal')
    pivot = grouped.pivot(index='Uur', columns='Weekdag', values='Aantal').fillna(0).reindex(columns=days_order)
    if pivot.empty: return ""
    fig = go.Figure(data=go.Heatmap(z=pivot.values, x=[nl_days[d] for d in pivot.columns], y=pivot.index, colorscale=[[0, 'rgba(255,255,255,0.03)'], [1, COLORS['mountainbike']]], showscale=False))
    fig.update_layout(title='📅 Hittekaart (Wanneer sport je?)', template='plotly_dark', margin=dict(t=50,b=40,l=10,r=10), height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis=dict(title='', range=[6, 23], fixedrange=True), xaxis=dict(fixedrange=True), font=dict(color='#94a3b8'))
    return f'<div class="chart-box">{fig.to_html(full_html=False, include_plotlyjs="cdn", config=PLOT_CONFIG)}</div>'

def create_scatter_plot(df_yr):
    df_bike = df_yr[df_yr['Categorie'] == 'Mountainbike']; df_walk = df_yr[df_yr['Categorie'] == 'Wandelen']
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_bike['Afstand_km'], y=df_bike['Gem_Snelheid'], mode='markers', name='MTB', marker=dict(color=COLORS['mountainbike'], size=8), text=df_bike['Naam']))
    fig.add_trace(go.Scatter(x=df_walk['Afstand_km'], y=df_walk['Gem_Snelheid'], mode='markers', name='Wandelen', marker=dict(color=COLORS['walk'], size=8), text=df_walk['Naam']))
    fig.update_layout(title='⚡ Snelheid vs Afstand', template='plotly_dark', margin=dict(t=50,b=60,l=0,r=10), height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center"), xaxis=dict(gridcolor='rgba(255,255,255,0.05)'), yaxis=dict(gridcolor='rgba(255,255,255,0.05)'), font=dict(color='#94a3b8'))
    return f'<div class="chart-box">{fig.to_html(full_html=False, include_plotlyjs="cdn", config=PLOT_CONFIG)}</div>'

def create_zone_pie(df_yr):
    df_hr = df_yr[(df_yr['Hartslag'] > 0) & (df_yr['Hartslag'].notna())].copy()
    if df_hr.empty: return ""
    df_hr['Zone'] = df_hr['Hartslag'].apply(determine_zone)
    color_map = {'Z1 Herstel': COLORS['z1'], 'Z2 Duur': COLORS['z2'], 'Z3 Tempo': COLORS['z3'], 'Z4 Drempel': COLORS['z4'], 'Z5 Max': COLORS['z5']}
    counts = df_hr['Zone'].value_counts().reset_index()
    fig = go.Figure(data=[go.Pie(labels=counts['Zone'], values=counts['count'], hole=0.6, marker=dict(colors=[color_map.get(z, '#334155') for z in counts['Zone']]))])
    fig.update_layout(title='❤️ Hartslagzones', template='plotly_dark', margin=dict(t=50,b=40,l=0,r=10), height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#94a3b8'))
    return f'<div class="chart-box">{fig.to_html(full_html=False, include_plotlyjs="cdn", config=PLOT_CONFIG)}</div>'

def generate_sport_cards(df_yr, df_prev_comp):
    html = '<div class="sport-grid">'
    cp = df_yr['Categorie'].unique(); co = ['Mountainbike', 'Padel', 'Wandelen', 'Overig']
    cats = [c for c in co if c in cp] + [c for c in cp if c not in co]
    
    for cat in cats:
        df_s = df_yr[df_yr['Categorie'] == cat]; df_p = df_prev_comp[df_prev_comp['Categorie'] == cat] if df_prev_comp is not None else pd.DataFrame()
        if df_s.empty: continue
        icon, color = get_sport_style(cat)
        
        n=len(df_s); np=len(df_p); d=df_s['Afstand_km'].sum(); dp=df_p['Afstand_km'].sum() if not df_p.empty else 0
        t=df_s['Beweegtijd_sec'].sum(); tp=df_p['Beweegtijd_sec'].sum() if not df_p.empty else 0
        hr=df_s['Hartslag'].mean(); wt=df_s['Wattage'].mean() if 'Wattage' in df_s.columns else None
        cal = df_s['Calorieën'].sum() if 'Calorieën' in df_s.columns else 0
        elev = df_s['Hoogtemeters'].sum() if 'Hoogtemeters' in df_s.columns else 0
        elev_p = df_p['Hoogtemeters'].sum() if 'Hoogtemeters' in df_p.columns and not df_p.empty else 0
        
        spd = f"{(d/(t/3600)):.1f} km/u" if t > 0 and cat != 'Padel' else "-"
        
        rows = f"""<div class="stat-row"><span>Sessies</span><div class="val-group"><strong>{n}</strong>{format_diff_html(n,np)}</div></div>
                   <div class="stat-row"><span>Tijd</span><div class="val-group"><strong>{format_time(t)}</strong>{format_diff_html(t/3600,tp/3600,"u")}</div></div>"""
        
        if cat != 'Padel': 
            rows += f"""<div class="stat-row"><span>Afstand</span><div class="val-group"><strong>{d:,.0f} km</strong>{format_diff_html(d,dp)}</div></div>
                        <div class="stat-row"><span>Snelheid</span><strong>{spd}</strong></div>"""
        
        if elev > 0: rows += f'<div class="stat-row"><span>Hoogtemeters</span><div class="val-group"><strong>⛰️ {elev:,.0f} m</strong>{format_diff_html(elev, elev_p)}</div></div>'                
        if pd.notna(wt) and wt>0: rows += f'<div class="stat-row"><span>Wattage</span><strong>⚡ {wt:.0f} W</strong></div>'
        if pd.notna(hr) and hr>0: rows += f'<div class="stat-row"><span>Hartslag</span><strong class="secure-hr" data-hr="{hr:.0f}">❤️ ***</strong></div>'
        if cal > 0: rows += f'<div class="stat-row"><span>Energie</span><strong>🔥 {cal:,.0f} kcal</strong></div>'
            
        html += f"""<div class="sport-card"><div class="sport-header" style="color:{color}"><div class="icon-circle" style="background:rgba(255,255,255,0.05); border:1px solid {color}40;">{icon}</div><h3>{cat}</h3></div><div class="sport-body">{rows}</div></div>"""
    return html + '</div>'

def generate_yearly_gear(df_yr, df_all, all_time_mode=False):
    df_g = df_all if all_time_mode else df_yr
    df_g = df_g.dropna(subset=['Gear']).copy()
    df_g = df_g[df_g['Gear'].str.strip() != '']
    if df_g.empty: return '<p style="color:var(--text_light); font-size:13px; padding:20px;">Geen materiaalgegevens bekend.</p>'
    
    gears = df_g['Gear'].unique()
    html = '<div class="kpi-grid">'
    
    for g in gears:
        dy = df_g[df_g['Gear'] == g]
        ky = dy['Afstand_km'].sum()
        sy = dy['Beweegtijd_sec'].sum()
        
        act_mode = dy['Categorie'].mode()[0] if not dy.empty else 'Mountainbike'
        icon = '👟' if act_mode == 'Wandelen' else '🚲'
        verb = 'Gelopen' if icon == '👟' else 'Gereden'
        
        da = df_all[df_all['Gear'] == g]
        ka = da['Afstand_km'].sum()
        sa = da['Beweegtijd_sec'].sum()
        
        html += f"""
        <div class="kpi-card" style="display:flex; flex-direction:column; gap:12px;">
            <div style="display:flex;align-items:center;gap:10px;">
                <span style="font-size:22px;">{icon}</span>
                <strong style="font-size:14px; line-height:1.2; color:var(--text);">{g}</strong>
            </div>
            
            <div style="background:rgba(0,0,0,0.2); border:1px solid rgba(255,255,255,0.05); padding:12px; border-radius:8px;">
                <div style="font-size:10px; color:var(--text_light); text-transform:uppercase; font-weight:800; margin-bottom:4px; letter-spacing:0.5px;">{verb} {"Totaal" if all_time_mode else "Dit Jaar"}</div>
                <div style="display:flex; justify-content:space-between; align-items:flex-end;">
                    <span style="font-size:20px; font-weight:800; color:var(--text); font-variant-numeric: tabular-nums;">{ky:,.0f} km</span>
                    <span style="font-size:13px; color:var(--text_light); font-weight:600;">⏱️ {sy/3600:,.1f} u</span>
                </div>
            </div>
            """
        
        if not all_time_mode:
            html += f"""
            <div style="padding:4px 8px;">
                <div style="font-size:10px; color:var(--text_light); text-transform:uppercase; font-weight:700; margin-bottom:4px; letter-spacing:0.5px;">All-Time Totaal</div>
                <div style="display:flex; justify-content:space-between; align-items:flex-end;">
                    <span style="font-size:15px; font-weight:700; color:var(--text_light); font-variant-numeric: tabular-nums;">{ka:,.0f} km</span>
                    <span style="font-size:12px; color:var(--text_light); font-weight:600;">{sa/3600:,.1f} u</span>
                </div>
            </div>"""
            
        html += "</div>"
    return html + "</div>"

def generate_hall_of_fame(df):
    html = '<div class="hof-grid">'
    df_h = df.dropna(subset=['Datum']).copy()
    for cat in ['Mountainbike', 'Wandelen']:
        df_s = df_h[df_h['Categorie'] == cat]
        if df_s.empty: continue
        icon, color = get_sport_style(cat)
        def t3(col,u):
            if col not in df_s.columns: return ""
            ds = df_s.sort_values(col, ascending=False).head(3); r=""
            for i,(_,row) in enumerate(ds.iterrows()):
                v=row[col]; val=f"{v:.1f} {u}" if u != 'm' else f"{v:.0f} {u}"
                
                r += f"""
                <div class="top3-item" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.05); padding-bottom:6px;">
                    <span style="font-weight:600; color:var(--text); font-size:13px;">{"🥇🥈🥉"[i]} {val}</span>
                    <span class="date" style="font-size:11px; color:var(--text_light); background:rgba(255,255,255,0.05); padding:2px 8px; border-radius:12px;">{row["Datum"].strftime("%d-%m-%y")}</span>
                </div>"""
            return r
        secs = f'<div class="hof-sec"><div class="sec-lbl">Langste Afstand</div>{t3("Afstand_km","km")}</div>'
        if 'Hoogtemeters' in df_s.columns and df_s['Hoogtemeters'].max() > 0: 
            secs += f'<div class="hof-sec" style="margin-top:10px;"><div class="sec-lbl">Meeste Hoogtemeters</div>{t3("Hoogtemeters","m")}</div>'
        else: 
            secs += f'<div class="hof-sec" style="margin-top:10px;"><div class="sec-lbl">Snelste Gem.</div>{t3("Gem_Snelheid","km/u")}</div>'
        html += f"""<div class="hof-card"><div class="hof-header" style="color:{color}; font-size:18px; font-weight:700; display:flex; gap:8px; align-items:center; margin-bottom:15px;">{icon} {cat}</div>{secs}</div>"""
    return html + '</div>'

def generate_logbook(df):
    rows = ""
    for _, r in df.sort_values('Datum', ascending=False).iterrows():
        km = f"{r['Afstand_km']:.1f}" if r['Afstand_km'] > 0 else "-"
        rows += f"<tr><td>{r['Datum'].strftime('%d-%m')}</td><td>{get_sport_style(r['Categorie'])[0]}</td><td>{r['Naam']}</td><td align='right'><strong>{km}</strong></td></tr>"
    return f'<div class="chart-box full-width" style="overflow-x:auto;"><table class="log-table" style="min-width:600px;"><thead><tr><th>Datum</th><th>Type</th><th>Naam activiteit</th><th align="right">km</th></tr></thead><tbody>{rows}</tbody></table></div>'

def generate_kpi(lbl, val, icon, diff_html, unit=""):
    val_html = f"{val}"
    if unit:
        val_html += f' <span style="font-size: 14px; color: var(--text_light); font-weight: 600;">{unit}</span>'
        
    return f"""<div class="kpi-card"><div style="display:flex;justify-content:space-between;"><div class="lbl" style="font-size:12px;color:var(--text_light);font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">{lbl}</div><div class="icon" style="font-size:18px;">{icon}</div></div><div class="val" style="font-size:26px;font-weight:800;color:var(--text);margin:8px 0; font-variant-numeric: tabular-nums;">{val_html}</div><div style="font-size:13px;">{diff_html}</div></div>"""

# --- MAIN ---
def genereer_dashboard():
    print("🚀 Start V72.0 (MTB, Padel, Wandelen & Hoogtemeters)...")
    try:
        df = pd.read_csv('activities.csv')
        # Toegevoegd: Hoogteverschil of Elevatiewinst vertalen naar Hoogtemeters
        nm = {'Datum van activiteit':'Datum', 'Naam activiteit':'Naam', 'Activiteitstype':'Activiteitstype', 'Beweegtijd':'Beweegtijd_sec', 'Afstand':'Afstand_km', 'Gemiddelde hartslag':'Hartslag', 'Gemiddelde snelheid':'Gem_Snelheid', 'Uitrusting voor activiteit':'Gear', 'Calorieën':'Calorieën', 'Hoogteverschil':'Hoogtemeters', 'Elevatiewinst':'Hoogtemeters'}
        df = df.rename(columns={k:v for k,v in nm.items() if k in df.columns})
        
        # Zorg dat Hoogtemeters altijd bestaat (voorkomt errors)
        if 'Hoogtemeters' not in df.columns: df['Hoogtemeters'] = 0
        
        for c in ['Afstand_km', 'Beweegtijd_sec', 'Gem_Snelheid', 'Calorieën', 'Hoogtemeters']:
            if c in df.columns: df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        df['Hartslag'] = pd.to_numeric(df['Hartslag'], errors='coerce')
        if 'Wattage' in df.columns: df['Wattage'] = pd.to_numeric(df['Wattage'], errors='coerce')
        
        df['Datum'] = df['Datum'].apply(solve_dates); df = df.dropna(subset=['Datum'])
        df['Categorie'] = df.apply(determine_category, axis=1); df['Jaar'] = df['Datum'].dt.year; df['Day'] = df['Datum'].dt.dayofyear
        if df['Gem_Snelheid'].mean() < 10: df['Gem_Snelheid'] *= 3.6
        
        years = sorted(df['Jaar'].unique(), reverse=True)
        nav, sects = "", ""
        
        for yr in years:
            df_yr = df[df['Jaar'] == yr]; df_prev = df[df['Jaar'] == yr-1]
            ytd = datetime.now().timetuple().tm_yday
            df_prev_comp = df_prev[df_prev['Day'] <= ytd] if yr == datetime.now().year else df_prev
            
            streaks_html = generate_streaks_box(df) if yr == datetime.now().year else ""
            
            cal_yr = df_yr['Calorieën'].sum() if 'Calorieën' in df_yr.columns else 0
            cal_prev = df_prev_comp['Calorieën'].sum() if 'Calorieën' in df_prev_comp.columns and not df_prev_comp.empty else 0
            hm_yr = df_yr['Hoogtemeters'].sum() if 'Hoogtemeters' in df_yr.columns else 0
            hm_prev = df_prev_comp['Hoogtemeters'].sum() if 'Hoogtemeters' in df_prev_comp.columns and not df_prev_comp.empty else 0
            
            # De nieuwe grid heeft 5 KPI's, de CSS grid is ingesteld op kolommen
            sects += f"""<div id="v-{yr}" class="tab-content" style="display:{"block" if yr == datetime.now().year else "none"}">
                <div class="kpi-grid">
                    {generate_kpi("Sessies", len(df_yr), "👟", format_diff_html(len(df_yr), len(df_prev_comp)))}
                    {generate_kpi("Afstand", f"{df_yr['Afstand_km'].sum():,.0f}", "📏", format_diff_html(df_yr['Afstand_km'].sum(), df_prev_comp['Afstand_km'].sum(), "km"), unit="km")}
                    {generate_kpi("Tijd", format_time(df_yr['Beweegtijd_sec'].sum()), "⏱️", format_diff_html(df_yr['Beweegtijd_sec'].sum()/3600, df_prev_comp['Beweegtijd_sec'].sum()/3600, "u"))}
                    {generate_kpi("Energie", f"{cal_yr:,.0f}", "🔥", format_diff_html(cal_yr, cal_prev, "kcal"), unit="kcal")}
                    {generate_kpi("Hoogtemeters", f"{hm_yr:,.0f}", "⛰️", format_diff_html(hm_yr, hm_prev, "m"), unit="m")}
                </div>
                {streaks_html}
                {create_ytd_chart(df, yr)}
                <h3 class="sec-sub">Per Sport</h3>{generate_sport_cards(df_yr, df_prev_comp)}
                <h3 class="sec-sub">Materiaal {yr}</h3>{generate_yearly_gear(df_yr, df)}
                <h3 class="sec-sub">Maandelijkse Voortgang</h3>{create_monthly_charts(df_yr, df_prev, yr)}
                <h3 class="sec-sub">Diepte-analyse</h3>
                <div class="chart-grid">{create_elevation_chart(df_yr)}{create_zone_pie(df_yr)}</div>
                <div class="chart-grid">{create_scatter_plot(df_yr)}{create_heatmap(df_yr)}</div>
                <h3 class="sec-sub">Records {yr}</h3>{generate_hall_of_fame(df_yr)}
                <h3 class="sec-sub">Logboek</h3>{generate_logbook(df_yr)}
            </div>"""
            nav += f'<button class="nav-btn {"active" if yr == datetime.now().year else ""}" onclick="openTab(event, \'v-{yr}\')">{yr}</button>'
            
        nav += '<button class="nav-btn" onclick="openTab(event, \'v-Tot\')">Carrière</button>'
        sects += f'<div id="v-Tot" class="tab-content" style="display:none"><h2 class="sec-title" style="color:var(--text);">All-Time Garage</h2>{generate_yearly_gear(df, df, True)}<h3 class="sec-sub">All-Time Records</h3>{generate_hall_of_fame(df)}</div>'
        
        # HTML template blijft hetzelfde, kpi-grid CSS krijgt nu auto-fit
        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>⚡ Sportoverzicht</title>
        
        <link rel="manifest" href="manifest.json">
        <link rel="icon" type="image/png" href="icon.png">
        <link rel="apple-touch-icon" href="icon.png">
        <meta name="theme-color" content="#0b0914">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
        :root{{--primary:#00e5ff;--bg:#0b0914;--card:#1e1b4b;--text:#f8fafc;--text_light:#94a3b8;}}
        * {{ box-sizing: border-box; }}
        body{{font-family:'Poppins',sans-serif;background:var(--bg);color:var(--text);margin:0;padding:20px 0;}}
        .container{{width:96%; max-width:1400px; margin:0 auto;}}
        
        .header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;}}
        .lock-btn{{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:6px 12px;border-radius:20px;cursor:pointer; font-family:'Poppins',sans-serif; color:white;}}
        
        .nav{{display:flex;gap:8px;overflow-x:auto;padding:10px 0;scrollbar-width:none;position:sticky;top:0;z-index:100;background:var(--bg);}}
        .nav-btn{{font-family:inherit;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:8px 16px;border-radius:20px;font-size:13px;font-weight:600;cursor:pointer; color:var(--text_light); transition:0.2s; flex-shrink: 0;}}
        .nav-btn.active{{background:linear-gradient(45deg, #00e5ff, #10b981);color:white; border:none; box-shadow:0 4px 15px rgba(0,229,255,0.2);}}
        
        .kpi-grid, .sport-grid, .hof-grid, .chart-grid {{display:grid; gap:12px; margin-bottom:20px; width: 100%;}}
        .kpi-grid{{grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));}} 
        .sport-grid, .hof-grid{{grid-template-columns:repeat(auto-fit,minmax(280px,1fr));}}
        .chart-grid{{grid-template-columns:repeat(auto-fit,minmax(280px,1fr));}}
        
        .kpi-card, .sport-card, .hof-card, .chart-box, .streaks-section {{
            background:linear-gradient(145deg, #1e1b4b, #151236); 
            padding:15px; 
            border-radius:16px; 
            border:1px solid rgba(255,255,255,0.05); 
            box-shadow:0 4px 10px rgba(0,0,0,0.3);
            width: 100%;
        }}
        .chart-box, .chart-grid {{ max-width: 100%; overflow-x: hidden; }}
        .chart-box.full-width {{ margin-bottom: 25px; width: 100%; }}
        .streaks-section {{ margin-bottom: 25px; width: 100%; }}
        
        .sec-title {{font-size:22px;font-weight:800;letter-spacing:-0.5px;margin:0 0 15px 0;color:var(--text)}}
        .sec-sub{{font-size:13px;text-transform:uppercase;letter-spacing:1px;margin:35px 0 10px 0;border-bottom:2px solid rgba(255,255,255,0.05);padding-bottom:5px;color:var(--primary);font-weight:800; display:inline-block;}}
        .sec-lbl{{font-size:10px;text-transform:uppercase;color:var(--text_light);font-weight:700;margin-top:5px;}}
        .box-title{{font-size:11px;color:var(--text_light);text-transform:uppercase;margin-bottom:12px;letter-spacing:0.5px;font-weight:700}}
        
        .stat-row{{display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px; color:var(--text_light); font-weight:500; align-items:center;}}
        .stat-row strong{{color:var(--text); font-weight:700}}
        .val-group{{display:flex;gap:8px;align-items:center}}
        
        .log-table{{width:100%;border-collapse:collapse;font-size:12px;}} .log-table th{{text-align:left;padding:12px 10px;border-bottom:1px solid rgba(255,255,255,0.05);color:var(--text_light);font-weight:700;}} .log-table td{{padding:12px 10px;border-bottom:1px solid rgba(255,255,255,0.02);font-weight:500; color:var(--text);}}
        .streak-row{{display:flex;justify-content:space-between;font-size:14px;font-weight:700;color:var(--text); margin-bottom:4px;}}
        .streak-sub{{font-size:11px;color:var(--text_light);}}
        .icon-circle{{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;margin-bottom:10px;}}
        </style></head><body><div class="container">
        <div class="header"><h1 style="font-size:28px;font-weight:800;letter-spacing:-1px;margin:0; background: -webkit-linear-gradient(45deg, #00e5ff, #10b981); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">⚡ Sportoverzicht</h1><button class="lock-btn" onclick="unlock()">❤️ 🔒</button></div>
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
            if(prompt("Wachtwoord:")==='Nala'){{
                document.querySelectorAll('.secure-hr').forEach(e => {{
                    e.innerHTML = '❤️ ' + e.getAttribute('data-hr');
                }});
                document.querySelector('.lock-btn').style.display='none';
            }}
        }}
        </script></body></html>"""
        
        with open('dashboard.html', 'w', encoding='utf-8') as f: f.write(html)
        print("✅ Dashboard (V72.0) klaar: Focus op MTB, Padel, Wandelen met Hoogtemeters-grafiek!")
    except Exception as e: print(f"❌ Fout: {e}")

if __name__ == "__main__": genereer_dashboard()
