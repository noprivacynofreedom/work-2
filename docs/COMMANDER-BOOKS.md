# Atlas Commander book tools

Atlas-Commander exposes five separate MCP tools for Project Gutenberg catalog entries:

- `book_search` searches by title, author, or topic.
- `book_list` lists entries with optional topic and language filters.
- `book_view` returns metadata, formats, and the official browser viewer URL.
- `book_read` returns a plain-text excerpt, up to 12,000 characters.
- `book_download` saves one TXT or EPUB file under `downloads/books` in the Commander project root.

The catalog service is Gutendex, which indexes Project Gutenberg metadata. Tools only accept entries that the catalog marks `copyright: false`. This is not a copyright determination for every country; check local rules and the book's license. Project Gutenberg itself recommends machine-readable catalog data for automation and warns that access rights can vary by country.

Network access is limited to HTTPS requests to `gutendex.com` and Project Gutenberg hosts. Redirects to other hosts fail. Downloads are limited to 20 MB, and existing files are never replaced. Set `ATLAS_COMMANDER_OFFLINE=1` to hide and block all network book tools.

The viewer URL opens Project Gutenberg's own reader in a browser. Book downloads require an explicit `book_download` tool call. This connector does not handle Z-Library credentials or automate its website. If Z-Library offers an official API for the user's account and requested books, add it as a separate provider after reviewing its published API and permitted-use rules.
