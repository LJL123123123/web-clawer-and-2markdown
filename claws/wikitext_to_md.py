"""
MediaWiki wikitext to Markdown converter.
Uses mwparserfromhell for structured parsing + regex for structural elements.
"""

import re
import mwparserfromhell


# ---- Template name patterns to strip entirely ----
_STRIP_TEMPLATES = {
    "infobox", "navbox", "sidebar", "reflist", "refbegin", "refend",
    "citation needed", "cite", "citation", "stub", "stub-",
    "as of", "update after", "clarify", "clarification needed",
    "cn", "fact", "dubious", "disputed inline",
    "toc", "toc limit", "tocleft", "tocright",
    "clear", "clear left", "clear right",
    "main", "see also", "seealso", "further", "details",
    "distinguish", "redirect", "for", "about",
    "short description", "shortdesc",
    "use dmy dates", "use mdy dates", "engvar",
    "commons", "commons category", "wikiquote", "wikisource", "wiktionary",
    "pp-", "protection", "pp",
    "italic title", "italicize title",
    "featured article", "good article",
    "defaultsort", "dEFAULTSORT", "displaytitle", "DISPLAYTITLE",
    "coord", "coords",
    "nihongo", "zh", "lang", "lang-",
    "anchor", "nbsp", "nowrap", "wbr",
    "efn", "notelist", "notelist-ua",
    "rp", "r", "refn",
    "snd", "small", "big", "sup", "sub",
    "color", "colored", "background",
}


def convert_wikitext_to_md(wikitext, title=""):
    """
    Convert MediaWiki wikitext to Markdown.

    Args:
        wikitext: Raw wikitext string.
        title: Page title (used for heading and context).

    Returns:
        Markdown string.
    """
    if not wikitext or not wikitext.strip():
        return f"# {title}\n\n*(空页面)*\n"

    try:
        code = mwparserfromhell.parse(wikitext)
    except Exception:
        # If mwparserfromhell fails, fall back to regex-only conversion
        return _regex_fallback(wikitext, title)

    md_lines = []

    # Add page title
    md_lines.append(f"# {title}")
    md_lines.append("")

    # Process top-level nodes
    for node in code.nodes:
        text = _convert_node(node)
        if text and text.strip():
            md_lines.append(text)

    result = "\n\n".join(md_lines)

    # Clean up
    result = _cleanup(result)

    return result


def _convert_node(node):
    """Convert a single mwparserfromhell node to Markdown text."""
    node_type = type(node).__name__

    # ---- Templates ----
    if node_type == "Template":
        name = str(node.name).strip().lower().replace("_", " ")
        # Strip known non-content templates
        if any(name.startswith(t) for t in _STRIP_TEMPLATES):
            return ""
        # For other templates, just strip silently
        return ""

    # ---- Wikilinks ----
    if node_type == "Wikilink":
        target = str(node.title).strip()
        text = str(node.text) if node.text else target

        # Skip file/image embeds
        if target.lower().startswith(("file:", "image:", "media:")):
            return ""

        # Handle interwiki / namespace prefixes we want to skip
        if ":" in target:
            prefix = target.split(":", 1)[0].lower().strip()
            if prefix in ("category", "file", "image", "help", "template"):
                return ""

        # Anchor/section links
        target = target.split("#")[0]

        if text == target:
            return f"[{text}]({target.replace(' ', '_')}.md)"
        else:
            return f"[{text}]({target.replace(' ', '_')}.md)"

    # ---- External links ----
    if node_type == "ExternalLink":
        url = str(node.url).strip()
        text = str(node.title).strip() if node.title else url
        return f"[{text}]({url})"

    # ---- Tags (<ref>, etc.) ----
    if node_type == "Tag":
        return ""  # Strip all tags (ref, gallery, source, etc.)

    # ---- HTML entities / comments / text ----
    if node_type in ("HTMLEntity",):
        return str(node)

    if node_type == "Comment":
        return ""

    # ---- Headings ----
    if node_type == "Heading":
        level = node.level
        text = str(node.title).strip()
        return f"{'#' * level} {text}"

    # ---- Text ----
    if node_type == "Text":
        return _convert_inline_formatting(str(node))

    # ---- Generic fallback ----
    return str(node)


def _convert_inline_formatting(text):
    """
    Convert inline wikitext formatting to Markdown.
    Assumes templates and links have already been handled.
    """
    # Bold+italic (5 quotes)
    text = re.sub(r"'''''(.+?)'''''", r"***\1***", text)

    # Bold (3 quotes)
    text = re.sub(r"'''(.+?)'''", r"**\1**", text)

    # Italic (2 quotes)
    text = re.sub(r"''(.+?)''", r"*\1*", text)

    # Strikethrough
    text = re.sub(r"<s>(.+?)</s>", r"~~\1~~", text)
    text = re.sub(r"<strike>(.+?)</strike>", r"~~\1~~", text)

    # Underline
    text = re.sub(r"<u>(.+?)</u>", r"<u>\1</u>", text)

    return text


