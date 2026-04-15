# Google Maps Scraper

A Python script to scrape Google Maps and export business data to CSV. Get names, addresses, phone numbers, ratings, websites, and opening hours for any city - ready for lead generation, market research, or competitive analysis. No browser or Selenium needed.

> **Disclaimer:** This tool is provided for educational and research purposes only. By using this Google Maps Scraper, you agree to comply with local and international laws regarding data scraping and privacy. The authors and contributors are not responsible for any misuse of this software. This tool should not be used to violate the rights of others, or for unethical purposes.

## Table of Contents

- [Google Maps Scraper Features](#google-maps-scraper-features)
- [What Data Can You Extract?](#what-data-can-you-extract)
- [What Can I Do with Google Maps Data?](#what-can-i-do-with-google-maps-data)
- [Quick Start](#quick-start)
- [Set Up with AI](#set-up-with-ai)
- [Proxy Setup](#proxy-setup)
- [Usage](#usage)
- [How the Google Maps Scraper Works](#how-the-google-maps-scraper-works)
- [FAQ](#faq)

## Google Maps Scraper Features

- **Grid-based city coverage** - divides any city into a grid of small cells to capture every business, not just the first page of results
- **CSV export** - clean output with 9 data fields per business, ready for spreadsheets, CRMs, or databases
- **Residential proxy resilience** - 7 retries with exponential backoff, circuit breaker, automatic health checks, and failed cell retry queue
- **Checkpoint and resume** - interrupted scrapes pick up exactly where they left off
- **Cross-cell deduplication** - businesses that appear in overlapping cells are only counted once
- **Anti-detection** - header rotation, session management, and adaptive delays between requests

## What Data Can You Extract?

Real data extracted from scraping Google Maps for barbershops in New York City:

| name | address | phone | category | rating | website |
|---|---|---|---|---|---|
| ELITE BARBERS NYC | 782 Lexington Ave, New York, NY 10065 | (212) 308-6660 | Barber shop | 4.9 | elitebarbersnyc.com |
| Pall Mall Barbers Midtown NYC | 10 Rockefeller Plaza, New York, NY 10020 | (212) 586-2220 | Barber shop | 4.8 | pallmallbarbers.nyc |
| Ray's Barber Shop Tribeca | 46 Park Pl, New York, NY 10007 | (646) 828-1052 | Barber shop | 4.9 | rays.brbrshop.com |

Each business is exported with 9 data fields. Here is a complete sample row:

```json
{
  "name": "ELITE BARBERS NYC",
  "address": "782 Lexington Ave, New York, NY 10065",
  "phone": "(212) 308-6660",
  "category": "Barber shop",
  "rating": "4.9",
  "review_count": "",
  "google_maps_url": "https://www.google.com/maps/place/?q=place_id:ChIJkebr65RZwokRI_QVOKhVN-k",
  "website": "https://elitebarbersnyc.com/",
  "opening_hours": "Open - Closes 7 PM"
}
```

## What Can I Do with Google Maps Data?

This Google Maps scraper is built for anyone who needs local business data at scale:

- **Lead generation** - build targeted prospect lists for sales outreach. Scrape every business in a category across an entire city, complete with phone numbers, websites, and addresses ready to import into your CRM
- **Market research** - analyze the competitive landscape for any industry in any city. See how many businesses operate, where they cluster, and how they rate
- **Local SEO audits** - extract Google Maps data to audit local search presence for your clients or competitors
- **Data enrichment** - enrich existing business databases with phone numbers, websites, ratings, and opening hours pulled directly from Google Maps
- **Sales enablement** - gather intel on prospects' locations, ratings, and online presence before outreach calls
- **Content and reporting** - create data-driven market reports, location analyses, or industry comparisons backed by real Google Maps data

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/worldscraping/google-maps-scraper.git
cd google-maps-scraper
pip install -r requirements.txt
```

### 2. Set up your proxy

This scraper requires a residential proxy from [MagneticProxy](https://www.magneticproxy.com) to work reliably. See the [Proxy Setup](#proxy-setup) section below for step-by-step instructions.

### 3. Run your first scrape

```bash
python main.py --query "barbershops" --city "New York City, United States" --lang en
```

### 4. Check your results

The scraper creates a CSV file in the current directory (e.g., `results_20260415_180000.csv`). Open it in any spreadsheet app or import it into your CRM.

## Set Up with AI

Already using Claude, ChatGPT, or Codex? Paste this prompt and let the AI do the setup for you. Just replace the placeholder values:

```
Clone the Google Maps scraper from https://github.com/worldscraping/google-maps-scraper
and set it up. My MagneticProxy credentials are:
- Username: YOURUSERNAME
- Password: YOURPASSWORD

Then scrape all [BUSINESS TYPE] in [CITY, COUNTRY] and export the results to CSV.
```

That's it. The AI will install dependencies, create the `.env` file, run the scraper, and show you the results.

Don't have proxy credentials yet? Follow the [Proxy Setup](#proxy-setup) steps below to get them in 2 minutes.

## Proxy Setup

This scraper uses [MagneticProxy](https://www.magneticproxy.com) residential proxies to route requests through real residential IPs. This is what prevents blocks and CAPTCHAs when scraping Google Maps at scale.

### Step-by-step setup

1. **Create an account** at [magneticproxy.com](https://www.magneticproxy.com) and sign up.

2. **Choose a Residential plan.** You can start with the smallest plan for just $1 to test the scraper (at the time of writing, there is a `firstpurchase` coupon that saves $4 on any plan). For real scraping, I recommend at least **10 GB of bandwidth**. A typical city scrape uses 1-3 GB depending on the city size and number of results, while a large metro like New York or Los Angeles can use 3-5 GB.

3. **Get your credentials.** After purchasing, go to [My Proxies](https://app.magneticproxy.com/#/my-proxies) in your dashboard. You will find your proxy username and password there.

4. **Create your `.env` file.** Copy the example file and paste your credentials:

```bash
cp .env.example .env
```

Then edit `.env`:

```
MAGNETIC_USERNAME=yourusername
MAGNETIC_PASSWORD=yourpassword
```

5. **Verify the connection.** Run any scrape command. The scraper runs a proxy health check at startup and will tell you immediately if the credentials are wrong or the proxy is unreachable.

## Usage

```
python main.py --query QUERY --city CITY [options]
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--query` | *(required)* | Search term (e.g., `"barbershops"`, `"restaurants"`, `"dentists"`) |
| `--city` | *(required)* | City name with country (e.g., `"New York City, United States"`) |
| `--output` | `results_{timestamp}.csv` | Output CSV file path |
| `--cell-size` | `2.0` | Grid cell size in km. Smaller = more thorough, slower |
| `--max-results` | *unlimited* | Stop after collecting N results |
| `--resume` | *off* | Resume from a previous checkpoint |
| `--delay-min` | `2.0` | Minimum delay between requests (seconds) |
| `--delay-max` | `5.0` | Maximum delay between requests (seconds) |
| `--lang` | `es` | Language for results (`es`, `en`, `pt`, etc.) |
| `--proxy-country` | *auto-detect* | Force proxy exit country (e.g., `us`, `co`, `mx`) |
| `--verbose` | *off* | Show detailed debug logs |

### Examples

**Scrape all barbershops in New York City for lead generation:**

```bash
python main.py --query "barbershops" --city "New York City, United States" --lang en
```

**Scrape restaurants in Los Angeles with a smaller grid for thorough coverage:**

```bash
python main.py --query "restaurants" --city "Los Angeles, United States" --lang en --cell-size 1.0
```

**Resume an interrupted scrape:**

```bash
python main.py --query "barbershops" --city "New York City, United States" --lang en --resume
```

## How the Google Maps Scraper Works

Google Maps limits search results to roughly 200 businesses per query, no matter how many actually exist in an area. This scraper extracts Google Maps data beyond that limit using a grid-based approach:

1. **Geocode** the city name into a bounding box using OpenStreetMap
2. **Generate a grid** of overlapping cells (default 2 km each) that covers the entire city
3. **Scrape each cell** independently with pagination (up to 10 pages of 20 results per cell)
4. **Deduplicate** results across cells - businesses near cell borders appear in multiple cells but are only kept once
5. **Export to CSV** - results are written progressively, so you get partial data even if the scrape is interrupted

### Reliability

The scraper is built to handle the instability of residential proxies:

- Each request retries up to **7 times** with exponential backoff (up to ~10 minutes of retry window)
- A **circuit breaker** detects sustained proxy failures and runs a connectivity health check before continuing
- **Failed cells are retried** at the end of the main scraping pass instead of being permanently skipped
- The scraper saves a **checkpoint after every cell**, so you can resume from exactly where you left off with `--resume`

## FAQ

### How much bandwidth does a Google Maps scrape use?

A typical city scrape uses **1-3 GB** depending on the city size and how many businesses match your query. A small town might use under 500 MB, while a large metro like New York City can use 3-5 GB. I recommend starting with a **10 GB plan** from MagneticProxy to have enough room for multiple scrapes.

### Can I use this Google Maps scraper for lead generation?

Yes. This is one of the most common use cases. Scrape every business in a specific category (e.g., barbershops, dentists, restaurants) across an entire city and export the results to CSV. You get business names, phone numbers, websites, and addresses - everything you need to build a targeted prospect list and import it into your CRM or outreach tool.

### Can I scrape Google Maps without getting blocked?

Yes. This scraper uses residential proxies (real IPs from real devices), rotates sessions and browser headers on every request, and adds randomized delays between requests. If a CAPTCHA is detected, the scraper automatically waits, rotates to a new IP, and retries.

### What data can I extract from Google Maps?

Each business in the output CSV includes: **name**, **address**, **phone number**, **category**, **rating**, **review count**, **Google Maps URL**, **website**, and **opening hours**.

### Can I resume an interrupted scrape?

Yes. The scraper saves a checkpoint file after every cell. If the process is interrupted (Ctrl+C, network drop, machine restart), run the same command with `--resume` and it picks up from the last completed cell. No data is lost.

### How do I scrape Google Maps for a specific city?

Run the scraper with `--query` for the business type and `--city` for the location. For example: `python main.py --query "restaurants" --city "Chicago, United States" --lang en`. The scraper geocodes the city, generates a grid, and scrapes every matching business within the city limits. Any city in the world that appears on Google Maps is supported.

### What cities and countries are supported?

Any city in the world that appears on Google Maps. The proxy exit country is auto-detected from the city name for better results, but you can override it with `--proxy-country`. The `--lang` flag controls the language of the returned data.

---

Built for scraping Google Maps at scale without getting blocked. If you find this useful, star the repo.
