"""
Transcode S3 videos into a canonical, AR-bucketed, fast-seek H.264 space.

Usage:
  python transcode.py --survey                      # print AR histogram, pick buckets
  python transcode.py --in-prefix raw/ --out-prefix transcoded/
"""
import argparse, json, math, subprocess, tempfile, os, collections
import boto3

# ── config ────────────────────────────────────────────────────────────────
BUCKET_NAME = "your-s3-bucket"
# (name, canvas_w, canvas_h) — fixed model input sizes, ~0.52 MP each, even dims.
AR_BUCKETS = [
    ("sq",   720, 720),   # 1.00
    ("4x3",  832, 624),   # 1.33
    ("16x9", 960, 540),   # 1.78
]
TARGET_FPS    = 30        # force CFR to this; set None to keep source fps (still CFR)
CRF           = 20
PRESET        = "slow"
GOP_SECONDS   = 1.0       # keyframe interval → fast random seeks, small size cost
ALLOW_UPSCALE = False     # don't invent detail in sources smaller than the canvas

s3 = boto3.client("s3")

# ── helpers ───────────────────────────────────────────────────────────────
def ffprobe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate,avg_frame_rate,codec_name",
         "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    st = j["streams"][0]
    def rate(s):
        n, d = s.split("/"); d = float(d) or 1.0; return float(n) / d
    return {
        "w": int(st["width"]), "h": int(st["height"]),
        "fps_r": rate(st["r_frame_rate"]), "fps_avg": rate(st["avg_frame_rate"]),
        "codec": st["codec_name"], "dur": float(j["format"]["duration"]),
    }

def pick_bucket(ar):
    # nearest in log-AR space → minimizes letterbox bar area
    return min(AR_BUCKETS, key=lambda b: abs(math.log(ar / (b[1] / b[2]))))

def even(x):
    return max(2, int(round(x / 2) * 2))

def letterbox(src_w, src_h, W, H):
    scale = min(W / src_w, H / src_h)
    if not ALLOW_UPSCALE:
        scale = min(scale, 1.0)
    aw, ah = even(src_w * scale), even(src_h * scale)
    return aw, ah, (W - aw) // 2, (H - ah) // 2     # active w,h + pad x,y

def transcode(src_path, out_path, meta, bucket):
    name, W, H = bucket
    aw, ah, px, py = letterbox(meta["w"], meta["h"], W, H)
    fps = TARGET_FPS or round(meta["fps_r"])
    g = max(1, round(fps * GOP_SECONDS))
    vf = (f"scale={aw}:{ah}:flags=lanczos,"
          f"pad={W}:{H}:{px}:{py}:color=black,setsar=1")
    subprocess.run(
        ["ffmpeg", "-y", "-i", src_path,
         "-vf", vf,
         "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-crf", str(CRF), "-preset", PRESET,
         "-g", str(g), "-keyint_min", str(g),
         "-x264-params", "scenecut=0:open-gop=0", "-bf", "2",
         "-fps_mode", "cfr", "-r", str(fps),
         "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart", out_path],
        check=True)
    return {"bucket": name, "canvas_w": W, "canvas_h": H,
            "active_w": aw, "active_h": ah, "pad_x": px, "pad_y": py, "fps": fps}

def list_videos(prefix):
    p = s3.get_paginator("list_objects_v2")
    for page in p.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
        for o in page.get("Contents", []):
            if o["Key"].lower().endswith((".mp4", ".mov", ".avi", ".mkv")):
                yield o["Key"]

# ── modes ─────────────────────────────────────────────────────────────────
def survey(prefix):
    hist = collections.Counter()
    with tempfile.TemporaryDirectory() as d:
        for key in list_videos(prefix):
            local = os.path.join(d, "v")
            s3.download_file(BUCKET_NAME, key, local)
            m = ffprobe(local)
            ar = m["w"] / m["h"]
            hist[round(ar, 2)] += 1
            vfr = abs(m["fps_r"] - m["fps_avg"]) > 0.01
            print(f"{key}: {m['w']}x{m['h']} AR={ar:.2f} {m['codec']} "
                  f"{m['fps_r']:.2f}fps{' VFR' if vfr else ''}")
    print("\nAR histogram:", dict(sorted(hist.items())))

def run(in_prefix, out_prefix):
    manifest = []
    with tempfile.TemporaryDirectory() as d:
        for key in list_videos(in_prefix):
            src = os.path.join(d, "in.mp4"); out = os.path.join(d, "out.mp4")
            s3.download_file(BUCKET_NAME, key, src)
            m = ffprobe(src)
            bucket = pick_bucket(m["w"] / m["h"])
            geom = transcode(src, out, m, bucket)
            out_meta = ffprobe(out)
            out_key = out_prefix + os.path.basename(key).rsplit(".", 1)[0] + ".mp4"
            s3.upload_file(out, BUCKET_NAME, out_key,
                           ExtraArgs={"ContentType": "video/mp4"})
            frame_count = round(out_meta["dur"] * geom["fps"])
            manifest.append({"video_id": os.path.basename(out_key),
                             "src_key": key, "out_key": out_key,
                             "src_w": m["w"], "src_h": m["h"],
                             "frame_count": frame_count, **geom})
            print(f"✓ {key} → {out_key} [{geom['bucket']}]")
    s3.put_object(Bucket=BUCKET_NAME, Key=out_prefix + "manifest.json",
                  Body=json.dumps(manifest, indent=2).encode(),
                  ContentType="application/json")
    print(f"\nWrote manifest with {len(manifest)} entries.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--survey", action="store_true")
    ap.add_argument("--in-prefix", default="raw/")
    ap.add_argument("--out-prefix", default="transcoded/")
    a = ap.parse_args()
    survey(a.in_prefix) if a.survey else run(a.in_prefix, a.out_prefix)
