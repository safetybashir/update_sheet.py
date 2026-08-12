name: Run Stock Scanner Automation

on:
  schedule:
    # Runs every 15 minutes during IST market hours (Mon-Fri)
    - cron: '*/15 3-10 * * 1-5'
  workflow_dispatch: # Allows manual trigger from GitHub UI

jobs:
  run-scanner:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python 3.10
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install yfinance pandas numpy requests gspread google-auth pytz

      - name: Execute Stock Scanner Script
        env:
          GCP_SA_KEY: ${{ secrets.GCP_CREDENTIALS_JSON }}
          SHEET_ID: ${{ secrets.SHEET_ID }}
        run: python update_sheet.py
