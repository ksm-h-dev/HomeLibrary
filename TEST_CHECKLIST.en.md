[**English**](TEST_CHECKLIST.en.md) | [**Русский**](TEST_CHECKLIST.md)

# Test Checklist — Home Librarian

Date: ______________  |  Tester: ______________________  |  Version: v1.0.0

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Passed |
| ❌ | Error (specify in column) |
| ⚠️ | Non-critical but odd |
| ➖ | Not tested |

---

## 1. Initial Launch (Setup Wizard)

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 1.1 | First launch without sources — redirect to `/setup` | | |
| 1.2 | Auto-import triggered when DEFAULT_SOURCE_PATH is configured | | |
| 1.3 | Opening `/setup` manually | | |
| 1.4 | "Select folder" button — opens folder selection dialog | | |
| 1.5 | After folder selection — displays the chosen path | | |
| 1.6 | "Start scanning" button — launches scan | | |
| 1.7 | Progress bar during scan | | |
| 1.8 | After completion — redirect to `/` | | |
| 1.9 | "Skip" button — creates source without scanning | | |
| 1.10 | After skipping — navigates to main page | | |
| 1.11 | Re-entry — no redirect to setup (needs_setup=false) | | |

---

## 2. Main Page (Catalog — "Books" tab)

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 2.1 | Loading statistics (books, categories, sources) | | |
| 2.2 | Displaying book cards | | |
| 2.3 | Green left border for available books | | |
| 2.4 | Red left border for unavailable books | | |
| 2.5 | Pagination (20 books per page) | | |
| 2.6 | Page navigation (forward/back/number) | | |
| 2.7 | "Nothing found" for empty results | | |
| 2.8 | Format, year, category, source on card | | |
| 2.9 | "Open file" button for available books | | |
| 2.10 | "File unavailable" button (disabled) for unavailable books | | |
| 2.11 | Edit button (✎) on card | | |
| 2.12 | Cover icon (📷) when cover_ext is present | | |

---

## 3. Filtering and Sorting

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 3.1 | Filter by format (PDF, DJVU, RAR, ZIP) | | |
| 3.2 | Filter by category (dropdown) | | |
| 3.3 | Filter by year (dropdown) | | |
| 3.4 | Filter by source (dropdown) | | |
| 3.5 | Sorting: by date, title, author, year, pages | | |
| 3.6 | Availability filter: "Available" | | |
| 3.7 | Availability filter: "Missing" | | |
| 3.8 | Availability filter: "New arrivals" | | |
| 3.9 | Filter combination (format + year + category + availability) | | |
| 3.10 | Reset filters ("Reset" action) | | |
| 3.11 | Subcategory filtering (by last part of full_path) | | |

---

## 4. Search

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 4.1 | Search by title (FTS5) | | |
| 4.2 | Search by author | | |
| 4.3 | Search by description | | |
| 4.4 | Prefix search (typing the beginning of a word) | | |
| 4.5 | Search with filters (format + category + year) | | |
| 4.6 | Search with availability filter | | |
| 4.7 | Result highlighting (title_hl) | | |
| 4.8 | Description snippet (desc_snippet, 150 characters) | | |
| 4.9 | Empty search (no query) — return to list | | |
| 4.10 | Pagination in search results | | |
| 4.11 | Search by ISBN (if isbn is present in description) | | |

---

## 5. Book Editing

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 5.1 | Opening the edit modal | | |
| 5.2 | Loading all fields: title, author, isbn, year, publisher, pages, format, language | | |
| 5.3 | Loading category list for selection | | |
| 5.4 | Loading description (textarea) | | |
| 5.5 | Saving changes (PUT /api/books/{id}) | | |
| 5.6 | Card update after saving | | |
| 5.7 | Export metadata to .json on save | | |
| 5.8 | Moving book files when category is changed | | |
| 5.9 | Moving associated files (.txt, .json, cover) | | |
| 5.10 | Cancel editing (no changes) | | |
| 5.11 | Error 404 for non-existent book_id | | |

---

