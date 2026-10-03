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

        # 1. GET /api/lb (Leaderboard)
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
            shop_id = params.get("id", [""])[0]
            chal_day = get_today_chal_date()
            start_sec, end_sec, week_key, week_title = get_week_bounds()
            conn = DB()
            cur = conn

            # Top scores for today's challenge
            cur.execute('''
                SELECT id, MAX(score) as best_score, COUNT(*) as rounds
                FROM challenges
                WHERE day = ?
                GROUP BY id
                ORDER BY best_score DESC
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
                SELECT COUNT(*), MAX(score)
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

        # AUTH: POST /api/auth/register
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

            # Flat response for submit
            return self.send_json({
                "rank": rank,
                "total": max(1, total)
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
