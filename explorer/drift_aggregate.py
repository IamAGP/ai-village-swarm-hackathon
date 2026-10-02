"""Merge first-text drift labels + 72 h per-message labels into one per-agent stance timeline for the ripple view."""
import json
PRI = {"neutral": 0, "hedges": 1, "repeats": 2, "checks": 3, "flags": 4, "amplifies": 5, "original": 6}
first = json.load(open("/data/findings/belief_drift_graffiti.json"))
items = {}
for k in (0, 1):
    for l in open(f"/work/drift72_{k}/items.jsonl"):
        it = json.loads(l); items[it["msg_id"]] = it
agents, missing = {}, 0
for aid, d in first["agents"].items():
    agents[aid] = {"timeline": [{"at": d["at"], "stance": d["stance"], "gist": d["gist"], "cue": d["cue"], "row": d["row"], "src": "first text"}]}
for k in (0, 1):
    for l in open(f"/work/drift72_{k}/drift.jsonl"):
        try:
            d = json.loads(l)
        except json.JSONDecodeError:
            continue
        it = items.get(d.get("msg_id"))
        if not it:
            missing += 1; continue
        aid = "agent:" + it["agent_id"]
        agents.setdefault(aid, {"timeline": []})["timeline"].append(
            {"at": it["at"], "stance": d["stance"], "gist": d.get("gist", ""), "cue": d.get("cue", ""), "row": it["msg_id"], "src": "chat"})
from collections import Counter
peak = Counter()
for aid, a in agents.items():
    a["timeline"].sort(key=lambda e: e["at"])
    best = max(a["timeline"], key=lambda e: (PRI.get(e["stance"], 0), -len(e["at"])))
    a["peak"] = best; peak[best["stance"]] += 1
    a["n_msgs"] = sum(1 for e in a["timeline"] if e["src"] == "chat")
json.dump({"seed": first["seed"], "basis": "first text + every chat message in the first 72 h mentioning the disproofs; headless Claude labels; peak = most escalated stance",
           "agents": agents}, open("/data/findings/belief_drift_graffiti_72h.json", "w"), indent=1)
print("agents", len(agents), "unmatched labels", missing, "peak stances", dict(peak))
