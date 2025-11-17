# Restaurant Review Scraper (Serper.dev + Python)

This project allows you to scrape **Google Maps restaurant data + reviews** from any **City** and **Area** using the **Serper.dev API**. It supports pagination, area filtering, and exports all data into a structured CSV file.

This README explains:
- Setup instructions
- API key configuration
- How the script works
- How to run the scraper
- Output format
- Limitations & notes

---

## 🚀 Features

- Scrape **restaurants** from a specific **City + Area** (e.g. *Gulshan, Dhaka*)
- Fetch up to **N restaurants** (depending on availability from Google Maps)
- Fetch **N reviews per restaurant**
- Accurate filtering so only restaurants from the requested area are included
- CSV output automatically named as:
  
  ```
  area_city_restaurant_data.csv
  ```
  Example: `gulshan_dhaka_restaurant_data.csv`
- Uses Serper.dev API (fast & reliable Google Search API)
- Works with your `.env` API key

---

## 📦 Requirements

Install dependencies:

```bash
pip install requests python-dotenv
```

---

## 🔐 API Key Setup

The scraper requires a **Serper.dev API key**.

1. Go to https://serper.dev
2. Create a free account (2,500 free searches)
3. Copy your API key from the **API Keys** page
4. Add it to a `.env` file in your project folder:

```
SERPER_API_KEY=your_key_here
```

Make sure `.env` is in the **same folder** as your script.

---

## 📁 Folder Structure

```
Restaurant Review Scrapper/
│
├── serper_dhaka_restaurants.py   # Main scraper script
├── .env                           # Contains your API key
└── README.md                      # This file
```

---

## 🧠 How the Script Works

### 1. User Inputs
The script first asks the user for:

- **City** (e.g., Dhaka)
- **Area** (e.g., Gulshan)
- **Number of restaurants** to scrape
- **Number of reviews** per restaurant

### 2. Query Construction
It builds a Google Maps query like:

```
restaurants in Gulshan, Dhaka
```

### 3. Pagination
Serper supports pagination **only when GPS (ll) is provided**.
Since Dhaka is your main use case, the script automatically uses:

```
@23.8103,90.4125,13z
```

This allows scraping multiple pages of results.

### 4. Area Filtering
Not all Google results belong to the exact area.

The script checks:

- `place.title`
- `place.address`

It ensures both contain:
- the **area** (e.g., "gulshan")
- the **city** (e.g., "dhaka")

Only **valid matches** are kept.

### 5. Fetching Reviews
For each restaurant, Serper’s `/reviews` API is called.
We extract:

- Reviewer name
- Rating
- Date
- Review text
- Additional info (likes, review ID, etc.)

### 6. CSV File
Finally, a CSV is created where **each row represents one review**, including business info.

---

## ▶️ Running the Scraper

Open terminal inside the project folder:

```bash
python serper_dhaka_restaurants.py
```

You will be prompted:

```
City name (e.g., Dhaka): Dhaka
Area name (e.g., Gulshan): Gulshan
Number of restaurants to scrape (e.g., 500): 500
Number of reviews per restaurant (e.g., 10): 10
```

---

## 📊 Output Format

The output CSV file will be named:

```
gulshan_dhaka_restaurant_data.csv
```

### Columns:

| Column | Description |
|--------|-------------|
| business_name | Restaurant name |
| business_address | Full address |
| business_phone | Phone number |
| business_website | Website if available |
| business_rating | Google rating |
| business_total_reviews | Total Google reviews |
| reviewer_name | Name of reviewer |
| review_rating | Review rating |
| review_date | Date posted |
| review_text | Review content |
| review_additional_info | Likes, review ID, etc. |

---

## ⚠️ Important Notes

### 1. "500 restaurants" is a **target**, not a guarantee
If Google Maps only returns 66 restaurants for Gulshan, the script cannot force more.

### 2. Serper limits
Your free plan includes 2,500 search credits.
- Each page of Maps = 1 credit
- Each restaurant review call = 1 credit

### 3. Area filtering affects count
Strict filtering (`Gulshan` + `Dhaka`) ensures high accuracy but reduces count.

You may relax filters if you want more results.

---

## 🛠 Optional Improvements
I can add any of these for you:

- Bounding box filtering using latitude/longitude
- Multi-query merging for higher coverage
- Export to Excel instead of CSV
- Add review sentiment scores
- Add category filters (cafés, buffet, etc.)
- Save raw JSON for debug use

Just tell me! 😊

---

## ❤️ Need Help?
If your script gives errors or you want new features, message me and I’ll improve it instantly.

Happy Scraping! 🚀

