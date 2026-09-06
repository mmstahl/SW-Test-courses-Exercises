@echo off
python triage_rules.py  80   41         Y
python triage_rules.py  120  35         N  --noheader
python triage_rules.py  120  37         N  --noheader
python triage_rules.py  80   41         N  --noheader
python triage_rules.py  120  41         N  --noheader
python triage_rules.py  120  35         Y  --noheader
python triage_rules.py  80   37         Y  --noheader
python triage_rules.py  80   35         Y  --noheader
python triage_rules.py  80   35         N  --noheader
python triage_rules.py  120  37         Y  --noheader
python triage_rules.py  80   37         N  --noheader
python triage_rules.py  120  41         Y  --noheader