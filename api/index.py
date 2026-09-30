# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler
import os
import sys
import json
import sqlite3
import random
import string
import time
import shutil
from urllib.parse import urlparse, parse_qs
from datetime import datetime

IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("NOW_REGION"))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if IS_VERCEL:
    DATA_DIR = "/tmp/data"
    DB_PATH = os.path.join(DATA_DIR, "tiemmicay.db")
else:
    DATA_DIR = os.path.join(BASE_DIR, "data")
    DB_PATH = os.path.join(DATA_DIR, "tiemmicay.db")

os.makedirs(DATA_DIR, exist_ok=True)

# Copy template db if exists and not present in /tmp
ORIG_DB = os.path.join(BASE_DIR, "data", "tiemmicay.db")
if IS_VERCEL and os.path.exists(ORIG_DB) and not os.path.exists(DB_PATH):
    try:
        shutil.copy2(ORIG_DB, DB_PATH)
    except Exception:
        pass

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS leaderboard (
            id TEXT PRIMARY KEY,
            name TEXT,
            profit INTEGER,
            day INTEGER,
            served INTEGER,
            lv INTEGER,
            rate REAL,
            updated_at INTEGER
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS challenges (
            id TEXT,
            day TEXT,
            score INTEGER,
            served INTEGER,
            perfect INTEGER,
            wrong INTEGER,
            lost INTEGER,
            created_at INTEGER
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS challenge_tokens (
            token TEXT PRIMARY KEY,
            id TEXT,
            day TEXT,
            n INTEGER,
            created_at INTEGER
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS cloud_saves (
            code TEXT PRIMARY KEY,
            save_data TEXT,
            created_at INTEGER
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS pranks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id TEXT,
            from_name TEXT,
            to_id TEXT,
            kind TEXT,
            taken INTEGER DEFAULT 0,
            created_at INTEGER
        )
    ''')

    cur.execute('SELECT COUNT(*) FROM leaderboard')
    if cur.fetchone()[0] == 0:
        seed_shops = [
            ("vua_mi_cay_vip", "Vua Mì Cay Hoàng Gia", 18500000, 25, 485, 10, 5.0, int(time.time())),
            ("sasin_01", "Mì Cay Sasin Phố", 14500000, 18, 220, 9, 4.9, int(time.time())),
            ("seoul_02", "Tiệm Mì Cay Seoul", 9800000, 14, 160, 8, 4.8, int(time.time())),
            ("nha_cao", "Mì Cay Nhà Cáo", 6200000, 10, 115, 6, 4.9, int(time.time())),
            ("be_ot_04", "Tiệm Mì Bé Ớt", 3800000, 7, 85, 5, 4.7, int(time.time())),
            ("co_ba_05", "Quán Mì Cô Ba", 1950000, 4, 45, 3, 4.6, int(time.time()))
        ]
        cur.executemany('''
            INSERT INTO leaderboard (id, name, profit, day, served, lv, rate, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', seed_shops)

    conn.commit()
    conn.close()

init_db()

def get_today_chal_date():
    now = datetime.now()
    return f"{now.day}/{now.month}"

def generate_sync_code():
    chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    part1 = ''.join(random.choices(chars, k=4))
    part2 = ''.join(random.choices(chars, k=4))
    return f"{part1}-{part2}"

class handler(BaseHTTPRequestHandler):
    def end_headers(self):
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
            if 0 < content_length <= 1048576:
                raw = self.rfile.read(content_length).decode("utf-8")
                return json.loads(raw)
        except Exception:
            pass
        return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # GET /api/lb
        if path == "/api/lb":
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
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

            top = [{"id": r[0], "name": r[1], "profit": r[2], "day": r[3], "served": r[4], "lv": r[5], "rate": r[6]} for r in rows]
            return self.send_json({"ok": True, "top": top, "total": total, "cups": {"vua_mi_cay_vip": 1, "sasin_01": 2}})

        # GET /api/chal
        if path == "/api/chal":
            shop_id = params.get("id", [""])[0]
            chal_day = get_today_chal_date()
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()

            cur.execute('''
                SELECT id, MAX(score) as best_score
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

            cur.execute('SELECT COUNT(*), MAX(score) FROM challenges WHERE day = ? AND id = ?', (chal_day, shop_id))
            me_row = cur.fetchone()
            rounds_done = me_row[0] if me_row else 0
            best_score = me_row[1] if me_row and me_row[1] else 0

            cur.execute('SELECT COUNT(DISTINCT id) FROM challenges WHERE day = ? AND score > ?', (chal_day, best_score))
            rank = cur.fetchone()[0] + 1 if best_score > 0 else 0

            cur.execute('SELECT COUNT(DISTINCT id) FROM challenges WHERE day = ?', (chal_day,))
            total_players = max(len(top), cur.fetchone()[0])
            conn.close()

            return self.send_json({
                "day": chal_day,
                "top": top,
                "me": {"left": max(0, 3 - rounds_done), "best": best_score, "rank": rank},
                "total": max(1, total_players)
            })

        # GET /api/sync
        if path == "/api/sync":
            code = params.get("code", [""])[0].strip().upper()
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute('SELECT save_data, created_at FROM cloud_saves WHERE code = ?', (code,))
            row = cur.fetchone()
            conn.close()

            if row and (int(time.time()) - row[1] < 86400):
                return self.send_json({"s": row[0]})
            return self.send_json({"error": "Mã không đúng hoặc đã hết hạn"}, status=404)

        # GET /api/prank
        if path == "/api/prank":
            shop_id = params.get("id", [""])[0]
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute('SELECT id, name, day, lv FROM leaderboard WHERE id != ? ORDER BY updated_at DESC LIMIT 15', (shop_id,))
            near = [{"id": r[0], "name": r[1], "day": r[2], "lv": r[3]} for r in cur.fetchall()]
            conn.close()

            return self.send_json({"left": 3, "sent": [], "near": near})

        # GET /api/admin/overview
        if path == "/api/admin/overview":
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
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
                pranks.append({"from_name": pr[0], "to_name": to_name, "kind": pr[2], "taken": pr[3], "created_at": pr[4]})
            conn.close()

            return self.send_json({"ok": True, "savesCount": saves_count, "saves": saves, "pranks": pranks})

        return self.send_json({"error": "Not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self.read_json_body()

        # POST /api/lb
        if path == "/api/lb":
            shop_id = str(body.get("id", ""))[:32].strip()
            name = str(body.get("name", "Tiệm Mì Cay"))[:26].strip()
            try:
                profit = int(body.get("profit", 0))
                day = max(1, int(body.get("day", 1)))
                served = max(0, int(body.get("served", 0)))
                lv = max(1, min(10, int(body.get("lv", 1))))
                rate = max(1.0, min(5.0, float(body.get("rate", 5.0))))
            except (ValueError, TypeError):
                return self.send_json({"ok": False, "error": "Invalid format"}, status=400)

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

                cur.execute('SELECT COUNT(*) FROM leaderboard WHERE profit > ?', (profit,))
                rank = cur.fetchone()[0] + 1
                cur.execute('SELECT COUNT(*) FROM leaderboard')
                total = cur.fetchone()[0]

                cur.execute('SELECT id, name, profit, day, served, lv, rate FROM leaderboard ORDER BY profit DESC LIMIT 50')
                top = [{"id": r[0], "name": r[1], "profit": r[2], "day": r[3], "served": r[4], "lv": r[5], "rate": r[6]} for r in cur.fetchall()]
                conn.close()

                return self.send_json({"ok": True, "rank": rank, "total": total, "top": top})
            return self.send_json({"ok": False}, status=400)

        # POST /api/chal
        if path == "/api/chal":
            op = body.get("op")
            chal_day = get_today_chal_date()
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()

            if op == "start":
                shop_id = body.get("id", "guest")
                token = "tok_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=16))
                cur.execute('SELECT COUNT(*) FROM challenges WHERE day = ? AND id = ?', (chal_day, shop_id))
                round_num = cur.fetchone()[0] + 1

                cur.execute('INSERT INTO challenge_tokens (token, id, day, n, created_at) VALUES (?, ?, ?, ?, ?)', (token, shop_id, chal_day, round_num, int(time.time())))
                conn.commit()
                conn.close()
                return self.send_json({"day": chal_day, "n": round_num, "token": token})

            token = body.get("token")
            score = int(body.get("score", 0))
            served = int(body.get("served", 0))
            perfect = int(body.get("perfect", 0))
            wrong = int(body.get("wrong", 0))
            lost = int(body.get("lost", 0))

            cur.execute('SELECT id, day FROM challenge_tokens WHERE token = ?', (token,))
            tok_row = cur.fetchone()
            shop_id = tok_row[0] if tok_row else "guest"

            cur.execute('INSERT INTO challenges (id, day, score, served, perfect, wrong, lost, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (shop_id, chal_day, score, served, perfect, wrong, lost, int(time.time())))
            conn.commit()

            cur.execute('SELECT COUNT(DISTINCT id) FROM challenges WHERE day = ? AND score > ?', (chal_day, score))
            rank = cur.fetchone()[0] + 1
            cur.execute('SELECT COUNT(DISTINCT id) FROM challenges WHERE day = ?', (chal_day,))
            total = cur.fetchone()[0]
            conn.close()

            return self.send_json({"rank": rank, "total": max(1, total)})

        # POST /api/sync
        if path == "/api/sync":
            save_data = body.get("s", "")
            if save_data:
                code = generate_sync_code()
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute('INSERT INTO cloud_saves (code, save_data, created_at) VALUES (?, ?, ?)', (code, save_data, int(time.time())))
                conn.commit()
                conn.close()
                return self.send_json({"code": code})
            return self.send_json({"error": "No save data"}, status=400)

        # POST /api/prank
        if path == "/api/prank":
            op = body.get("op")
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()

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

                cur.execute('INSERT INTO pranks (from_id, from_name, to_id, kind, created_at) VALUES (?, ?, ?, ?, ?)', (from_id, from_name, to_id, kind, int(time.time())))
                conn.commit()
                conn.close()
                return self.send_json({"name": to_name})

            if op == "take":
                shop_id = body.get("id")
                cur.execute('SELECT from_id, from_name, kind FROM pranks WHERE to_id = ? AND taken = 0', (shop_id,))
                rows = cur.fetchall()
                cur.execute('UPDATE pranks SET taken = 1 WHERE to_id = ?', (shop_id,))
                conn.commit()
                conn.close()

                gifts = [{"f": r[0], "n": r[1], "k": r[2]} for r in rows]
                return self.send_json({"gifts": gifts})

            conn.close()
            return self.send_json({"error": "Invalid operation"}, status=400)

        # POST /api/ai
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
                ]
            }
            category = "apology" if "xin lỗi" in str(body).lower() or "voucher" in str(body).lower() else "humor"
            selected_reply = random.choice(replies.get(category, replies["apology"]))
            return self.send_json({"ok": True, "text": selected_reply, "fixStar": True})

        # POST /api/err & /api/copy
        if path in ["/api/err", "/api/copy"]:
            return self.send_json({"ok": True})

        # POST /api/admin/player/delete
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

        # POST /api/admin/save/delete
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

        return self.send_json({"error": "Endpoint not found"}, status=404)
