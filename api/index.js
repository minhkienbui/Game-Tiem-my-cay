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

function getWeekBounds(targetDate = new Date()) {
  const vnTime = new Date(targetDate.getTime() + 7 * 3600000);
  const dayOfWeek = vnTime.getUTCDay(); // 0 is Sun, 1 is Mon...
  const diffToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;

  const monday = new Date(Date.UTC(vnTime.getUTCFullYear(), vnTime.getUTCMonth(), vnTime.getUTCDate() + diffToMonday, 0, 0, 0));
  const sunday = new Date(Date.UTC(vnTime.getUTCFullYear(), vnTime.getUTCMonth(), vnTime.getUTCDate() + diffToMonday + 6, 23, 59, 59, 999));

  const startSec = Math.floor((monday.getTime() - 7 * 3600000) / 1000);
  const endSec = Math.floor((sunday.getTime() - 7 * 3600000) / 1000);

  const weekYear = monday.getUTCFullYear();
  const oneJan = new Date(Date.UTC(weekYear, 0, 1));
  const weekNum = Math.ceil((((monday - oneJan) / 86400000) + 1) / 7);
  const weekKey = `${weekYear}-W${String(weekNum).padStart(2, "0")}`;

  const mDay = String(monday.getUTCDate()).padStart(2, "0");
  const mMon = String(monday.getUTCMonth() + 1).padStart(2, "0");
  const sDay = String(sunday.getUTCDate()).padStart(2, "0");
  const sMon = String(sunday.getUTCMonth() + 1).padStart(2, "0");
  const weekTitle = `Tuần ${weekNum} (${mDay}/${mMon} - ${sDay}/${sMon})`;

  return { startSec, endSec, weekKey, weekTitle };
}

const DEFAULT_GAME_CONFIG = {
  announcement_active: false,
  announcement_text: "Đại hội Giải Mì Tuần đang diễn ra sôi nổi! Top 1 nhận 1.000.000đ tiền mặt vào két quán!",
  announcement_type: "event",
  daySec: 210,
  startMoney: 400000,
  rent: 40000,
  util: 15000,
  appFee: 20,
  policeFee: 100000,
  catchRate: 50,
  theftEnabled: true,
  chalRounds: 3,
  rewardTop1: 1000000,
  rewardTop2: 300000,
  rewardTop3: 100000,
  taxCycleDays: 3,
  taxBaseRate: 50000
};

