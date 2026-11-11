"""조달청 나라장터쇼핑몰 품목 등록 내역(원본 CSV, data/raw/)에서 테스트 품목만 뽑아 fixture로 저장한다.

원본: 조달데이터허브 > 나라장터쇼핑몰 품목 등록 내역 (대분류 '사무/교육/가구', 현재 등록된 품목만)
출력: data/fixtures/procurement_prices.csv (업체명·사업자번호는 제외하고 업체 구분용 해시만 남김)

실행: python scripts/extract_procurement.py
"""
import csv
import hashlib
import statistics as st
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RAW = next((BASE / "data" / "raw").glob("*나라장터쇼핑몰 품목 등록 내역*.csv"))
OUT = BASE / "data" / "fixtures" / "procurement_prices.csv"

# (item_id, 세부품명, 규격 문자열) — 규격은 품목명에서 '세부품명, 제조사, 모델' 뒤에 오는 부분과 정확히 일치해야 한다
GROUPS = [
    ("I01", "프린트및복사용지", "일반, A4, 80g/㎡, 2500매/상자"),
    ("I02", "프린트및복사용지", "일반, A4, 80g/㎡, 2500매(250매×10권)/상자"),
    ("I03", "중질지", "A4, 70g/㎡, 2500매/상자"),
    ("I04", "작업용의자", "595×600×895mm"),
    ("I05", "캐비닛", "800×400×800mm"),
    ("I06", "회의용탁자", "1800×900×720mm, 사각형"),
    ("I07", "이동형파일서랍", "400×800×720mm, 3단"),
    ("I08", "사무실칸막이", "1200×30×1160mm"),
    ("I09", "문서세단기", "270mm"),
    ("I10", "전자복사기", "흑백30cpm"),
]
SPARSE_ITEMS = ["라벨용지"]  # 같은 규격 표본이 적은 품목(판단 불가 케이스) — 전체 행을 저장


def read_rows():
    with open(RAW, encoding="utf-16", newline="") as f:
        for _ in range(40):  # 검색조건 머리말
            next(f)
        yield from csv.DictReader(f, delimiter="\t")


def iqr_filter(prices):
    if len(prices) < 4:
        return prices
    q = st.quantiles(prices, n=4)
    lo, hi = q[0] - 1.5 * (q[2] - q[0]), q[2] + 1.5 * (q[2] - q[0])
    return [p for p in prices if lo <= p <= hi]


def main():
    wanted = {(g[1], g[2]): g[0] for g in GROUPS}
    out = []
    for r in read_rows():
        parts = [p.strip() for p in (r["품목명"] or "").split(",")]
        spec = ", ".join(parts[3:])
        key = (r["세부품명"], spec)
        item_id = wanted.get(key) or ("SPARSE" if r["세부품명"] in SPARSE_ITEMS else None)
        if not item_id:
            continue
        out.append({
            "item_id": item_id,
            "세부품명": r["세부품명"],
            "모델": parts[2] if len(parts) > 2 else "",
            "규격": spec,
            "단가": r["단가"],
            "단위": r["단위"],
            "MAS여부": r["MAS여부"],
            "업체키": hashlib.sha1((r["업체사업자등록번호"] or "").encode()).hexdigest()[:8],
            "계약기간": r["계약기간"],
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    print(f"saved {len(out)} rows -> {OUT.relative_to(BASE)}")
    for item_id, name, spec in GROUPS + [("SPARSE", "라벨용지", "(전체)")]:
        rows = [o for o in out if o["item_id"] == item_id]
        prices = [float(o["단가"]) for o in rows]
        kept = iqr_filter(prices)
        med = st.median(kept) if kept else None
        print(f"{item_id} {name} | {spec} | rows {len(rows)} vendors {len({o['업체키'] for o in rows})} "
              f"| raw median {st.median(prices) if prices else None} | IQR kept {len(kept)} median {med}")


if __name__ == "__main__":
    main()
