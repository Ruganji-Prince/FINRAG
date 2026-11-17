"""Explicit financial query normalization and source-local evidence qualification.
No values are calculated, rewritten or inferred. Ambiguous table fragments fail closed.
"""

import re

MONTHS = "January February March April May June July August September October November December".split()


def expand(question):
    text = question
    for pattern, replacement in [
        (r"consumer price index", "CPI"),
        (r"producer price index", "PPI"),
        (r"gross domestic product", "GDP"),
        (r"year[ -](?:on|over)[ -]year", "annual"),
        (r"month[ -]on[ -]month", "monthly"),
        (r"headline inflation", "urban CPI"),
        (r"factory output", "industrial output"),
    ]:
        text = re.sub(pattern, replacement, text, flags=re.I)
    return text


def report_periods(question):
    return list(
        dict.fromkeys(
            m.group(0).lower()
            for m in re.finditer(
                r"\b(?:" + "|".join(MONTHS) + r")\s+(?:19|20)\d{2}\b", question, re.I
            )
        )
    )


def topic(question):
    q = expand(question).lower()
    if re.search(
        r"\bcpi\b|core index|fresh products index|imported goods index|energy index", q
    ):
        return "CPI"
    if re.search(r"\bppi\b|producer prices", q):
        return "PPI"
    if re.search(r"\bgdp\b", q):
        return "GDP"
    if re.search(r"industrial (?:production|output)|\biip\b", q):
        return "Industrial"
    return None


def frequency(pair, kind):
    item, sentence = pair
    text = sentence["text"]
    if kind == "annual":
        if re.search(r"annual average", text, re.I):
            return False
        if re.search(
            r"annual|year.on.year|year.over.year|same month of|same month in|same month last year|12 months",
            text,
            re.I,
        ):
            return True
        # NISR often says "compared to September 2025" rather than "annual".
        years = [int(x) for x in re.findall(r"\b(?:19|20)\d{2}\b", text)]
        if (
            len(set(years)) >= 2
            and max(years) - min(years) == 1
            and re.search(r"compared", text, re.I)
        ):
            return True
    else:
        if re.search(r"monthly|month.on.month", text, re.I):
            return True
    # A bullet/list can inherit a preceding explicit frequency marker within its chunk.
    prefix = item.get("_source_text", "").split(text, 1)[0]
    markers = list(re.finditer(r"\b(annual|monthly)\b", prefix, re.I))
    return bool(
        markers
        and markers[-1].group(1).lower() == kind
        and len(prefix) - markers[-1].end() < 650
    )


def scope(pair, requested):
    item, sentence = pair
    text = sentence["text"]
    if re.search(r"\b" + requested + r"\b", text, re.I):
        return True
    if re.search(r"\b(urban|rural|Rwanda CPI)\b", text, re.I):
        return False
    # Selected-indices paragraphs inherit only an explicit local urban heading;
    # a CPI title alone does not establish urban scope.
    prefix = item.get("_source_text", "").split(text, 1)[0]
    markers = list(re.finditer(r"\b(urban|rural)\b", prefix, re.I))
    return bool(markers and markers[-1].group(1).lower() == requested)


def qualify(candidates, question):
    q = expand(question)
    measures = [
        (r"energy index", r"energy index"),
        (r"core index|underlying inflation", r"core index|underlying inflation"),
        (r"fresh products index", r"fresh products index"),
        (r"imported goods index", r"imported goods index"),
        (r"local goods index", r"local goods index"),
        (r"export (?:ppi|producer)", r"export (?:ppi|producer)"),
        (r"local (?:ppi|producer)", r"local (?:ppi|producer)"),
    ]
    methodology = bool(
        re.search(
            r"methodology|sample|base year|rebasing|updated weights|definition|what does .{0,40}measure",
            q,
            re.I,
        )
    )
    out = []
    for item, sentence in candidates:
        text = sentence["text"]
        # Headings, axes and flattened matrices are not self-contained numerical claims.
        if re.search(
            r"\bTABLE\s*\d|Figure\s*\d|Jan-\d|Feb-\d", text, re.I
        ) and not re.search(
            r"\b(increased|decreased|grew|estimated|contributed|was|is|measures|updated)\b",
            text,
            re.I,
        ):
            continue
        words = text.split()
        if len(re.findall(r"\b\d+(?:[.,]\d+)?%?", text)) / max(1, len(words)) > 0.32:
            continue
        if any(
            re.search(requested, q, re.I) and not re.search(required, text, re.I)
            for requested, required in measures
        ):
            continue
        if methodology and not re.search(
            r"methodology|sample|weights|base year|rebased|rebase|measures|defined|definition",
            text,
            re.I,
        ):
            continue
        if re.search(r"\bindustrial output\b", q, re.I) and not re.search(
            r"industrial output", text, re.I
        ):
            continue
        if re.search(r"\baverage\b", q, re.I) and not re.search(
            r"\baverage\b", text, re.I
        ):
            continue
        if not re.search(r"\baverage\b", q, re.I) and re.search(
            r"annual average", text, re.I
        ):
            continue
        out.append((item, sentence))
    return out