def _regex_fallback(wikitext, title):
    """
    Pure regex-based wikitext→MD conversion.
    Used when mwparserfromhell fails to parse.
    """
    md = [f"# {title}", ""]

    # Remove HTML comments
    wikitext = re.sub(r"<!--.*?-->", "", wikitext, flags=re.DOTALL)

    # Remove templates (best-effort, handles nested braces)
    wikitext = _strip_templates_regex(wikitext)

    # Remove <ref>...</ref> and <ref ... />
    wikitext = re.sub(r"<ref[^>]*?/>", "", wikitext, flags=re.IGNORECASE)
    wikitext = re.sub(r"<ref[^>]*?>.*?</ref>", "", wikitext, flags=re.DOTALL | re.IGNORECASE)

    # Remove <gallery>, <source>, <syntaxhighlight>, <pre>, <code> blocks
    for tag in ("gallery", "source", "syntaxhighlight", "pre", "code",
                 "blockquote", "div", "span", "center", "font"):
        wikitext = re.sub(
            rf"<{tag}[^>]*?>.*?</{tag}>",
            "", wikitext, flags=re.DOTALL | re.IGNORECASE
        )
        wikitext = re.sub(
            rf"<{tag}[^>]*?/>",
            "", wikitext, flags=re.IGNORECASE
        )

    # Convert headings
    wikitext = re.sub(r"^======(.+?)======\s*$", r"###### \1", wikitext, flags=re.MULTILINE)
    wikitext = re.sub(r"^=====(.+?)=====\s*$", r"##### \1", wikitext, flags=re.MULTILINE)
    wikitext = re.sub(r"^====(.+?)====\s*$", r"#### \1", wikitext, flags=re.MULTILINE)
    wikitext = re.sub(r"^===(.+?)===\s*$", r"### \1", wikitext, flags=re.MULTILINE)
    wikitext = re.sub(r"^==(.+?)==\s*$", r"## \1", wikitext, flags=re.MULTILINE)

    # Convert horizontal rules
    wikitext = re.sub(r"^----+\s*$", "---", wikitext, flags=re.MULTILINE)

    # Convert wikilinks [[Page|Text]] and [[Page]]
    wikitext = re.sub(
        r"\[\[([^\[\]\|]+?)\|([^\[\]]+?)\]\]",
        lambda m: f"[{m.group(2)}]({_sanitize_link_target(m.group(1))}.md)",
        wikitext
    )
    wikitext = re.sub(
        r"\[\[([^\[\]]+?)\]\]",
        lambda m: _handle_simple_wikilink(m.group(1)),
        wikitext
    )

    # Convert external links [http://... text]
    wikitext = re.sub(
        r"\[(https?://[^\]\s]+)\s+([^\]]+)\]",
        r"[\2](\1)",
        wikitext
    )

    # Plain external URLs
    wikitext = re.sub(
        r"(?<!\[)(https?://[^\s\]]+)",
        r"<\1>",
        wikitext
    )

    # Bold + Italic
    wikitext = re.sub(r"'''''(.+?)'''''", r"***\1***", wikitext)
    wikitext = re.sub(r"'''(.+?)'''", r"**\1**", wikitext)
    wikitext = re.sub(r"''(.+?)''", r"*\1*", wikitext)

    # Convert wikitext tables to Markdown tables
    wikitext = _convert_tables_regex(wikitext)

    # Strip remaining HTML tags
    wikitext = re.sub(r"<[^>]+>", "", wikitext)

    # Collapse blank lines
    wikitext = re.sub(r"\n{3,}", "\n\n", wikitext)

    return wikitext.strip() + "\n"


def _sanitize_link_target(target):
    """Clean a wikilink target for use as a filename."""
    target = target.strip().replace(" ", "_")
    # Remove namespace prefixes we skip
    parts = target.split(":", 1)
    if len(parts) > 1:
        prefix = parts[0].lower().strip()
        if prefix in ("category", "file", "image", "template", "help", "mediawiki",
                      "special", "user", "talk", "module", "gadget", "timedtext"):
            return ""
    return re.sub(r'[\\/:*?"<>|]', "_", target)


