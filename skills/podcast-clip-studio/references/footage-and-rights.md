# Footage and rights

## The source clips
- Clip the rightsholder's own channels when you can. A campaign brief usually names them; if it does not, ask.
- Download only the window you need, after the user agrees.

## Cutaway footage
- Official highlight reels (fight broadcasters, league channels, the event's own uploads) look best and are easiest to date. Search with `yt-dlp "ytsearch8:query"` and print `%(duration_string)s | %(view_count)s | %(channel)s | %(title)s`.
- Pull a low-resolution review copy first (`yt-dlp -f "bv*[height<=360]+ba/b[height<=360]"`), look at it on a labelled contact sheet (`scripts/sheet.py`), choose the seconds, then download only that section in HD.
- **Do not trust a title.** Confirm in the frames that it shows what you need.
- Third-party broadcast footage can trigger Content ID or a copyright claim. Put a "Cutaway footage" line with the source in every clip's notes and description, and tell the user to check with the client.
- Footage from the same episode (stills, B-roll the show itself cut in) carries no extra risk.

## Real people and images
- Do not generate an AI likeness of a real person to put in a thumbnail or a cutaway. Use real frames.
- Thumbnails: `scripts/make_thumb.py` builds 9:16 and 16:9 covers from a real frame, with a size cap on the text so the face stays clear.

## Names and channels
- A fan channel should say so in its description and never use "official". Do not use the person's face, logo or the event company's branding as the channel identity.
- YouTube can limit monetisation for channels that mostly repost others' footage. Edits and commentary help but do not guarantee anything.

## Sounds the user asks for
- If they point you at a specific real sound (for example a keyboard recording), analyse it, cut clean samples from it, and say where they came from. Check the licence of the source: a video on the standard YouTube licence is not Creative Commons. CC0 libraries (for example BigSoundBank) are the safe alternative; their pages may block plain `curl`, so use a normal browser to download.
