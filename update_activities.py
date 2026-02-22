import os
import requests
import pandas as pd
import time
import warnings

# Onderdrukt de HTTPS waarschuwingen
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# --- INSTELLINGEN ---
CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')
CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')
REFRESH_TOKEN = os.getenv('STRAVA_REFRESH_TOKEN')

# Hier kan Joël later zijn eigen schoenen of fietsen toevoegen als hij dat wil.
# Bijvoorbeeld: 'g1234567': 'S-Works Tarmac'
MANUAL_GEAR_MAP = {}

def get_access_token():
    url = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'refresh_token': REFRESH_TOKEN,
        'grant_type': 'refresh_token'
    }
    res = requests.post(url, data=payload, verify=False)
    if res.status_code != 200:
        print(f"❌ Fout bij ophalen token: {res.text}")
        exit(1)
    return res.json()['access_token']

def translate_type(sport_type):
    translations = {
        'Ride': 'Fietsrit',
        'VirtualRide': 'Virtuele fietsrit',
        'Run': 'Hardloopsessie',
        'Walk': 'Wandeling',
        'Swim': 'Zwemmen',
        'WeightTraining': 'Krachttraining',
        'Workout': 'Workout',
        'GravelRide': 'Gravelrit',
        'EBikeRide': 'E-Bike rit'
    }
    return translations.get(sport_type, sport_type)

def main():
    print("🚀 Start met ophalen van Strava historie voor Joël...")
    access_token = get_access_token()
    headers = {'Authorization': f'Bearer {access_token}'}
    
    csv_file = 'activities.csv'
    existing_ids = set()
    existing_data = []
    
    # Check of we al een archief hebben, zo ja: laad het in
    if os.path.exists(csv_file):
        try:
            df_existing = pd.read_csv(csv_file)
            if 'Activity ID' in df_existing.columns:
                existing_ids = set(df_existing['Activity ID'].astype(str))
                existing_data = df_existing.to_dict('records')
                print(f"✅ {len(existing_ids)} bestaande ritten gevonden.")
        except:
            print("Nieuw logboek wordt aangemaakt.")

    page = 1
    new_activities = []
    
    while True:
        print(f"📄 Strava logboek pagina {page} doorzoeken...")
        url = f"https://www.strava.com/api/v3/athlete/activities?page={page}&per_page=100"
        res = requests.get(url, headers=headers, verify=False)
        
        if res.status_code == 429:
            print("❌ Strava weigert dienst (Code 429). De 15-minuten limiet is bereikt!")
            print("We slaan op wat we tot nu toe hebben. De rest komt bij de volgende automatische update!")
            break
        elif res.status_code != 200:
            print(f"❌ Fout bij ophalen ritten: {res.text}")
            break
            
        activities = res.json()
        if not activities:
            break # Geen ritten meer gevonden, we zijn klaar
            
        for a in activities:
            act_id = str(a['id'])
            
            # Sla over als de rit al in de CSV staat
            if act_id in existing_ids:
                continue 
                
            dt = a['start_date_local'].replace('T', ' ').replace('Z', '')
            sport_type = translate_type(a['type'])
            
            gear_id = a.get('gear_id')
            gear_name = MANUAL_GEAR_MAP.get(gear_id, gear_id) if gear_id else ""
            
            # Calorieën ophalen vereist een extra API-verzoek per rit
            calories = 0
            detail_url = f"https://www.strava.com/api/v3/activities/{act_id}"
            detail_res = requests.get(detail_url, headers=headers, verify=False)
            
            if detail_res.status_code == 200:
                calories = detail_res.json().get('calories', 0)
            elif detail_res.status_code == 429:
                print("⚠️ Limiet bereikt tijdens het ophalen van calorieën. Overslaan voor deze rit.")
            
            new_act = {
                'Activity ID': act_id,
                'Datum van activiteit': dt,
                'Naam activiteit': a.get('name', ''),
                'Activiteitstype': sport_type,
                'Beweegtijd': a.get('moving_time', 0),
                'Afstand': a.get('distance', 0) / 1000.0,
                'Totale stijging': a.get('total_elevation_gain', 0), # Hiermee halen we de hoogtemeters op!
                'Gemiddelde snelheid': a.get('average_speed', 0) * 3.6,
                'Gemiddelde hartslag': a.get('average_heartrate', ''),
                'Wattage': a.get('average_watts', ''),
                'Uitrusting voor activiteit': gear_name,
                'Calorieën': calories
            }
            new_activities.append(new_act)
            
        page += 1

    # Opslaan van de data
    if new_activities:
        print(f"🎉 {len(new_activities)} nieuwe ritten binnengehaald!")
        all_data = existing_data + new_activities
        df_final = pd.DataFrame(all_data)
        df_final = df_final.sort_values(by='Datum van activiteit', ascending=False)
        df_final.to_csv(csv_file, index=False)
        print("✅ Data succesvol opgeslagen in activities.csv!")
    else:
        print("✅ Geen nieuwe activiteiten gevonden. Alles was al up-to-date!")

if __name__ == "__main__":
    main()