## 6. Code Lookup (ISBN/DOI/ISSN)

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 6.1 | Entering ISBN with hyphens — normalization | | |
| 6.2 | Type detection: isbn13 (97[89] + 10 digits) | | |
| 6.3 | Type detection: isbn10 (9 digits + X) | | |
| 6.4 | Type detection: doi (10.xxxx/) | | |
| 6.5 | Type detection: issn (8 digits) | | |
| 6.6 | Request to OpenLibrary / CrossRef / ISSN | | |
| 6.7 | Filling form with search results | | |
| 6.8 | Saving result to .lookup.json | | |
| 6.9 | Background cover download from external API | | |
| 6.10 | "..." button — loading state (spinner) | | |
| 6.11 | Modal for manual type selection for UDK/BBK/LCC | | |
| 6.12 | Handling "not found" error | | |
| 6.13 | Search by classification code in local DB | | |

---

## 7. Covers

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 7.1 | Auto-detection of cover during scan | | |
| 7.2 | Cover proxy (/api/cover?path=...) | | |
| 7.3 | Search by exact path | | |
| 7.4 | Search by cover_path in DB | | |
| 7.5 | Fallback — search in book directory | | |
| 7.6 | Supported formats: jpg, jpeg, png, gif, bmp, webp, tiff | | |
| 7.7 | Cover preview modal (click on 📷) | | |
| 7.8 | Closing cover modal (click on X or background) | | |
| 7.9 | Background cover download (cover_downloaded = true) | | |
| 7.10 | 404 if cover not found | | |

---

## 8. Source Management ("Sources" tab)

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 8.1 | Displaying source list | | |
| 8.2 | Source type badge (local, hdd, ssd, dvd, nas, network, cloud) | | |
| 8.3 | Availability status (Available/Unavailable/Archive) | | |
| 8.4 | Number of books in source | | |
| 8.5 | Adding a new source | | |
| 8.6 | Folder selection via 📂 button | | |
| 8.7 | Auto-fill name from folder name | | |
| 8.8 | Editing source (name, path, type, status) | | |
| 8.9 | Deleting source with confirmation | | |
| 8.10 | Cascading deletion of books when deleting a source | | |
| 8.11 | Statistics update after add/delete | | |

---

## 9. Source Scanning

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 9.1 | "Scan" button on source card | | |
| 9.2 | Confirmation modal before scanning | | |
| 9.3 | SSE connection (/api/sources/{id}/scan-stream) | | |
| 9.4 | Scan progress bar (0→100%) | | |
| 9.5 | Displaying processed / imported / confirmed counts | | |
| 9.6 | Displaying covers found | | |
| 9.7 | Displaying missing books | | |
| 9.8 | Current file being processed | | |
| 9.9 | Scan duration | | |
| 9.10 | `complete` event — "Scan complete!" status | | |
| 9.11 | "Close" button after completion | | |
| 9.12 | Source list and statistics update after scan | | |
| 9.13 | Error handling (invalid source_id, path does not exist) | | |
| 9.14 | Confirming existing books without overwrite (confirmed) | | |
| 9.15 | Importing new books with is_new_arrival=1 flag | | |
| 9.16 | Marking missing books as is_available=0 | | |
| 9.17 | Determining categories by folder names | | |
| 9.18 | Handling .part1.rar — main file only, extra_files = [.part2.rar, ...] | | |
| 9.19 | Handling .7z.001 — main file only, skip .7z.002, .7z.003... | | |
| 9.20 | Skip .z01, .z02 (archive volumes) | | |
| 9.21 | Parsing .json metadata (priority over .txt) | | |
| 9.22 | Parsing .txt metadata (KOI8-R, CP1251, CP866) | | |
| 9.23 | Cover with double extension (bookname.rar.jpg) | | |
| 9.24 | Reset is_new_arrival older than 7 days | | |
| 9.25 | Updating total_size and last_scanned | | |

---

## 10. Source Transfer

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 10.1 | Opening transfer modal (Tools tab) | | |
| 10.2 | Selecting source from dropdown | | |
| 10.3 | Loading information (path, books, size) | | |
| 10.4 | "Browse" button — select target folder | | |
| 10.5 | Transfer confirmation (confirm modal) | | |
| 10.6 | Transfer progress bar | | |
| 10.7 | Copying book files (.pdf, .djvu, .rar...) | | |
| 10.8 | Copying covers | | |
| 10.9 | Copying .json and .txt metadata | | |
| 10.10 | Copying multi-part files (extra_files) | | |
| 10.11 | Deleting originals after successful copy | | |
| 10.12 | Creating new source (new source_id) | | |
| 10.13 | Updating paths in DB | | |
| 10.14 | Deleting old source from DB | | |
| 10.15 | Deleting empty folders after transfer | | |
| 10.16 | Conflict handling (file already exists — skip) | | |
| 10.17 | Error report (errors_count) | | |
| 10.18 | Free space check | | |
| 10.19 | Closing modal after success | | |

