import sqlite3
import os

c = sqlite3.connect('library.db').cursor()

# Find C:\Book which was the source of transfer
print('=== Check C:\\Book ===')
if os.path.exists('C:\\Book'):
    files = os.listdir('C:\\Book')
    print(f'C:\\Book: {len(files)} items')
    for f in files[:15]:
        print(f'  {f}')
else:
    print('C:\\Book does not exist')

# Check where Book source (44) points to
c.execute("SELECT id, name, path FROM sources WHERE id = 44")
book44 = c.fetchone()
print(f'\nSource 44 (Book): {book44}')

# Was the original Book source C:\Book? Let me find the original source
# It would have been deleted after transfer
# Check if there was a source with path C:\Book that was deleted
print('\n=== Looking for original source ===')
c.execute("SELECT id, name, path FROM sources")
for s in c.fetchall():
    print(s)