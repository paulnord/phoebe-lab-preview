import csv
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXAMPLES=ROOT/"site"/"examples"


def rows(name):
    with (EXAMPLES/name).open(newline="") as handle:
        return list(csv.reader(handle))


def test_published_observation_csvs_are_app_compatible_and_unmodified():
    contact=rows("observed-gsc3822-1056-johnson-v.csv")
    semi=rows("observed-sz-her-johnson-v.csv")
    assert contact[0]==["hjd","johnson_v_magnitude"] and len(contact)==272
    assert semi[0]==["hjd","differential_johnson_v_magnitude"] and len(semi)==438
    for table in (contact,semi):
        values=[[float(cell) for cell in row] for row in table[1:]]
        assert all(len(row)==2 and all(math.isfinite(value) for value in row) for row in values)
        assert all(row[0]>2 for row in values)  # the UI's automatic time-axis test
        assert "mag" in table[0][1]             # the UI's automatic magnitude test
    assert contact[1]==["2450495.49280","12.371"]
    assert contact[-1]==["2450500.78560","12.440"]
    assert semi[1]==["2454525.24769","0.183"]
    assert semi[-1]==["2454604.28266","0.060"]


def test_published_ephemerides_cover_both_orbits_without_phase_columns():
    for name,epoch,period in [
        ("observed-gsc3822-1056-johnson-v.csv",2450495.5212,0.30989069),
        ("observed-sz-her-johnson-v.csv",2454588.167997,0.8180837),
    ]:
        table=rows(name)
        phases=[((float(row[0])-epoch)/period)%1 for row in table[1:]]
        bins={int(phase*20)%20 for phase in phases}
        assert len(bins)>=18
        assert len({row[0] for row in table[1:]})==len(table)-1
    note=(EXAMPLES/"OBSERVATIONS.md").read_text()
    assert "publishes neither" in note
    assert "No phase column is stored" in note
    assert "No radial-velocity file is bundled" in note