---

## 11. Anomaly Detection

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 11.1 | Opening anomaly modal (Tools tab) | | |
| 11.2 | Loading source list | | |
| 11.3 | Launching anomaly scan | | |
| 11.4 | Detecting unlisted supported files (unlisted_supported) | | |
| 11.5 | Detecting metadata without book (metadata_orphan) | | |
| 11.6 | Detecting double-extension metadata (double_ext_metadata) | | |
| 11.7 | Detecting archive fragments (multi_part_orphan) | | |
| 11.8 | Detecting Download Master files (.dusd) | | |
| 11.9 | Detecting covers without book (orphan_cover) | | |
| 11.10 | Detecting unknown file types (unknown_type) | | |
| 11.11 | Detecting empty folders | | |
| 11.12 | Summary by anomaly type (colored badges) | | |
| 11.13 | Anomaly table with type, path, size | | |
| 11.14 | "No anomalies found" message for clean source | | |

---

## 12. Tools (tab)

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 12.1 | "Settings" button | | |
| 12.2 | Displaying current library path | | |
| 12.3 | Changing path ("Change folder" button) | | |
| 12.4 | Saving path to config.py | | |
| 12.5 | Server restart after path change | | |
| 12.6 | Audit log toggle (on/off) | | |
| 12.7 | Saving audit state to config.py | | |
| 12.8 | Server restart after audit toggle | | |
| 12.9 | "Open audit.log" button (only when audit is enabled) | | |
| 12.10 | Library initialization (full reset) | | |
| 12.11 | Initialization confirmation (double confirm) | | |
| 12.12 | After initialization — DB cleanup and reload | | |
| 12.13 | "Clean up database" tile (delete unavailable books) | | |
| 12.14 | "Erase database" tile | | |
| 12.15 | "Transfer source" tile | | |
| 12.16 | "Log" tile | | |
| 12.17 | "Anomaly detection" tile | | |

---

## 13. Log Viewer

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 13.1 | Opening log modal | | |
| 13.2 | Switching between app.log and audit.log | | |
| 13.3 | Selecting line count (100/200/500/1000) | | |
| 13.4 | "Refresh" button | | |
| 13.5 | Auto-refresh (10 seconds) | | |
| 13.6 | Auto-scroll (on/off) | | |
| 13.7 | Color highlighting: ERROR=red, WARNING=orange, INFO=yellow | | |
| 13.8 | Closing modal — stops auto-refresh | | |

---

## 14. Opening Book File

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 14.1 | POST /api/books/{id}/open — open file with system application | | |
| 14.2 | File existence check (404 if missing) | | |
| 14.3 | File size consistency check (update on mismatch) | | |
| 14.4 | Warning if file size has changed | | |
| 14.5 | "File unavailable" button disabled for is_available=0 | | |
| 14.6 | Empty file_path — 400 Bad Request | | |

---

## 15. API Endpoints (in-depth)

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 15.1 | GET /api/health — server responds | | |
| 15.2 | GET /api/stats — correct counters | | |
| 15.3 | GET /api/categories — category list with hierarchy | | |
| 15.4 | GET /api/books?limit=&offset= — pagination | | |
| 15.5 | GET /api/books/{id} — book details | | |
| 15.6 | GET /api/books/{id} — 404 for non-existent | | |
| 15.7 | PUT /api/books/{id} — update with export + move | | |
| 15.8 | DELETE /api/sources/{id} — cascading delete + response with books_deleted | | |
| 15.9 | POST /api/sources/{id}/scan — returns scanned/imported/confirmed/covers_found/missing | | |
| 15.10 | POST /api/setup/initialize — delete everything + reset FTS | | |
| 15.11 | GET /api/cover?path=... — cover proxy | | |
| 15.12 | POST /api/books/cleanup — delete unavailable books | | |

---

