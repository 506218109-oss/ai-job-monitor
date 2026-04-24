.PHONY: install run scrape snapshot init-db login seed

install:
	python3 -m pip install -r backend/requirements.txt
	python3 -m playwright install chromium
	python3 scripts/init_db.py

run:
	python3 -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload

scrape:
	python3 scripts/run_scrape.py

snapshot:
	python3 scripts/generate_snapshots.py

init-db:
	python3 scripts/init_db.py

login:
	python3 scripts/login_boss.py

seed:
	python3 scripts/seed_demo_data.py
