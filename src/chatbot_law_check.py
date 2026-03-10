from openai import OpenAI
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


def ask_gpt(question, context):
    prompt = f"""
You are an Arizona family law research assistant.

Answer the question using ONLY the legal text provided.

Provide citations to the statute numbers when possible.

LEGAL TEXT:
{context}

QUESTION:
{question}
"""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an Arizona family law research assistant. Answer using only the legal text provided. Cite statute numbers when possible."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content or ""
