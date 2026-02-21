import requests
import pandas as pd
import os
import time

# --- CONFIGURATIE ---
CLIENT_ID = os.environ.get('STRAVA_CLIENT_ID')
CLIENT_SECRET = os.environ.get('STRAVA_CLIENT_SECRET')
REFRESH_TOKEN = os.environ.get('STRAVA_REFRESH_TOKEN')

AUTH_URL = "https://www.strava.com/oauth/token"
ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
ACTIVITY_DETAIL_URL = "https://www.strava.com/api/v3/activities"

# --- ZELF GEDEFINIEERDE UITRUSTING (SCHOENEN) ---
MANUAL_GEAR_MAP = {      
}

def get_access_token():
    payload = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'refresh_token': REFRESH_TOKEN, 'grant_type': 'refresh_token', 'f': 'json'}
    try:
        res = requests.post(AUTH_URL, data=payload, verify=False)
        res.raise_for_status()
        return res.json()['access_token']
    except Exception as e:
        print(f"❌ Fout bij token: {e}")
        exit(1)

def translate_type(strava_type):
    mapping = {'Run': 'Hardlopen', 'Ride': 'Fietsrit', 'VirtualRide': 'Virtuele fietsrit', 'Walk': 'Wandelen', 'Swim': 'Zwemmen', 'WeightTraining': 'Krachttraining', 'Workout': 'Training', 'Hike': 'Wandelen', 'GravelRide': 'Fietsrit', 'MountainBikeRide': 'Fietsrit', 'E-BikeRide': 'Fietsrit', 'Velomobile': 'Fietsrit'}
    return mapping.get(strava_type, strava_type)

def process_data():
    token = get_access_token()
    headers = {'Authorization': f"Bearer {token}"}
    
    existing_cals = {}
    if os.path.exists('activities.csv'):
        try:
            df_old = pd.read_csv('activities.csv')
            if 'Calorieën' in df_old.columns and 'Datum van activiteit' in df_old.columns:
                for _, row in df_old.iterrows():
                    if pd.notna(row['Calorieën']) and float(row['Calorieën']) > 0:
                        existing_cals[str(row['Datum van activiteit'])] = float(row['Calorieën'])
        except:
            print("Geen oude cache kunnen laden.")

    all_activities = []
    page = 1
    print("📥 Bezig met ophalen historie...")
    
    while True:
        r = requests.get(f"{ACTIVITIES_URL}?per_page=200&page={page}", headers=headers)
        
        # 🔥 Echte waarschuwing: Stuur een exit error (rood kruisje) als we direct geblokkeerd worden
        if r.status_code != 200:
            print(f"❌ Strava weigert dienst (Code {r.status_code}). Waarschijnlijk de API limiet bereikt!")
            exit(1)
            
        data = r.json()
        if isinstance(data, dict) and 'message' in data:
            print(f"❌ Foutmelding van Strava: {data['message']}")
            exit(1)
            
        if not data: 
            break
            
        all_activities.extend(data)
        if len(all_activities) >= 1500: 
            break
        page += 1

    if not all_activities:
        print("❌ Geen activiteiten gevonden.")
        exit(1)

    clean_data = []
    api_calls = 0
    
   for a in all_activities:
        dt = a['start_date_local'].replace('T', ' ').replace('Z', '')
        sport_type = translate_type(a['type'])
        
        gear_id = a.get('gear_id')
        gear_name = MANUAL_GEAR_MAP.get(gear_id, gear_id) if gear_id else ""
                
        cal = existing_cals.get(dt, 0)
        
        # We vragen calorieën pas op zolang Strava ons niet blokkeert (api_calls < 999)
        if cal == 0 and api_calls < 80: 
            act_id = a['id']
            try:
                res = requests.get(f"{ACTIVITY_DETAIL_URL}/{act_id}", headers=headers)
                if res.status_code == 200:
                    detail = res.json()
                    cal = detail.get('calories', 0)
                    api_calls += 1
                    time.sleep(0.5)
                elif res.status_code == 429:
                    # 🔥 Slimme fix: Limiet bereikt TUSSENDOOR? Stop met calorieën zoeken, 
                    # maar ga wel door met het opslaan van je nieuwe ritten!
                    print("⚠️ API limiet bereikt tijdens het zoeken naar calorieën. We slaan op wat we hebben!")
                    api_calls = 999
            except:
                pass

        clean_data.append({
            'Datum van activiteit': dt,
            'Naam activiteit': a['name'],
            'Activiteitstype': sport_type,
            'Afstand': a['distance'] / 1000,
            'Beweegtijd': a['moving_time'],
            'Gemiddelde snelheid': a['average_speed'] * 3.6,
            'Gemiddelde hartslag': a.get('average_heartrate', ''),
            'Gemiddeld wattage': a.get('average_watts', ''),
            'Uitrusting voor activiteit': gear_name,
            'Calorieën': cal
        })

    df = pd.DataFrame(clean_data)
    df.to_csv('activities.csv', index=False)
    print(f"💾 Klaar! {len(df)} activiteiten opgeslagen. Nieuwe data is toegevoegd.")

if __name__ == "__main__":
    if not CLIENT_ID: 
        print("❌ Geen API keys gevonden.")
        exit(1)
    else: 
        process_data()
