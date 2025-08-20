import os
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential,TokenCredential
from openai import AzureOpenAI
 
def get_auth_mode() -> str:
    return os.getenv("AUTH_MODE", "managed").lower()
 
# ---------- Azure AI Search ----------
def get_search_credential() -> "TokenCredential|AzureKeyCredential":
    mode = get_auth_mode()
    if mode == "apikey":
        key = os.getenv("SEARCH_API_KEY")
        if not key:
            raise ValueError("SEARCH_API_KEY missing in apikey mode")
        return AzureKeyCredential(key)
    return DefaultAzureCredential()
 
# ---------- AzureOpenAI ----------
def get_openai_client() -> AzureOpenAI:
    from dotenv import load_dotenv
    load_dotenv(override=True)
 
    endpoint = os.getenv("OPENAI_ENDPOINT_URL")
    if not endpoint:
        raise ValueError("OPENAI_ENDPOINT_URL missing")
 
    mode = get_auth_mode()
    if mode == "apikey":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY missing in apikey mode")
        return AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version="2024-02-01"
        )
    # managed identity path
    credential = DefaultAzureCredential()
    return AzureOpenAI(
        azure_ad_token_provider=lambda: credential.get_token(
"https://cognitiveservices.azure.com/.default"
        ).token,
        azure_endpoint=endpoint,
        api_version="2024-02-01"
    )
