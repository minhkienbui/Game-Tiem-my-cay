# -*- coding: utf-8 -*-
"""
Backend Server cho Web Game "Tiệm Mì Cay"
Cung cấp đầy đủ các API:
  - GET / POST /api/lb       : Bảng xếp hạng người chơi
  - GET / POST /api/chal     : Giải mì (Đề thi ngày, tạo token, nộp điểm, xếp hạng)
  - GET / POST /api/sync     : Đồng bộ & chuyển dữ liệu lưu trữ qua mã 8 ký tự
  - GET / POST /api/prank    : Chọc quán khác & nhận quà tặng
  - POST       /api/ai       : AI thông minh phản hồi đánh giá khách hàng
  - POST       /api/err      : Ghi nhận lỗi telemetry
  - POST       /api/copy     : Thống kê chia sẻ
  - Static file server       : index.html, game.js, music/*.mp3, icons, webmanifest
"""

import http.server
import socketserver
import os
import sys
import json
import sqlite3
import random
import string
import time
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
import hashlib
import base64

def hash_password(password):
    return hashlib.sha256(("tiemMiCayAuth$" + password).encode("utf-8")).hexdigest()


try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "tiemmicay.db")

os.makedirs(DATA_DIR, exist_ok=True)

# ----------------- DATABASE INITIALIZATION -----------------
# ----------------- DATABASE ADAPTER (NEON POSTGRESQL / SQLITE) -----------------
POSTGRES_URL = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")
if POSTGRES_URL and POSTGRES_URL.startswith("postgres://"):
    POSTGRES_URL = POSTGRES_URL.replace("postgres://", "postgresql://", 1)

import ssl
try:
    import pg8000.dbapi
except ImportError:
    pass

class DB:
    def __init__(self):
        self.is_pg = bool(POSTGRES_URL)
        if self.is_pg:
            url = urlparse(POSTGRES_URL)
            ssl_ctx = ssl.create_default_context()
            self.conn = pg8000.dbapi.connect(
                user=url.username,
                password=url.password,
                host=url.hostname,
                port=url.port or 5432,
                database=url.path.lstrip("/"),
                ssl_context=ssl_ctx
            )
        else:
            self.conn = sqlite3.connect(DB_PATH)
        self.cur = self.conn.cursor()

    def execute(self, sql, params=()):
        if self.is_pg:
            sql = sql.replace("?", "%s")
        return self.cur.execute(sql, params)

    def executemany(self, sql, seq_of_params):
        if self.is_pg:
            sql = sql.replace("?", "%s")
        return self.cur.executemany(sql, seq_of_params)

    def fetchone(self):
        return self.cur.fetchone()

    def fetchall(self):
        return self.cur.fetchall()

    @property
    def lastrowid(self):
        return getattr(self.cur, "lastrowid", 0)

    def commit(self):
        return self.conn.commit()

    def close(self):
        try:
            self.cur.close()
            self.conn.close()
        except Exception:
            pass

