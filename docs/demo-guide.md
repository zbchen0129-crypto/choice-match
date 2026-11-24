# Three-minute portfolio walkthrough

Start `python3 scripts/preview_lab.py` and open http://127.0.0.1:8789/. No model key or database is needed. All properties and reviews in this walkthrough are fictional. The UI labels below match the Chinese interface.

**0:00–0:30 — State the problem.**
“Rental search has structured constraints and messy evidence. I built a prototype that keeps hard constraints, missing information, and conflicting reviews separate.” Show two bedrooms, cats allowed, and the $3,500 monthly budget.

**0:30–1:10 — Explain the three buckets.**
The default remote-work result has A and D under 已知满足, C under 待核实 because fees are incomplete, and B under 已排除 because cats are not allowed. ‘Eligible’ refers to the listed hard conditions; it is not a claim of overall suitability. Point out A's mixed quiet evidence and D's dropped-call risk.

**1:10–2:00 — Inspect and act on evidence.**
Open D's 查看证据与缺口. Explain the quote, date, and unresolved cause/repair condition. In 我的排除决定, enter “不接受已有会议掉线记录,” choose D-R1, and give a reason. Confirm. Eligible falls from two to one; excluded rises from one to two. Open D under 已排除 to show the reason and 撤销我的排除. Undo restores the original result. This is a user choice, not an automated factual certification.

**2:00–2:30 — Show uncertainty and user control.**
Visit 待核实 and explain why missing fees do not count as zero. Changing the original text clears prior decisions. JSON export preserves the current evidence and decision trace. Raw text alone does not change structured filters until requirements are parsed/confirmed or manually edited.

**2:30–3:00 — Show an honest experiment.**
Open 检索实验. Switch the fixed original-query weight choices and point out both improved scenario matching and lost risk evidence. This panel replays previously computed synthetic cases; changing it makes no API calls and does not change the workbench's production default.

Closing line: “The important engineering result was separating relevance from suitability and preserving failure evidence. More complex fusion did not reliably beat the simpler baseline, so I kept the unsuccessful experiments visible rather than claiming an accuracy win.”

Do not describe this as live Zillow/Redfin integration, a deployed service, human-validated recommendation quality, or a proven improvement in matching accuracy. If asked for live AI, explain that it is an optional paid path and that this repeatable demo uses fixed evidence.
