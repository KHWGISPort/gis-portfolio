# -*- coding: utf-8 -*-
"""
[Phase 5 - 임장 정리 1단계] 임장 사진을 순위별로 이름을 정리하고,
폭 1200px로 축소한 사본을 만든다 (원본은 그대로 보존).

원본: docs/fieldwork/{순위}위 ({n}).jpg  (예: "1위 (1).jpg")
사본: docs/fieldwork/photos/{순위:02d}_{장소명}_{n:02d}.jpg  (폭 1200px로 축소)

이미지 크기 조정에는 Pillow(PIL)를 사용한다 -- 새로 설치한 것이 아니라
matplotlib 설치 시 이미 함께 들어와 있던 라이브러리를 그대로 쓴 것.
"""
import glob
import io
import os
import re

from PIL import Image
from PIL.ExifTags import TAGS

MAX_WIDTH = 1200

# 종합 순위 -> 장소명 (임장 보고서 기준)
RANK_TO_NAME = {
    1: "상봉역",
    2: "금강사거리",
    3: "타임호프",
    8: "먹자골목",
    9: "진로아파트",
}

report = io.StringIO()


def log(text=""):
    print(text)
    report.write(str(text) + "\n")


def get_capture_time(path):
    """사진의 EXIF 촬영시각을 읽어온다 (없으면 None)."""
    try:
        img = Image.open(path)
        exif = img.getexif()
        if not exif:
            return None
        for tag_id, value in exif.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "DateTime":
                return value
    except Exception:
        return None
    return None


if __name__ == "__main__":
    src_dir = "docs/fieldwork"
    out_dir = "docs/fieldwork/photos"
    os.makedirs(out_dir, exist_ok=True)

    files = sorted(glob.glob(os.path.join(src_dir, "*.jpg")))
    log(f"원본 사진 수: {len(files)}\n")

    # 파일명에서 순위와 번호를 뽑는다: "1위 (3).jpg" -> rank=1, n=3
    pattern = re.compile(r"(\d+)위 \((\d+)\)\.jpg$")

    grouped = {}
    for fp in files:
        m = pattern.search(os.path.basename(fp))
        if not m:
            log(f"[건너뜀] 패턴에 안 맞는 파일: {fp}")
            continue
        rank, n = int(m.group(1)), int(m.group(2))
        grouped.setdefault(rank, []).append((n, fp))

    exif_times = {}
    for rank in sorted(grouped):
        name = RANK_TO_NAME.get(rank, f"순위{rank}")
        # 원래 번호(괄호 안 숫자) 순서대로 정렬해서 1부터 다시 매김 (중간에 빠진 번호가 있어도 연속되게)
        items = sorted(grouped[rank], key=lambda x: x[0])
        log(f"=== {rank}위 ({name}): 원본 {len(items)}장 ===")
        for new_idx, (orig_n, fp) in enumerate(items, start=1):
            new_name = f"{rank:02d}_{name}_{new_idx:02d}.jpg"
            out_path = os.path.join(out_dir, new_name)

            img = Image.open(fp)
            # 카메라가 EXIF Orientation을 남기는 경우가 많아, 회전을 반영해서 저장
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)

            w, h = img.size
            if w > MAX_WIDTH:
                new_h = int(h * MAX_WIDTH / w)
                img = img.resize((MAX_WIDTH, new_h), Image.LANCZOS)
            img.convert("RGB").save(out_path, "JPEG", quality=88)

            t = get_capture_time(fp)
            if t:
                exif_times.setdefault(rank, []).append(t)

            log(f"  {os.path.basename(fp)} -> {new_name} (원본 {w}x{h} -> {img.size[0]}x{img.size[1]})")
        if rank in exif_times:
            times = sorted(exif_times[rank])
            log(f"  EXIF 촬영시각 범위: {times[0]} ~ {times[-1]}")
        else:
            log(f"  EXIF 촬영시각 없음")
        log("")

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/31_organize_fieldwork_photos_log.txt", "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    log("완료: outputs/31_organize_fieldwork_photos_log.txt 저장됨")
