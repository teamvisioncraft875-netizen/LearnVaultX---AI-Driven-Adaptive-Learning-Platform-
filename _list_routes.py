from app import app
import sys

print("Listing all routes:")
for rule in app.url_map.iter_rules():
    print(f"{rule} -> {rule.endpoint}")
