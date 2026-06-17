# Quy tắc chuyển đổi Markdown sang DOCX

Tài liệu này quy định các bước kỹ thuật bắt buộc khi chuyển báo cáo Markdown sang Word `.docx`, đặc biệt với các tài liệu được tạo qua Pandoc và hậu xử lý bằng script trong dự án.

## 1. Nguyên tắc chung
* **Markdown là nguồn nội dung chính:** Nội dung học thuật, bảng dữ liệu, caption, anchor và tham chiếu phải được viết đúng trong file `.md` trước khi chuyển đổi.
* **DOCX cần hậu xử lý:** Không giả định Pandoc tự tạo ra mọi định dạng Word mong muốn. Sau khi sinh DOCX, phải chạy bước hậu xử lý để chuẩn hóa caption, danh mục, viền bảng, width cột và line break trong ô bảng nếu cần.
* **Không sửa tay DOCX thay cho sửa nguồn:** Nếu lỗi xuất phát từ nội dung hoặc cấu trúc Markdown, sửa trong `.md`. Nếu lỗi xuất phát từ render Word, ghi nhận vào script hậu xử lý hoặc quy tắc chuyển đổi.

## 2. Quy tắc bảng trong DOCX
* **Font bảng mặc định là 12 pt:** Không giảm font bảng xuống 10 pt hoặc nhỏ hơn nếu người dùng không yêu cầu rõ ràng.
* **Dùng layout cố định cho bảng phức tạp:** Các bảng nhiều cột hoặc bảng có nội dung dài phải dùng fixed layout và width rõ ràng để tránh Word/LibreOffice tự chia cột sai.
* **Dùng đơn vị DXA cho width:** Khi can thiệp XML, đặt `tblW`, `tblGrid/gridCol` và `tcW` bằng đơn vị DXA. Không phụ thuộc vào percentage width nếu cần render ổn định giữa Word, LibreOffice và Google Docs.
* **Không chia đều cột theo mặc định:** Width cột phải dựa trên nội dung. Cột tên biến, tên mô hình hoặc diễn giải cần rộng hơn; cột `STT`, `Giá trị p`, `PPV`, `NPV` thường hẹp hơn.
* **Tổng width phải khớp vùng nội dung:** Với trang Letter margin 1 inch, width nội dung thường là 9360 DXA. Tổng các cột của bảng full-width phải khớp giá trị này.

## 3. Quy tắc line break trong ô bảng
* **`<br>` trong Markdown phải thành line break Word thật:** Sau chuyển đổi, kiểm tra trong `word/document.xml` để bảo đảm line break được biểu diễn bằng `w:br`.
* **Bảng cấu hình mô hình:** Cột `Cấu hình tham số chính` phải hiển thị mỗi tham số trên một dòng. Ví dụ `model_path`, `device` và `random_state` phải nằm trên các dòng riêng.
* **Không chỉ dựa vào word wrap tự động:** Word wrap theo width cột không thay thế cho line break có chủ đích trong các ô cấu hình hoặc danh sách tham số.

## 4. Caption, sequence field và danh mục
* **Caption bảng/hình phải chuyển thành sequence field:** Caption dạng `Bảng 1. Đặc điểm lâm sàng nền của hai nhóm bệnh nhân` và `Hình 4. Kiến trúc mô hình TabPFN-3-Plus` cần được hậu xử lý thành sequence field để danh mục bảng/hình hoạt động ổn định.
* **Danh mục không được tự động cập nhật gây lệch:** Nếu Word tự cập nhật field làm hỏng danh mục, cần tắt automatic field update trong settings hoặc dùng hậu xử lý đã kiểm soát.
* **Bookmark thừa cần được loại bỏ:** Bookmark sinh ra trong quá trình chuyển đổi có thể làm danh mục hoặc field hoạt động không ổn định, nên được loại bỏ trong hậu xử lý nếu không cần thiết.

## 5. Kiểm tra sau chuyển đổi
* **Kiểm tra DOCX là ZIP hợp lệ:** Chạy `unzip -t path/to/file.docx` và yêu cầu không có lỗi.
* **Kiểm tra XML bảng:** Đọc `word/document.xml` để xác nhận số bảng, số cột, `tblGrid`, `tcW`, font size và số lượng `w:br` ở các bảng quan trọng.
* **Convert sang PDF để kiểm tra render:** Dùng LibreOffice headless để chuyển DOCX sang PDF, sau đó render các trang có bảng chính bằng `pdftoppm`.
* **Kiểm tra trực quan các bảng chính:** Bảng đặc điểm nền, bảng tỷ lệ khuyết thiếu, bảng cấu hình mô hình và hai bảng hiệu năng phải được kiểm tra bằng ảnh render hoặc mở trong Word/LibreOffice.
* **Cảnh báo ảnh không đồng nghĩa lỗi DOCX:** Cảnh báo kiểu `libpng warning: zTXt: CRC error` thường liên quan metadata ảnh nhúng. Nếu conversion vẫn exit code 0 và PDF render được, cảnh báo này không phải lỗi cấu trúc DOCX.

## 6. Quan hệ với quy tắc viết báo cáo
* **Quy tắc viết nội dung nằm ở `docs/report-writing-rules.md`:** File đó quyết định cách viết Markdown nguồn, cách trình bày p-value và cách đặt caption/anchor.
* **Quy tắc này chỉ áp dụng cho chuyển đổi và hậu xử lý:** File này quyết định cách xác minh và sửa render DOCX sau khi nội dung Markdown đã đúng.
