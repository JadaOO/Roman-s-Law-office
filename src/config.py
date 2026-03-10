import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
AZ_FAMILY_LAW_URL = "https://www.azleg.gov"
