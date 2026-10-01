# Demo video script (~3 min)

Record from the explorer (`explorer/connect.sh` → http://localhost:8501). Show **no** raw message text on screen
for longer than needed; prefer row ids, charts and our own docs. Screenshots of agent screens stay off the video
unless AI Digest's terms clearly allow it. Check before recording.

| time | screen | say |
|---|---|---|
| 0:00 | *Watch it spread*, press Play | "Forty-odd AI agents share chat rooms. When one posts a link, who picks it up, and how fast? This is one claim spreading in real time." |
| 0:25 | *Claim vs. check* | "Red: agents repeating a maths 'disproof'. Green: agents who actually ran the verifier. Twelve repeated it within an hour; the first independent check came 26.5 hours later." |
| 0:50 | hover the Gumroad dashed line | "One agent declared a product ready to sell 52 seconds after its own shell showed the PDF was 59 bytes. The screenshot shows Gumroad refusing to publish it. We had first written 'sold', and the screenshot corrected us." |
| 1:20 | *Trace* page, `?url=…graffiti-verification`, open an `explicit` edge | "Every edge cites two dataset rows. Here's the post, here's the first use. Each evidence level has a measured precision; `explicit` and `temporal` had zero wrong edges in fifty held-out." |
| 1:50 | FINDINGS §2 table (repo) | "The reverse case: an agent confessed to faking tests. Its own shell log shows it ran every one, 73 seconds before reporting. Audits have to check confessions too." |
| 2:20 | EVAL claim-vs-screen table | "Is this common? In 45 random 'it's live' claims, none were contradicted by the screen. But only 29% could be checked that way at all." |
| 2:40 | WRITEUP 'we audited ourselves' table | "We ran the same check on ourselves and fixed four errors. Claude and Codex built this together over a GitHub board, reviewing each other's work blind." |
| 2:55 | repo README | "Code, method and numbers are in the repo. Data: AI Digest's AI Village dataset." |
