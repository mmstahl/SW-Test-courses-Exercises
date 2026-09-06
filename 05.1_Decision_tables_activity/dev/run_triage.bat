@echo off
python triage_rules.py  H	L	Y
python triage_rules.py  L	H	N  --noheader
python triage_rules.py  M	H	N  --noheader
python triage_rules.py  H	L	N  --noheader
python triage_rules.py  H	H	N  --noheader
python triage_rules.py  L	H	Y  --noheader
python triage_rules.py  M	L	Y  --noheader
python triage_rules.py  L	L	Y  --noheader
python triage_rules.py  L	L	N  --noheader
python triage_rules.py  M	H	Y  --noheader
python triage_rules.py  M	L	N  --noheader
python triage_rules.py  H	H	Y  --noheader