def _handle_simple_wikilink(target):
    """Handle a [[target]] wikilink."""
    target = target.strip()

    # Ignore file/image embeds
    if target.lower().startswith(("file:", "image:", "media:")):
        return ""

    # Ignore certain namespaces
    parts = target.split(":", 1)
    if len(parts) > 1:
        prefix = parts[0].lower().strip()
        if prefix in ("category", "file", "image", "template", "help", "mediawiki",
                      "special", "user", "talk", "module", "gadget", "timedtext"):
            return ""

    # Handle section links
    display = target.split("#")[0] if "#" in target else target
    clean_target = target.split("#")[0].replace(" ", "_")
    clean_target = re.sub(r'[\\/:*?"<>|]', "_", clean_target)

    if display == clean_target.replace("_", " "):
        return f"[{display}]({clean_target}.md)"
    else:
        return f"[{display}]({clean_target}.md)"


def _strip_templates_regex(text):
    """
    Strip MediaWiki templates using brace counting.
    Handles nested templates (e.g., {{a|{{b}}}}).
    """
    result = []
    i = 0
    depth = 0
    start = -1

    while i < len(text):
        if text[i:i+2] == "{{" and (i == 0 or text[i-1] != "{"):
            if depth == 0:
                start = i
            depth += 1
            i += 2
            continue
        elif text[i:i+2] == "}}" and (i == 0 or text[i-1] != "}"):
            depth -= 1
            if depth == 0 and start >= 0:
                # Strip the template
                result.append("")  # placeholder
                start = -1
            i += 2
            continue
        elif depth == 0:
            result.append(text[i])
        i += 1

    return "".join(result)


def _convert_tables_regex(text):
    """
    Convert MediaWiki table syntax to Markdown tables.
    Handles basic {| ... |} tables.
    """
    lines = text.split("\n")
    result = []
    in_table = False
    table_lines = []
    has_header = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("{|"):
            in_table = True
            table_lines = []
            has_header = False
            continue

        if in_table:
            if stripped.startswith("|}"):
                # End of table — convert to MD
                md_table = _wikitable_to_md(table_lines, has_header)
                if md_table:
                    result.append(md_table)
                in_table = False
                table_lines = []
                continue

            if stripped.startswith("|+"):
                # Caption — skip
                continue

            if stripped.startswith("|-"):
                # Row separator — mark previous row
                table_lines.append("|-|")
                continue

            if stripped.startswith("!"):
                has_header = True
                table_lines.append(stripped)
                continue

            if stripped.startswith("|"):
                table_lines.append(stripped)
                continue

            # Multi-line content within table cell
            if table_lines:
                table_lines[-1] += " " + stripped

            continue

        result.append(line)

    return "\n".join(result)


def _wikitable_to_md(lines, has_header):
    """Convert a list of wikitable row lines to a Markdown table."""
    rows = []
    current_row = []

    for line in lines:
        if line == "|-|":
            if current_row:
                rows.append(current_row)
            current_row = []
        elif line.startswith("!"):
            # Header cell
            cells = _split_table_cells(line, header=True)
            current_row.extend(cells)
        elif line.startswith("|"):
            cells = _split_table_cells(line, header=False)
            current_row.extend(cells)

    if current_row:
        rows.append(current_row)

    if not rows:
        return ""

    # Normalize column count
    max_cols = max(len(r) for r in rows) if rows else 0
    if max_cols == 0:
        return ""

    md = []
    for i, row in enumerate(rows):
        # Pad row to max_cols
        padded = row + [""] * (max_cols - len(row))
        md.append("| " + " | ".join(padded) + " |")
        # Add header separator after first row if it's a header
        if i == 0 and has_header:
            md.append("| " + " | ".join(["---"] * max_cols) + " |")

    return "\n".join(md)


def _split_table_cells(line, header=False):
    """Split a wikitable row line into individual cells."""
    # Remove the leading ! or | and optional attributes
    if header:
        line = re.sub(r"^!+", "", line)
        cells = re.split(r"!!", line)
    else:
        line = re.sub(r"^\|", "", line)
        cells = re.split(r"\|\|", line)

    # Strip leading attributes (e.g., style="..." |)
    cleaned = []
    for cell in cells:
        cell = cell.strip()
        # Remove style/class attributes at start of cell content
        cell = re.sub(r"^(?:style|class|align|scope|rowspan|colspan|id|title|lang|dir|bgcolor|valign|width|height)\s*=\s*[\"'][^\"']*[\"']\s*", "", cell, flags=re.IGNORECASE)
        cell = cell.strip()
        # Remove any leading | that might remain
        cell = re.sub(r"^\|\s*", "", cell)
        cleaned.append(cell)
    return [c.strip() for c in cleaned]


def _cleanup(md_text):
    """Post-process Markdown text for cleanliness."""
    # Collapse 3+ blank lines
    md_text = re.sub(r"\n{3,}", "\n\n", md_text)

    # Remove trailing whitespace per line
    md_text = re.sub(r"[ \t]+$", "", md_text, flags=re.MULTILINE)

    # Ensure no lone empty lines between list items with same indent
    # (html2text and wikitext both preserve intended spacing)

    return md_text.strip() + "\n"
