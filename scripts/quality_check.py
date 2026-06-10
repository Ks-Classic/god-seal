
import json

checks = [
    ("kohata_yasuhiko_chart.html", "HTML output"),
    ("data/ingod_meanings.json", "InGod meanings"),
]

ok = 0
for f, name in checks:
    try:
        if f.endswith(".html"):
            open(f).read()
        else:
            json.load(open(f))
        ok += 1
    except:
        print(f"FAIL: {name}")

print(f"ok: {ok}/{len(checks)} checks")
