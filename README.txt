REAL ESTATE BLOCKCHAIN REGISTRY — ONLINE WEB APP

This is a Python + Streamlit educational simulation for a course project.

FEATURES
- Web dashboard
- Register properties
- Transfer ownership with a current-owner check
- Search property records
- View transaction history and blocks
- SHA-256 hash chain validation
- SQLite database for demo persistence in the running environment

RUN LOCALLY
1. Install Python 3.9+.
2. Open Command Prompt in this folder.
3. Run:
   py -m pip install -r requirements.txt
   py -m streamlit run app.py
4. Your browser should open the app.

DEPLOY ONLINE
You can deploy with Streamlit Community Cloud:
1. Create a GitHub repository and upload app.py and requirements.txt.
2. Visit https://share.streamlit.io/ and sign in with GitHub.
3. Choose the repository, branch, and app.py, then deploy.

IMPORTANT
- Online hosting is not automatically created by this ZIP; you must deploy it to a hosting service.
- For reliable permanent online data, connect a managed database such as Supabase/PostgreSQL. The SQLite file on a free cloud host may reset or not be shared across instances.
- This is a course demo, not a legally valid property registry.
- It does not include distributed nodes, consensus, digital signatures, official identity checks, or government registry integration.
- Never enter real sensitive personal or property documents into this demo.