def init_db():
    try:
        db = DB()
        auto_id_type = "SERIAL" if db.is_pg else "INTEGER"
        auto_inc = "" if db.is_pg else "AUTOINCREMENT"

        db.execute(f"""
            CREATE TABLE IF NOT EXISTS users (
                id {auto_id_type} PRIMARY KEY {auto_inc},
                username TEXT UNIQUE,
                password_hash TEXT,
                created_at BIGINT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS user_saves (
                username TEXT PRIMARY KEY,
                save_data TEXT,
                updated_at BIGINT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard (
                id TEXT PRIMARY KEY,
                name TEXT,
                profit BIGINT,
                day INT,
                served INT,
                lv INT,
                rate REAL,
                updated_at BIGINT
            )
        """)
        db.execute(f"""
            CREATE TABLE IF NOT EXISTS admin_gifts (
                id {auto_id_type} PRIMARY KEY {auto_inc},
                target_type TEXT,
                target_id TEXT,
                target_name TEXT,
                store_code TEXT,
                amount BIGINT,
                title TEXT,
                message TEXT,
                claimed INT DEFAULT 0,
                created_at BIGINT
            )
        """)
        db.execute(f"""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id {auto_id_type} PRIMARY KEY {auto_inc},
                conversation_id TEXT,
                sender_type TEXT,
                sender_name TEXT,
                store_code TEXT,
                message TEXT,
                created_at BIGINT,
                is_read_by_admin INT DEFAULT 0,
                is_read_by_user INT DEFAULT 0
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_chat_conv ON chat_messages(conversation_id, created_at)")
        db.execute(f"""
            CREATE TABLE IF NOT EXISTS admin_messages (
                id {auto_id_type} PRIMARY KEY {auto_inc},
                sender TEXT,
                store_code TEXT,
                topic TEXT,
                content TEXT,
                status TEXT DEFAULT 'pending',
                created_at BIGINT,
                updated_at BIGINT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS game_config (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at BIGINT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS weekly_hall_of_fame (
                id TEXT PRIMARY KEY,
                week_key TEXT,
                week_title TEXT,
                rank INT,
                shop_id TEXT,
                shop_name TEXT,
                total_score INT,
                reward_money INT,
                custom_title TEXT,
                claimed_shops TEXT DEFAULT '',
                created_at BIGINT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS challenges (
                id TEXT,
                day TEXT,
                score INT,
                served INT,
                perfect INT,
                wrong INT,
                lost INT,
                created_at BIGINT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS challenge_tokens (
                token TEXT PRIMARY KEY,
                id TEXT,
                day TEXT,
                n INT,
                created_at BIGINT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS cloud_saves (
                code TEXT PRIMARY KEY,
                save_data TEXT,
                created_at BIGINT
            )
        """)
        db.execute(f"""
            CREATE TABLE IF NOT EXISTS pranks (
                id {auto_id_type} PRIMARY KEY {auto_inc},
                from_id TEXT,
                from_name TEXT,
                to_id TEXT,
                kind TEXT,
                taken INT DEFAULT 0,
                created_at BIGINT
            )
        """)

        db.execute("SELECT COUNT(*) FROM weekly_hall_of_fame")
        hof_cnt = db.fetchone()
        if hof_cnt and hof_cnt[0] == 0:
            now_sec = int(time.time())
            hof_seeds = [
                ("2026-W38_1", "2026-W38", "Tuần 38 (Mùa Khai Xuân)", 1, "vua_mi_cay_vip", "Vua Mì Cay Sasin", 18650, 1000000, "👑 QUÁN QUÂN ĐỆ NHẤT MÌ CAY TOÀN QUỐC", "", now_sec - 86400*7),
                ("2026-W38_2", "2026-W38", "Tuần 38 (Mùa Khai Xuân)", 2, "seoul_02", "Tiệm Mì Cay Seoul Phố", 14820, 300000, "🥈 Á QUÂN BẬC THẦY HỎA LỰC", "", now_sec - 86400*7),
                ("2026-W38_3", "2026-W38", "Tuần 38 (Mùa Khai Xuân)", 3, "nha_cao", "Mì Cay Nhà Cáo", 11450, 100000, "🥉 QUÝ QUÂN TINH ANH NẤU MÌ", "", now_sec - 86400*7)
            ]
            db.executemany("""
                INSERT INTO weekly_hall_of_fame (id, week_key, week_title, rank, shop_id, shop_name, total_score, reward_money, custom_title, claimed_shops, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, hof_seeds)

        db.execute("SELECT COUNT(*) FROM leaderboard")
        row = db.fetchone()
        if row and row[0] == 0:
            seed_shops = [
                ("vua_mi_cay_vip", "Vua Mì Cay Hoàng Gia", 18500000, 25, 485, 10, 5.0, int(time.time())),
                ("sasin_01", "Mì Cay Sasin Phố", 14500000, 18, 220, 9, 4.9, int(time.time())),
                ("seoul_02", "Tiệm Mì Cay Seoul", 9800000, 14, 160, 8, 4.8, int(time.time())),
                ("nha_cao", "Mì Cay Nhà Cáo", 6200000, 10, 115, 6, 4.9, int(time.time())),
                ("be_ot_04", "Tiệm Mì Bé Ớt", 3800000, 7, 85, 5, 4.7, int(time.time())),
                ("co_ba_05", "Quán Mì Cô Ba", 1950000, 4, 45, 3, 4.6, int(time.time()))
            ]
            db.executemany("""
                INSERT INTO leaderboard (id, name, profit, day, served, lv, rate, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, seed_shops)

        try:
            db.execute("ALTER TABLE users ADD COLUMN store_code TEXT")
        except Exception:
            pass
        db.commit()
        db.close()
    except Exception as e:
        print("init_db status:", e)

init_db()

# ----------------- HELPER FUNCTIONS -----------------
def get_week_bounds(target_date=None):
    if target_date is None:
        target_date = datetime.now()
    # Monday is 0, Sunday is 6
    day_of_week = target_date.weekday()
    monday = target_date - timedelta(days=day_of_week, hours=target_date.hour, minutes=target_date.minute, seconds=target_date.second, microseconds=target_date.microsecond)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    start_sec = int(monday.timestamp())
    end_sec = int(sunday.timestamp())
    iso_year, iso_week, _ = monday.isocalendar()
    week_key = f"{iso_year}-W{iso_week:02d}"
    m_str = monday.strftime("%d/%m")
    s_str = sunday.strftime("%d/%m")
    week_title = f"Tuần {iso_week} ({m_str} - {s_str})"
    return start_sec, end_sec, week_key, week_title

DEFAULT_GAME_CONFIG = {
    "announcement_active": False,
    "announcement_text": "Đại hội Giải Mì Tuần đang diễn ra sôi nổi! Top 1 nhận 1.000.000đ tiền mặt vào két quán!",
    "announcement_type": "event",
    "daySec": 210,
    "startMoney": 400000,
    "rent": 40000,
    "util": 15000,
    "appFee": 20,
    "policeFee": 100000,
    "catchRate": 50,
    "theftEnabled": True,
    "chalRounds": 3,
    "rewardTop1": 1000000,
    "rewardTop2": 300000,
    "rewardTop3": 100000,
    "taxCycleDays": 3,
    "taxBaseRate": 50000
}

def auto_finalize_completed_weeks():
    try:
        now_sec = int(time.time())
        # Check last week
        start_sec, end_sec, week_key, week_title = get_week_bounds(datetime.now() - timedelta(days=7))
        conn = DB()
        cur = conn
        cur.execute("SELECT COUNT(*) FROM weekly_hall_of_fame WHERE week_key = ?", (week_key,))
        cnt = cur.fetchone()[0]
        if cnt == 0:
            cur.execute("""
                SELECT id, SUM(score) as s, COUNT(*) as rounds
                FROM challenges
                WHERE created_at >= ? AND created_at <= ?
                GROUP BY id
                ORDER BY s DESC
                LIMIT 3
            """, (start_sec, end_sec))
            top_rows = cur.fetchall()
            for idx, r in enumerate(top_rows):
                rank = idx + 1
                reward_money = 1000000 if rank == 1 else (300000 if rank == 2 else 100000)
                custom_title = "👑 QUÁN QUÂN ĐỆ NHẤT MÌ CAY TOÀN QUỐC" if rank == 1 else ("🥈 Á QUÂN BẬC THẦY HỎA LỰC" if rank == 2 else "🥉 QUÝ QUÂN TINH ANH NẤU MÌ")
                cur.execute("SELECT name FROM leaderboard WHERE id = ?", (r[0],))
                name_row = cur.fetchone()
                shop_name = name_row[0] if name_row else "Tiệm Mì Cay"
                row_id = f"{week_key}_{rank}"
                cur.execute("""
                    INSERT OR REPLACE INTO weekly_hall_of_fame (
                        id, week_key, week_title, rank, shop_id, shop_name, total_score, reward_money, custom_title, claimed_shops, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?)
                """, (row_id, week_key, week_title, rank, r[0], shop_name, r[1], reward_money, custom_title, now_sec))
            conn.commit()
        conn.close()
    except Exception as e:
        print("auto_finalize_completed_weeks error:", e)

def st_hash(A):
    n = 2166136261
    for char in A:
        n ^= ord(char)
        n = (n * 16777619) & 0xFFFFFFFF
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if n == 0:
        return "0"
    res = []
    while n > 0:
        res.append(chars[n % 36])
        n //= 36
    return "".join(reversed(res))

FNV_SALTS = ["mc!7Ay#q", "t0m~yum*"]
def Fn_sig(A):
    return st_hash(FNV_SALTS[0] + A).zfill(7) + st_hash(A + FNV_SALTS[1]).zfill(7)

def update_save_data_money(save_data, new_money):
    if not isinstance(save_data, str) or not save_data.startswith("MC2|"):
        return save_data
    try:
        parts = save_data.split("|")
        if len(parts) != 3:
            return save_data
        dec = base64.b64decode(parts[1]).decode("utf-8")
        obj = json.loads(dec)
        obj["money"] = new_money
        new_json = json.dumps(obj, separators=(",", ":"))
        new_b64 = base64.b64encode(new_json.encode("utf-8")).decode("ascii")
        new_sig = Fn_sig(new_json)
        return f"MC2|{new_b64}|{new_sig}"
    except Exception:
        return save_data

def get_today_chal_date():
    now = datetime.now()
    return f"{now.day}/{now.month}"

def generate_sync_code():
    chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    part1 = ''.join(random.choices(chars, k=4))
    part2 = ''.join(random.choices(chars, k=4))
    return f"{part1}-{part2}"

# ----------------- REQUEST HANDLER -----------------
class GameServerHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def end_headers(self):
        # Security Headers
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("X-XSS-Protection", "1; mode=block")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            # Protect against oversized payloads (Max 1MB)
            if 0 < content_length <= 1048576:
                raw = self.rfile.read(content_length).decode("utf-8")
                return json.loads(raw)
        except Exception:
            pass
        return {}

    def is_blocked_path(self, path):
        # Block access to database files, python source scripts, and private data
        lowered = path.lower()
        if lowered.startswith("/data") or "/.." in lowered or "\\.." in lowered:
            return True
        for ext in [".db", ".sqlite", ".py", ".env", ".log", ".bak", ".sh", ".git"]:
            if lowered.endswith(ext) or ext + "?" in lowered:
                return True
        return False

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Dedicated private route for Admin
        if path in ["/admin", "/admin/"]:
            admin_file = os.path.join(BASE_DIR, "admin.html")
            if not os.path.exists(admin_file):
                admin_file = os.path.join(BASE_DIR, "public", "admin.html")
            if os.path.exists(admin_file):
                with open(admin_file, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        # GET /api/auth/save
        if path == "/api/auth/save":
            params = parse_qs(parsed.query)
            username = params.get("username", [""])[0].strip().lower()
            if username:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute("SELECT save_data FROM user_saves WHERE username = ?", (username,))
                row = cur.fetchone()
                conn.close()
                if row:
                    return self.send_json({"ok": True, "save": row[0]})
            return self.send_json({"ok": False}, status=404)
        params = parse_qs(parsed.query)

        # Defense against Path Traversal and Sensitive File Access
        if self.is_blocked_path(path):
            self.send_response(403)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"403 Forbidden: Access to sensitive files is prohibited.")
            return

        if path == "/api/config" or path == "/api/admin/config":
            conn = DB()
            cur = conn
            cur.execute("SELECT key, value, updated_at FROM game_config")
            rows = cur.fetchall()
            conn.close()
            cfg = dict(DEFAULT_GAME_CONFIG)
            last_updated = 0
            for r in rows:
                try:
                    cfg[r[0]] = json.loads(r[1])
                except Exception:
                    cfg[r[0]] = r[1]
                if r[2] and r[2] > last_updated:
                    last_updated = r[2]
            res = {"ok": True, "config": cfg, "updated_at": last_updated}
            res.update(cfg)
            return self.send_json(res)

        # 1. GET /api/lb (Leaderboard)
                # GET /api/user/gifts
        if path == "/api/user/gifts":
            shop_id = params.get("id", [""])[0].strip()
            username = params.get("username", [""])[0].strip().lower()
            store_code = params.get("code", [""])[0].strip().upper()
            conn = DB()
            cur = conn
            cur.execute("""
                SELECT id, target_type, target_id, target_name, amount, title, message, created_at
                FROM admin_gifts
                WHERE claimed = 0 AND (
                    (target_type = 'user' AND LOWER(target_id) = ?) OR
                    (target_type = 'code' AND UPPER(store_code) = ?) OR
                    (target_type = 'shop' AND target_id = ?) OR
                    (target_type = 'all')
                )
                ORDER BY created_at ASC
                LIMIT 5
            """, (username, store_code, shop_id))
            rows = cur.fetchall()
            conn.close()
            gifts = []
            for r in rows:
                gifts.append({
                    "id": r[0], "target_type": r[1], "target_id": r[2], "target_name": r[3],
                    "amount": r[4], "title": r[5], "message": r[6], "created_at": r[7]
                })
            return self.send_json({"ok": True, "gifts": gifts})

        if path == "/api/lb":
            conn = DB()
            cur = conn
            cur.execute('''
                SELECT id, name, profit, day, served, lv, rate
                FROM leaderboard
                ORDER BY profit DESC
                LIMIT 50
            ''')
            rows = cur.fetchall()
            cur.execute('SELECT COUNT(*) FROM leaderboard')
            total = cur.fetchone()[0]
            conn.close()

            top = []
            for r in rows:
                top.append({
                    "id": r[0], "name": r[1], "profit": r[2],
                    "day": r[3], "served": r[4], "lv": r[5], "rate": r[6]
                })

            return self.send_json({
                "ok": True,
                "top": top,
                "total": total,
                "cups": {"sasin_01": 1, "seoul_02": 2}
            })

        # 2. GET /api/chal (Tournament Challenge)
        if path == "/api/chal":
            auto_finalize_completed_weeks()
            shop_id = params.get("id", [""])[0]
            chal_day = get_today_chal_date()
            start_sec, end_sec, week_key, week_title = get_week_bounds()
            conn = DB()
            cur = conn

            # Top scores for today's challenge (Cộng dồn SUM score)
            cur.execute('''
                SELECT id, SUM(score) as total_score, COUNT(*) as rounds, SUM(served) as served
                FROM challenges
                WHERE day = ?
                GROUP BY id
                ORDER BY total_score DESC
                LIMIT 20
            ''', (chal_day,))
            top_rows = cur.fetchall()

            top = []
            for r in top_rows:
                cur.execute('SELECT name FROM leaderboard WHERE id = ?', (r[0],))
                name_row = cur.fetchone()
                name = name_row[0] if name_row else "Chủ quán ẩn danh"
                top.append({"id": r[0], "name": name, "s": r[1]})

            # Player's rounds today
            cur.execute('''
                SELECT COUNT(*), SUM(score)
                FROM challenges
                WHERE day = ? AND id = ?
            ''', (chal_day, shop_id))
            me_row = cur.fetchone()
            rounds_done = me_row[0] if me_row else 0
            best_score = me_row[1] if me_row and me_row[1] else 0

            cur.execute('SELECT COUNT(DISTINCT id) FROM challenges WHERE day = ? AND score > ?', (chal_day, best_score))
            rank = cur.fetchone()[0] + 1 if best_score > 0 else 0

            cur.execute('SELECT COUNT(DISTINCT id) FROM challenges WHERE day = ?', (chal_day,))
            total_players = max(len(top), cur.fetchone()[0])

            # Weekly rankings: Total tournament score within the week
            cur.execute('''
                SELECT id, SUM(score) as tot_score, COUNT(*) as rounds
                FROM challenges
                WHERE created_at >= ? AND created_at <= ?
                GROUP BY id
                ORDER BY tot_score DESC
                LIMIT 30
            ''', (start_sec, end_sec))
            wtop_rows = cur.fetchall()

            wtop = []
            for idx, wr in enumerate(wtop_rows):
                cur.execute('SELECT name FROM leaderboard WHERE id = ?', (wr[0],))
                name_row = cur.fetchone()
                name = name_row[0] if name_row else "Chủ quán ẩn danh"
                prize = 1000000 if idx == 0 else (300000 if idx == 1 else (100000 if idx == 2 else 0))
                wtop.append({
                    "id": wr[0],
                    "name": name,
                    "s": wr[1],
                    "rounds": wr[2],
                    "rank": idx + 1,
                    "prize": prize
                })

            cur.execute('SELECT COUNT(DISTINCT id) FROM challenges WHERE created_at >= ? AND created_at <= ?', (start_sec, end_sec))
            wtotal = max(len(wtop), cur.fetchone()[0])

            # Player's weekly total
            cur.execute('''
                SELECT COUNT(*), SUM(score)
                FROM challenges
                WHERE created_at >= ? AND created_at <= ? AND id = ?
            ''', (start_sec, end_sec, shop_id))
            wme_row = cur.fetchone()
            wbest = wme_row[1] if wme_row and wme_row[1] else 0
            wrank = 0
            if wbest > 0:
                cur.execute('''
                    SELECT COUNT(*) FROM (
                        SELECT id, SUM(score) as tot FROM challenges
                        WHERE created_at >= ? AND created_at <= ?
                        GROUP BY id HAVING tot > ?
                    )
                ''', (start_sec, end_sec, wbest))
                wrank = cur.fetchone()[0] + 1

            # Hall of Fame
            cur.execute('''
                SELECT id, week_key, week_title, rank, shop_id, shop_name, total_score, reward_money, custom_title, claimed_shops, created_at
                FROM weekly_hall_of_fame
                ORDER BY created_at DESC, rank ASC
                LIMIT 20
            ''')
            hof_raw = cur.fetchall()
            if not hof_raw:
                now_sec = int(time.time())
                seeds = [
                    ("2026-W38_1", "2026-W38", "Tuần 38 (Mùa Khai Xuân)", 1, "vua_mi_cay_vip", "Vua Mì Cay Sasin", 18650, 1000000, "👑 QUÁN QUÂN ĐỆ NHẤT MÌ CAY TOÀN QUỐC", "", now_sec - 86400*7),
                    ("2026-W38_2", "2026-W38", "Tuần 38 (Mùa Khai Xuân)", 2, "seoul_02", "Tiệm Mì Cay Seoul Phố", 14820, 300000, "🥈 Á QUÂN BẬC THẦY HỎA LỰC", "", now_sec - 86400*7),
                    ("2026-W38_3", "2026-W38", "Tuần 38 (Mùa Khai Xuân)", 3, "nha_cao", "Mì Cay Nhà Cáo", 11450, 100000, "🥉 QUÝ QUÂN TINH ANH NẤU MÌ", "", now_sec - 86400*7)
                ]
                cur.executemany('''
                    INSERT OR IGNORE INTO weekly_hall_of_fame (id, week_key, week_title, rank, shop_id, shop_name, total_score, reward_money, custom_title, claimed_shops, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', seeds)
                conn.commit()
                cur.execute('''
                    SELECT id, week_key, week_title, rank, shop_id, shop_name, total_score, reward_money, custom_title, claimed_shops, created_at
                    FROM weekly_hall_of_fame
                    ORDER BY created_at DESC, rank ASC
                    LIMIT 20
                ''')
                hof_raw = cur.fetchall()

            hall_of_fame = []
            cups = {}
            for h in hof_raw:
                hall_of_fame.append({
                    "id": h[0], "week_key": h[1], "week_title": h[2], "rank": h[3],
                    "shop_id": h[4], "shop_name": h[5], "total_score": h[6],
                    "reward_money": h[7], "custom_title": h[8], "claimed": bool(h[4] in (h[9] or "").split(","))
                })
                if h[4] and h[4] not in cups and h[3] <= 3:
                    cups[h[4]] = h[3]

            unclaimed_reward = None
            if shop_id:
                cur.execute('''
                    SELECT id, week_key, week_title, rank, reward_money, custom_title, claimed_shops
                    FROM weekly_hall_of_fame
                    WHERE shop_id = ?
                    ORDER BY created_at DESC LIMIT 1
                ''', (shop_id,))
                rw = cur.fetchone()
                if rw and shop_id not in (rw[6] or "").split(","):
                    unclaimed_reward = {
                        "id": rw[0], "week_key": rw[1], "week_title": rw[2],
                        "rank": rw[3], "money": rw[4], "custom_title": rw[5]
                    }

            conn.close()

            return self.send_json({
                "day": chal_day,
                "top": top,
                "wtop": wtop,
                "wtotal": max(1, wtotal),
                "me": {
                    "left": max(0, 3 - rounds_done),
                    "best": best_score,
                    "rank": rank,
                    "wbest": wbest,
                    "wrank": wrank
                },
                "total": max(1, total_players),
                "cups": cups,
                "rewards_info": [
                    { "rank": 1, "money": 1000000, "title": "🥇 TOP 1 - QUÁN QUÂN: 1.000.000đ + Vinh Danh Hoàng Gia" },
                    { "rank": 2, "money": 300000, "title": "🥈 TOP 2 - Á QUÂN 1: 300.000đ + Vinh Danh Bảng Vàng" },
                    { "rank": 3, "money": 100000, "title": "🥉 TOP 3 - Á QUÂN 2: 100.000đ + Vinh Danh Bảng Vàng" }
                ],
                "hall_of_fame": hall_of_fame,
                "unclaimed_reward": unclaimed_reward
            })

        # 3. GET /api/sync (Download save from cloud)
        if path == "/api/sync":
            code = params.get("code", [""])[0].strip().upper()
            conn = DB()
            cur = conn
            cur.execute('SELECT save_data, created_at FROM cloud_saves WHERE code = ?', (code,))
            row = cur.fetchone()
            conn.close()

            if row:
                # Check 24h expiry
                if int(time.time()) - row[1] < 86400:
                    return self.send_json({"s": row[0]})
            return self.send_json({"error": "Mã không đúng hoặc đã hết hạn"}, status=404)

        # 4. GET /api/prank (Social pranks and gifts)
        if path == "/api/prank":
            shop_id = params.get("id", [""])[0]
            conn = DB()
            cur = conn
            cur.execute('''
                SELECT id, name, day, lv FROM leaderboard
                WHERE id != ?
                ORDER BY updated_at DESC
                LIMIT 15
            ''', (shop_id,))
            near = [{"id": r[0], "name": r[1], "day": r[2], "lv": r[3]} for r in cur.fetchall()]
            conn.close()

            # Return format expected by _A
            return self.send_json({
                "left": 3,
                "sent": [],
                "near": near
            })

        # 5. GET /api/admin/overview
        if path.startswith("/api/admin"):
            adm_code = self.headers.get("X-Admin-Code") or params.get("admin_code", [""])[0]
            if adm_code != "09659":
                return self.send_json({"error": "Yêu cầu mã code quản trị 09659!"}, status=401)
        if path == "/api/admin/overview":
            conn = DB()
            cur = conn
            cur.execute('SELECT code, save_data, created_at FROM cloud_saves ORDER BY created_at DESC LIMIT 30')
            saves = [{"code": r[0], "size": len(r[1]), "created_at": r[2]} for r in cur.fetchall()]
            cur.execute('SELECT COUNT(*) FROM cloud_saves')
            saves_count = cur.fetchone()[0]

            cur.execute('SELECT from_name, to_id, kind, taken, created_at FROM pranks ORDER BY created_at DESC LIMIT 30')
            prank_rows = cur.fetchall()
            pranks = []
            for pr in prank_rows:
                cur.execute('SELECT name FROM leaderboard WHERE id = ?', (pr[1],))
                to_row = cur.fetchone()
                to_name = to_row[0] if to_row else pr[1]
                pranks.append({
                    "from_name": pr[0],
                    "to_name": to_name,
                    "kind": pr[2],
                    "taken": pr[3],
                    "created_at": pr[4]
                })
            conn.close()

            return self.send_json({
                "ok": True,
                "savesCount": saves_count,
                "saves": saves,
                "pranks": pranks
            })
        # 6. GET /api/admin/users
                # GET /api/admin/inbox
                # GET /api/chat/messages
        if path == "/api/chat/messages":
            conv_id = params.get("conversation_id", [""])[0].strip()
            if not conv_id:
                return self.send_json({"ok": False, "error": "Missing conversation_id"}, status=400)
            conn = DB()
            cur = conn
            cur.execute("""
                SELECT id, conversation_id, sender_type, sender_name, store_code, message, created_at
                FROM chat_messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC, id ASC
                LIMIT 200
            """, (conv_id,))
            rows = cur.fetchall()
            cur.execute("UPDATE chat_messages SET is_read_by_user = 1 WHERE conversation_id = ? AND sender_type = 'admin'", (conv_id,))
            conn.commit()
            conn.close()

            messages = []
            for r in rows:
                messages.append({
                    "id": r[0], "conversation_id": r[1], "sender_type": r[2],
                    "sender_name": r[3], "store_code": r[4] or "",
                    "message": r[5], "created_at": r[6]
                })
            return self.send_json({"ok": True, "conversation_id": conv_id, "messages": messages})

        # GET /api/admin/chat/conversations
        if path == "/api/admin/chat/conversations":
            conn = DB()
            cur = conn
            cur.execute("""
                SELECT
                    conversation_id,
                    MAX(sender_name) as display_name,
                    MAX(store_code) as store_code,
                    MAX(created_at) as last_time,
                    SUM(CASE WHEN sender_type = 'user' AND is_read_by_admin = 0 THEN 1 ELSE 0 END) as unread_count,
                    COUNT(*) as total_count
                FROM chat_messages
                GROUP BY conversation_id
                ORDER BY last_time DESC
                LIMIT 100
            """)
            rows = cur.fetchall()
            convs = []
            for r in rows:
                cur.execute("""
                    SELECT message, sender_type, created_at
                    FROM chat_messages
                    WHERE conversation_id = ?
                    ORDER BY created_at DESC, id DESC LIMIT 1
                """, (r[0],))
                last_m = cur.fetchone()
                convs.append({
                    "conversation_id": r[0],
                    "display_name": r[1] or r[0],
                    "store_code": r[2] or "",
                    "last_time": r[3] or 0,
                    "unread_count": r[4] or 0,
                    "total_count": r[5] or 0,
                    "last_message": last_m[0] if last_m else "",
                    "last_sender_type": last_m[1] if last_m else "user"
                })
            cur.execute("SELECT COUNT(*) FROM chat_messages WHERE sender_type = 'user' AND is_read_by_admin = 0")
            total_unread = cur.fetchone()[0]
            conn.close()
            return self.send_json({"ok": True, "conversations": convs, "total_unread": total_unread})

        # GET /api/admin/chat/messages
        if path == "/api/admin/chat/messages":
            conv_id = params.get("conversation_id", [""])[0].strip()
            if not conv_id:
                return self.send_json({"ok": False, "error": "Missing conversation_id"}, status=400)
            conn = DB()
            cur = conn
            cur.execute("""
                SELECT id, conversation_id, sender_type, sender_name, store_code, message, created_at
                FROM chat_messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC, id ASC
                LIMIT 300
            """, (conv_id,))
            rows = cur.fetchall()
            cur.execute("UPDATE chat_messages SET is_read_by_admin = 1 WHERE conversation_id = ? AND sender_type = 'user'", (conv_id,))
            conn.commit()
            conn.close()

            messages = []
            for r in rows:
                messages.append({
                    "id": r[0], "conversation_id": r[1], "sender_type": r[2],
                    "sender_name": r[3], "store_code": r[4] or "",
                    "message": r[5], "created_at": r[6]
                })
            return self.send_json({"ok": True, "conversation_id": conv_id, "messages": messages})

        if path == "/api/admin/inbox":
            conn = DB()
            cur = conn
            status_filter = params.get("status", [""])[0].strip()
            if status_filter in ("pending", "resolved"):
                cur.execute("""
                    SELECT id, sender, store_code, topic, content, status, created_at, updated_at
                    FROM admin_messages
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT 100
                """, (status_filter,))
            else:
                cur.execute("""
                    SELECT id, sender, store_code, topic, content, status, created_at, updated_at
                    FROM admin_messages
                    ORDER BY (CASE WHEN status = 'pending' THEN 0 ELSE 1 END), created_at DESC
                    LIMIT 100
                """)
            rows = cur.fetchall()
            cur.execute("SELECT COUNT(*) FROM admin_messages WHERE status = 'pending'")
            p_cnt = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM admin_messages")
            tot = cur.fetchone()[0]
            conn.close()

            messages = []
            for r in rows:
                messages.append({
                    "id": r[0],
                    "sender": r[1] or "Ẩn danh",
                    "store_code": r[2] or "",
                    "topic": r[3] or "Góp ý",
                    "content": r[4] or "",
                    "status": r[5] or "pending",
                    "created_at": r[6] or 0,
                    "updated_at": r[7] or 0
                })
            return self.send_json({
                "ok": True,
                "messages": messages,
                "pending_count": p_cnt,
                "total": tot
            })

        if path == "/api/admin/users":
            conn = DB()
            cur = conn
            cur.execute("""
                SELECT u.id, u.username, u.created_at, u.last_login_at, u.login_count,
                       u.device_info, u.current_lv, u.current_day, u.current_money,
                       (s.save_data IS NOT NULL) as has_save
                FROM users u
                LEFT JOIN user_saves s ON LOWER(u.username) = LOWER(s.username)
                ORDER BY u.last_login_at DESC, u.created_at DESC
                LIMIT 100
            """)
            rows = cur.fetchall()
            cur.execute("SELECT COUNT(*) FROM users")
            count_row = cur.fetchone()
            total_users = count_row[0] if count_row else len(rows)
            conn.close()

            users = []
            for r in rows:
                users.append({
                    "id": r[0],
                    "username": r[1],
                    "created_at": r[2],
                    "last_login_at": r[3],
                    "login_count": r[4] or 1,
                    "device_info": r[5] or "Desktop",
                    "lv": r[6] or 1,
                    "day": r[7] or 1,
                    "money": r[8] or 400000,
                    "has_save": bool(r[9])
                })
            return self.send_json({"ok": True, "users": users, "total": total_users})


        # Default static file serving
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        path = parsed.path
        if "path" in params:
            path = "/api/" + params["path"][0]
        body = self.read_json_body()

        # POST /api/inbox (Public Send Message to Admin)
                # POST /api/chat/send (User: Send message to Admin 1-on-1)
                # POST /api/admin/chal/finalize (Admin: Finalize Week and Award Top 1-2-3)
        if path == "/api/admin/chal/finalize":
            scope = str(body.get("scope", "last")).strip()
            target_date = datetime.now() if scope == "current" else (datetime.now() - timedelta(days=7))
            start_sec, end_sec, week_key, week_title = get_week_bounds(target_date)
            now_sec = int(time.time())
            conn = DB()
            cur = conn
            cur.execute("""
                SELECT id, SUM(score) as s, COUNT(*) as rounds
                FROM challenges
                WHERE created_at >= ? AND created_at <= ?
                GROUP BY id
                ORDER BY s DESC
                LIMIT 3
            """, (start_sec, end_sec))
            top_rows = cur.fetchall()
            if not top_rows:
                conn.close()
                return self.send_json({"ok": False, "message": f"Tuần {week_title} chưa có lượt thi đấu nào để trao giải."})

            results = []
            for idx, r in enumerate(top_rows):
                rank = idx + 1
                reward_money = 1000000 if rank == 1 else (300000 if rank == 2 else 100000)
                custom_title = "👑 QUÁN QUÂN ĐỆ NHẤT MÌ CAY TOÀN QUỐC" if rank == 1 else ("🥈 Á QUÂN BẬC THẦY HỎA LỰC" if rank == 2 else "🥉 QUÝ QUÂN TINH ANH NẤU MÌ")
                cur.execute("SELECT name FROM leaderboard WHERE id = ?", (r[0],))
                name_row = cur.fetchone()
                shop_name = name_row[0] if name_row else "Tiệm Mì Cay"
                row_id = f"{week_key}_{rank}"
                cur.execute("""
                    INSERT OR REPLACE INTO weekly_hall_of_fame (
                        id, week_key, week_title, rank, shop_id, shop_name, total_score, reward_money, custom_title, claimed_shops, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?)
                """, (row_id, week_key, week_title, rank, r[0], shop_name, r[1], reward_money, custom_title, now_sec))
                results.append({"rank": rank, "shopName": shop_name, "id": r[0], "score": r[1], "reward_money": reward_money})

            conn.commit()
            conn.close()
            return self.send_json({
                "ok": True,
                "message": f"Đã kết thúc và đẩy Top 1-2-3 của {week_title} lên Bảng Vinh Danh thành công!",
                "week_key": week_key,
                "results": results
            })

        if path == "/api/chat/send":
            conv_id = str(body.get("conversation_id", "")).strip()
            sender_name = str(body.get("sender_name") or body.get("sender") or "Khách").strip()[:50]
            store_code = str(body.get("store_code") or body.get("storeCode") or "").strip().upper()[:20]
            message = str(body.get("message") or body.get("content") or "").strip()[:3000]

            if not conv_id or not message:
                return self.send_json({"ok": False, "error": "Vui lòng nhập nội dung tin nhắn!"}, status=400)

            now_t = int(time.time())
            conn = DB()
            cur = conn
            cur.execute("""
                INSERT INTO chat_messages (conversation_id, sender_type, sender_name, store_code, message, created_at, is_read_by_admin, is_read_by_user)
                VALUES (?, 'user', ?, ?, ?, ?, 0, 1)
            """, (conv_id, sender_name, store_code, message, now_t))
            msg_id = cur.lastrowid
            conn.commit()
            conn.close()

            return self.send_json({
                "ok": True,
                "message": {
                    "id": msg_id,
                    "conversation_id": conv_id,
                    "sender_type": "user",
                    "sender_name": sender_name,
                    "store_code": store_code,
                    "message": message,
                    "created_at": now_t
                }
            })

        # POST /api/admin/chat/send (Admin: Reply directly to user)
        if path == "/api/admin/chat/send":
            conv_id = str(body.get("conversation_id", "")).strip()
            admin_name = str(body.get("admin_name", "Admin Quản Trị")).strip()[:50]
            message = str(body.get("message", "")).strip()[:3000]

            if not conv_id or not message:
                return self.send_json({"ok": False, "error": "Vui lòng nhập nội dung phản hồi!"}, status=400)

            now_t = int(time.time())
            conn = DB()
            cur = conn
            cur.execute("SELECT store_code FROM chat_messages WHERE conversation_id = ? LIMIT 1", (conv_id,))
            st_row = cur.fetchone()
            store_code = st_row[0] if st_row and st_row[0] else ""

            cur.execute("""
                INSERT INTO chat_messages (conversation_id, sender_type, sender_name, store_code, message, created_at, is_read_by_admin, is_read_by_user)
                VALUES (?, 'admin', ?, ?, ?, ?, 1, 0)
            """, (conv_id, admin_name, store_code, message, now_t))
            msg_id = cur.lastrowid
            conn.commit()
            conn.close()

            return self.send_json({
                "ok": True,
                "message": {
                    "id": msg_id,
                    "conversation_id": conv_id,
                    "sender_type": "admin",
                    "sender_name": admin_name,
                    "store_code": store_code,
                    "message": message,
                    "created_at": now_t
                }
            })

        # POST /api/admin/chat/delete-conversation (Delete entire thread)
        if path == "/api/admin/chat/delete-conversation":
            conv_id = str(body.get("conversation_id", "")).strip()
            if conv_id:
                conn = DB()
                cur = conn
                cur.execute("DELETE FROM chat_messages WHERE conversation_id = ?", (conv_id,))
                conn.commit()
                conn.close()
                return self.send_json({"ok": True, "conversation_id": conv_id})
            return self.send_json({"ok": False, "error": "Missing conversation_id"}, status=400)

        # POST /api/admin/chat/delete-message (Delete single message)
        if path == "/api/admin/chat/delete-message":
            msg_id = int(body.get("id", 0))
            if msg_id:
                conn = DB()
                cur = conn
                cur.execute("DELETE FROM chat_messages WHERE id = ?", (msg_id,))
                conn.commit()
                conn.close()
                return self.send_json({"ok": True, "id": msg_id})
            return self.send_json({"ok": False, "error": "Missing message id"}, status=400)

        if path == "/api/inbox":
            sender = str(body.get("sender", "Khách ẩn danh")).strip()[:50]
            store_code = str(body.get("store_code") or body.get("storeCode") or "").strip().upper()[:20]
            topic = str(body.get("topic", "Góp ý chung")).strip()[:80]
            content = str(body.get("content", "")).strip()[:2000]

            if not content or len(content) < 3:
                return self.send_json({"ok": False, "error": "Nội dung tin nhắn tối thiểu 3 ký tự!"}, status=400)

            now_t = int(time.time())
            conn = DB()
            cur = conn
            cur.execute("""
                INSERT INTO admin_messages (sender, store_code, topic, content, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """, (sender, store_code, topic, content, now_t, now_t))
            conn.commit()
            conn.close()
            return self.send_json({"ok": True, "message": "Đã gửi tin nhắn đến Admin thành công!"})

        # POST /api/admin/inbox/status (Update Message Status)
        if path == "/api/admin/inbox/status":
            msg_id = int(body.get("id", 0))
            new_status = str(body.get("status", "resolved")).strip()
            if msg_id:
                now_t = int(time.time())
                conn = DB()
                cur = conn
                cur.execute("UPDATE admin_messages SET status = ?, updated_at = ? WHERE id = ?", (new_status, now_t, msg_id))
                conn.commit()
                conn.close()
                return self.send_json({"ok": True, "id": msg_id, "status": new_status})
            return self.send_json({"ok": False, "error": "Thiếu ID tin nhắn"}, status=400)

        # POST /api/admin/inbox/delete (Delete Message)
        if path == "/api/admin/inbox/delete":
            msg_id = int(body.get("id", 0))
            if msg_id:
                conn = DB()
                cur = conn
                cur.execute("DELETE FROM admin_messages WHERE id = ?", (msg_id,))
                conn.commit()
                conn.close()
                return self.send_json({"ok": True, "id": msg_id})
            return self.send_json({"ok": False, "error": "Thiếu ID tin nhắn"}, status=400)

        if path == "/api/admin/config":
            payload = body.get("config", body)
            now_t = int(time.time())
            conn = DB()
            cur = conn
            for k, v in payload.items():
                if k in ("admin_code", "ok", "config"):
                    continue
                v_str = json.dumps(v)
                try:
                    cur.execute("""
                        INSERT INTO game_config (key, value, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                    """, (k, v_str, now_t))
                except Exception:
                    cur.execute("REPLACE INTO game_config (key, value, updated_at) VALUES (?, ?, ?)", (k, v_str, now_t))
            conn.commit()

            cur.execute("SELECT key, value FROM game_config")
            rows = cur.fetchall()
            conn.close()
            cfg = dict(DEFAULT_GAME_CONFIG)
            for r in rows:
                try:
                    cfg[r[0]] = json.loads(r[1])
                except Exception:
                    cfg[r[0]] = r[1]

            return self.send_json({
                "ok": True,
                "message": "Đã lưu cấu hình game thành công!",
                "config": cfg,
                "updated_at": now_t
            })

                # POST /api/admin/gift (Admin: Gift Money)
                # POST /api/admin/money/adjust (Admin: Money Management)
        if path == "/api/admin/money/adjust":
            target_type = str(body.get("target_type", "user")).strip()
            target_id = str(body.get("target_id", "")).strip()
            action = str(body.get("action", "add")).strip()
            amount = int(body.get("amount", 0))
            reason = str(body.get("reason", "")).strip()
            notify_player = body.get("notify_player", True)
            now_t = int(time.time())

            if not target_id or amount < 0:
                return self.send_json({"ok": False, "error": "Vui lòng nhập đối tượng và số tiền hợp lệ!"}, status=400)

            conn = DB()
            cur = conn
            old_money = 0
            new_money = 0
            display_name = target_id
            store_code = ""

            if target_type == "user":
                cur.execute("SELECT id, username, current_money, store_code FROM users WHERE LOWER(username) = ?", (target_id.lower(),))
                u_row = cur.fetchone()
                if not u_row:
                    conn.close()
                    return self.send_json({"ok": False, "error": "Không tìm thấy tài khoản: " + target_id}, status=404)
                display_name = u_row[1]
                old_money = int(u_row[2] or 400000)
                store_code = u_row[3] or ""

                if action == "add":
                    new_money = old_money + amount
                elif action == "deduct":
                    new_money = max(0, old_money - amount)
                else:
                    new_money = max(0, amount)

                cur.execute("UPDATE users SET current_money = ? WHERE LOWER(username) = ?", (new_money, target_id.lower()))

                cur.execute("SELECT save_data FROM user_saves WHERE LOWER(username) = ?", (target_id.lower(),))
                sv_row = cur.fetchone()
                if sv_row and sv_row[0]:
                    upd_save = update_save_data_money(sv_row[0], new_money)
                    cur.execute("UPDATE user_saves SET save_data = ?, updated_at = ? WHERE LOWER(username) = ?", (upd_save, now_t, target_id.lower()))
                    if store_code:
                        cur.execute("UPDATE cloud_saves SET save_data = ?, created_at = ? WHERE UPPER(code) = ?", (upd_save, now_t, store_code.upper()))

                if notify_player:
                    diff = new_money - old_money
                    if diff != 0:
                        is_add = diff > 0
                        title = "🎁 Cộng Tiền Vào Két Từ Admin" if is_add else "🏛️ Khấu Trừ Tiền Két Từ Admin"
                        default_msg = f"Admin đã cộng +{diff:,}đ vào két quán của bạn!" if is_add else f"Admin đã trừ -{abs(diff):,}đ khỏi két quán của bạn."
                        msg = (default_msg + " Lý do: " + reason) if reason else default_msg
                        cur.execute("""
                            INSERT INTO admin_gifts (target_type, target_id, target_name, store_code, amount, title, message, claimed, created_at)
                            VALUES ('user', ?, ?, ?, ?, ?, ?, 0, ?)
                        """, (target_id, display_name, store_code, diff, title, msg, now_t))

            else: # shop
                cur.execute("SELECT id, name, profit FROM leaderboard WHERE id = ?", (target_id,))
                s_row = cur.fetchone()
                if not s_row:
                    conn.close()
                    return self.send_json({"ok": False, "error": "Không tìm thấy quán mì: " + target_id}, status=404)
                display_name = s_row[1] or target_id
                old_money = int(s_row[2] or 0)

                if action == "add":
                    new_money = old_money + amount
                elif action == "deduct":
                    new_money = max(0, old_money - amount)
                else:
                    new_money = max(0, amount)

                cur.execute("UPDATE leaderboard SET profit = ?, updated_at = ? WHERE id = ?", (new_money, now_t, target_id))

                # Synchronize user account & save file
                matched_user = None
                user_save = None
                store_code = ""

                cur.execute("SELECT s.username, s.save_data, u.store_code FROM user_saves s LEFT JOIN users u ON LOWER(s.username) = LOWER(u.username)")
                all_saves = cur.fetchall()
                for s in all_saves:
                    if s[1] and s[1].startswith("MC2|"):
                        try:
                            parts = s[1].split("|")
                            dec = base64.b64decode(parts[1]).decode("utf-8")
                            obj = json.loads(dec)
                            if obj.get("pid") == target_id or (display_name and obj.get("shopName") == display_name) or s[0].lower() == target_id.lower():
                                matched_user = s[0]
                                user_save = s[1]
                                store_code = s[2] or obj.get("storeCode") or ""
                                break
                        except Exception:
                            pass

                if matched_user:
                    cur.execute("UPDATE users SET current_money = ? WHERE LOWER(username) = ?", (new_money, matched_user.lower()))
                    if user_save:
                        upd_save = update_save_data_money(user_save, new_money)
                        cur.execute("UPDATE user_saves SET save_data = ?, updated_at = ? WHERE LOWER(username) = ?", (upd_save, now_t, matched_user.lower()))
                        if store_code:
                            cur.execute("UPDATE cloud_saves SET save_data = ?, created_at = ? WHERE UPPER(code) = ?", (upd_save, now_t, store_code.upper()))

                    if notify_player:
                        diff = new_money - old_money
                        if diff != 0:
                            is_add = diff > 0
                            title = "🎁 Cộng Tiền Vào Két Từ Admin" if is_add else "🏛️ Khấu Trừ Tiền Két Từ Admin"
                            default_msg = f"Admin đã cộng +{diff:,}đ vào két quán! Tiền két hiện tại: {new_money:,}đ." if is_add else f"Admin đã trừ -{abs(diff):,}đ khỏi két quán! Tiền két hiện tại: {new_money:,}đ."
                            msg = (default_msg + " Lý do: " + reason) if reason else default_msg
                            cur.execute("""
                                INSERT INTO admin_gifts (target_type, target_id, target_name, store_code, amount, title, message, claimed, created_at)
                                VALUES ('user', ?, ?, ?, ?, ?, ?, 0, ?)
                            """, (matched_user, display_name, store_code, diff, title, msg, now_t))

                # Synchronize user account & save file
                matched_user = None
                user_save = None
                store_code = ""

                cur.execute("SELECT s.username, s.save_data, u.store_code FROM user_saves s LEFT JOIN users u ON LOWER(s.username) = LOWER(u.username)")
                all_saves = cur.fetchall()
                for s in all_saves:
                    if s[1] and s[1].startswith("MC2|"):
                        try:
                            parts = s[1].split("|")
                            dec = base64.b64decode(parts[1]).decode("utf-8")
                            obj = json.loads(dec)
                            if obj.get("pid") == target_id or (display_name and obj.get("shopName") == display_name) or s[0].lower() == target_id.lower():
                                matched_user = s[0]
                                user_save = s[1]
                                store_code = s[2] or obj.get("storeCode") or ""
                                break
                        except Exception:
                            pass

                if matched_user:
                    cur.execute("UPDATE users SET current_money = ? WHERE LOWER(username) = ?", (new_money, matched_user.lower()))
                    if user_save:
                        upd_save = update_save_data_money(user_save, new_money)
                        cur.execute("UPDATE user_saves SET save_data = ?, updated_at = ? WHERE LOWER(username) = ?", (upd_save, now_t, matched_user.lower()))
                        if store_code:
                            cur.execute("UPDATE cloud_saves SET save_data = ?, created_at = ? WHERE UPPER(code) = ?", (upd_save, now_t, store_code.upper()))

                    if notify_player:
                        diff = new_money - old_money
                        if diff != 0:
                            is_add = diff > 0
                            title = "🎁 Cộng Tiền Vào Két Từ Admin" if is_add else "🏛️ Khấu Trừ Tiền Két Từ Admin"
                            default_msg = f"Admin đã cộng +{diff:,}đ vào két quán! Tiền két hiện tại: {new_money:,}đ." if is_add else f"Admin đã trừ -{abs(diff):,}đ khỏi két quán! Tiền két hiện tại: {new_money:,}đ."
                            msg = (default_msg + " Lý do: " + reason) if reason else default_msg
                            cur.execute("""
                                INSERT INTO admin_gifts (target_type, target_id, target_name, store_code, amount, title, message, claimed, created_at)
                                VALUES ('user', ?, ?, ?, ?, ?, ?, 0, ?)
                            """, (matched_user, display_name, store_code, diff, title, msg, now_t))

            conn.commit()
            conn.close()
            return self.send_json({
                "ok": True,
                "action": action,
                "old_money": old_money,
                "new_money": new_money,
                "target_id": target_id,
                "display_name": display_name,
                "message": f"Đã cập nhật tiền két cho {display_name} thành {new_money:,}đ!"
            })

        if path == "/api/admin/gift":
            target_type = str(body.get("target_type", "user")).strip()
            target_id = str(body.get("target_id", "")).strip()
            target_name = str(body.get("target_name") or target_id).strip()
            store_code = str(body.get("store_code", "")).strip().upper()
            amount = int(body.get("amount", 0))
            title = str(body.get("title", "🎁 Quà Tặng Từ Ban Quản Trị")).strip()
            message = str(body.get("message", "Chúc quán bạn kinh doanh phát đạt!")).strip()
            now_t = int(time.time())

            if not target_id or amount <= 0:
                return self.send_json({"ok": False, "error": "Vui lòng nhập đối tượng và số tiền hợp lệ!"}, status=400)

            conn = DB()
            cur = conn
            cur.execute("""
                INSERT INTO admin_gifts (target_type, target_id, target_name, store_code, amount, title, message, claimed, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
            """, (target_type, target_id, target_name, store_code, amount, title, message, now_t))

            if target_type == "user":
                cur.execute("""
                    UPDATE users SET current_money = COALESCE(current_money, 400000) + ? WHERE LOWER(username) = ?
                """, (amount, target_id.lower()))
            elif target_type == "shop":
                cur.execute("""
                    UPDATE leaderboard SET profit = COALESCE(profit, 0) + ? WHERE id = ?
                """, (amount, target_id))

            conn.commit()
            conn.close()
            return self.send_json({
                "ok": True,
                "message": f"Đã gửi tặng thành công {amount:,}đ cho {target_name}!"
            })

        # POST /api/user/gift/claim
        if path == "/api/user/gift/claim":
            gift_id = int(body.get("id", 0))
            username = str(body.get("username", "")).strip().lower()
            shop_id = str(body.get("shop_id", "")).strip()
            store_code = str(body.get("store_code", "")).strip().upper()

            conn = DB()
            cur = conn
            if gift_id:
                cur.execute("UPDATE admin_gifts SET claimed = 1 WHERE id = ?", (gift_id,))
            if username:
                cur.execute("UPDATE admin_gifts SET claimed = 1 WHERE target_type = 'user' AND LOWER(target_id) = ?", (username,))
            if shop_id and shop_id != "guest":
                cur.execute("UPDATE admin_gifts SET claimed = 1 WHERE target_type = 'shop' AND target_id = ?", (shop_id,))
            if store_code:
                cur.execute("UPDATE admin_gifts SET claimed = 1 WHERE target_type = 'code' AND UPPER(store_code) = ?", (store_code,))
            conn.commit()
            conn.close()
            return self.send_json({"ok": True, "claimed_id": gift_id})

        if path == "/api/auth/register":
            username = str(body.get("username", "")).strip().lower()
            password = str(body.get("password", ""))
            confirm_password = str(body.get("confirmPassword", ""))

            if not username or len(username) < 3 or len(username) > 30:
                return self.send_json({"ok": False, "error": "Tên tài khoản phải từ 3 đến 30 ký tự!"}, status=400)
            if not password or len(password) < 6:
                return self.send_json({"ok": False, "error": "Mật khẩu tối thiểu phải từ 6 ký tự!"}, status=400)
            if password != confirm_password:
                return self.send_json({"ok": False, "error": "Mật khẩu nhập lại không khớp!"}, status=400)

            pwd_hash = hash_password(password)

            conn = DB()
            cur = conn
            cur.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cur.fetchone():
                conn.close()
                return self.send_json({"ok": False, "error": "Tên tài khoản này đã được sử dụng!"}, status=400)

            now_t = int(time.time())
            ua = self.headers.get("User-Agent", "")
            dev = "Mobile" if any(w in ua.lower() for w in ["iphone", "android", "mobile"]) else "Desktop"
            dev_str = f"{dev} ({ua[:50]})" if ua else dev

            cur.execute("""
                INSERT INTO users (username, password_hash, created_at, last_login_at, login_count, device_info, current_lv, current_day, current_money)
                VALUES (?, ?, ?, ?, 1, ?, 1, 1, 400000)
            """, (username, pwd_hash, now_t, now_t, dev_str))
            conn.commit()
            conn.close()

            return self.send_json({"ok": True, "username": username, "message": "Đăng ký tài khoản thành công!"})

        # AUTH: POST /api/auth/login
        if path == "/api/auth/login":
            username = str(body.get("username", "")).strip().lower()
            password = str(body.get("password", ""))

            if not username or not password:
                return self.send_json({"ok": False, "error": "Vui lòng nhập đầy đủ tài khoản và mật khẩu!"}, status=400)

            pwd_hash = hash_password(password)

            conn = DB()
            cur = conn
            cur.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
            row = cur.fetchone()

            if not row or row[0] != pwd_hash:
                conn.close()
                return self.send_json({"ok": False, "error": "Sai tài khoản hoặc mật khẩu!"}, status=400)

            now_t = int(time.time())
            ua = self.headers.get("User-Agent", "")
            dev = "Mobile" if any(w in ua.lower() for w in ["iphone", "android", "mobile"]) else "Desktop"
            dev_str = f"{dev} ({ua[:50]})" if ua else dev

            cur.execute("""
                UPDATE users SET last_login_at = ?, login_count = COALESCE(login_count, 0) + 1, device_info = ?
                WHERE username = ?
            """, (now_t, dev_str, username))
            conn.commit()

            # Check if user has an existing saved game
            cur.execute("SELECT save_data FROM user_saves WHERE username = ?", (username,))
            save_row = cur.fetchone()
            conn.close()

            return self.send_json({
                "ok": True,
                "username": username,
                "save": save_row[0] if save_row else None,
                "message": "Đăng nhập thành công!"
            })

        # AUTH: POST /api/auth/save
        if path == "/api/auth/save":
            username = str(body.get("username", "")).strip().lower()
            save_data = str(body.get("save", ""))

            if username and save_data:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                now_t = int(time.time())
                day_val = max(1, int(body.get("day", 1)))
                money_val = int(body.get("money", 400000))
                lv_val = max(1, min(50, int(body.get("lv", 1))))

                cur.execute('''
                    INSERT INTO user_saves (username, save_data, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(username) DO UPDATE SET
                        save_data = excluded.save_data,
                        updated_at = excluded.updated_at
                ''', (username, save_data, now_t))

                cur.execute("""
                    UPDATE users SET current_day = ?, current_money = ?, current_lv = ?, last_login_at = ?
                    WHERE username = ?
                """, (day_val, money_val, lv_val, now_t, username))

                conn.commit()
                conn.close()
                return self.send_json({"ok": True})
            return self.send_json({"ok": False}, status=400)
        body = self.read_json_body()

        # 1. POST /api/lb (Submit score to Leaderboard)
        if path == "/api/lb":
            shop_id = str(body.get("id", ""))[:32].strip()
            name = str(body.get("name", "Tiệm Mì Cay"))[:26].strip()
            try:
                profit = int(body.get("profit", 0))
                day = max(1, int(body.get("day", 1)))
                served = max(0, int(body.get("served", 0)))
                lv = max(1, min(50, int(body.get("lv", 1))))
                rate = max(1.0, min(5.0, float(body.get("rate", 5.0))))
            except (ValueError, TypeError):
                return self.send_json({"ok": False, "error": "Invalid data format"}, status=400)

            if shop_id:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute('''
                    INSERT INTO leaderboard (id, name, profit, day, served, lv, rate, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        profit = excluded.profit,
                        day = excluded.day,
                        served = excluded.served,
                        lv = excluded.lv,
                        rate = excluded.rate,
                        updated_at = excluded.updated_at
                ''', (shop_id, name, profit, day, served, lv, rate, int(time.time())))
                conn.commit()

                # Get updated rank
                cur.execute('SELECT COUNT(*) FROM leaderboard WHERE profit > ?', (profit,))
                rank = cur.fetchone()[0] + 1
                cur.execute('SELECT COUNT(*) FROM leaderboard')
                total = cur.fetchone()[0]

                cur.execute('''
                    SELECT id, name, profit, day, served, lv, rate
                    FROM leaderboard
                    ORDER BY profit DESC
                    LIMIT 50
                ''')
                top = [{"id": r[0], "name": r[1], "profit": r[2], "day": r[3], "served": r[4], "lv": r[5], "rate": r[6]} for r in cur.fetchall()]
                conn.close()

                return self.send_json({
                    "ok": True,
                    "rank": rank,
                    "total": total,
                    "top": top
                })
            return self.send_json({"ok": False}, status=400)

        # 2. POST /api/chal (Tournament challenge actions)
        if path == "/api/chal":
            op = body.get("op")
            if op == "claim-reward":
                shop_id = body.get("id", "").strip()
                week_key = body.get("week_key", "").strip()
                if shop_id and week_key:
                    conn = DB()
                    cur = conn
                    cur.execute("SELECT id, claimed_shops, reward_money, rank FROM weekly_hall_of_fame WHERE week_key = ? AND shop_id = ?", (week_key, shop_id))
                    r = cur.fetchone()
                    if r:
                        claimed = [x for x in (r[1] or "").split(",") if x]
                        if shop_id not in claimed:
                            claimed.append(shop_id)
                            cur.execute("UPDATE weekly_hall_of_fame SET claimed_shops = ? WHERE id = ?", (",".join(claimed), r[0]))
                            conn.commit()
                            conn.close()
                            return self.send_json({"ok": True, "rank": r[3], "reward_money": r[2]})
                    conn.close()
                return self.send_json({"ok": True})

            chal_day = get_today_chal_date()
            conn = DB()
            cur = conn

            # Start challenge round
            if op == "start":
                shop_id = body.get("id", "guest")
                token = "tok_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=16))
                cur.execute('SELECT COUNT(*) FROM challenges WHERE day = ? AND id = ?', (chal_day, shop_id))
                round_num = cur.fetchone()[0] + 1

                cur.execute('''
                    INSERT INTO challenge_tokens (token, id, day, n, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (token, shop_id, chal_day, round_num, int(time.time())))
                conn.commit()
                conn.close()

                # Flat response for start
                return self.send_json({
                    "day": chal_day,
                    "n": round_num,
                    "token": token
                })

            # Submit challenge result
            token = body.get("token")
            score = int(body.get("score", 0))
            served = int(body.get("served", 0))
            perfect = int(body.get("perfect", 0))
            wrong = int(body.get("wrong", 0))
            lost = int(body.get("lost", 0))

            cur.execute('SELECT id, day FROM challenge_tokens WHERE token = ?', (token,))
            tok_row = cur.fetchone()
            shop_id = tok_row[0] if tok_row else "guest"

            cur.execute('''
                INSERT INTO challenges (id, day, score, served, perfect, wrong, lost, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (shop_id, chal_day, score, served, perfect, wrong, lost, int(time.time())))
            conn.commit()

            # Calculate rank
            cur.execute('SELECT COUNT(DISTINCT id) FROM challenges WHERE day = ? AND score > ?', (chal_day, score))
            rank = cur.fetchone()[0] + 1
            cur.execute('SELECT COUNT(DISTINCT id) FROM challenges WHERE day = ?', (chal_day,))
            total = cur.fetchone()[0]
            conn.close()

            cur.execute('SELECT SUM(score) FROM challenges WHERE day = ? AND id = ?', (chal_day, shop_id))
            best = cur.fetchone()[0] or score
            cur.execute('SELECT COUNT(*) FROM challenges WHERE day = ? AND id = ?', (chal_day, shop_id))
            rounds_done = cur.fetchone()[0] or 1
            left = max(0, 3 - rounds_done)

            cur.execute('''
                SELECT COUNT(*) FROM (
                    SELECT id, SUM(score) as tot FROM challenges
                    WHERE day = ?
                    GROUP BY id HAVING tot > ?
                )
            ''', (chal_day, best))
            day_rank = cur.fetchone()[0] + 1
            cur.execute('SELECT COUNT(DISTINCT id) FROM challenges WHERE day = ?', (chal_day,))
            day_total = cur.fetchone()[0]

            start_sec, end_sec, week_key, week_title = get_week_bounds()
            cur.execute('''
                SELECT SUM(score) FROM challenges
                WHERE created_at >= ? AND created_at <= ? AND id = ?
            ''', (start_sec, end_sec, shop_id))
            wbest = cur.fetchone()[0] or best
            cur.execute('''
                SELECT COUNT(*) FROM (
                    SELECT id, SUM(score) as tot FROM challenges
                    WHERE created_at >= ? AND created_at <= ?
                    GROUP BY id HAVING tot > ?
                )
            ''', (start_sec, end_sec, wbest))
            wrank = cur.fetchone()[0] + 1
            conn.close()

            return self.send_json({
                "ok": True,
                "rank": day_rank,
                "total": max(1, day_total),
                "best": best,
                "wbest": wbest,
                "wrank": wrank,
                "left": left
            })

        # 3. POST /api/sync (Upload save state to cloud)
        if path == "/api/sync":
            save_data = body.get("s", "")
            if save_data:
                code = generate_sync_code()
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute('''
                    INSERT INTO cloud_saves (code, save_data, created_at)
                    VALUES (?, ?, ?)
                ''', (code, save_data, int(time.time())))
                conn.commit()
                conn.close()
                return self.send_json({"code": code})
            return self.send_json({"error": "No save data"}, status=400)

        # 4. POST /api/prank
        if path == "/api/prank":
            op = body.get("op")
            conn = DB()
            cur = conn

            if op == "send":
                from_id = body.get("from")
                to_id = body.get("to")
                kind = body.get("k", "flower")

                cur.execute('SELECT name FROM leaderboard WHERE id = ?', (from_id,))
                f_name = cur.fetchone()
                from_name = f_name[0] if f_name else "Quán bạn"

                cur.execute('SELECT name FROM leaderboard WHERE id = ?', (to_id,))
                t_name = cur.fetchone()
                to_name = t_name[0] if t_name else "Quán bạn"

                cur.execute('''
                    INSERT INTO pranks (from_id, from_name, to_id, kind, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (from_id, from_name, to_id, kind, int(time.time())))
                conn.commit()
                conn.close()
                return self.send_json({"name": to_name})

            if op == "take":
                shop_id = body.get("id")
                cur.execute('''
                    SELECT from_id, from_name, kind FROM pranks
                    WHERE to_id = ? AND taken = 0
                ''', (shop_id,))
                rows = cur.fetchall()
                cur.execute('UPDATE pranks SET taken = 1 WHERE to_id = ?', (shop_id,))
                conn.commit()
                conn.close()

                gifts = [{"f": r[0], "n": r[1], "k": r[2]} for r in rows]
                return self.send_json({"gifts": gifts})

            conn.close()
            return self.send_json({"error": "Invalid operation"}, status=400)

        # 5. POST /api/ai (AI Customer response generator)
        if path == "/api/ai":
            reply_type = body.get("type", "kind")
            cust_name = body.get("n", "Khách")

            replies = {
                "apology": [
                    f"{cust_name} mỉm cười: 'Dạ quán chu đáo quá, em nhận voucher nha, bữa sau em lại ghé!'",
                    f"{cust_name}: 'Thấy quán có tâm sửa sai vậy là vui rồi, em cho lại 5 sao nha!'",
                    f"{cust_name}: 'Quán nhiệt tình ghê, lần sau nhớ làm đúng cho em nhé!'"
                ],
                "humor": [
                    f"{cust_name} bật cười: 'Haha chủ quán mặn ghê, thôi hết giận rồi, mai ghé ăn tiếp!'",
                    f"{cust_name}: 'Nói chuyện duyên dữ thần, đành phải quay lại ủng hộ thôi!'",
                    f"{cust_name}: 'Thôi được rồi, vì nụ cười của chủ quán em đổi thành 5 sao nè!'"
                ],
                "sharp": [
                    f"{cust_name} đáp: 'Ủa quán đanh đá vậy luôn? Nhưng thôi mì ngon nên bỏ qua đó!'",
                    f"{cust_name}: 'Chủ quán cá tính quá trời, mai em rủ bạn qua kiểm chứng lần nữa!'",
                    f"{cust_name}: 'Bị bắt bẻ mà thấy cưng ghê, 5 sao cho sự thẳng thắn!'"
                ]
            }
            category = "apology" if "xin lỗi" in str(body).lower() or "voucher" in str(body).lower() else "humor"
            selected_reply = random.choice(replies.get(category, replies["apology"]))

            return self.send_json({
                "ok": True,
                "text": selected_reply,
                "fixStar": True
            })

        # 6. POST /api/err & /api/copy
        if path in ["/api/err", "/api/copy"]:
            return self.send_json({"ok": True})

        # 7. POST /api/admin/player/delete
        if path == "/api/admin/player/delete":
            player_id = body.get("id")
            if player_id:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute('DELETE FROM leaderboard WHERE id = ?', (player_id,))
                conn.commit()
                conn.close()
                return self.send_json({"ok": True})
            return self.send_json({"error": "Missing player id"}, status=400)

        # 8. POST /api/admin/save/delete
        if path == "/api/admin/save/delete":
            save_code = body.get("code")
            if save_code:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute('DELETE FROM cloud_saves WHERE code = ?', (save_code,))
                conn.commit()
                conn.close()
                return self.send_json({"ok": True})
            return self.send_json({"error": "Missing save code"}, status=400)
        # POST /api/admin/user/delete
        if path.startswith("/api/admin"):
            adm_code = self.headers.get("X-Admin-Code") or body.get("admin_code", "")
            if adm_code != "09659":
                return self.send_json({"error": "Yêu cầu mã code quản trị 09659!"}, status=401)
        if path == "/api/admin/user/delete":
            username = str(body.get("username", "")).strip().lower()
            if username:
                conn = DB()
                cur = conn
                cur.execute("DELETE FROM users WHERE username = ?", (username,))
                cur.execute("DELETE FROM user_saves WHERE username = ?", (username,))
                conn.commit()
                conn.close()
                return self.send_json({"ok": True})
            return self.send_json({"error": "Missing username"}, status=400)

        # POST /api/admin/user/reset-password
        if path == "/api/admin/user/reset-password":
            username = str(body.get("username", "")).strip().lower()
            new_pwd = str(body.get("newPassword", "")).strip()
            if username and len(new_pwd) >= 6:
                pwd_hash = hash_password(new_pwd)
                conn = DB()
                cur = conn
                cur.execute("UPDATE users SET password_hash = ? WHERE username = ?", (pwd_hash, username))
                conn.commit()
                conn.close()
                return self.send_json({"ok": True})
            return self.send_json({"error": "Mật khẩu tối thiểu 6 ký tự!"}, status=400)


        return self.send_json({"error": "Endpoint not found"}, status=404)

if __name__ == "__main__":
    Handler = GameServerHandler
    socketserver.TCPServer.allow_reuse_address = True
    print(f"[STARTING] Tiem Mi Cay Backend Server on http://localhost:{PORT}")
    with socketserver.ThreadingTCPServer(("", PORT), Handler) as httpd:
        print(f"[READY] Server running at port {PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[STOPPED] Server stopped.")
