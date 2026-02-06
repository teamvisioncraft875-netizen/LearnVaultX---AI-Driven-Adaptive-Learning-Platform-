from dotenv import load_dotenv
import os
load_dotenv()

from modules.kyknox_ai_new import KyKnoX

kyknox = KyKnoX()
print("API Key loaded:", bool(kyknox.api_key))
response, provider = kyknox.generate_response('Hello, test message')
print('Response:', response[:100] + '...' if len(response) > 100 else response)
print('Provider:', provider)