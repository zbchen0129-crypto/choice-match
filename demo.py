import json

from engine import recommend
from fixtures import CANDIDATES, REMOTE_WORK, VACATION
from rental import domain_checks


if __name__ == "__main__":
    print("所有候选、费用、评论与日期均为人工虚构；规则分不是匹配概率。")
    for label, requirements in [("远程办公", REMOTE_WORK), ("休假", VACATION)]:
        print(json.dumps({"scenario": label, "results": recommend(CANDIDATES, requirements, domain_checks)},
                         ensure_ascii=False, indent=2))
