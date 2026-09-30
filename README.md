# Tiệm Mì Cay 7 Cấp Độ (Full-Stack Web Game Tycoon)

Dự án Web Game mô phỏng quản lý quán ăn và nấu mì cay 7 cấp độ được xây dựng và nâng cấp toàn diện dựa trên kiến trúc của [aenhatrang.com](https://aenhatrang.com/) và tài liệu đặc tả kỹ thuật `Tiem_Mi_Cay_AI_Master_Prompt_Specification.docx`.

Hệ thống bao gồm đầy đủ **Frontend Game**, **Trang Quản Trị Admin Panel** và **Backend Server (Python + SQLite)** phục vụ dữ liệu trực tiếp trong thời gian thực.

---

## 🌟 Toàn Bộ Tính Năng Đỉnh Cao Đã Hoàn Thiện 100%

### 1. Dây Chuyền 6 Nhân Viên Tự Động Hóa 100% (Full Kitchen Automation)
Khi người chơi thuê đủ 6 nhân sự, tiệm mì chuyển sang chế độ tự vận hành thần tốc:
- **Anh Hấu (Nêm nếm)**: Tự động múc đúng loại nước lẩu mà khách hàng đang chọn vào tô (9 loại lẩu).
- **Bé Ổi (Topping)**: Tự động gắp đầy đủ các món topping theo yêu cầu của khách vào tô (21 loại topping).
- **Bé Na (Luộc mì)**: Tự động luộc mì trên cả 3 nồi, canh đúng vạch XANH chín tới vớt vào rổ mì chín, và tự gắp mì chín vào tô nếu tô đã có nước dùng.
- **Tự động lấy tô sứ**: Khi quầy bếp trống và có khách chờ, hệ thống tự động xuất tô mới lên bàn làm việc. Người chơi chỉ việc bóp sốt ớt (0-7 giọt) và bấm Giao món!
- **Bé Mít (Chạy bàn)**: Tự động quét khách chờ, hễ ai kiên nhẫn < 65% là tự bưng trà đá giải nhiệt hồi kiên nhẫn, và tự lau sạch sàn nhà trong 1s khi có mì đổ.
- **Cô Chôm (Đi chợ)**: Tự động quét kho hàng, hễ món nào chạm đáy (về 0) mà khách đang gọi là phóng xe máy đi chợ mua cấp tốc 5 phần về ngay.
- **Chị Mận (Thu ngân)**: Canh chừng quầy thu ngân, ngăn chặn 100% khách ăn quỵt và bắt đúng tiền đưa nhầm.

### 2. Hệ Thống Thuế Kinh Doanh & Niêm Phong Cửa Hàng (Tax & Bankruptcy System)
- **Cơ chế nộp thuế tự giác**: Không có thông báo hay popup làm phiền người chơi. Người chơi phải **tự giác vào Tab "Sổ sách"** để kiểm tra hạn chót và bấm nút **`[🏛️ Tự Giác Nộp Thuế]`**. Thuế tính theo cấp bậc quán (từ 40k đến 450k / kỳ 3 ngày).
- **Hậu quả trốn thuế (Phá sản & Niêm phong)**: Nếu quá hạn nộp thuế mà người chơi không nộp, cửa hàng lập tức bị **NIÊM PHONG TOÀN BỘ & PHÁ SẢN**! Bếp nấu bị khóa chặt, dán băng niêm phong đỏ `⛔ ĐÃ NIÊM PHONG DO TRỐN THUẾ ⛔`. Hộp thoại phá sản hiện ra yêu cầu nộp phạt gấp đôi ($3 \times \text{Thuế}$) để gỡ niêm phong hoặc chấp nhận phá sản chơi lại từ đầu.
- **Phúc lợi hấp dẫn khi nộp thuế đầy đủ (Hộ kinh doanh gương mẫu)**:
  - 🎁 **Giảm 30%** tiền thuê mặt bằng và tiền điện nước mỗi đêm!
  - 🛡️ **Miễn trừ 100%** đoàn thanh tra vệ sinh an toàn thực phẩm.
  - 🌟 **Tăng +20%** lượng khách ghé quán nhờ danh tiếng minh bạch.

### 3. Tùy Biến Cửa Hàng Đa Dạng (28+ Món Decor)
Người chơi có thể cá nhân hóa quán mì với hơn 28+ vật phẩm trang trí phong phú:
- **Mái hiên**: Đỏ ớt, Hồng dâu, Xanh bạc hà, Vàng trứng, Tím khoai môn, **Đen huyền bí**, **Cam Habanero**, **Cầu vồng rực rỡ**, **Gỗ cổ kính**.
- **Thú cưng tương tác**: Mèo mướp Mochi, Cún shiba Bơ, Hamster Đậu, **🦦 Rái cá Bi** (vỗ tay bim bịp), **🦫 Capybara Cam** (điềm tĩnh đội cam), **🦆 Vịt vàng Bon** (đội nón lá kêu cạp cạp), **🐕 Corgi Mông Đào** (lắc mông quả đào đón khách).
- **Cây cảnh**: Chậu xương rồng, Cây trầu bà, Chậu hoa cúc, **🪴 Bonsai Tùng**, **🌻 Hoa hướng dương**, **🎋 Trúc phú quý**, **🌸 Anh đào hồng**.
- **Đèn & Nội thất phong thủy**: Đèn lồng đỏ, Chuông gió, **🏮 Đèn Neon MÌ CAY**, **✨ Dây đèn Fairy ấm áp**, **🐠 Bể cá thủy sinh**, **⛲ Đài nước phong thủy tụ tài lộc**.

### 4. Hệ Thống An Ninh & Bắt Trộm 50/50
- Có tỉ lệ khách ăn quỵt hoặc kẻ gian lẻn vào móc két tiền trong ca bán hàng.
- Bật hộp thoại khẩn cấp với 2 lựa chọn:
  - **Báo cảnh sát (Phí 100.000đ)**:
    - **50% Bắt được**: Cảnh sát chốt chặn tóm gọn kẻ gian, thu hồi 100% số tiền bị trộm trả lại cho quán, thu phạt thêm bồi thường và cộng `+45 XP`!
    - **50% Trốn thoát**: Kẻ trộm chạy thoát vào ngõ hẹp, quán mất số tiền bị trộm và mất luôn 100k phí báo án.
  - **Thôi, tự chịu**: Quán ngậm ngùi chịu mất số tiền trên, nhắc nhau cẩn thận hơn.

### 5. Lên Cấp Càng Đông Khách & Thương Hiệu Nổi Tiếng
- Mỗi lần lên cấp, lưu lượng khách ghé quán tăng thêm **+16% mỗi cấp** (Cấp 10 lên tới 178 khách/ngày!).
- Quán đạt Cấp 7+ (*Tiệm nổi tiếng*) nhận huy hiệu **`👑 THƯƠNG HIỆU NỔI TIẾNG`** trên biển hiệu, cộng thêm **+35% khách** và doanh thu nhượng quyền **+80.000đ/đêm**.

### 6. Hòm Thư Góp Ý Của Khách Hàng
- Khách dùng bữa xong gửi lời nhắn góp ý chân thành và dí dỏm về quán.
- Tab **"Đánh giá & Góp ý"** tích hợp mục **💡 Hòm Thư Góp Ý Của Khách**: Chủ quán bấm nút **"Ghi nhận & Cảm ơn (+20 XP)"** để nhận ngay điểm kinh nghiệm.

### 7. Trang Quản Trị Hệ Thống (Admin Panel - `/admin.html`)
- Dashboard trực quan quản lý Bảng xếp hạng trực tuyến, lịch sử Giải mì, mã đồng bộ đám mây và cấu hình toàn server.

---

## 🛠️ Kiến Trúc Backend Server (`server.py`)

Backend server được viết bằng Python chuẩn (Zero Dependency) kết hợp cơ sở dữ liệu **SQLite** (`data/tiemmicay.db`):

| Endpoint | Method | Chức năng |
| :--- | :---: | :--- |
| `/admin.html` | `GET` | **Trang quản trị Admin Panel** giao diện trực quan |
| `/api/admin/overview` | `GET` | Thống kê số lượng bản lưu đám mây, nhật ký chọc quán |
| `/api/admin/player/delete`| `POST` | Xóa người chơi/tiệm mì khỏi bảng xếp hạng |
| `/api/admin/save/delete` | `POST` | Xóa bản lưu đám mây |
| `/api/lb` | `GET / POST` | Bảng xếp hạng trực tuyến: Lưu điểm, tổng lãi, số ngày, cấp độ và xếp hạng người chơi toàn cầu |
| `/api/chal` | `GET / POST` | Thử thách Giải mì: Cung cấp đề thi ngày, cấp token thi đấu, ghi nhận điểm và xếp hạng |
| `/api/sync` | `GET / POST` | Đồng bộ đám mây: Tạo mã 8 ký tự (vd `K7QX-2M9P`) để chuyển tiến trình sang máy khác (hạn 24h) |
| `/api/prank` | `GET / POST` | Tính năng Chọc quán khác: Gửi quà, hoa hoặc chọc phá giữa các quán mì lân cận |
| `/api/ai` | `POST` | Dịch vụ AI phản hồi đánh giá: Tự động tạo câu trả lời của khách khi chủ quán phản hồi review |
| `/api/err`, `/api/copy` | `POST` | Telemetry & phân tích chia sẻ |
| `/` | `GET` | Static Web Server: Phục vụ HTML, CSS, JS, nhạc nền MP3, Icons PWA |

---

## 💻 Cách Khởi Chạy Hệ Thống

Chạy toàn bộ cả Frontend, Backend và Admin Panel bằng một lệnh:

```bash
python server.py
```
- Truy cập vào **Game**: **`http://localhost:8000`**
- Truy cập vào **Trang Quản Trị Admin**: **`http://localhost:8000/admin.html`**
