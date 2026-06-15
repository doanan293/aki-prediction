-- Lua filter to remove elements with class 'markdown-only' when converting to Word (.docx)
function Div(el)
  if el.classes:includes('markdown-only') then
    return {}
  end
end
