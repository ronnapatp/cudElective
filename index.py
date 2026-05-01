import os
import requests
import sys
import pandas as pd
import json
import re

with open("links.json") as f:
    linkData = json.load(f)

def extract_ids_from_url(url):
    spreadsheet_id_match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    gid_match = re.search(r'gid=([0-9]+)', url)
    
    s_id = spreadsheet_id_match.group(1) if spreadsheet_id_match else None
    gid = gid_match.group(1) if gid_match else "0"
    return s_id, gid

def getGoogleSheet(url, outFile):
    spreadsheet_id, gid = extract_ids_from_url(url)
    if not spreadsheet_id:
        print(f"Could not parse URL: {url}")
        return False

    download_url = f'https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}'
    response = requests.get(download_url)
    
    if response.status_code == 200:
        os.makedirs(os.path.dirname(outFile), exist_ok=True)
        with open(outFile, 'wb') as f:
            f.write(response.content)
            print(f'CSV {outFile}')
        return True
    else:
        print(f'err {response.status_code}')
        return False

def csvToJson(filePath, outputFile, grade_label):
    df_raw = pd.read_csv(filePath, header=None)

    # Detect format: m1-3 has schedule cols at 9-16, m4-6 has at 10-25
    # Check by looking at row 1 col 9 (m1-3 has day header 'จันทร์', m4-6 has 'รหัสวิชา')
    if df_raw.iloc[1, 9] == 'จันทร์':
        # m1-3 format: schedule cols 9-16
        schedule_start = 9
        schedule_cols = 8
    else:
        # m4-6 format: schedule cols 10-25
        schedule_start = 10
        schedule_cols = 16

    schedule_end = schedule_start + schedule_cols
    day_headers = df_raw.iloc[1, schedule_start:schedule_end].ffill().tolist()
    period_headers = df_raw.iloc[2, schedule_start:schedule_end].fillna('').tolist()
    schedule_labels = [f"{d} {p}".strip() for d, p in zip(day_headers, period_headers)]

    rows = []
    for idx, row in df_raw.iloc[5:].iterrows():
        if pd.isna(row[1]) and not pd.isna(row[0]):
            continue
        if pd.isna(row[0]) and pd.isna(row[5]) and pd.isna(row[6]):
            continue

        active_times = [schedule_labels[i] for i, val in enumerate(row[schedule_start:schedule_end]) if val == '✔']
        
        rows.append({
            'code': row[0],
            'name': row[1],
            'credit': row[2],
            'classPerWeek': row[3],
            'group': str(row[6]) if not pd.isna(row[6]) else "",
            'instructor': row[5],
            'enrollment': row[7],
            'electiveQuantity': str(row[8]) if not pd.isna(row[8]) else "",
            'updatedElectiveQuantity': str(row[8]) if not pd.isna(row[8]) else "",
            'classtime': ', '.join(active_times),
            'classroom': "", 
            'note': row[9] if not pd.isna(row[9]) else ""
        })
        
    if not rows:
        return

    df = pd.DataFrame(rows)
    
    df[['code', 'name', 'credit', 'classPerWeek']] = df[['code', 'name', 'credit', 'classPerWeek']].ffill()
    
    code_to_order = {}
    curr = 1
    orders = []
    for c in df['code']:
        if c not in code_to_order:
            code_to_order[c] = curr
            curr += 1
        orders.append(code_to_order[c])
    df['order'] = orders

    grouped_df = df.groupby(['order', 'code']).agg({
        'name': 'first',
        'credit': 'first',
        'classPerWeek': 'first',
        'group': lambda x: x.tolist() if len(x) > 1 else x.iloc[0],
        'instructor': lambda x: x.tolist() if len(x) > 1 else x.iloc[0],
        'enrollment': lambda x: x.tolist() if len(x) > 1 else x.iloc[0],
        'electiveQuantity': lambda x: x.tolist() if len(x) > 1 else x.iloc[0],
        'updatedElectiveQuantity': lambda x: x.tolist() if len(x) > 1 else x.iloc[0],
        'classtime': lambda x: x.tolist() if len(x) > 1 else x.iloc[0],
        'classroom': lambda x: x.tolist() if len(x) > 1 else x.iloc[0],
        'note': lambda x: x.tolist() if len(x) > 1 else x.iloc[0],
    }).reset_index()

    grouped_df['order'] = pd.to_numeric(grouped_df['order']).astype('Int64')
    json_data = grouped_df.to_json(orient='records', force_ascii=False, default_handler=str, indent=2)

    with open(f'{outputFile}.json', 'w', encoding='utf-8') as json_file:
        json_file.write(json_data)
        print(f"converted {grade_label}")

year_key = "2025/2"
for i in range(1, 7):
    grade_key = f"m{i}"
    if grade_key in linkData[year_key]:
        url = linkData[year_key][grade_key]
        csv_path = f'./data/csv/m{i}.csv'
        json_path = f'./data/json/m{i}'
        
        if getGoogleSheet(url, csv_path):
            csvToJson(csv_path, json_path, grade_key)

sys.exit(0)