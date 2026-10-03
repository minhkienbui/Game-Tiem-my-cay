# Tiệm Mì Cay 7 Cấp Độ (Full-Stack Web Game Tycoon)
Hệ thống bao gồm đầy đủ **Frontend Game**, **Trang Quản Trị Admin Panel** và **Backend Server (Python + SQLite)** phục vụ dữ liệu trực tiếp trong thời gian thực.
--

## 🌐 HƯỚNG DẪN ĐỒNG BỘ TOÀN BỘ NGƯỜI DÙNG & MÁY CHỦ

Vercel là nền tảng Serverless (mỗi request có thể chạy trên một container độc lập). Để **tất cả người dùng trên toàn cầu cùng chia sẻ chung một tài khoản, bảng xếp hạng và tiến trình lưu trữ thời gian thực**, bạn có 2 giải pháp hoàn hảo:

### 🌟 Giải Pháp 1: Triển Khai Backend 24/7 Miễn Phí Trên Render (Khuyên Dùng)
Dự án đã có sẵn file `render.yaml` và `Dockerfile`. Bạn chỉ cần:
1. Đăng ký tài khoản miễn phí tại **[render.com](https://render.com)**.
2. Bấm **New** $\rightarrow$ **Blueprint** $\rightarrow$ Chọn repo GitHub `minhkienbui/Game-Tiem-my-cay`.
3. Render sẽ tự động khởi chạy máy chủ Python 24/7 với ổ đĩa lưu trữ `data/tiemmicay.db` vĩnh viễn, cấp cho bạn link (ví dụ: `https://tiem-mi-cay-backend.onrender.com`).
4. **Kết nối vào Vercel**:
   - Mở Vercel Dashboard $\rightarrow$ Vào dự án `Game-Tiem-my-cay` $\rightarrow$ **Settings** $\rightarrow$ **Environment Variables**.
   - Thêm biến:
     * `Key`: `REMOTE_BACKEND_URL`
     * `Value`: `https://tiem-mi-cay-backend.onrender.com`
   - Bấm **Save** và Redeploy. Vercel sẽ tự động chuyển tiếp toàn bộ API về máy chủ Render, mọi người chơi trên thế giới đều dùng chung 1 database duy nhất!

---

### 🌟 Giải Pháp 2: Dùng Turso Cloud SQLite (Dành Riêng Cho Vercel)
Turso là dịch vụ SQLite trên đám mây miễn phí (9GB):
1. Vào **[turso.tech](https://turso.tech)** tạo tài khoản và tạo database `tiem-mi-cay`.
2. Lấy `TURSO_DATABASE_URL` và `TURSO_AUTH_TOKEN`.
3. Thêm 2 biến này vào **Vercel Settings $\rightarrow$ Environment Variables**.
4. Toàn bộ người chơi trên Vercel sẽ đọc/ghi vào cùng một database Turso trên đám mây!

---

## 🌟 Toàn Bộ Tính Năng Đỉnh Cao Đã Hoàn Thiện

1. **Hệ Thống Tài Khoản Đăng Nhập / Đăng Ký**:
   - Đăng ký tài khoản với 3 trường: *Tài khoản - Mật khẩu - Nhập lại mật khẩu*.
   - Tự động đồng bộ tiến trình của quán lên tài khoản đám mây. Đăng nhập ở bất kỳ thiết bị nào cũng tiếp tục chơi được ngay.
2. **Trang Quản Trị Hệ Thống Riêng Biệt (`/admin`)**:
   - Ẩn hoàn toàn khỏi trang chủ, chỉ người có link `/admin` mới truy cập được.
   - Dashboard quản lý bảng xếp hạng, chỉnh sửa tài khoản người chơi, xóa bản lưu, xem lịch sử giải đấu.
3. **Hệ Thống Thuế Kinh Doanh & Niêm Phong Cửa Hàng (Phá Sản)**:
   - Tự giác nộp thuế trong tab *Sổ sách* (không có thông báo làm phiền).
   - Nộp đủ thuế: Hưởng gói phúc lợi giảm 30% tiền thuê mặt bằng & điện nước, tăng +20% khách.
   - Trốn thuế: Quán bị niêm phong toàn bộ và phá sản, phải đóng phạt gấp đôi để gỡ niêm phong.
4. **Dây Chuyền 6 Nhân Viên Tự Động Hóa 100%**:
   - *Anh Hấu* tự múc nước lẩu, *Bé Ổi* tự gắp topping, *Bé Na* tự luộc mì chín tới và gắp vào tô, *Bé Mít* tự bưng trà đá giải nhiệt và lau sàn bẩn, *Cô Chôm* tự phóng xe đi chợ mua hàng cháy, *Chị Mận* khóa chặt quầy chống ăn quỵt.
5. **28+ Món Đồ Trang Trí Quán Đa Dạng**:
   - Mái hiên ngũ sắc, thú cưng tương tác (*Corgi, Capybara, Rái cá*), cây cảnh (*Bonsai, Trúc phú quý*), đèn neon và đài nước phong thủy.
6. **An Ninh Bắt Trộm 50/50**:
   - Kẻ trộm móc két tiền, người chơi có thể báo cảnh sát (phí 100k) với tỷ lệ 50% bắt được thu hồi tiền + bồi thường.
7. **Lên Cấp Càng Đông Khách & Ngày Vô Hạn**:
   - Mỗi cấp tăng +16% khách (Cấp 10 lên đến 178 khách/ngày!), chơi liên tục không giới hạn ngày.

---

## 📂 Cấu Trúc Thư Mục Dự Án

```
QuanMyCayy/
├── server.py               # Backend Server chạy 24/7 (Local / Render / VPS)
├── api/
│   └── index.py            # Vercel Serverless Function & Reverse Proxy
├── render.yaml             # File cấu hình deploy 1-click lên Render.com
├── Dockerfile              # Container Docker chuẩn cho mọi nền tảng
├── vercel.json             # Cấu hình định tuyến Vercel
├── .env.example            # Mẫu cấu hình biến môi trường
├── index.html              # Frontend Game chính
├── admin.html              # Trang Quản trị Admin Panel riêng biệt
├── game.js                 # Engine game & 6 nhân viên tự động hóa
├── public/                 # Thư mục phân phối CDN của Vercel
├── data/
│   └── tiemmicay.db        # Cơ sở dữ liệu SQLite cục bộ
├── music/                  # 5 bản nhạc nền MP3 chất lượng cao
├── icon-192.png            # Icon PWA cho Android/Chrome
├── apple-touch-icon.png    # Icon cho iOS Safari
├── manifest.webmanifest    # Cấu hình PWA mở toàn màn hình
└── og.jpg                  # Ảnh thumbnail chia sẻ
```

---

## 💻 Cách Khởi Chạy

### Chạy Local:
```bash
python server.py
```
- Game: `http://localhost:8000`
- Admin: `http://localhost:8000/admin`

### Chạy Online Trên Vercel:
- Game: `https://game-tiem-my-cay.vercel.app`
- Admin: `https://game-tiem-my-cay.vercel.app/admin`
