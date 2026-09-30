// -*- coding: utf-8 -*-
const crypto = require("crypto");
const { neon } = require("@neondatabase/serverless");

const DEFAULT_NEON_URL = "postgresql://neondb_owner:npg_SCxPc8WBwy7Q@ep-small-bird-b3izwjr0-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb?channel_binding=require&sslmode=require";

function getDbUrl() {
  return process.env.DATABASE_URL || process.env.POSTGRES_URL || DEFAULT_NEON_URL;
}

function hashPassword(password) {
  return crypto.createHash("sha256").update("tiemMiCayAuth$" + password).digest("hex");
}

function getTodayChalDate() {
  const now = new Date();
  return `${now.getDate()}/${now.getMonth() + 1}`;
}

function generateSyncCode() {
  const chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ";
  let p1 = "", p2 = "";
  for (let i = 0; i < 4; i++) p1 += chars[Math.floor(Math.random() * chars.length)];
  for (let i = 0; i < 4; i++) p2 += chars[Math.floor(Math.random() * chars.length)];
  return `${p1}-${p2}`;
}

module.exports = async (req, res) => {
  // CORS & Security headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "SAMEORIGIN");
  res.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");

  if (req.method === "OPTIONS") {
    return res.status(204).end();
  }

  const urlObj = new URL(req.url, `https://${req.headers.host || "localhost"}`);
  let path = urlObj.pathname;
  if (urlObj.searchParams.has("path")) {
    path = "/api/" + urlObj.searchParams.get("path");
  }

  const dbUrl = getDbUrl();
  if (!dbUrl) {
    return res.status(500).json({ error: "Chưa cấu hình DATABASE_URL trên Vercel" });
  }

  const sql = neon(dbUrl);

  // Parse body if needed
  let body = req.body || {};
  if (typeof body === "string") {
    try { body = JSON.parse(body); } catch (e) { body = {}; }
  }

  try {
    // ----------------- GET ENDPOINTS -----------------
    if (req.method === "GET") {
      // 1. GET /api/lb
      if (path === "/api/lb") {
        const top = await sql`
          SELECT id, name, CAST(profit AS FLOAT) as profit, day, served, lv, CAST(rate AS FLOAT) as rate
          FROM leaderboard
          ORDER BY profit DESC
          LIMIT 50
        `;
        const countRes = await sql`SELECT count(*) FROM leaderboard`;
        const total = Number(countRes[0]?.count || top.length);
        return res.json({
          ok: true,
          top,
          total,
          cups: { vua_mi_cay_vip: 1, sasin_01: 2 }
        });
      }

      // 2. GET /api/chal
      if (path === "/api/chal") {
        const shopId = urlObj.searchParams.get("id") || "";
        const chalDay = getTodayChalDate();

        const topRows = await sql`
          SELECT id, MAX(score) as s
          FROM challenges
          WHERE day = ${chalDay}
          GROUP BY id
          ORDER BY s DESC
          LIMIT 20
        `;

        const top = [];
        for (const r of topRows) {
          const nameRows = await sql`SELECT name FROM leaderboard WHERE id = ${r.id}`;
          top.push({ id: r.id, name: nameRows[0]?.name || "Chủ quán ẩn danh", s: Number(r.s) });
        }

        const meRows = await sql`
          SELECT count(*) as rounds, MAX(score) as best
          FROM challenges
          WHERE day = ${chalDay} AND id = ${shopId}
        `;
        const roundsDone = Number(meRows[0]?.rounds || 0);
        const bestScore = Number(meRows[0]?.best || 0);

        let rank = 0;
        if (bestScore > 0) {
          const rankRows = await sql`
            SELECT count(DISTINCT id) as cnt
            FROM challenges
            WHERE day = ${chalDay} AND score > ${bestScore}
          `;
          rank = Number(rankRows[0]?.cnt || 0) + 1;
        }

        const totalRows = await sql`SELECT count(DISTINCT id) as cnt FROM challenges WHERE day = ${chalDay}`;
        const total = Math.max(top.length, Number(totalRows[0]?.cnt || 1));

        return res.json({
          day: chalDay,
          top,
          me: {
            left: Math.max(0, 3 - roundsDone),
            best: bestScore,
            rank
          },
          total
        });
      }

      // 3. GET /api/sync
      if (path === "/api/sync") {
        const code = (urlObj.searchParams.get("code") || "").trim().toUpperCase();
        const rows = await sql`SELECT save_data, created_at FROM cloud_saves WHERE code = ${code}`;
        if (rows.length && (Math.floor(Date.now() / 1000) - Number(rows[0].created_at) < 86400)) {
          return res.json({ s: rows[0].save_data });
        }
        return res.status(404).json({ error: "Mã không đúng hoặc đã hết hạn" });
      }

      // 4. GET /api/prank
      if (path === "/api/prank") {
        const shopId = urlObj.searchParams.get("id") || "";
        const near = await sql`
          SELECT id, name, day, lv
          FROM leaderboard
          WHERE id != ${shopId}
          ORDER BY updated_at DESC
          LIMIT 15
        `;
        return res.json({ left: 3, sent: [], near });
      }

      // 5. GET /api/auth/save
      if (path === "/api/auth/save") {
        const username = (urlObj.searchParams.get("username") || "").trim().toLowerCase();
        if (username) {
          const rows = await sql`SELECT save_data FROM user_saves WHERE LOWER(username) = ${username}`;
          if (rows.length) {
            return res.json({ ok: true, save: rows[0].save_data });
          }
        }
        return res.status(404).json({ ok: false });
      }

      // 6. GET /api/admin/users
      if (path === "/api/admin/users") {
        const rows = await sql`
          SELECT u.id, u.username, u.created_at, u.last_login_at, u.login_count,
                 u.device_info, u.current_lv, u.current_day, CAST(u.current_money AS FLOAT) as current_money,
                 (s.save_data IS NOT NULL) as has_save
          FROM users u
          LEFT JOIN user_saves s ON LOWER(u.username) = LOWER(s.username)
          ORDER BY u.last_login_at DESC, u.created_at DESC
          LIMIT 100
        `;
        const countRes = await sql`SELECT count(*) FROM users`;
        const total = Number(countRes[0]?.count || rows.length);

        const users = rows.map(r => ({
          id: r.id,
          username: r.username,
          created_at: Number(r.created_at),
          last_login_at: Number(r.last_login_at || 0),
          login_count: Number(r.login_count || 1),
          device_info: r.device_info || "Desktop",
          lv: Number(r.current_lv || 1),
          day: Number(r.current_day || 1),
          money: Number(r.current_money || 400000),
          has_save: Boolean(r.has_save)
        }));

        return res.json({ ok: true, users, total });
      }

      // 7. GET /api/admin/overview
      if (path === "/api/admin/overview") {
        const saves = await sql`
          SELECT code, LENGTH(save_data) as size, created_at
          FROM cloud_saves
          ORDER BY created_at DESC
          LIMIT 30
        `;
        const countSaves = await sql`SELECT count(*) FROM cloud_saves`;

        const prankRows = await sql`
          SELECT from_name, to_id, kind, taken, created_at
          FROM pranks
          ORDER BY created_at DESC
          LIMIT 30
        `;
        const pranks = [];
        for (const pr of prankRows) {
          const toNameRows = await sql`SELECT name FROM leaderboard WHERE id = ${pr.to_id}`;
          pranks.push({
            from_name: pr.from_name,
            to_name: toNameRows[0]?.name || pr.to_id,
            kind: pr.kind,
            taken: pr.taken,
            created_at: Number(pr.created_at)
          });
        }

        return res.json({
          ok: true,
          savesCount: Number(countSaves[0]?.count || saves.length),
          saves: saves.map(s => ({ code: s.code, size: Number(s.size), created_at: Number(s.created_at) })),
          pranks
        });
      }
    }

    // ----------------- POST ENDPOINTS -----------------
    if (req.method === "POST") {
      // 1. POST /api/auth/register
      if (path === "/api/auth/register") {
        const username = String(body.username || "").trim().toLowerCase();
        const password = String(body.password || "");
        const confirmPassword = String(body.confirmPassword || "");

        if (!username || username.length < 3 || username.length > 30) {
          return res.status(400).json({ ok: false, error: "Tên tài khoản phải từ 3 đến 30 ký tự!" });
        }
        if (!password || password.length < 6) {
          return res.status(400).json({ ok: false, error: "Mật khẩu tối thiểu phải từ 6 ký tự!" });
        }
        if (password !== confirmPassword) {
          return res.status(400).json({ ok: false, error: "Mật khẩu nhập lại không khớp!" });
        }

        const existing = await sql`SELECT id FROM users WHERE LOWER(username) = ${username}`;
        if (existing.length) {
          return res.status(400).json({ ok: false, error: "Tên tài khoản này đã được sử dụng!" });
        }

        const pwdHash = hashPassword(password);
        const nowT = Math.floor(Date.now() / 1000);
        const ua = req.headers["user-agent"] || "";
        const dev = /iphone|android|mobile/i.test(ua) ? "Mobile" : "Desktop";
        const devStr = ua ? `${dev} (${ua.slice(0, 45)})` : dev;

        await sql`
          INSERT INTO users (username, password_hash, created_at, last_login_at, login_count, device_info, current_lv, current_day, current_money)
          VALUES (${username}, ${pwdHash}, ${nowT}, ${nowT}, 1, ${devStr}, 1, 1, 400000)
        `;

        return res.json({ ok: true, username, message: "Đăng ký tài khoản thành công!" });
      }

      // 2. POST /api/auth/login
      if (path === "/api/auth/login") {
        const username = String(body.username || "").trim().toLowerCase();
        const password = String(body.password || "");

        if (!username || !password) {
          return res.status(400).json({ ok: false, error: "Vui lòng nhập đầy đủ tài khoản và mật khẩu!" });
        }

        const pwdHash = hashPassword(password);
        const userRows = await sql`SELECT password_hash FROM users WHERE LOWER(username) = ${username}`;

        if (!userRows.length || userRows[0].password_hash !== pwdHash) {
          return res.status(400).json({ ok: false, error: "Sai tài khoản hoặc mật khẩu!" });
        }

        const nowT = Math.floor(Date.now() / 1000);
        const ua = req.headers["user-agent"] || "";
        const dev = /iphone|android|mobile/i.test(ua) ? "Mobile" : "Desktop";
        const devStr = ua ? `${dev} (${ua.slice(0, 45)})` : dev;

        await sql`
          UPDATE users
          SET last_login_at = ${nowT}, login_count = COALESCE(login_count, 0) + 1, device_info = ${devStr}
          WHERE LOWER(username) = ${username}
        `;

        const saveRows = await sql`SELECT save_data FROM user_saves WHERE LOWER(username) = ${username}`;

        return res.json({
          ok: true,
          username,
          save: saveRows[0]?.save_data || null,
          message: "Đăng nhập thành công!"
        });
      }

      // 3. POST /api/auth/save
      if (path === "/api/auth/save") {
        const username = String(body.username || "").trim().toLowerCase();
        const saveData = String(body.save || "");
        const dayVal = Math.max(1, parseInt(body.day, 10) || 1);
        const moneyVal = parseInt(body.money, 10) || 400000;
        const lvVal = Math.max(1, Math.min(10, parseInt(body.lv, 10) || 1));
        const nowT = Math.floor(Date.now() / 1000);

        if (username && saveData) {
          await sql`
            INSERT INTO user_saves (username, save_data, updated_at)
            VALUES (${username}, ${saveData}, ${nowT})
            ON CONFLICT(username) DO UPDATE SET
              save_data = EXCLUDED.save_data,
              updated_at = EXCLUDED.updated_at
          `;

          await sql`
            UPDATE users
            SET current_day = ${dayVal}, current_money = ${moneyVal}, current_lv = ${lvVal}, last_login_at = ${nowT}
            WHERE LOWER(username) = ${username}
          `;

          return res.json({ ok: true });
        }
        return res.status(400).json({ ok: false });
      }

      // 4. POST /api/lb
      if (path === "/api/lb") {
        const shopId = String(body.id || "").slice(0, 32).trim();
        const name = String(body.name || "Tiệm Mì Cay").slice(0, 26).trim();
        const profit = parseInt(body.profit, 10) || 0;
        const day = Math.max(1, parseInt(body.day, 10) || 1);
        const served = Math.max(0, parseInt(body.served, 10) || 0);
        const lv = Math.max(1, Math.min(10, parseInt(body.lv, 10) || 1));
        const rate = Math.max(1.0, Math.min(5.0, parseFloat(body.rate) || 5.0));
        const nowT = Math.floor(Date.now() / 1000);

        if (shopId) {
          await sql`
            INSERT INTO leaderboard (id, name, profit, day, served, lv, rate, updated_at)
            VALUES (${shopId}, ${name}, ${profit}, ${day}, ${served}, ${lv}, ${rate}, ${nowT})
            ON CONFLICT(id) DO UPDATE SET
              name = EXCLUDED.name,
              profit = EXCLUDED.profit,
              day = EXCLUDED.day,
              served = EXCLUDED.served,
              lv = EXCLUDED.lv,
              rate = EXCLUDED.rate,
              updated_at = EXCLUDED.updated_at
          `;

          const rankRows = await sql`SELECT count(*) FROM leaderboard WHERE profit > ${profit}`;
          const rank = Number(rankRows[0]?.count || 0) + 1;
          const totalRows = await sql`SELECT count(*) FROM leaderboard`;

          const top = await sql`
            SELECT id, name, CAST(profit AS FLOAT) as profit, day, served, lv, CAST(rate AS FLOAT) as rate
            FROM leaderboard
            ORDER BY profit DESC
            LIMIT 50
          `;

          return res.json({ ok: true, rank, total: Number(totalRows[0]?.count || 1), top });
        }
        return res.status(400).json({ ok: false });
      }

      // 5. POST /api/chal
      if (path === "/api/chal") {
        const op = body.op;
        const chalDay = getTodayChalDate();
        const nowT = Math.floor(Date.now() / 1000);

        if (op === "start") {
          const shopId = body.id || "guest";
          const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
          let token = "tok_";
          for (let i = 0; i < 16; i++) token += chars[Math.floor(Math.random() * chars.length)];

          const roundRows = await sql`SELECT count(*) FROM challenges WHERE day = ${chalDay} AND id = ${shopId}`;
          const roundNum = Number(roundRows[0]?.count || 0) + 1;

          await sql`
            INSERT INTO challenge_tokens (token, id, day, n, created_at)
            VALUES (${token}, ${shopId}, ${chalDay}, ${roundNum}, ${nowT})
          `;

          return res.json({ day: chalDay, n: roundNum, token });
        }

        const token = body.token;
        const score = parseInt(body.score, 10) || 0;
        const served = parseInt(body.served, 10) || 0;
        const perfect = parseInt(body.perfect, 10) || 0;
        const wrong = parseInt(body.wrong, 10) || 0;
        const lost = parseInt(body.lost, 10) || 0;

        const tokRows = await sql`SELECT id FROM challenge_tokens WHERE token = ${token}`;
        const shopId = tokRows[0]?.id || "guest";

        await sql`
          INSERT INTO challenges (id, day, score, served, perfect, wrong, lost, created_at)
          VALUES (${shopId}, ${chalDay}, ${score}, ${served}, ${perfect}, ${wrong}, ${lost}, ${nowT})
        `;

        const rankRows = await sql`SELECT count(DISTINCT id) as cnt FROM challenges WHERE day = ${chalDay} AND score > ${score}`;
        const rank = Number(rankRows[0]?.cnt || 0) + 1;
        const totalRows = await sql`SELECT count(DISTINCT id) as cnt FROM challenges WHERE day = ${chalDay}`;

        return res.json({ rank, total: Math.max(1, Number(totalRows[0]?.cnt || 1)) });
      }

      // 6. POST /api/sync
      if (path === "/api/sync") {
        const saveData = String(body.s || "");
        if (saveData) {
          const code = generateSyncCode();
          const nowT = Math.floor(Date.now() / 1000);
          await sql`
            INSERT INTO cloud_saves (code, save_data, created_at)
            VALUES (${code}, ${saveData}, ${nowT})
          `;
          return res.json({ code });
        }
        return res.status(400).json({ error: "No save data" });
      }

      // 7. POST /api/prank
      if (path === "/api/prank") {
        const op = body.op;
        const nowT = Math.floor(Date.now() / 1000);

        if (op === "send") {
          const fromId = body.from;
          const toId = body.to;
          const kind = body.k || "flower";

          const fRows = await sql`SELECT name FROM leaderboard WHERE id = ${fromId}`;
          const tRows = await sql`SELECT name FROM leaderboard WHERE id = ${toId}`;
          const fromName = fRows[0]?.name || "Quán bạn";
          const toName = tRows[0]?.name || "Quán bạn";

          await sql`
            INSERT INTO pranks (from_id, from_name, to_id, kind, created_at)
            VALUES (${fromId}, fromName, ${toId}, ${kind}, ${nowT})
          `;
          return res.json({ name: toName });
        }

        if (op === "take") {
          const shopId = body.id;
          const gifts = await sql`
            SELECT from_id as f, from_name as n, kind as k
            FROM pranks
            WHERE to_id = ${shopId} AND taken = 0
          `;
          await sql`UPDATE pranks SET taken = 1 WHERE to_id = ${shopId}`;
          return res.json({ gifts });
        }
      }

      // 8. POST /api/admin/user/delete
      if (path === "/api/admin/user/delete") {
        const username = String(body.username || "").trim().toLowerCase();
        if (username) {
          await sql`DELETE FROM users WHERE LOWER(username) = ${username}`;
          await sql`DELETE FROM user_saves WHERE LOWER(username) = ${username}`;
          return res.json({ ok: true });
        }
        return res.status(400).json({ error: "Missing username" });
      }

      // 9. POST /api/admin/user/reset-password
      if (path === "/api/admin/user/reset-password") {
        const username = String(body.username || "").trim().toLowerCase();
        const newPwd = String(body.newPassword || "").trim();
        if (username && newPwd.length >= 6) {
          const pwdHash = hashPassword(newPwd);
          await sql`UPDATE users SET password_hash = ${pwdHash} WHERE LOWER(username) = ${username}`;
          return res.json({ ok: true });
        }
        return res.status(400).json({ error: "Mật khẩu tối thiểu 6 ký tự!" });
      }

      // 10. POST /api/admin/player/delete
      if (path === "/api/admin/player/delete") {
        const playerId = body.id;
        if (playerId) {
          await sql`DELETE FROM leaderboard WHERE id = ${playerId}`;
          return res.json({ ok: true });
        }
        return res.status(400).json({ error: "Missing player id" });
      }

      // 11. POST /api/admin/save/delete
      if (path === "/api/admin/save/delete") {
        const saveCode = body.code;
        if (saveCode) {
          await sql`DELETE FROM cloud_saves WHERE code = ${saveCode}`;
          return res.json({ ok: true });
        }
        return res.status(400).json({ error: "Missing save code" });
      }

      // 12. POST /api/ai
      if (path === "/api/ai") {
        const custName = body.n || "Khách";
        const replies = [
          `${custName} mỉm cười: 'Dạ quán chu đáo quá, em nhận voucher nha, bữa sau em lại ghé!'`,
          `${custName}: 'Thấy quán có tâm sửa sai vậy là vui rồi, em cho lại 5 sao nha!'`,
          `${custName} bật cười: 'Haha chủ quán mặn ghê, thôi hết giận rồi, mai ghé ăn tiếp!'`,
          `${custName}: 'Nói chuyện duyên dữ thần, đành phải quay lại ủng hộ thôi!'`
        ];
        return res.json({
          ok: true,
          text: replies[Math.floor(Math.random() * replies.length)],
          fixStar: true
        });
      }

      // 13. POST /api/err & /api/copy
      if (path === "/api/err" || path === "/api/copy") {
        return res.json({ ok: true });
      }
    }

    return res.status(404).json({ error: "Endpoint not found" });
  } catch (err) {
    console.error("Vercel Serverless Error:", err);
    return res.status(500).json({ error: err.message || "Lỗi máy chủ nội bộ" });
  }
};
