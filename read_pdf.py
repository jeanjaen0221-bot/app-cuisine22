from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
from io import StringIO
import re

# Extract with layout
output = StringIO()
with open('77c7e340-62f8-4a95-aa5f-3af26d52b7e1.pdf', 'rb') as f:
    extract_text_to_fp(f, output, laparams=LAParams(), output_type='text', codec=None)

text = output.getvalue()
lines = [ln.rstrip() for ln in text.splitlines()]

print(f"Total lines: {len(lines)}")
print("\n=== Lines with time pattern (HH:MM) ===\n")

for i, line in enumerate(lines):
    # Find lines that start with time
    if re.match(r'^\d{1,2}:\d{2}', line):
        # Show context: 2 lines before, the line, 5 lines after
        start = max(0, i-2)
        end = min(len(lines), i+6)
        print(f"\n--- Line {i} ---")
        for j in range(start, end):
            marker = ">>>" if j == i else "   "
            print(f"{marker} {j:3d}: {lines[j]}")
