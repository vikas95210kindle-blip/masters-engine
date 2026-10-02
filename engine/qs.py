"""Read the official QS World University Rankings by Subject workbook.

Stdlib only - this Mac has no openpyxl or pandas. An .xlsx is a zip of XML,
so we unzip it and parse directly.

Why this matters: until now the engine filtered on ranks carried in from
general knowledge and flagged ESTIMATED. Two of them turned out to be wrong
(Edinburgh, UCD). This replaces guesswork with the publisher's own file.
"""

import html
import os
import re
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_LOCAL = os.path.join(_HERE, os.pardir, "data", "qs", "qs-subject-2026.xlsx")
_ICLOUD = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/STUDIES/CVs/"
    "QS World University Rankings by Subject 2026 - Public Results v1.4 (qs.com)_18.xlsx")

# Prefer the copy inside the project. iCloud Drive evicts files it thinks are
# cold, and a ranking filter that silently stops working because a file was
# offloaded is exactly the kind of invisible failure this engine keeps hitting.
DEFAULT_PATH = _LOCAL if os.path.exists(_LOCAL) else _ICLOUD

_CELL = re.compile(r'<c r="([A-Z]+)(\d+)"([^>]*)>(.*?)</c>|<c r="([A-Z]+)(\d+)"([^>]*)/>', re.S)
_V = re.compile(r"<v>(.*?)</v>", re.S)
_T = re.compile(r"<t[^>]*>(.*?)</t>", re.S)


def _col(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


class Workbook:
    def __init__(self, path=DEFAULT_PATH):
        self.path = path
        self.z = zipfile.ZipFile(path)
        self.shared = self._shared_strings()
        self.sheets = self._sheet_map()

    def _shared_strings(self):
        try:
            xml = self.z.read("xl/sharedStrings.xml").decode("utf8", "ignore")
        except KeyError:
            return []
        out = []
        for si in re.findall(r"<si>(.*?)</si>", xml, re.S):
            out.append(html.unescape("".join(_T.findall(si))))
        return out

    def _sheet_map(self):
        wb = self.z.read("xl/workbook.xml").decode("utf8", "ignore")
        rels = self.z.read("xl/_rels/workbook.xml.rels").decode("utf8", "ignore")
        rid_to_target = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
        out = {}
        for name, rid in re.findall(r'<sheet name="([^"]+)"[^>]*r:id="([^"]+)"', wb):
            t = rid_to_target.get(rid, "")
            if not t.startswith("/"):
                t = "xl/" + t.lstrip("/")
            out[html.unescape(name)] = t.lstrip("/")
        return out

    def rows(self, sheet_name):
        """Yield rows as lists of strings."""
        target = self.sheets.get(sheet_name)
        if not target:
            for k in self.sheets:
                if k.lower().startswith(sheet_name.lower()[:22]):
                    target = self.sheets[k]
                    break
        if not target:
            raise KeyError("no sheet like %r" % sheet_name)
        xml = self.z.read(target).decode("utf8", "ignore")
        for rm in re.finditer(r"<row[^>]*>(.*?)</row>", xml, re.S):
            cells = {}
            for m in _CELL.finditer(rm.group(1)):
                if m.group(1):
                    col, attrs, body = m.group(1), m.group(3), m.group(4)
                else:
                    col, attrs, body = m.group(5), m.group(7), ""
                v = _V.search(body)
                raw = v.group(1) if v else ""
                if 't="s"' in attrs and raw.isdigit():
                    val = self.shared[int(raw)] if int(raw) < len(self.shared) else ""
                elif 't="inlineStr"' in attrs:
                    val = html.unescape("".join(_T.findall(body)))
                else:
                    val = raw
                cells[_col(col)] = html.unescape(val)
            if cells:
                width = max(cells) + 1
                yield [cells.get(i, "") for i in range(width)]


def subject_table(sheet_name, path=DEFAULT_PATH, limit=None):
    """Return the full subject table.

    The sheet's header row is the one whose first cell is a 4-digit year; that
    column IS the subject rank. An earlier version matched on the word "rank"
    and silently picked up ACADEMIC RANK instead, which put INSEAD (academic
    rank 1) above Harvard. Anchor on the year column.
    """
    wb = Workbook(path)
    rows = list(wb.rows(sheet_name))

    hdr_i = None
    for i, r in enumerate(rows[:20]):
        if r and re.fullmatch(r"20\d\d", (r[0] or "").strip()) and \
           any("institution" in (c or "").lower() for c in r):
            hdr_i = i
            break
    if hdr_i is None:
        return []
    hdr = [(c or "").strip().lower() for c in rows[hdr_i]]

    def col(*keys, exact=None):
        if exact is not None:
            for j, c in enumerate(hdr):
                if c == exact:
                    return j
        for j, c in enumerate(hdr):
            if all(k in c for k in keys):
                return j
        return None

    c_rank = 0
    c_prev = 1 if len(hdr) > 1 and re.fullmatch(r"20\d\d", hdr[1]) else None
    c_inst = col("institution")
    c_ctry = col("country") or col("territory")
    c_acad = col("academic", exact="academic")
    c_acad_r = col("academic", "rank")
    c_emp = col("employer", exact="employer")
    c_emp_r = col("employer", "rank")
    c_cit = col("citations", exact="citations")
    c_h = col("h", exact="h")
    c_irn = col("irn", exact="irn")

    def g(r, j):
        return r[j].strip() if (j is not None and j < len(r)) else ""

    def num(v):
        try:
            return round(float(v), 1)
        except (TypeError, ValueError):
            return None

    out = []
    for r in rows[hdr_i + 1:]:
        name = g(r, c_inst)
        rank_raw = g(r, c_rank)
        if not name or not rank_raw:
            continue
        out.append({
            "rank_raw": rank_raw,
            "rank": _rank_num(rank_raw),
            "prev_rank": _rank_num(g(r, c_prev)) if c_prev is not None else None,
            "institution": name,
            "country": g(r, c_ctry),
            "academic": num(g(r, c_acad)),
            "academic_rank": _rank_num(g(r, c_acad_r)),
            "employer": num(g(r, c_emp)),
            "employer_rank": _rank_num(g(r, c_emp_r)),
            "citations": num(g(r, c_cit)),
            "h_index": num(g(r, c_h)),
            "irn": num(g(r, c_irn)),
        })
        if limit and len(out) >= limit:
            break
    return out


def _rank_num(raw):
    """'51-100' -> 51, '=12' -> 12, '7' -> 7."""
    if not raw:
        return None
    m = re.search(r"\d+", raw.replace("=", ""))
    return int(m.group()) if m else None


def list_sheets(path=DEFAULT_PATH):
    return list(Workbook(path).sheets)