async function autoFinalizeCompletedWeeks(sql) {
  try {
    const nowSec = Math.floor(Date.now() / 1000);
    // 1. Check last week (which has already ended)
    const lastWeek = getWeekBounds(new Date(Date.now() - 7 * 86400000));

    // Check if last week is already in weekly_hall_of_fame
    const existing = await sql`
      SELECT count(*) FROM weekly_hall_of_fame WHERE week_key = ${lastWeek.weekKey}
    `;

    if (Number(existing[0]?.count || 0) === 0) {
      // Find top 3 from challenges for last week
      const topRows = await sql`
        SELECT id, SUM(score) as s, COUNT(*) as rounds
        FROM challenges
        WHERE created_at >= ${lastWeek.startSec} AND created_at <= ${lastWeek.endSec}
        GROUP BY id
        ORDER BY s DESC
        LIMIT 3
      `;

      if (topRows.length > 0) {
        for (let idx = 0; idx < topRows.length; idx++) {
          const r = topRows[idx];
          const rank = idx + 1;
          const reward_money = rank === 1 ? 1000000 : (rank === 2 ? 300000 : 100000);
          const custom_title = rank === 1 ? '👑 QUÁN QUÂN ĐỆ NHẤT MÌ CAY TOÀN QUỐC' : (rank === 2 ? '🥈 Á QUÂN BẬC THẦY HỎA LỰC' : '🥉 QUÝ QUÂN TINH ANH NẤU MÌ');
          const nameRows = await sql`SELECT name FROM leaderboard WHERE id = ${r.id}`;
          const shopName = nameRows[0]?.name || "Tiệm Mì Cay";
          const rowId = `${lastWeek.weekKey}_${rank}`;

          await sql`
            INSERT INTO weekly_hall_of_fame (
              id, week_key, week_title, rank, shop_id, shop_name, total_score, reward_money, custom_title, claimed_shops, created_at
            ) VALUES (
              ${rowId}, ${lastWeek.weekKey}, ${lastWeek.weekTitle}, ${rank}, ${r.id}, ${shopName}, ${Number(r.s)}, ${reward_money}, ${custom_title}, '', ${nowSec}
            )
            ON CONFLICT (id) DO UPDATE SET
              shop_name = EXCLUDED.shop_name,
              total_score = EXCLUDED.total_score,
              reward_money = EXCLUDED.reward_money,
              custom_title = EXCLUDED.custom_title,
              created_at = EXCLUDED.created_at
          `;
        }
      }
    }
  } catch (e) {
    console.error("autoFinalizeCompletedWeeks error:", e);
  }
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
  // Auto-migration: ensure game_config table exists
  try {
    await sql`
      CREATE TABLE IF NOT EXISTS chat_messages (
        id SERIAL PRIMARY KEY,
        conversation_id TEXT,
        sender_type TEXT,
        sender_name TEXT,
        store_code TEXT,
        message TEXT,
        created_at BIGINT,
        is_read_by_admin INT DEFAULT 0,
        is_read_by_user INT DEFAULT 0
      )
    `;
  } catch (e) {}

  try {
    await sql`
      CREATE INDEX IF NOT EXISTS idx_chat_conv ON chat_messages(conversation_id, created_at)
    `;
  } catch (e) {}

  try {
    await sql`
      CREATE TABLE IF NOT EXISTS admin_messages (
        id SERIAL PRIMARY KEY,
        sender TEXT,
        store_code TEXT,
        topic TEXT,
        content TEXT,
        status TEXT DEFAULT pending,
        created_at BIGINT,
        updated_at BIGINT
      )
    `;
  } catch (e) {}

  try {
    await sql`
      CREATE TABLE IF NOT EXISTS game_config (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at BIGINT
      )
    `;
  } catch (e) {}

  // Auto-migration: ensure store_code column exists in users
  try {
    await sql`ALTER TABLE users ADD COLUMN IF NOT EXISTS store_code TEXT`;
  } catch (e) {}


  // Parse body if needed
  let body = req.body || {};
  if (typeof body === "string") {
    try {
    // Enforce Admin Code 09659 on all /api/admin/* endpoints
    if (path.startsWith("/api/admin")) {
      const code = req.headers["x-admin-code"] || urlObj.searchParams.get("admin_code");
      if (code !== "09659") {
        return res.status(401).json({ error: "Yêu cầu mã code quản trị 09659!" });
      }
    }
 body = JSON.parse(body); } catch (e) { body = {}; }
  }

  try {
    // ----------------- GET ENDPOINTS -----------------
    if (req.method === "GET") {
      // GET /api/config (Public Game Configuration)
      if (path === "/api/config") {
        let cfg = { ...DEFAULT_GAME_CONFIG };
        let lastUpdated = 0;
        try {
          const rows = await sql`SELECT key, value, updated_at FROM game_config`;
          for (const r of rows) {
            try {
              cfg[r.key] = JSON.parse(r.value);
            } catch (e) {
              cfg[r.key] = r.value;
            }
            if (Number(r.updated_at) > lastUpdated) lastUpdated = Number(r.updated_at);
          }
        } catch (e) {}
        return res.json({ ok: true, config: cfg, updated_at: lastUpdated, ...cfg });
      }

      // GET /api/admin/config (Admin Protected Game Configuration)
      if (path === "/api/admin/config") {
        let cfg = { ...DEFAULT_GAME_CONFIG };
        let lastUpdated = 0;
        try {
          const rows = await sql`SELECT key, value, updated_at FROM game_config`;
          for (const r of rows) {
            try {
              cfg[r.key] = JSON.parse(r.value);
            } catch (e) {
              cfg[r.key] = r.value;
            }
            if (Number(r.updated_at) > lastUpdated) lastUpdated = Number(r.updated_at);
          }
        } catch (e) {}
        return res.json({ ok: true, config: cfg, updated_at: lastUpdated });
      }

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

      // 2. GET /api/chal (DAILY, WEEKLY TOURNAMENT TOP 1-2-3, HALL OF FAME)
      if (path === "/api/chal") {
        const shopId = urlObj.searchParams.get("id") || "";
        const chalDay = getTodayChalDate();
        const curWeek = getWeekBounds();
        await autoFinalizeCompletedWeeks(sql);

        // Automatically finalize any completed weeks and push top 1-2-3 to Hall of Fame
        await autoFinalizeCompletedWeeks(sql);

        // Auto-migration: ensure weekly_hall_of_fame table exists
        try {
          await sql`
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
          `;
        } catch (e) {}

        // Today's top scores
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

        // Today's player stats
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

        // Weekly rankings: Total tournament score within the week
        const wtopRows = await sql`
          SELECT id, SUM(score) as s, COUNT(*) as rounds, MAX(score) as best
          FROM challenges
          WHERE created_at >= ${curWeek.startSec} AND created_at <= ${curWeek.endSec}
          GROUP BY id
          ORDER BY s DESC
          LIMIT 30
        `;

        const wtop = [];
        for (let idx = 0; idx < wtopRows.length; idx++) {
          const wr = wtopRows[idx];
          const nameRows = await sql`SELECT name FROM leaderboard WHERE id = ${wr.id}`;
          wtop.push({
            id: wr.id,
            name: nameRows[0]?.name || "Chủ quán ẩn danh",
            s: Number(wr.s),
            rounds: Number(wr.rounds),
            rank: idx + 1,
            prize: idx === 0 ? 1000000 : idx === 1 ? 300000 : idx === 2 ? 100000 : 0
          });
        }

        const wCountRows = await sql`
          SELECT count(DISTINCT id) as cnt
          FROM challenges
          WHERE created_at >= ${curWeek.startSec} AND created_at <= ${curWeek.endSec}
        `;
        const wtotal = Math.max(wtop.length, Number(wCountRows[0]?.cnt || 1));

        // Weekly stats for current player
        const wmeRows = await sql`
          SELECT count(*) as rounds, SUM(score) as wscore, MAX(score) as wbest
          FROM challenges
          WHERE created_at >= ${curWeek.startSec} AND created_at <= ${curWeek.endSec} AND id = ${shopId}
        `;
        const wbest = Number(wmeRows[0]?.wscore || 0);
        let wrank = 0;
        if (wbest > 0) {
          const wrankRows = await sql`
            SELECT count(*) as cnt FROM (
              SELECT id, SUM(score) as tot
              FROM challenges
              WHERE created_at >= ${curWeek.startSec} AND created_at <= ${curWeek.endSec}
              GROUP BY id
              HAVING SUM(score) > ${wbest}
            ) sub
          `;
          wrank = Number(wrankRows[0]?.cnt || 0) + 1;
        }

        // Query Hall of Fame (Bảng Vinh Danh)
        let hofRows = [];
        try {
          hofRows = await sql`
            SELECT id, week_key, week_title, rank, shop_id, shop_name, total_score, reward_money, custom_title, claimed_shops, created_at
            FROM weekly_hall_of_fame
            ORDER BY created_at DESC, rank ASC
            LIMIT 20
          `;

          // Seed default prestigious Hall of Fame if empty
          if (!hofRows.length) {
            const nowSec = Math.floor(Date.now() / 1000);
            const seeds = [
              { id: "2026-W38_1", week_key: "2026-W38", week_title: "Tuần 38 (Mùa Khai Xuân)", rank: 1, shop_id: "vua_mi_cay_vip", shop_name: "Vua Mì Cay Sasin", total_score: 18650, reward_money: 1000000, custom_title: "👑 QUÁN QUÂN ĐỆ NHẤT MÌ CAY TOÀN QUỐC", claimed_shops: "", created_at: nowSec - 86400 * 7 },
              { id: "2026-W38_2", week_key: "2026-W38", week_title: "Tuần 38 (Mùa Khai Xuân)", rank: 2, shop_id: "seoul_02", shop_name: "Tiệm Mì Cay Seoul Phố", total_score: 14820, reward_money: 300000, custom_title: "🥈 Á QUÂN BẬC THẦY HỎA LỰC", claimed_shops: "", created_at: nowSec - 86400 * 7 },
              { id: "2026-W38_3", week_key: "2026-W38", week_title: "Tuần 38 (Mùa Khai Xuân)", rank: 3, shop_id: "nha_cao", shop_name: "Mì Cay Nhà Cáo", total_score: 11450, reward_money: 100000, custom_title: "🥉 QUÝ QUÂN TINH ANH NẤU MÌ", claimed_shops: "", created_at: nowSec - 86400 * 7 }
            ];
            for (const s of seeds) {
              await sql`
                INSERT INTO weekly_hall_of_fame (id, week_key, week_title, rank, shop_id, shop_name, total_score, reward_money, custom_title, claimed_shops, created_at)
                VALUES (${s.id}, ${s.week_key}, ${s.week_title}, ${s.rank}, ${s.shop_id}, ${s.shop_name}, ${s.total_score}, ${s.reward_money}, ${s.custom_title}, ${s.claimed_shops}, ${s.created_at})
                ON CONFLICT (id) DO NOTHING
              `;
            }
            hofRows = await sql`
              SELECT id, week_key, week_title, rank, shop_id, shop_name, total_score, reward_money, custom_title, claimed_shops, created_at
              FROM weekly_hall_of_fame
              ORDER BY created_at DESC, rank ASC
              LIMIT 20
            `;
          }
        } catch (e) {}

        // Check if player has an unclaimed weekly prize (Top 1: 1Tr, Top 2: 300k, Top 3: 100k)
        let unclaimed_reward = null;
        if (shopId) {
          try {
            const rewardRows = await sql`
              SELECT id, week_key, week_title, rank, reward_money, custom_title, claimed_shops
              FROM weekly_hall_of_fame
              WHERE shop_id = ${shopId}
              ORDER BY created_at DESC
              LIMIT 10
            `;
            for (const r of rewardRows) {
              const claimed = (r.claimed_shops || "").split(",").map(x => x.trim()).filter(Boolean);
              if (!claimed.includes(shopId)) {
                unclaimed_reward = {
                  id: r.id,
                  week_key: r.week_key,
                  week_title: r.week_title,
                  rank: Number(r.rank),
                  money: Number(r.reward_money),
                  custom_title: r.custom_title
                };
                break;
              }
            }
          } catch (e) {}
        }

        // Trophies / Cups for previous week champions
        const cups = {};
        for (const h of hofRows) {
          if (h.shop_id && !cups[h.shop_id] && Number(h.rank) <= 3) {
            cups[h.shop_id] = Number(h.rank);
          }
        }

        return res.json({
          day: chalDay,
          top,
          wtop,
          wtotal,
          me: {
            left: Math.max(0, 3 - roundsDone),
            best: bestScore,
            rank,
            wbest,
            wrank
          },
          total,
          cups,
          rewards_info: [
            { rank: 1, money: 1000000, title: "🥇 TOP 1 - QUÁN QUÂN: 1.000.000đ + Vinh Danh Hoàng Gia" },
            { rank: 2, money: 300000, title: "🥈 TOP 2 - Á QUÂN 1: 300.000đ + Vinh Danh Bảng Vàng" },
            { rank: 3, money: 100000, title: "🥉 TOP 3 - Á QUÂN 2: 100.000đ + Vinh Danh Bảng Vàng" }
          ],
          hall_of_fame: hofRows.map(h => ({
            id: h.id,
            week_key: h.week_key,
            week_title: h.week_title,
            rank: Number(h.rank),
            shop_id: h.shop_id,
            shop_name: h.shop_name,
            total_score: Number(h.total_score),
            reward_money: Number(h.reward_money),
            custom_title: h.custom_title,
            claimed: Boolean((h.claimed_shops || "").includes(h.shop_id))
          })),
          unclaimed_reward
        });
      }

      // 3. GET /api/sync (Permanent Store Code / Save Sync)
      if (path === "/api/sync") {
        const code = (urlObj.searchParams.get("code") || "").trim().toUpperCase();
        const rows = await sql`SELECT save_data, created_at FROM cloud_saves WHERE UPPER(code) = ${code}`;
        if (rows.length) {
          return res.json({ s: rows[0].save_data });
        }
        return res.status(404).json({ error: "Mã không đúng hoặc không tìm thấy tiệm" });
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

      // GET /api/chat/messages (User 1-on-1 Chat History)
      if (path === "/api/chat/messages") {
        const convId = (urlObj.searchParams.get("conversation_id") || "").trim();
        if (!convId) {
          return res.status(400).json({ ok: false, error: "Missing conversation_id" });
        }
        const rows = await sql`
          SELECT id, conversation_id, sender_type, sender_name, store_code, message, created_at
          FROM chat_messages
          WHERE conversation_id = ${convId}
          ORDER BY created_at ASC, id ASC
          LIMIT 200
        `;
        // Mark admin messages as read by user
        await sql`
          UPDATE chat_messages
          SET is_read_by_user = 1
          WHERE conversation_id = ${convId} AND sender_type = 'admin'
        `;
        return res.json({
          ok: true,
          conversation_id: convId,
          messages: rows.map(r => ({
            id: r.id,
            conversation_id: r.conversation_id,
            sender_type: r.sender_type,
            sender_name: r.sender_name,
            store_code: r.store_code || "",
            message: r.message,
            created_at: Number(r.created_at)
          }))
        });
      }

      // GET /api/admin/chat/conversations (Admin: List all 1-on-1 user threads)
      if (path === "/api/admin/chat/conversations") {
        const rows = await sql`
          SELECT
            c.conversation_id,
            MAX(c.sender_name) as display_name,
            MAX(c.store_code) as store_code,
            MAX(c.created_at) as last_time,
            SUM(CASE WHEN c.sender_type = 'user' AND c.is_read_by_admin = 0 THEN 1 ELSE 0 END) as unread_count,
            COUNT(*) as total_count
          FROM chat_messages c
          GROUP BY c.conversation_id
          ORDER BY last_time DESC
          LIMIT 100
        `;

        const convs = [];
        for (const r of rows) {
          // get last message snippet
          const lastMsgRows = await sql`
            SELECT message, sender_type, created_at
            FROM chat_messages
            WHERE conversation_id = ${r.conversation_id}
            ORDER BY created_at DESC, id DESC
            LIMIT 1
          `;
          const lastM = lastMsgRows[0] || {};
          convs.push({
            conversation_id: r.conversation_id,
            display_name: r.display_name || r.conversation_id,
            store_code: r.store_code || "",
            last_message: lastM.message || "",
            last_sender_type: lastM.sender_type || "user",
            last_time: Number(r.last_time || 0),
            unread_count: Number(r.unread_count || 0),
            total_count: Number(r.total_count || 0)
          });
        }

        const totalUnreadRes = await sql`
          SELECT count(*) FROM chat_messages WHERE sender_type = 'user' AND is_read_by_admin = 0
        `;
        return res.json({
          ok: true,
          conversations: convs,
          total_unread: Number(totalUnreadRes[0]?.count || 0)
        });
      }

      // GET /api/admin/chat/messages (Admin: Get full thread for selected user)
      if (path === "/api/admin/chat/messages") {
        const convId = (urlObj.searchParams.get("conversation_id") || "").trim();
        if (!convId) {
          return res.status(400).json({ ok: false, error: "Missing conversation_id" });
        }
        const rows = await sql`
          SELECT id, conversation_id, sender_type, sender_name, store_code, message, created_at
          FROM chat_messages
          WHERE conversation_id = ${convId}
          ORDER BY created_at ASC, id ASC
          LIMIT 300
        `;
        // Mark user messages as read by admin
        await sql`
          UPDATE chat_messages
          SET is_read_by_admin = 1
          WHERE conversation_id = ${convId} AND sender_type = 'user'
        `;
        return res.json({
          ok: true,
          conversation_id: convId,
          messages: rows.map(r => ({
            id: r.id,
            conversation_id: r.conversation_id,
            sender_type: r.sender_type,
            sender_name: r.sender_name,
            store_code: r.store_code || "",
            message: r.message,
            created_at: Number(r.created_at)
          }))
        });
      }

      // GET /api/admin/inbox (List Inbox Messages)
      if (path === "/api/admin/inbox") {
        const status = urlObj.searchParams.get("status");
        let rows;
        if (status === "pending" || status === "resolved") {
          rows = await sql`
            SELECT id, sender, store_code, topic, content, status, created_at, updated_at
            FROM admin_messages
            WHERE status = ${status}
            ORDER BY created_at DESC
            LIMIT 100
          `;
        } else {
          rows = await sql`
            SELECT id, sender, store_code, topic, content, status, created_at, updated_at
            FROM admin_messages
            ORDER BY (CASE WHEN status = 'pending' THEN 0 ELSE 1 END), created_at DESC
            LIMIT 100
          `;
        }
        const pendingRes = await sql`SELECT count(*) FROM admin_messages WHERE status = 'pending'`;
        const totalRes = await sql`SELECT count(*) FROM admin_messages`;
        return res.json({
          ok: true,
          messages: rows.map(r => ({
            id: r.id,
            sender: r.sender || "Ẩn danh",
            store_code: r.store_code || "",
            topic: r.topic || "Góp ý",
            content: r.content || "",
            status: r.status || "pending",
            created_at: Number(r.created_at || 0),
            updated_at: Number(r.updated_at || 0)
          })),
          pending_count: Number(pendingRes[0]?.count || 0),
          total: Number(totalRes[0]?.count || rows.length)
        });
      }

      // 6. GET /api/admin/users
      if (path === "/api/admin/users") {
        const rows = await sql`
          SELECT u.id, u.username, u.created_at, u.last_login_at, u.login_count,
                 u.device_info, u.current_lv, u.current_day, CAST(u.current_money AS FLOAT) as current_money,
                 u.store_code, (s.save_data IS NOT NULL) as has_save
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
          store_code: r.store_code || "",
          has_save: Boolean(r.has_save)
        }));

        return res.json({ ok: true, users, total });
      }

      // GET /api/admin/store-code/lookup
      if (path === "/api/admin/store-code/lookup") {
        const code = (urlObj.searchParams.get("code") || "").trim().toUpperCase();
        if (!code) return res.status(400).json({ ok: false, error: "Vui lòng nhập mã cửa hàng!" });
        const rows = await sql`SELECT code, save_data, created_at FROM cloud_saves WHERE UPPER(code) = ${code}`;
        if (!rows.length) {
          return res.status(404).json({ ok: false, error: "Không tìm thấy dữ liệu cho mã: " + code });
        }
        const userRows = await sql`SELECT username, current_lv, current_day, CAST(current_money AS FLOAT) as current_money FROM users WHERE UPPER(store_code) = ${code}`;
        return res.json({
          ok: true,
          code: rows[0].code,
          save: rows[0].save_data,
          created_at: Number(rows[0].created_at),
          user: userRows[0] || null
        });
      }

      // POST /api/admin/user/assign-code
      if (path === "/api/admin/user/assign-code") {
        const username = String(body.username || "").trim().toLowerCase();
        let code = (body.code || generateSyncCode()).trim().toUpperCase();
        if (username) {
          const saveRows = await sql`SELECT save_data FROM user_saves WHERE LOWER(username) = ${username}`;
          const nowT = Math.floor(Date.now() / 1000);
          if (saveRows.length && saveRows[0].save_data) {
            await sql`
              INSERT INTO cloud_saves (code, save_data, created_at)
              VALUES (${code}, ${saveRows[0].save_data}, ${nowT})
              ON CONFLICT(code) DO UPDATE SET
                save_data = EXCLUDED.save_data,
                created_at = EXCLUDED.created_at
            `;
          }
          await sql`UPDATE users SET store_code = ${code} WHERE LOWER(username) = ${username}`;
          return res.json({ ok: true, code, username });
        }
        return res.status(400).json({ ok: false, error: "Missing username" });
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
      // POST /api/admin/config (Save Game Configuration)
      if (path === "/api/admin/config") {
        const payload = body.config || body;
        const nowT = Math.floor(Date.now() / 1000);
        let updatedCount = 0;

        for (const [key, val] of Object.entries(payload)) {
          if (key === "admin_code" || key === "ok" || key === "config") continue;
          const valStr = JSON.stringify(val);
          await sql`
            INSERT INTO game_config (key, value, updated_at)
            VALUES (${key}, ${valStr}, ${nowT})
            ON CONFLICT (key) DO UPDATE SET
              value = EXCLUDED.value,
              updated_at = EXCLUDED.updated_at
          `;
          updatedCount++;
        }

        let cfg = { ...DEFAULT_GAME_CONFIG };
        const rows = await sql`SELECT key, value FROM game_config`;
        for (const r of rows) {
          try {
            cfg[r.key] = JSON.parse(r.value);
          } catch (e) {
            cfg[r.key] = r.value;
          }
        }

        return res.json({
          ok: true,
          message: "Đã lưu cấu hình game thành công!",
          updatedCount,
          config: cfg,
          updated_at: nowT
        });
      }

      // POST /api/admin/chal/finalize (Admin: Finalize and Award Week to Hall of Fame)
      if (path === "/api/admin/chal/finalize") {
        const scope = String(body.scope || "last").trim(); // 'last' or 'current'
        const weekToFinalize = (scope === "current") ? getWeekBounds() : getWeekBounds(new Date(Date.now() - 7 * 86400000));
        const nowSec = Math.floor(Date.now() / 1000);

        const topRows = await sql`
          SELECT id, SUM(score) as s, COUNT(*) as rounds
          FROM challenges
          WHERE created_at >= ${weekToFinalize.startSec} AND created_at <= ${weekToFinalize.endSec}
          GROUP BY id
          ORDER BY s DESC
          LIMIT 3
        `;

        if (!topRows.length) {
          return res.json({ ok: false, message: `Tuần ${weekToFinalize.weekTitle} chưa có lượt thi đấu nào để trao giải.` });
        }

        const results = [];
        for (let idx = 0; idx < topRows.length; idx++) {
          const r = topRows[idx];
          const rank = idx + 1;
          const reward_money = rank === 1 ? 1000000 : (rank === 2 ? 300000 : 100000);
          const custom_title = rank === 1 ? '👑 QUÁN QUÂN ĐỆ NHẤT MÌ CAY TOÀN QUỐC' : (rank === 2 ? '🥈 Á QUÂN BẬC THẦY HỎA LỰC' : '🥉 QUÝ QUÂN TINH ANH NẤU MÌ');
          const nameRows = await sql`SELECT name FROM leaderboard WHERE id = ${r.id}`;
          const shopName = nameRows[0]?.name || "Tiệm Mì Cay";
          const rowId = `${weekToFinalize.weekKey}_${rank}`;

          await sql`
            INSERT INTO weekly_hall_of_fame (
              id, week_key, week_title, rank, shop_id, shop_name, total_score, reward_money, custom_title, claimed_shops, created_at
            ) VALUES (
              ${rowId}, ${weekToFinalize.weekKey}, ${weekToFinalize.weekTitle}, ${rank}, ${r.id}, ${shopName}, ${Number(r.s)}, ${reward_money}, ${custom_title}, '', ${nowSec}
            )
            ON CONFLICT (id) DO UPDATE SET
              shop_name = EXCLUDED.shop_name,
              total_score = EXCLUDED.total_score,
              reward_money = EXCLUDED.reward_money,
              custom_title = EXCLUDED.custom_title,
              created_at = EXCLUDED.created_at
          `;
          results.push({ rank, shopName, id: r.id, score: Number(r.s), reward_money });
        }

        return res.json({
          ok: true,
          message: `Đã kết thúc và đẩy Top 1-2-3 của ${weekToFinalize.weekTitle} lên Bảng Vinh Danh thành công!`,
          week: weekToFinalize,
          results
        });
      }

      // POST /api/chat/send (User: Send message to Admin 1-on-1)
      if (path === "/api/chat/send") {
        const convId = String(body.conversation_id || "").trim();
        const senderName = String(body.sender_name || body.sender || "Khách").slice(0, 50).trim();
        const storeCode = String(body.store_code || body.storeCode || "").slice(0, 20).trim().toUpperCase();
        const message = String(body.message || body.content || "").slice(0, 3000).trim();

        if (!convId || !message) {
          return res.status(400).json({ ok: false, error: "Vui lòng nhập nội dung tin nhắn!" });
        }

        const nowT = Math.floor(Date.now() / 1000);
        const inserted = await sql`
          INSERT INTO chat_messages (conversation_id, sender_type, sender_name, store_code, message, created_at, is_read_by_admin, is_read_by_user)
          VALUES (${convId}, 'user', ${senderName}, ${storeCode}, ${message}, ${nowT}, 0, 1)
          RETURNING id, conversation_id, sender_type, sender_name, store_code, message, created_at
        `;

        const row = inserted[0] || {};
        return res.json({
          ok: true,
          message: {
            id: row.id || Date.now(),
            conversation_id: row.conversation_id || convId,
            sender_type: row.sender_type || "user",
            sender_name: row.sender_name || senderName,
            store_code: row.store_code || storeCode,
            message: row.message || message,
            created_at: Number(row.created_at || nowT)
          }
        });
      }

      // POST /api/admin/chat/send (Admin: Reply directly to user)
      if (path === "/api/admin/chat/send") {
        const convId = String(body.conversation_id || "").trim();
        const adminName = String(body.admin_name || "Admin Quản Trị").slice(0, 50).trim();
        const message = String(body.message || "").slice(0, 3000).trim();

        if (!convId || !message) {
          return res.status(400).json({ ok: false, error: "Vui lòng nhập nội dung phản hồi!" });
        }

        // Get user store_code if available
        const prevRows = await sql`SELECT store_code FROM chat_messages WHERE conversation_id = ${convId} LIMIT 1`;
        const storeCode = prevRows[0]?.store_code || "";

        const nowT = Math.floor(Date.now() / 1000);
        const inserted = await sql`
          INSERT INTO chat_messages (conversation_id, sender_type, sender_name, store_code, message, created_at, is_read_by_admin, is_read_by_user)
          VALUES (${convId}, 'admin', ${adminName}, ${storeCode}, ${message}, ${nowT}, 1, 0)
          RETURNING id, conversation_id, sender_type, sender_name, store_code, message, created_at
        `;

        return res.json({
          ok: true,
          message: inserted[0] || {
            id: Date.now(),
            conversation_id: convId,
            sender_type: "admin",
            sender_name: adminName,
            store_code: storeCode,
            message,
            created_at: nowT
          }
        });
      }

      // POST /api/admin/chat/delete-conversation (Delete entire thread)
      if (path === "/api/admin/chat/delete-conversation") {
        const convId = String(body.conversation_id || "").trim();
        if (convId) {
          await sql`DELETE FROM chat_messages WHERE conversation_id = ${convId}`;
          return res.json({ ok: true, conversation_id: convId });
        }
        return res.status(400).json({ ok: false, error: "Missing conversation_id" });
      }

      // POST /api/admin/chat/delete-message (Delete single message)
      if (path === "/api/admin/chat/delete-message") {
        const id = parseInt(body.id, 10);
        if (id) {
          await sql`DELETE FROM chat_messages WHERE id = ${id}`;
          return res.json({ ok: true, id });
        }
        return res.status(400).json({ ok: false, error: "Missing message id" });
      }

      // POST /api/inbox (Public: Send message / feedback to Admin)
      if (path === "/api/inbox") {
        const sender = String(body.sender || "Khách ẩn danh").slice(0, 50).trim();
        const store_code = String(body.store_code || body.storeCode || "").slice(0, 20).trim().toUpperCase();
        const topic = String(body.topic || "Góp ý chung").slice(0, 80).trim();
        const content = String(body.content || "").slice(0, 2000).trim();

        if (!content || content.length < 3) {
          return res.status(400).json({ ok: false, error: "Nội dung tin nhắn tối thiểu 3 ký tự!" });
        }

        const nowT = Math.floor(Date.now() / 1000);
        await sql`
          INSERT INTO admin_messages (sender, store_code, topic, content, status, created_at, updated_at)
          VALUES (${sender}, ${store_code}, ${topic}, ${content}, 'pending', ${nowT}, ${nowT})
        `;

        return res.json({ ok: true, message: "Đã gửi tin nhắn đến Admin thành công!" });
      }

      // POST /api/admin/inbox/status (Update Message Status: 'pending' or 'resolved')
      if (path === "/api/admin/inbox/status") {
        const id = parseInt(body.id, 10);
        const status = String(body.status || "resolved").trim();
        const nowT = Math.floor(Date.now() / 1000);

        if (id) {
          await sql`
            UPDATE admin_messages
            SET status = ${status}, updated_at = ${nowT}
            WHERE id = ${id}
          `;
          return res.json({ ok: true, id, status });
        }
        return res.status(400).json({ ok: false, error: "Missing message id" });
      }

      // POST /api/admin/inbox/delete (Delete Message)
      if (path === "/api/admin/inbox/delete") {
        const id = parseInt(body.id, 10);
        if (id) {
          await sql`DELETE FROM admin_messages WHERE id = ${id}`;
          return res.json({ ok: true, id });
        }
        return res.status(400).json({ ok: false, error: "Missing message id" });
      }

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
        const lvVal = Math.max(1, Math.min(50, parseInt(body.lv, 10) || 1));
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
        const lv = Math.max(1, Math.min(50, parseInt(body.lv, 10) || 1));
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
        // Handle reward claim for Top 1, 2, 3
        if (body.op === "claim-reward") {
          const shopId = String(body.id || "").trim();
          const weekKey = String(body.week_key || "").trim();
          if (shopId && weekKey) {
            const rows = await sql`
              SELECT id, claimed_shops, reward_money, rank
              FROM weekly_hall_of_fame
              WHERE week_key = ${weekKey} AND shop_id = ${shopId}
            `;
            if (rows.length) {
              const claimed = (rows[0].claimed_shops || "").split(",").filter(Boolean);
              if (!claimed.includes(shopId)) {
                claimed.push(shopId);
                await sql`
                  UPDATE weekly_hall_of_fame
                  SET claimed_shops = ${claimed.join(",")}
                  WHERE id = ${rows[0].id}
                `;
                return res.json({ ok: true, rank: Number(rows[0].rank), reward_money: Number(rows[0].reward_money), message: "Đã nhận thưởng giải mì!" });
              }
            }
          }
          return res.json({ ok: true, message: "Đã nhận hoặc không có phần thưởng" });
        }

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

      // 6. POST /api/sync (Permanent Store Code / Save Sync)
      if (path === "/api/sync") {
        const saveData = String(body.s || "");
        let code = (body.code || "").trim().toUpperCase();
        const username = (body.username || "").trim().toLowerCase();
        if (!code) {
          code = generateSyncCode();
        }
        if (saveData) {
          const nowT = Math.floor(Date.now() / 1000);
          await sql`
            INSERT INTO cloud_saves (code, save_data, created_at)
            VALUES (${code}, ${saveData}, ${nowT})
            ON CONFLICT(code) DO UPDATE SET
              save_data = EXCLUDED.save_data,
              created_at = EXCLUDED.created_at
          `;
          if (username) {
            await sql`
              UPDATE users SET store_code = ${code}
              WHERE LOWER(username) = ${username}
            `;
          }
          return res.json({ ok: true, code });
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
