import os
from datetime import datetime

from google import genai

from core.schemas import MarketDataQuery


# Do not initialize a global client to prevent module crash if API key is missing
def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in the environment.")
    return genai.Client(api_key=api_key)

def parse_text_to_query(text: str) -> MarketDataQuery:
    """
    Use Gemini API to convert the user's natural language query
    into a structured MarketDataQuery based on a JSON Schema.
    """
    prompt = f"""
    You are an AI assistant specialized in analyzing market data queries (crypto/stocks).
    Your task is to read the user's request and extract the necessary parameters to query the DB.
    
    Current Date and Time (UTC): {datetime.utcnow().isoformat() + "Z"}
    
    User query: "{text}"
    
    Strictly adhere to the requested Schema (MarketDataQuery model).
    If a parameter is not explicitly stated, infer it based on the current context. For example, "past 3 days" is calculated from the current time.
    """

    client = get_client()
    # Call API with Structured Output requirement
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config={
            'response_mime_type': 'application/json',
            'response_schema': MarketDataQuery,
            'temperature': 0.1,
        },
    )

    # The genai SDK automatically checks syntax and ensures valid JSON,
    # we validate again with Pydantic to create an object usable in Python
    # Although response_schema requires a Pydantic model, response.text returns JSON as text.
    if not response.text:
        raise ValueError("LLM returned an empty response")
    return MarketDataQuery.model_validate_json(response.text)
