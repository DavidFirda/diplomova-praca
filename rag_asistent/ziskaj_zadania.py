"""Stiahne homeworkXX.md za 2024 a 2025 z repozitara predmetu (stav na konci semestra)."""
import requests

from config import DATA

REPO = "https://raw.githubusercontent.com/ianmagyar/introduction-to-python"
SNAPSHOTS = {
    2024: ("59d89393e99e389e75446a4f6a2cc032d426b8d5", "assignments/homeworks", ["H06_example.pdf"]),
    2025: ("050c90c0f8dbb6c1d355046e32575d92c779aba0", "homeworks", ["H07_example.pdf"]),
}


def main():
    for year, (sha, folder, extra) in SNAPSHOTS.items():
        out = DATA / "zadania" / str(year)
        out.mkdir(parents=True, exist_ok=True)
        names = [f"homework{i:02d}.md" for i in range(1, 11)] + extra
        for name in names:
            r = requests.get(f"{REPO}/{sha}/{folder}/{name}", timeout=60)
            r.raise_for_status()
            (out / name).write_bytes(r.content)
        print(f"{year}: {len(names)} súborov -> {out}")


if __name__ == "__main__":
    main()
