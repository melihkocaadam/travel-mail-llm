# training/make_slots_dataset.py

import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
LABELED_PATH = BASE_DIR / "data" / "train" / "labeled_emails.jsonl"
OUT_PATH = BASE_DIR / "data" / "train" / "finetune_slots_dataset.jsonl"


def best_requests_from_label(lbl: dict):
    reqs = lbl.get("requests") or []
    return [r for r in reqs if r.get("type") in ("flight", "hotel", "transfer")]


def make_slots_for_request(req: dict) -> str:
    """
    Tek bir flight/hotel/transfer request'ini düz slot formatına çevirir.
    Örnek:
    type=hotel; city=Berlin; check_in_exact=2025-11-25; adult=2; ...
    """
    t = req.get("type") or "unknown"
    parts = [f"type={t}"]

    if t == "flight" and req.get("flight"):
        f = req["flight"]
        parts.append(f"trip_type={f.get('trip_type') or 'null'}")

        pax = f.get("pax") or {}
        parts.append(f"adult={pax.get('adult', 0)}")
        parts.append(f"child={pax.get('child', 0)}")
        parts.append(f"infant={pax.get('infant', 0)}")

        legs = f.get("legs") or []
        # İlk 3 bacağı alalım
        for i, leg in enumerate(legs[:3], start=1):
            prefix = f"leg{i}_"
            parts.append(f"{prefix}from={leg.get('from') or 'null'}")
            parts.append(f"{prefix}to={leg.get('to') or 'null'}")

            d = (leg.get("date") or {})
            parts.append(f"{prefix}date_type={d.get('type') or 'null'}")
            parts.append(f"{prefix}date_exact={d.get('exact') or 'null'}")
            parts.append(f"{prefix}date_from={d.get('from') or 'null'}")
            parts.append(f"{prefix}date_to={d.get('to') or 'null'}")

            tm = (leg.get('time') or {})
            parts.append(f"{prefix}time_type={tm.get('type') or 'null'}")
            parts.append(f"{prefix}time_exact={tm.get('exact') or 'null'}")
            parts.append(f"{prefix}time_from={tm.get('from') or 'null'}")
            parts.append(f"{prefix}time_to={tm.get('to') or 'null'}")

    elif t == "hotel" and req.get("hotel"):
        h = req["hotel"]
        parts.append(f"city={h.get('city') or 'null'}")
        parts.append(f"area={h.get('area') or 'null'}")

        date = h.get("date") or {}
        ci = date.get("check_in") or {}
        co = date.get("check_out") or {}

        parts.append(f"check_in_type={ci.get('type') or 'null'}")
        parts.append(f"check_in_exact={ci.get('exact') or 'null'}")
        parts.append(f"check_out_type={co.get('type') or 'null'}")
        parts.append(f"check_out_exact={co.get('exact') or 'null'}")

        parts.append(f"nights={h.get('nights') or 0}")

        pax = h.get("pax") or {}
        parts.append(f"adult={pax.get('adult', 0)}")
        parts.append(f"child={pax.get('child', 0)}")

        parts.append(f"purpose={h.get('purpose') or 'null'}")
        parts.append(f"hotel_class={h.get('hotel_class') or 'null'}")

    elif t == "transfer" and req.get("transfer"):
        tr = req["transfer"]
        parts.append(f"direction={tr.get('direction') or 'null'}")
        parts.append(f"from={tr.get('from') or 'null'}")
        parts.append(f"to={tr.get('to') or 'null'}")

        d = tr.get("date") or {}
        parts.append(f"date_type={d.get('type') or 'null'}")
        parts.append(f"date_exact={d.get('exact') or 'null'}")
        parts.append(f"date_from={d.get('from') or 'null'}")
        parts.append(f"date_to={d.get('to') or 'null'}")

        tm = tr.get("time") or {}
        parts.append(f"time_type={tm.get('type') or 'null'}")
        parts.append(f"time_exact={tm.get('exact') or 'null'}")

        pax = tr.get("pax") or {}
        parts.append(f"adult={pax.get('adult', 0)}")
        parts.append(f"child={pax.get('child', 0)}")
        parts.append(f"infant={pax.get('infant', 0)}")

    # "key=value; key2=value2; ..." şeklinde birleştir
    return " ".join(f"{p};" for p in parts)


def main():
    assert LABELED_PATH.exists(), f"Labeled file not found: {LABELED_PATH}"
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    used = 0

    with LABELED_PATH.open("r", encoding="utf-8") as fin, OUT_PATH.open(
        "w", encoding="utf-8"
    ) as fout:
        for line in fin:
            total += 1
            rec = json.loads(line)

            # review_needed=True ise istersen atlayalım
            if rec.get("review_needed"):
                continue

            text = (rec.get("text") or "").strip()
            if not text:
                continue

            reqs = best_requests_from_label(rec.get("label") or {})
            if not reqs:
                continue

            slots_lines = []
            for idx, req in enumerate(reqs, start=1):
                slots = make_slots_for_request(req)
                slots_lines.append(f"REQUEST {idx}: {slots}")

            target = "\n".join(slots_lines)

            obj = {
                "input": text,
                "target": target,
            }
            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            used += 1

    print(f"Toplam kayıt: {total}, kullanılan (slot üretilen): {used}")
    print(f"Yazılan dataset: {OUT_PATH}")


if __name__ == "__main__":
    main()
