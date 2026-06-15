# Quy tắc viết báo cáo dành cho AI Agent

Tài liệu này định nghĩa các quy chuẩn định dạng và hành văn bắt buộc áp dụng khi viết hoặc cập nhật các báo cáo, tài liệu Markdown trong dự án này (đặc biệt khi chuyển đổi sang định dạng Word .docx qua Pandoc).

## 1. Định dạng văn bản (Formatting)
* **Không bôi đậm dưới mọi hình thức:** Tuyệt đối KHÔNG sử dụng cú pháp bôi đậm (`**` hoặc `__`) ở bất kỳ đâu trong toàn bộ tài liệu, bao gồm nội dung chính, tiêu đề, bảng biểu (kể cả tiêu đề cột), chú thích, v.v. Tất cả văn bản phải sử dụng định dạng chữ thường (regular).
* **Đúng:** `Trọng số của BUN là lớn nhất trong mô hình.`
* **Sai:** `Trọng số của **BUN** là lớn nhất trong mô hình.`

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
  ### 1.1.1 Thuật toán XGBoost
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
  `Mô hình XGBoost sử dụng các đặc trưng đầu vào quan trọng bao gồm BUN, lượng nước tiểu, cân nặng, tuổi tác và tiểu cầu.`
* **Sai:**
  `Mô hình XGBoost sử dụng các đặc trưng đầu vào quan trọng sau:`
  `- BUN`
  `- Lượng nước tiểu`
  `- Cân nặng`

## 4. Phong cách diễn đạt (Style & Tone)
* **Tính liên kết và xuyên suốt:** Văn phong học thuật, chuyên nghiệp, rõ ràng. Đảm bảo mạch lập luận logic chảy suốt từ đoạn này sang đoạn khác.
* **Tránh diễn đạt rời rạc:** Không viết các câu ngắn cụt ngủn hoặc các ý rời rạc thiếu từ nối/liên kết ngữ nghĩa.