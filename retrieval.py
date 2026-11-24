"""Local SQLite lexical retrieval baseline, with candidate isolation."""
import json
import re
import sqlite3

TERMS = {
    "quiet": ["quiet", "noise", "noisy", "construction", "安静", "噪声", "音乐", "施工"],
    "video_calls": ["internet", "wifi", "wi-fi", "network", "网络", "会议", "掉线"],
    "workspace": ["desk", "office", "workspace", "书桌", "办公", "吧台"],
    "parking": ["parking", "garage", "停车", "车库"],
    "laundry": ["laundry", "washer", "dryer", "洗衣"],
}


class EvidenceIndex:
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS sources (candidate TEXT, id TEXT, data TEXT, PRIMARY KEY(candidate,id))")

    def close(self):
        self.db.close()

    def replace(self, candidates):
        records = [(c["id"], sid, json.dumps(source, ensure_ascii=False))
                   for c in candidates for sid, source in c["sources"].items()]
        with self.db:
            self.db.execute("DELETE FROM sources")
            self.db.executemany("INSERT INTO sources VALUES (?,?,?)", records)

    def search(self, candidate_ids, topic, limit=6):
        if topic not in TERMS or limit < 1:
            raise ValueError("Unsupported topic or limit")
        if not candidate_ids:
            return []
        placeholders = ",".join("?" for _ in candidate_ids)
        records = self.db.execute(f"SELECT candidate,id,data FROM sources WHERE candidate IN ({placeholders})", list(candidate_ids))
        hits = []
        for cid, sid, raw in records:
            source = json.loads(raw)
            text = source["text"].lower()
            # No sentiment filter: both favorable and unfavorable matches enter.
            score = sum(bool(re.search(r"\b" + re.escape(term) + r"\b", text))
                        if term.isascii() else term in text for term in TERMS[topic])
            if score:
                hits.append({"candidate_id": cid, "source_id": sid, "source": source, "retrieval_score": score})
        return sorted(hits, key=lambda h: (-h["retrieval_score"], h["candidate_id"], h["source_id"]))[:limit]
