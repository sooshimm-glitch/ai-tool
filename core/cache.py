#!/usr/bin/env python3
"""
cache_fix_patch.py
------------------
competitor_finder.py 와 industry_classifier.py 의
  if cached:  →  if cached is not None:
패치를 적용합니다.

사용법:
  python3 cache_fix_patch.py <repo_root>

예시:
  python3 cache_fix_patch.py /path/to/ai-tool
"""

import sys
import re
from pathlib import Path


PATCHES = {
    "core/competitor_finder.py": [
        (
            # 원본
            "    if use_cache:\n"
            "        cached = cache.get(cache_key)\n"
            "        if cached:\n"
            "            logger.info(f\"Cache HIT: competitors({domain})\")\n"
            "            return [Competitor(**c) for c in cached]",
            # 수정
            "    if use_cache:\n"
            "        cached = cache.get(cache_key)\n"
            "        if cached is not None:  # [FIX] None 명시 비교 — 빈 리스트도 유효한 캐시값\n"
            "            logger.info(f\"Cache HIT: competitors({domain})\")\n"
            "            return [Competitor(**c) for c in cached]",
        ),
    ],
    "core/industry_classifier.py": [
        (
            # 원본
            "    if use_cache:\n"
            "        cached = get_cache().get(cache_key)\n"
            "        if cached:\n"
            "            logger.info(f\"Cache HIT: classify_industry({domain})\")\n"
            "            return BusinessInfo.from_dict(cached)",
            # 수정
            "    if use_cache:\n"
            "        cached = get_cache().get(cache_key)\n"
            "        if cached is not None:  # [FIX] None 명시 비교 — 빈 dict도 유효한 캐시값\n"
            "            logger.info(f\"Cache HIT: classify_industry({domain})\")\n"
            "            return BusinessInfo.from_dict(cached)",
        ),
    ],
}


def apply_patches(repo_root: Path):
    success = []
    failed = []

    for rel_path, replacements in PATCHES.items():
        fpath = repo_root / rel_path
        if not fpath.exists():
            print(f"[SKIP]  {rel_path} — 파일 없음")
            failed.append(rel_path)
            continue

        src = fpath.read_text(encoding="utf-8")
        patched = src

        for old, new in replacements:
            if old in patched:
                patched = patched.replace(old, new, 1)
                print(f"[OK]    {rel_path} — 패치 적용됨")
                success.append(rel_path)
            else:
                # 이미 수정됐거나 구조가 다름
                if "is not None" in patched:
                    print(f"[SKIP]  {rel_path} — 이미 수정된 것으로 보임")
                else:
                    print(f"[WARN]  {rel_path} — 패턴 불일치, 수동 확인 필요")
                    failed.append(rel_path)

        if patched != src:
            fpath.write_text(patched, encoding="utf-8")

    print(f"\n결과: 성공 {len(success)}개 / 실패 {len(failed)}개")
    if failed:
        print("수동 수정 필요:", failed)
        print("\n수동 수정 방법 (두 파일 모두 동일):")
        print("  if cached:          # 이 줄을")
        print("  if cached is not None:  # 이렇게 변경")


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    apply_patches(root)