## 16. Audit Log

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 16.1 | Audit is written when AUDIT_ENABLED=true | | |
| 16.2 | Audit is NOT written when AUDIT_ENABLED=false | | |
| 16.3 | Event: source_scan_start (params: source_id, name, path, mode) | | |
| 16.4 | Event: source_scan_complete (scanned, imported, confirmed, covers_found, missing, missing_books) | | |
| 16.5 | Event: source_created (name, type, path, volume_label, catalog_id) | | |
| 16.6 | Event: source_updated (source_id, name, changes) | | |
| 16.7 | Event: source_deleted (source_id, name, books_deleted) | | |
| 16.8 | Event: source_transferred (old_path, target_path, transferred_count, errors) | | |
| 16.9 | Event: book_updated (book_id, title, changes) | | |
| 16.10 | Event: book_exported (book_id, export_path) | | |
| 16.11 | Event: book_files_moved (book_id, title, old_path, new_path) | | |
| 16.12 | Event: code_lookup (code, detected_type, found) | | |
| 16.13 | Event: lookup_metadata_saved (book_id, lookup_source, lookup_code) | | |
| 16.14 | Event: cover_downloaded (book_id, cover_url, status/error) | | |
| 16.15 | Event: library_initialized (books_deleted, sources_deleted, categories_deleted) | | |
| 16.16 | Event: audit_toggled (enabled, previous) | | |
| 16.17 | Event: file_size_updated (book_id, old_size, new_size) | | |
| 16.18 | Event: cleanup_unavailable (deleted_count) | | |

---

## 17. Edge Cases

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 17.1 | Empty library (0 books, 0 sources) | | |
| 17.2 | Source without books — delete empty | | |
| 17.3 | Very long book titles (200+ characters) | | |
| 17.4 | Unicode in metadata (Cyrillic, Japanese, Arabic) | | |
| 17.5 | Book file with path > 260 characters (Windows MAX_PATH) | | |
| 17.6 | Book file manually deleted — is_available=0 | | |
| 17.7 | Two scans of the same source simultaneously | | |
| 17.8 | SSE connection loss during scan | | |
| 17.9 | Server restarted during book editing | | |
| 17.10 | Adding source with an already existing path (duplicate) | | |
| 17.11 | Editing book without changes (just "Save") | | |
| 17.12 | Transferring source to the same folder (where it already is) | | |
| 17.13 | Insufficient disk space during transfer | | |
| 17.14 | Missing file when opening book (404) | | |
| 17.15 | Initializing DB followed by auto-import | | |
| 17.16 | Scanning a folder without books (empty) | | |
| 17.17 | Scanning with 10+ nested folder levels | | |
| 17.18 | Files starting with dot (.hidden_file.pdf) — should be skipped | | |
| 17.19 | Metadata in KOI8-R with Cyrillic | | |
| 17.20 | Metadata in CP1251 with Cyrillic | | |
| 17.21 | JSON metadata with null fields | | |
| 17.22 | Missing_books: list of books marked is_available=0 | | |

---

## 18. Interface (UI/UX)

| # | Step | Status | What's wrong / Expected |
|---|------|--------|-------------------------|
| 18.1 | Responsiveness: 1920px screen width | | |
| 18.2 | Responsiveness: 1366px screen width | | |
| 18.3 | Responsiveness: 1024px screen width | | |
| 18.4 | Responsiveness: 768px screen width (tablet) | | |
| 18.5 | Modals: dark background, centered | | |
| 18.6 | Closing modals via × button or Cancel | | |
| 18.7 | Notifications (showNotification) — pop up top-right, disappear | | |
| 18.8 | Tab switching (Catalog/Sources/Tools) | | |
| 18.9 | Tool tab tiles: icons + labels | | |
| 18.10 | Color indication of source status | | |
| 18.11 | Enter in search field — triggers search | | |

---

## Summary

| Category | Total tests | ✅ | ❌ | ⚠️ | ➖ |
|----------|-------------|---|---|----|----|
| 1. Initial Launch | 11 | | | | |
| 2. Main Page | 12 | | | | |
| 3. Filtering and Sorting | 11 | | | | |
| 4. Search | 11 | | | | |
| 5. Book Editing | 11 | | | | |
| 6. Code Lookup | 13 | | | | |
| 7. Covers | 10 | | | | |
| 8. Source Management | 11 | | | | |
| 9. Scanning | 25 | | | | |
| 10. Source Transfer | 19 | | | | |
| 11. Anomaly Detection | 14 | | | | |
| 12. Tools | 17 | | | | |
| 13. Log Viewer | 8 | | | | |
| 14. Opening File | 6 | | | | |
| 15. API Endpoints | 12 | | | | |
| 16. Audit Log | 18 | | | | |
| 17. Edge Cases | 22 | | | | |
| 18. UI/UX | 11 | | | | |
| **TOTAL** | **242** | | | | |

---

## Notes and Suggestions

| # | Section | Description |
|---|---------|-------------|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
