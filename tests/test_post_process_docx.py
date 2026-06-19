import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from docs.post_process import post_process


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"


def _write_docx(path: Path, document_xml: str, settings_xml: str) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("word/document.xml", document_xml)
        docx.writestr("word/settings.xml", settings_xml)


def _read_xml(path: Path, member: str) -> ET.Element:
    with zipfile.ZipFile(path) as docx:
        return ET.fromstring(docx.read(member))


def test_post_process_adds_word_table_of_figures_fields(tmp_path):
    docx_path = tmp_path / "sample.docx"
    document_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="{W_NS}">
  <w:body>
    <w:p>
      <w:pPr><w:pStyle w:val="TableofFigures"/></w:pPr>
      <w:r><w:fldSimple w:instr="TOC \\h \\z \\c &quot;Bảng&quot;"/></w:r>
    </w:p>
    <w:p>
      <w:pPr><w:pStyle w:val="TableCaption"/></w:pPr>
      <w:r><w:fldChar w:fldCharType="begin"/></w:r>
      <w:r><w:instrText> PAGEREF _Toc123 \\h </w:instrText></w:r>
      <w:r><w:t>Bảng 1. Dòng danh mục đã cập nhật 3</w:t></w:r>
      <w:r><w:fldChar w:fldCharType="end"/></w:r>
    </w:p>
    <w:p>
      <w:pPr><w:pStyle w:val="TableCaption"/></w:pPr>
      <w:r><w:t>Bảng 1. Bảng thử nghiệm</w:t></w:r>
    </w:p>
    <w:p>
      <w:pPr><w:pStyle w:val="ImageCaption"/></w:pPr>
      <w:r><w:t>Hình 4. Hình thử nghiệm</w:t></w:r>
    </w:p>
  </w:body>
</w:document>
"""
    settings_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:settings xmlns:w="{W_NS}"/>
"""
    _write_docx(docx_path, document_xml, settings_xml)

    post_process(str(docx_path))

    document = _read_xml(docx_path, "word/document.xml")
    settings = _read_xml(docx_path, "word/settings.xml")

    toc_fields = [
        fld
        for fld in document.findall(f".//{W}fldSimple")
        if (fld.get(f"{W}instr") or "").startswith("TOC ")
    ]
    seq_instrs = [
        fld.get(f"{W}instr")
        for fld in document.findall(f".//{W}fldSimple")
        if (fld.get(f"{W}instr") or "").startswith("SEQ ")
    ]
    caption_styles = [
        pstyle.get(f"{W}val")
        for pstyle in document.findall(f".//{W}pPr/{W}pStyle")
        if pstyle.get(f"{W}val") in {"TableCaption", "ImageCaption", "Caption"}
    ]

    assert toc_fields[0].get(f"{W}dirty") is None
    assert document.find(f".//{W}r/{W}fldSimple") is None
    assert seq_instrs.count("SEQ Bảng \\r 1 \\* ARABIC") == 1
    assert "SEQ Hình \\r 4 \\* ARABIC" in seq_instrs
    assert caption_styles == ["TableCaption", "TableCaption", "ImageCaption"]
    assert settings.find(f"./{W}updateFields") is None
