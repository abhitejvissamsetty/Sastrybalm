import os
import re

mobile_lib = "/Users/johnwesleygovada/Desktop/Safar/mobile/lib"

pattern = re.compile(r'(bool|Future<bool>)\s+([a-zA-Z0-9_]+|[a-zA-Z0-9_]+\s*\([^)]*\))')

for root, dirs, files in os.walk(mobile_lib):
    for f in files:
        if f.endswith('.dart'):
            filepath = os.path.join(root, f)
            with open(filepath, 'r') as file:
                lines = file.readlines()
                for idx, line in enumerate(lines):
                    if 'bool' in line:
                        print(f"{os.path.relpath(filepath, mobile_lib)}:{idx+1}: {line.strip()}")
