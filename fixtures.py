"""Hand-authored fictional Chicago rentals; no real listings or reviews."""


def listing(identifier, name, rent, extra, complete, cats, evidence):
    source_id = identifier + "-DETAILS"
    facts = f"演示虚构：两卧室，养猫规则={cats}，月租={rent}美分，额外月费={extra}美分。"
    return {"id": identifier, "name": name, "synthetic": True, "domain": "rental",
            "attributes": {"bedrooms": 2, "cats_allowed": cats},
            "attribute_sources": {"bedrooms": source_id, "cats_allowed": source_id},
            "monthly_costs": {"complete": complete, "items": [
                {"label": "rent", "amount_cents": rent, "source_id": source_id},
                {"label": "mandatory_monthly_fees", "amount_cents": extra, "source_id": source_id}]},
            "sources": {source_id: {"text": facts, "date": "2026-10-20", "type": "synthetic_listing"},
                        **{identifier + f"-R{i}": {"text": text, "date": date, "type": "synthetic_resident_note"}
                           for i, (topic, direction, text, date, scope) in enumerate(evidence)}},
            "evidence": [{"topic": topic, "direction": direction, "quote": text,
                          "source_id": identifier + f"-R{i}", "conditions": scope}
                         for i, (topic, direction, text, date, scope) in enumerate(evidence)]}


CANDIDATES = [
    listing("A", "梧桐公寓（虚构）", 320000, 20000, True, True, [
        ("video_calls", "support", "工作日视频会议没有掉线。", "2026-10-15", "仅为一位住客的工作日体验；没有测速"),
        ("quiet", "risk", "周五晚上听到楼下音乐。", "2026-10-15", "周五夜间，音量未知"),
        ("quiet", "support", "周一到周四晚上很安静。", "2026-10-22", "未住周末"),
    ]),
    listing("B", "河岸公寓（虚构）", 335000, 0, True, False, []),
    listing("C", "花园公寓（虚构）", 310000, None, False, True, [
        ("quiet", "support", "这次入住夜间很安静。", "2026-10-19", "一次主观经历，非当前保证"),
    ]),
    listing("D", "湖畔公寓（虚构）", 330000, 10000, True, True, [
        ("quiet", "support", "这次入住夜间很安静。", "2026-10-20", "一次主观经历"),
        ("video_calls", "risk", "两次视频会议掉线，改用手机热点。", "2026-10-20", "未核实原因或后续修复"),
    ]),
]

REMOTE_WORK = {"hard": [("bedrooms", "gte", 2), ("cats_allowed", "eq", True)],
               "monthly_budget_cents": 350000,
               "preferences": {"video_calls": 3, "quiet": 2}}
VACATION = {**REMOTE_WORK, "preferences": {"quiet": 2}}
