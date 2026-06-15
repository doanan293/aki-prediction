import zipfile
import re
import os
import sys

def post_process(docx_path):
    if not os.path.exists(docx_path):
        print(f"Lỗi: Không tìm thấy tệp {docx_path}")
        sys.exit(1)
        
    temp_path = docx_path + ".tmp"
    
    with zipfile.ZipFile(docx_path, 'r') as yin:
        with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as yout:
            for item in yin.infolist():
                data = yin.read(item.filename)
                if item.filename == "word/document.xml":
                    xml_content = data.decode("utf-8")
                    # Lọc bỏ thẻ bookmarkStart và bookmarkEnd
                    xml_content = re.sub(r'<w:bookmarkStart[^>]*?>', '', xml_content)
                    xml_content = re.sub(r'<w:bookmarkEnd[^>]*?>', '', xml_content)
                    
                    # Thêm viền đầy đủ cho tất cả các bảng
                    borders_xml = (
                        '<w:tblBorders>'
                        '<w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
                        '<w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
                        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
                        '<w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
                        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
                        '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
                        '</w:tblBorders>'
                    )
                    # Chèn tblBorders SAU <w:tblStyle .../> nếu có (self-closing tag)
                    # (OOXML schema yêu cầu tblBorders đứng sau tblStyle)
                    xml_content = re.sub(
                        r'(<w:tblStyle\b[^/]*/\s*>)',
                        r'\1' + borders_xml,
                        xml_content
                    )
                    # Với bảng không có tblStyle, chèn sau <w:tblPr>
                    xml_content = re.sub(
                        r'(<w:tblPr>)(?!.*?<w:tblBorders)',
                        r'\1' + borders_xml,
                        xml_content,
                        flags=re.DOTALL
                    )
                    data = xml_content.encode("utf-8")
                yout.writestr(item, data)
                
    os.replace(temp_path, docx_path)
    print(f"Đã thực hiện hậu xử lý (loại bỏ bookmark, thêm viền bảng) thành công cho tệp: {docx_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Sử dụng: python3 post_process.py <path_to_docx>")
        sys.exit(1)
    post_process(sys.argv[1])
