import os
from collections import Counter

book_dir = r'C:\Book'

print(f"=== Contents of {book_dir} ===\n")

# Count files by extension
ext_counter = Counter()
files_with_issues = []

for root, dirs, files in os.walk(book_dir):
    # Check for empty directories
    if not files and not dirs:
        print(f"EMPTY DIR: {root}")
    
    for f in files:
        full_path = os.path.join(root, f)
        ext = os.path.splitext(f)[1].lower()
        ext_counter[ext] += 1
        
        # Check for files without extensions (potential issues)
        if not ext:
            files_with_issues.append(f)

print("\n=== Files by Extension ===")
for ext, count in sorted(ext_counter.items()):
    ext_name = ext if ext else "(NO EXTENSION)"
    print(f"  {ext_name}: {count}")

print(f"\n=== Summary ===")
print(f"Total folders scanned")

total_files = sum(ext_counter.values())
print(f"Total files: {total_files}")

if files_with_issues:
    print(f"\nFiles without extension: {len(files_with_issues)}")
    for f in files_with_issues[:10]:
        print(f"  {f}")