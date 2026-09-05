---
target: homepage
total_score: 19
max_score: 32
na_heuristics: 7,10
p0_count: 0
p1_count: 2
target_identity: "file:C:\\Users\\Josh\\Downloads\\2026Q1\\106L-4\\Proj\\repo\\LigtasPH\\templates\\public\\home.html"
target_fingerprint: "sha256:c486f1ee84772ce26521a396e4b8b9dfa3f59a276fe118512307f230894bcdb4"
target_path: "C:\\Users\\Josh\\Downloads\\2026Q1\\106L-4\\Proj\\repo\\LigtasPH\\templates\\public\\home.html"
timestamp: 2026-09-05T10-57-42Z
slug: templates-public-home-html
---
# Critique re-run — templates/public/home.html (after refinement)

Method: dual-agent (design re-review + detect rescan, isolated). No browser tool.
Heuristics (7, 10 n/a): 1:2 silent async loads · 2:3 PHT good, hero labels plain · 3:3 skip/esc/confirm good · 4:2 legend 3-state vs 4-state dots · 5:1 hero fail-open, dismiss-all destructive · 6:3 saved prefs reused, dead stats · 8:3 crowded but ordered · 9:2 weather links out, no retry. Total 19/32 (59%, Acceptable; up from ~13/32).
Cognitive load: 4/8 fail (was 6/8). Detector: 0 findings (was 0 + 1 warning, warning gone).
Fixed this round: hero city+locate deep links with ?city= hydration on map/directory; splash 400ms + Skip; Unknown stat card; critical never clamped; PHT meta; tel: links; weather saved-location + loading/error; banner dot replaces stripe; dismiss-all confirm; Esc bell.
Remaining: P1 wrong-city weather label; P2 hero fail-open; P3 dead stats/preview sample; P4 color-only severity. Follow-ups applied: city-param weather + honest default label; Find disabled until loaded with validation + offline msg; clickable stat cards + preview count + Unknown legend + directory ?status=; severity text chip + alert role + dot labels.
Personas: Jordan (stacked hero controls, abrupt locate nav), Riley (aria-expanded, dialog labelling), Casey (network-hard deps, no coord deep link).
