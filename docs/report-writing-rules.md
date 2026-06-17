# Quy tắc viết báo cáo dành cho AI Agent

Tài liệu này định nghĩa các quy chuẩn định dạng và hành văn bắt buộc áp dụng khi viết hoặc cập nhật các báo cáo, tài liệu Markdown trong dự án này (đặc biệt khi chuyển đổi sang định dạng Word .docx qua Pandoc).

## 1. Định dạng văn bản (Formatting)
* **Không bôi đậm dưới mọi hình thức:** Tuyệt đối KHÔNG sử dụng cú pháp bôi đậm (`**` hoặc `__`) ở bất kỳ đâu trong toàn bộ tài liệu, bao gồm nội dung chính, tiêu đề, bảng biểu (kể cả tiêu đề cột), chú thích, v.v. Tất cả văn bản phải sử dụng định dạng chữ thường (regular).
* **Đúng:** `Yếu tố A có mức đóng góp lớn nhất trong mô hình.`
* **Sai:** `Yếu tố **A** có mức đóng góp lớn nhất trong mô hình.`

## 2. Cấu trúc tiêu đề (Headings)
* **Quy chuẩn đánh số tiêu đề:** Agent phải tự động đánh số thứ tự thủ công vào các tiêu đề Markdown theo cấu trúc phân cấp dưới đây. Không phụ thuộc vào bộ tự động đánh số của trình biên dịch.
* **Cấu trúc phân cấp:**
  * Tiêu đề chính (Title / Level 1 heading `#`): `# 1. [Tên tiêu đề]`
  * Tiêu đề cấp 2 (Level 2 heading `##`): `## 1.1 [Tên tiêu đề]`
  * Tiêu đề cấp 3 (Level 3 heading `###`): `### 1.1.1 [Tên tiêu đề]`
* **Đúng:**
  ```markdown
  # 1. Giới thiệu
  ## 1.1 Tổng quan về mô hình
  ### 1.1.1 Phương pháp phân tích
  ```
* **Sai:**
  ```markdown
  # Giới thiệu
  ## Tổng quan
  ```

## 3. Cấu trúc nội dung (Paragraph Layout)
* **Trình bày dạng đoạn văn mạch lạc:** Tuyệt đối KHÔNG sử dụng danh sách gạch đầu dòng (bullet points như `-`, `*`, `+`) hoặc danh sách đánh số tự động trong văn bản chính.
* **Nguyên tắc viết:** Mọi ý kiến, danh sách hoặc quy trình phải được viết dưới dạng các câu hoàn chỉnh, liên kết logic và tổ chức thành các đoạn văn (paragraphs) mạch lạc.
* **Đúng:**
  `Mô hình phân tích sử dụng các biến đầu vào quan trọng bao gồm biến A, biến B, biến C và biến D.`
* **Sai:**
  `Mô hình phân tích sử dụng các biến đầu vào quan trọng sau:`
  `- Biến A`
  `- Biến B`
  `- Biến C`

## 4. Phong cách diễn đạt (Style & Tone)
* **Tính liên kết và xuyên suốt:** Văn phong học thuật, chuyên nghiệp, rõ ràng. Đảm bảo mạch lập luận logic chảy suốt từ đoạn này sang đoạn khác.
* **Tránh diễn đạt rời rạc:** Không viết các câu ngắn cụt ngủn hoặc các ý rời rạc thiếu từ nối/liên kết ngữ nghĩa.

## 5. Quy tắc bảng biểu trong Markdown
* **Caption bảng bắt buộc theo chuẩn Pandoc:** Mỗi bảng phải có caption dạng `Table: Bảng 1. Tên bảng mô tả nội dung` để Pandoc có thể nhận diện và chuyển đổi nhất quán sang Word.
* **Anchor ổn định cho danh mục bảng:** Nếu bảng xuất hiện trong danh mục bảng biểu hoặc được tham chiếu trong nội dung, đặt anchor ngay trước caption, ví dụ `<a id="bang-1"></a>`.
* **Không bôi đậm trong bảng:** Tiêu đề cột, ô dữ liệu, dòng nhóm và chú thích trong bảng đều phải tuân thủ quy tắc không bôi đậm.
* **Bảng phải có tiêu đề cột rõ nghĩa:** Tên cột cần đủ thông tin để người đọc hiểu nội dung mà không phải suy đoán, ví dụ `Tổng số (N = 970)`, `Nhóm A (n = 593)`, `Nhóm B (n = 377)` và `Giá trị p`.
* **Không chia đều cột một cách máy móc:** Khi viết bảng nguồn, cần nhận diện cột nào chứa nhãn dài, cột nào chứa số liệu ngắn, cột nào chứa p-value. Việc căn chiều rộng cuối cùng được xử lý ở bước chuyển DOCX, nhưng cấu trúc bảng Markdown phải phản ánh đúng loại nội dung của từng cột.

## 6. Quy tắc trình bày p-value trong bảng đặc điểm nền
* **Biến liên tục hoặc biến nhị phân:** Ghi p-value trực tiếp trên cùng dòng biến.
* **Biến phân loại nhiều mức:** Chỉ ghi p-value tổng thể ở dòng biến cha, ví dụ `Nhóm phân loại`, `Loại đối tượng` hoặc `Mức độ phân tầng`. Các dòng mức con như `Mức 1`, `Mức 2`, `Nhóm con A` hoặc `Nhóm con B` không được lặp lại p-value.
* **Không hiểu ô p-value trống là thiếu dữ liệu:** Ô p-value trống ở dòng mức con thể hiện rằng kiểm định được thực hiện cho toàn bộ biến phân loại, không phải kiểm định riêng từng mức con.
* **Không lặp cùng một p-value xuống các dòng con:** Việc lặp p-value ở từng mức con dễ gây hiểu nhầm rằng từng dòng được kiểm định độc lập.

## 7. Quy tắc xuống dòng trong ô bảng
* **Dùng `<br>` khi ô cần nhiều dòng:** Với bảng cấu hình mô hình hoặc bảng có danh sách tham số, mỗi ý hoặc mỗi tham số nên được ngăn bằng `<br>` trong Markdown nguồn.
* **Bảng cấu hình mô hình:** Cột `Cấu hình tham số chính` phải trình bày một tham số trên một dòng trong bản Word cuối cùng. Không để chuỗi dày đặc kiểu `key: value;key: value;key: value` trong DOCX.
* **Không giả định `<br>` luôn render đúng trong Word:** Sau khi chuyển sang DOCX, phải kiểm tra theo quy tắc trong `docs/docx-conversion-rules.md` để bảo đảm `<br>` đã trở thành line break thật trong ô Word.

## 8. Đồng bộ bảng, hình, caption và danh mục
* **Tên trong danh mục phải khớp caption:** Mục trong `Danh mục bảng biểu` và `Danh mục hình vẽ` phải trùng với caption thực tế trong nội dung.
* **Số thứ tự phải nhất quán:** Không bỏ qua hoặc lặp số bảng/hình.
* **Tham chiếu trong nội dung:** Khi nhắc đến bảng hoặc hình trong đoạn văn, dùng đúng số và tên đã khai báo, ví dụ `Bảng 1` hoặc `Hình 4`.
* **Quy tắc DOCX riêng:** Các yêu cầu về sequence field, danh mục tự động, chiều rộng cột, font bảng và kiểm tra render được quy định trong `docs/docx-conversion-rules.md`.
