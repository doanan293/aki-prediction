import zipfile
import os
import sys
from copy import deepcopy
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"
XML_NS = "http://www.w3.org/XML/1998/namespace"

ET.register_namespace("w", W_NS)


def _w(tag):
    return f"{W}{tag}"


def _paragraph_text(paragraph):
    return "".join(node.text or "" for node in paragraph.findall(f".//{_w('t')}"))


def _contains_field_result(paragraph):
    if paragraph.find(f".//{_w('instrText')}") is not None:
        return True

    if paragraph.find(f".//{_w('fldChar')}") is not None:
        return True

    return False


def _run_with_text(text, preserve_space=True):
    run = ET.Element(_w("r"))
    text_node = ET.SubElement(run, _w("t"))
    if preserve_space:
        text_node.set(f"{{{XML_NS}}}space", "preserve")
    text_node.text = text
    return run


def _seq_field(label, number):
    field = ET.Element(_w("fldSimple"))
    field.set(_w("instr"), f"SEQ {label} \\r {number} \\* ARABIC")
    run = ET.SubElement(field, _w("r"))
    text_node = ET.SubElement(run, _w("t"))
    text_node.text = number
    return field


def _remove_bookmarks(root):
    bookmark_tags = {_w("bookmarkStart"), _w("bookmarkEnd")}
    for parent in root.iter():
        for child in list(parent):
            if child.tag in bookmark_tags:
                parent.remove(child)


def _unwrap_toc_fields(root):
    for paragraph in root.findall(f".//{_w('p')}"):
        for index, child in enumerate(list(paragraph)):
            if child.tag != _w("r"):
                continue

            run_children = list(child)
            if len(run_children) != 1 or run_children[0].tag != _w("fldSimple"):
                continue

            field = run_children[0]
            instr = field.get(_w("instr")) or ""
            if not instr.startswith("TOC "):
                continue

            child.remove(field)
            paragraph.remove(child)
            paragraph.insert(index, field)

    for field in root.findall(f".//{_w('fldSimple')}"):
        instr = field.get(_w("instr")) or ""
        if instr.startswith("TOC ") and _w("dirty") in field.attrib:
            del field.attrib[_w("dirty")]


def _add_caption_sequence_fields(root):
    caption_pattern = re_caption_pattern()
    for paragraph in root.findall(f".//{_w('p')}"):
        if _contains_field_result(paragraph):
            continue

        pstyle = paragraph.find(f"./{_w('pPr')}/{_w('pStyle')}")
        if pstyle is None:
            continue

        text = _paragraph_text(paragraph)
        match = caption_pattern.match(text)
        if not match:
            continue

        label, number, suffix = match.groups()
        pstyle.set(_w("val"), "TableCaption" if label == "Bảng" else "ImageCaption")

        paragraph_properties = paragraph.find(f"./{_w('pPr')}")
        for child in list(paragraph):
            if child is not paragraph_properties:
                paragraph.remove(child)

        paragraph.append(_run_with_text(f"{label} "))
        paragraph.append(_seq_field(label, number))
        paragraph.append(_run_with_text(f".{suffix}"))


def re_caption_pattern():
    import re

    return re.compile(r"^(Bảng|Hình)\s+(\d+)\.(.*)$")


def _table_borders():
    borders = ET.Element(_w("tblBorders"))
    for tag in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = ET.SubElement(borders, _w(tag))
        border.set(_w("val"), "single")
        border.set(_w("sz"), "4")
        border.set(_w("space"), "0")
        border.set(_w("color"), "auto")
    return borders


def _get_or_add(parent, tag, insert_at=None):
    child = parent.find(f"./{_w(tag)}")
    if child is not None:
        return child

    child = ET.Element(_w(tag))
    if insert_at is None:
        parent.append(child)
    else:
        parent.insert(insert_at, child)
    return child


def _set_table_column_widths(table, widths):
    table_properties = _get_or_add(table, "tblPr", 0)

    table_width = _get_or_add(table_properties, "tblW", 0)
    table_width.set(_w("w"), str(sum(widths)))
    table_width.set(_w("type"), "dxa")

    layout = table_properties.find(f"./{_w('tblLayout')}")
    if layout is None:
        layout = ET.Element(_w("tblLayout"))
        table_properties.insert(1, layout)
    layout.set(_w("type"), "fixed")

    grid = table.find(f"./{_w('tblGrid')}")
    if grid is None:
        grid = ET.Element(_w("tblGrid"))
        table.insert(1 if table.find(f"./{_w('tblPr')}") is not None else 0, grid)

    for child in list(grid):
        grid.remove(child)
    for width in widths:
        col = ET.SubElement(grid, _w("gridCol"))
        col.set(_w("w"), str(width))

    for row in table.findall(f"./{_w('tr')}"):
        col_index = 0
        for cell in row.findall(f"./{_w('tc')}"):
            cell_properties = _get_or_add(cell, "tcPr", 0)
            span_node = cell_properties.find(f"./{_w('gridSpan')}")
            span = int(span_node.get(_w("val"), "1")) if span_node is not None else 1
            cell_width_value = sum(widths[col_index : col_index + span])

            cell_width = _get_or_add(cell_properties, "tcW", 0)
            cell_width.set(_w("w"), str(cell_width_value))
            cell_width.set(_w("type"), "dxa")
            col_index += span


