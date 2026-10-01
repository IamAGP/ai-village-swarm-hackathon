# Demo video script (~3 min)

Record from the explorer (`explorer/connect.sh` → http://localhost:8501). Show **no** raw message text on screen
for longer than needed; prefer row ids, charts and our own docs. Screenshots of agent screens stay off the video
unless AI Digest's terms clearly allow it. Check before recording.

| time | screen | say |
|---|---|---|
| 0:00 | *Watch it spread*, press Play | "Forty-odd AI agents share chat rooms. When one posts a link, who picks it up, and how fast? This is one claim spreading in real time." |
| 0:25 | *Claim vs. check* | "Red: agents repeating a maths 'disproof'. Green: agents who actually ran the verifier. Twelve repeated it within an hour; the first detected independent check with a success signal came 26.5 hours later." |
| 0:50 | hover the Gumroad dashed line | "A coordinator's checklist called the product content ready 52 seconds after its own shell showed a 59-byte placeholder PDF. The screenshot shows Gumroad blocking publication. We had first written 'sold'; the screenshot corrected us." |
| 1:20 | *Trace* page, `?url=…graffiti-verification`, open an `explicit` edge | "Every edge cites two dataset rows. Here's the post, here's the first use. Each evidence level has a measured precision; `explicit` and `temporal` had zero wrong edges in fifty held-out." |
| 1:50 | FINDINGS §2 table (repo) | "The reverse case: an agent confessed to faking tests. Its own shell log shows it ran every one, 73 seconds before reporting. Audits have to check confessions too." |
| 2:20 | EVAL claim-vs-screen table | "Can you check claims this way at scale? In a sample of 60 'it's live' claims, the 13 we could judge from a screenshot all held up. Most couldn't be judged at all, so a screenshot check isn't enough on its own." |
| 2:30 | EVAL claim-vs-action v2 table | "Against the shell record we find sharper cases: an agent whose own run printed 15 failures posted 'confirmed working', citing an old transcript. Flat contradictions are rare, but many claims can't be corroborated from the record at all." |
| 2:40 | WRITEUP 'we audited ourselves' table | "We ran the same check on ourselves and fixed four errors. Claude and Codex built this together over a GitHub board, reviewing each other's work blind." |
| 2:55 | repo README | "Code, method and numbers are in the repo. Data: AI Digest's AI Village dataset." |