def _set_table_font_size(table, half_points):
    for run in table.findall(f".//{_w('r')}"):
        run_properties = _get_or_add(run, "rPr", 0)
        size = _get_or_add(run_properties, "sz")
        size.set(_w("val"), str(half_points))
        complex_script_size = _get_or_add(run_properties, "szCs")
        complex_script_size.set(_w("val"), str(half_points))

    for size in table.findall(f".//{_w('sz')}") + table.findall(f".//{_w('szCs')}"):
        size.set(_w("val"), str(half_points))


def _run_with_break():
    run = ET.Element(_w("r"))
    ET.SubElement(run, _w("br"))
    return run


def _set_cell_lines(cell, lines):
    paragraphs = cell.findall(f"./{_w('p')}")
    if paragraphs:
        paragraph = paragraphs[0]
        for extra_paragraph in paragraphs[1:]:
            cell.remove(extra_paragraph)
    else:
        paragraph = ET.SubElement(cell, _w("p"))

    paragraph_properties = paragraph.find(f"./{_w('pPr')}")
    for child in list(paragraph):
        if child is not paragraph_properties:
            paragraph.remove(child)

    for index, line in enumerate(lines):
        paragraph.append(_run_with_text(line, preserve_space=False))
        if index < len(lines) - 1:
            paragraph.append(_run_with_break())


def _split_config_lines(text):
    parts = [part.strip() for part in text.split(";") if part.strip()]
    lines = []
    for index, part in enumerate(parts):
        suffix = ";" if index < len(parts) - 1 else ""
        lines.append(f"{part}{suffix}")
    return lines or [text]


def _add_configuration_table_line_breaks(table):
    rows = table.findall(f"./{_w('tr')}")
    for row_index, row in enumerate(rows[1:], start=1):
        cells = row.findall(f"./{_w('tc')}")
        if len(cells) < 3:
            continue

        if row_index == 1:
            _set_cell_lines(cells[1], ["TabPFN-3-Plus", "– mô hình đề xuất"])

        config_text = "".join(node.text or "" for node in cells[2].findall(f".//{_w('t')}"))
        _set_cell_lines(cells[2], _split_config_lines(config_text))


def _adjust_table_column_widths(root):
    table_widths = [
        [2000, 3600],
        [2400, 1850, 2050, 2050, 1010],
        [4550, 1700, 3110],
        [720, 1800, 3420, 3420],
        [1700, 850, 1100, 1060, 1120, 1200, 750, 750, 830],
        [1700, 850, 1100, 1060, 1120, 1200, 750, 750, 830],
    ]

    tables = root.findall(f".//{_w('tbl')}")
    for table, widths in zip(tables, table_widths):
        _set_table_column_widths(table, widths)

    if len(tables) >= 4:
        _add_configuration_table_line_breaks(tables[3])

    for table in tables:
        _set_table_font_size(table, 24)


def _add_table_borders(root):
    for table_properties in root.findall(f".//{_w('tblPr')}"):
        if table_properties.find(f"./{_w('tblBorders')}") is not None:
            continue

        insert_at = 0
        for index, child in enumerate(list(table_properties)):
            if child.tag == _w("tblStyle"):
                insert_at = index + 1
                break
        table_properties.insert(insert_at, deepcopy(_table_borders()))


def _disable_automatic_field_updates(settings_xml):
    if settings_xml is None:
        return None

    root = ET.fromstring(settings_xml)
    update_fields = root.find(f"./{_w('updateFields')}")
    if update_fields is not None:
        root.remove(update_fields)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _process_document_xml(data):
    root = ET.fromstring(data)
    _remove_bookmarks(root)
    _unwrap_toc_fields(root)
    _add_caption_sequence_fields(root)
    _adjust_table_column_widths(root)
    _add_table_borders(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)

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
                    data = _process_document_xml(data)
                elif item.filename == "word/settings.xml":
                    data = _disable_automatic_field_updates(data)
                yout.writestr(item, data)
                
    os.replace(temp_path, docx_path)
    print(f"Đã thực hiện hậu xử lý (loại bỏ bookmark, thêm viền bảng, sửa field danh mục) thành công cho tệp: {docx_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Sử dụng: python3 post_process.py <path_to_docx>")
        sys.exit(1)
    post_process(sys.argv[1])
