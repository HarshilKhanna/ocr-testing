"""
segmentation.py — Supreme Court cause-list case segmenter.

Three engines: tesseract, azure, paddle.

Tesseract pipeline (most complex — handles column-dump artifacts):
  1. _normalize_ocr_noise()       — strip = prefix / trailing dot on serial lines
  2. _reassemble_column_dumps()   — detect standalone-serial zones, infer missing
                                    serials, zip with case-type blocks, distribute
                                    party content from the parties column
  3. segment_cases_tesseract()    — split on inline serial boundaries, stitch
                                    page-break orphans, merge connected sub-cases
"""
import re
from typing import Optional


# ════════════════════════════════════════════════════════════════════
# TESSERACT — helpers
# ════════════════════════════════════════════════════════════════════

def _normalize_ocr_noise(line: str) -> str:
    """
    Strip common Tesseract mis-reads on serial-number lines.
      '14 =C.A. No. 2560/2020'    → '14 C.A. No. 2560/2020'
      '15. SLP(C) No. 11727/2020' → '15 SLP(C) No. 11727/2020'
    Normal lines are returned unchanged.
    """
    m = re.match(r'^(\s*)(\d{1,3}(?:\.\d+)?)(\.)?\s+([=]?\s*)(.*)', line)
    return f"{m.group(1)}{m.group(2)} {m.group(5)}" if m else line


def _is_genuine_inline_serial(stripped: str) -> bool:
    """
    True when a line begins with a real case serial number.
    Rejects 'IA No. …' and 'No. 2218/2023' fragments that start with a digit
    only because they follow 'in SLP(C)'.
    """
    if not re.match(r'^\d{1,3}(?:\.\d+)?\s+\S', stripped):
        return False
    return not re.match(r'^(?:IA|No\.)\s', stripped)


def _infer_serials(prev_inline: Optional[int],
                   found_standalones: list,
                   n_blocks: int) -> list:
    """
    Build the complete ordered serial list for a column-dump zone.

    Example: prev=7, found=[10,11,12,13], n_blocks=6
             → ['8','9','10','11','12','13']   (8 and 9 were absent from OCR)
    """
    if not found_standalones:
        start = (prev_inline or 0) + 1
        return [str(i) for i in range(start, start + n_blocks)]
    first_main = min(int(s.split('.')[0]) for s in found_standalones)
    start = (prev_inline or 0) + 1
    gap = [str(i) for i in range(start, first_main)]
    complete = gap + list(found_standalones)
    last_main = int(complete[-1].split('.')[0]) if complete else (prev_inline or 0)
    while len(complete) < n_blocks:
        last_main += 1
        complete.append(str(last_main))
    return complete[:n_blocks]


_CASE_TYPE_OPENER_RE = re.compile(
    r'(?m)^(?:C\.A\.|SLP\(|W\.P\.\(|Crl\.A\.|MA\s+\d|Diary\s+No\.)'
)
_BENCH_CODE_RE = re.compile(r'^(?:[IVX]+-?[A-Z]?|[A-Z]{1,3}|Il|PIL-\w+)$')


def _split_case_type_blocks(text: str) -> list:
    """Split a content block on case-type openers → per-case sub-blocks."""
    starts = [m.start() for m in _CASE_TYPE_OPENER_RE.finditer(text)]
    if not starts:
        return []
    return [text[s:(starts[k+1] if k+1 < len(starts) else len(text))].strip()
            for k, s in enumerate(starts)
            if text[s:(starts[k+1] if k+1 < len(starts) else len(text))].strip()]


def _find_party_start_in_block(block: str) -> int:
    """
    Return the char offset inside the last case-type block where party names begin.
    Skips: the case-type header line, the bench-code line, blank lines.
    """
    lines = block.split('\n')
    pos, seen = 0, False
    for line in lines:
        s = line.strip()
        if not s:
            pos += len(line) + 1
            continue
        if re.match(r'^(?:C\.A\.|SLP\(|W\.P\.\(|Crl\.A\.|MA\s+\d|Diary\s+No\.)', s):
            seen = True
            pos += len(line) + 1
            continue
        if seen and (_BENCH_CODE_RE.match(s) or re.match(r'^[\d\-/,]+$', s)):
            pos += len(line) + 1
            continue
        if seen:
            return pos
        pos += len(line) + 1
    return len(block)


_PARTY_SKIP = (
    'IA ', 'FOR ', 'IN ', 'I.R.', 'SLP', 'C.A.', 'Diary', 'W.P.', 'Crl.',
    'FILING', 'C/C', 'AFFIDAVIT', 'CONDONATION', 'EXEMPTION', 'PERMISSION',
    'CLARIFICATION', 'STAY', 'RELIEF', 'APPLICATION', 'MODIFICATION',
    'No.', 'ADDL', 'LENGTHY', 'ADDITIONAL',
)


def _looks_like_party(text: str) -> bool:
    """True when the first line of text looks like a party/litigant name."""
    fl = text.strip().split('\n')[0].strip()
    if not fl or not fl[0].isupper():
        return False
    if any(fl.startswith(s) for s in _PARTY_SKIP):
        return False
    if not re.match(r'^[A-Z][A-Z0-9\s\.,&/@\-()\'\"M/S]+$', fl):
        return False
    return len(fl) >= 4


def _split_resp_frag(text: str) -> tuple:
    """
    Split a between-Versus fragment into (respondent_and_IAs, next_petitioner).
    When the last party name is at the START of the fragment (no preceding IAs),
    the whole fragment is the respondent and next_petitioner is empty.
    """
    paras = re.split(r'\n\n+', text.strip())
    last = next((i for i in range(len(paras)-1, -1, -1) if _looks_like_party(paras[i])), None)
    if last is None:
        return text.strip(), ""
    if last > 0:
        return '\n\n'.join(paras[:last]).strip(), '\n\n'.join(paras[last:]).strip()
    return text.strip(), ""   # party at position 0 → whole block = respondent


def _split_frag0(text: str) -> tuple:
    """
    Split fragment[0] (before the first Versus) into:
      (inline_respondent_for_prev_case,  petitioner_for_first_dump_case)
    If only one party name is present it IS the first petitioner (no inline resp).
    """
    paras = re.split(r'\n\n+', text.strip())
    last = next((i for i in range(len(paras)-1, -1, -1) if _looks_like_party(paras[i])), None)
    if last is None or last == 0:
        return "", text.strip()
    return '\n\n'.join(paras[:last]).strip(), '\n\n'.join(paras[last:]).strip()


def _distribute_parties(case_blocks: list, serials: list, party_content: str) -> tuple:
    """
    Distribute the parties column dump across the reassembled case blocks.

    The party column typically looks like:
        INLINE_RESP                 ← respondent for the preceding inline case
        PETITIONER_0
        Versus
        RESPONDENT_0 [IAs]
        PETITIONER_1
        Versus
        RESPONDENT_1 [IAs]
        …

    Returns (inline_respondent, [party_block_per_case]).
    inline_respondent is appended to the preceding inline case by the caller.
    """
    frags = re.compile(r'\n[ \t]*Versus[ \t]*\n').split(party_content)
    n = len(case_blocks)
    if len(frags) < 2:
        return "", [party_content] + [""] * (n - 1)

    frag0_resp, case0_pet = _split_frag0(frags[0])

    blocks = []
    for i in range(n):
        pet = case0_pet if i == 0 else _split_resp_frag(frags[i])[1]
        resp = _split_resp_frag(frags[i + 1])[0] if i + 1 < len(frags) else ""
        if pet and resp:
            blocks.append(f"{pet}\nVersus\n{resp}")
        elif pet:
            blocks.append(pet)
        elif resp:
            blocks.append(f"Versus\n{resp}")
        else:
            blocks.append("")

    return frag0_resp, blocks


# ════════════════════════════════════════════════════════════════════
# TESSERACT — column-dump reassembler
# ════════════════════════════════════════════════════════════════════

def _reassemble_column_dumps(text: str) -> str:
    """
    Fix Tesseract --psm 4 column-dump artefacts:

    Tesseract reads a 3-column table column-by-column, so instead of:
        8 SLP(C) No. 14930/2019  SHREETRON LTD.  Versus  BHARAT SANCHAR …
    it produces:
        10              ← standalone serial col
        11
        12
        13
        SLP(C) No. 14930/2019   ← case-type col (no serial prefix)
        SLP(C) No. 14368/2021
        …
        SHREETRON LTD.          ← party col (no serial prefix)
        Versus
        BHARAT SANCHAR …
        …

    This function:
      1. Normalises OCR noise on every line (= prefix, trailing dot on serial).
      2. Detects zones of 2+ consecutive standalone numbers.
      3. Infers any completely absent serials (e.g. 8 and 9 were not in OCR at all).
      4. Splits following content into case-type blocks + party block.
      5. Distributes party block across cases using Versus as a delimiter.
      6. Emits fully reconstructed inline-style lines.
    """
    text = '\n'.join(_normalize_ocr_noise(l) for l in text.split('\n'))
    lines = text.split('\n')
    output: list = []
    i = 0
    last_inline: Optional[int] = None

    while i < len(lines):
        stripped = lines[i].strip()

        # ── normal inline serial line ─────────────────────────────────────────
        if _is_genuine_inline_serial(stripped):
            m = re.match(r'^(\d{1,3})', stripped)
            if m:
                last_inline = int(m.group(1))
            output.append(lines[i])
            i += 1
            continue

        # ── detect start of standalone-serial dump zone ───────────────────────
        if re.match(r'^\d{1,3}(?:\.\d+)?$', stripped) and stripped:
            j = i
            standalones: list = []
            while j < len(lines):
                s = lines[j].strip()
                if re.match(r'^\d{1,3}(?:\.\d+)?$', s) and s:
                    standalones.append(s)
                    j += 1
                elif s == '':
                    j += 1
                else:
                    break

            if len(standalones) < 2:          # single number — not a dump
                output.append(lines[i])
                i += 1
                continue

            # Find end of content window (where the next inline serial begins)
            nxt = next(
                (k for k in range(j, len(lines)) if _is_genuine_inline_serial(lines[k].strip())),
                len(lines)
            )
            content = '\n'.join(lines[j:nxt])
            case_blocks = _split_case_type_blocks(content)

            if not case_blocks:
                output.append(lines[i])
                i += 1
                continue

            full_serials = _infer_serials(last_inline, standalones, len(case_blocks))

            # ── separate case-type content from party content ─────────────────
            type_starts = [m.start() for m in _CASE_TYPE_OPENER_RE.finditer(content)]
            if type_starts:
                last_type_start = type_starts[-1]
                last_block_text = content[last_type_start:]
                psi = _find_party_start_in_block(last_block_text)
                if psi < len(last_block_text):
                    party_content = content[last_type_start + psi:].strip()
                    clean_last = last_block_text[:psi].strip()
                    case_blocks = case_blocks[:-1] + ([clean_last] if clean_last else [])
                else:
                    party_content = ""
            else:
                party_content = ""

            # ── distribute party content ──────────────────────────────────────
            if party_content:
                inline_resp, party_blocks = _distribute_parties(
                    case_blocks, full_serials, party_content
                )
                if inline_resp:
                    # Append the preceding inline case's respondent
                    output.append(f"Versus\n{inline_resp}")
            else:
                party_blocks = [""] * len(case_blocks)

            # ── emit reassembled cases ────────────────────────────────────────
            for serial, cblock, pb in zip(full_serials, case_blocks, party_blocks):
                combined = f"{cblock}\n{pb}" if pb else cblock
                nl = combined.find('\n')
                if nl == -1:
                    output.append(f"{serial} {combined}")
                else:
                    output.append(f"{serial} {combined[:nl]}\n{combined[nl + 1:]}")
                last_inline = int(serial.split('.')[0])

            i = nxt
            continue

        output.append(lines[i])
        i += 1

    return '\n'.join(output)


# ════════════════════════════════════════════════════════════════════
# TESSERACT — core segmenter
# ════════════════════════════════════════════════════════════════════

_TESSERACT_LEADING_RE = re.compile(
    r'^(?P<main>\d{1,3})(?:\.(?P<sub>\d+))?\s+(?!(?:No\.|no\.|NO\.))'
)
_TESSERACT_SPLIT_RE = re.compile(
    r'(?=(?:^|\n)\s*\d{1,3}(?:\.\d+)?\s+(?!No\.|no\.|NO\.)[A-Z({\[])',
    re.MULTILINE,
)


def _tesseract_parse_serial(block: str) -> Optional[tuple]:
    m = _TESSERACT_LEADING_RE.match(block.lstrip())
    if not m:
        return None
    return int(m.group("main")), (int(m.group("sub")) if m.group("sub") else None)


def segment_cases_tesseract(text: str) -> dict:
    """
    Parse raw Tesseract OCR into {serial_key: full_case_text}.

    Pipeline:
      1. _reassemble_column_dumps() — fixes column-dump artefacts, distributes
         party content, recovers absent serials.
      2. Split on inline-serial boundaries (tight regex, no IA false-fires).
      3. Orphan stitching — blocks with no leading serial are appended to the
         last seen parent (handles page-break tails and advocate columns).
      4. Connected-case merging — sub-serials (4.1, 25.7 …) are folded into
         their parent key so querying cases["4"] returns the full cluster.

    Residual limitations (inherent to Tesseract --psm 4 multi-column output):
      • Cases 14–16 and 17 have no party text — Tesseract placed their parties
        in an unstructured block appended to case 17.2 (the last inline case
        before the next dump zone). Those blocks are too interleaved with
        advocate names to distribute reliably.
      • Case 34: NITESH PURI in the output is the advocate name, not a party.
        The actual case-34 party content is absent from this OCR pass.
      Re-running with --psm 6 eliminates these issues at source.
    """
    text = _reassemble_column_dumps(text)

    cases: dict = {}
    last_key: Optional[str] = None

    for block in _TESSERACT_SPLIT_RE.split(text):
        block = block.strip()
        if not block:
            continue
        parsed = _tesseract_parse_serial(block)
        if parsed is None:
            if last_key:
                cases[last_key] += "\n\n" + block
            continue
        main, sub = parsed
        key = str(main)
        if sub is not None:
            cases[key] = cases.get(key, '') + f"\n\n--- Connected {main}.{sub} ---\n{block}"
        else:
            cases[key] = cases.get(key, '') + ("\n\n" if key in cases else "") + block
        last_key = key

    return cases


# ================================
# AZURE SEGMENTATION
# ================================

def _azure_tag_line(line: str) -> str:
    """
    Classify a single line for blob-splitting purposes.

    VERSUS   — line begins with 'Versus'
    IA       — IA/FOR application line or I.R. notation
    ADVOCATE — contains [R-N] / [P-N] / [CAVEAT] bracket notation
    EMPTY    — blank line
    PARTY    — everything else (party name, court remark, …)
    """
    s = line.strip()
    if not s:
        return 'EMPTY'
    if re.match(r'^Versus\b', s):
        return 'VERSUS'
    if (re.match(r'^IA (?:No\.|FOR )', s) or
            re.match(
                r'^FOR (?:EXEMPTION|ADMISSION|CONDONATION|PERMISSION|'
                r'GRANT|APPLICATION|MODIFICATION|STAY|CLARIFICATION|'
                r'APPROPRIATE|I\.R\.)',
                s,
            ) or
            re.match(r'^I\.R\.', s)):
        return 'IA'
    if re.search(r'\[(?:R|P|CAVEAT)-', s):
        return 'ADVOCATE'
    return 'PARTY'


def _azure_split_blob(blob: str) -> list[str]:
    """
    Split a content blob containing multiple merged case entries into one
    block per Petitioner/Versus/Respondent unit.

    Algorithm
    ---------
    For each consecutive pair of Versus lines (V[k-1], V[k]) we find where
    V[k-1]'s respondent section ends and V[k]'s petitioner section begins:

    * If V[k-1] carries an inline respondent ("Versus FOO BAR"), the very
      next non-empty, non-IA, non-ADVOCATE line is a new petitioner.
    * Otherwise the first PARTY line after V[k-1] is the respondent; the
      next PARTY line after any IA/ADVOCATE lines is the new petitioner.

    block[0] contains content that belongs to the blob-owner case.
    blocks[1..] contain content for the stub cases that precede the owner.
    """
    lines = blob.split('\n')
    n = len(lines)
    tags = [_azure_tag_line(l) for l in lines]

    def versus_is_inline(i: int) -> bool:
        s = lines[i].strip()
        m = re.match(r'^Versus\s+(.+)', s)
        return bool(m and m.group(1).strip())

    versus_positions = [i for i, t in enumerate(tags) if t == 'VERSUS']
    if not versus_positions:
        return [blob.strip()] if blob.strip() else []

    pet_starts: list[int] = []

    for k, vi in enumerate(versus_positions):
        if k == 0:
            pet_starts.append(0)
            continue

        prev_vi = versus_positions[k - 1]
        inline = versus_is_inline(prev_vi)

        j = prev_vi + 1
        last_section_end = prev_vi
        respondent_found = inline  # inline Versus already consumed the respondent

        while j < vi:
            t = tags[j]
            if t == 'EMPTY':
                j += 1
                continue
            if not respondent_found and t == 'PARTY':
                # First PARTY after a non-inline Versus = respondent name
                last_section_end = j
                respondent_found = True
            elif t in ('IA', 'ADVOCATE'):
                last_section_end = j
                respondent_found = True
            elif t == 'PARTY' and respondent_found:
                # Second PARTY line after respondent section = new petitioner — stop
                break
            j += 1

        ps = last_section_end + 1
        while ps < vi and tags[ps] == 'EMPTY':
            ps += 1
        pet_starts.append(ps)

    blocks: list[str] = []
    for k in range(len(pet_starts)):
        start = pet_starts[k]
        end = pet_starts[k + 1] if k + 1 < len(pet_starts) else n
        block = '\n'.join(lines[start:end]).strip()
        if block:
            blocks.append(block)

    return blocks


_STRUCTURAL_LINE_RE = re.compile(
    r'^(?:'
    r'---\s*Connected'
    r'|\d{1,3}(?:\.\d+)?\s+'
    r'|(?:C\.A\.|SLP\(|W\.P\.\(|Crl\.A\.|MA\s+\d|Diary\s+No\.)'
    r')'
)


def _azure_tag_for_struct(line: str) -> str:
    """Tag a line for blob-start detection purposes."""
    s = line.strip()
    if not s:
        return 'EMPTY'
    if re.match(r'^Versus\b', s):
        return 'VERSUS'
    if (re.match(r'^IA (?:No\.|FOR )', s) or
            re.match(
                r'^FOR (?:EXEMPTION|ADMISSION|CONDONATION|PERMISSION|GRANT|'
                r'APPLICATION|MODIFICATION|STAY|CLARIFICATION|APPROPRIATE|I\.R\.)',
                s,
            ) or re.match(r'^I\.R\.', s)):
        return 'IA'
    if re.search(r'\[(?:R|P|CAVEAT)-', s):
        return 'ADVOCATE'
    if _STRUCTURAL_LINE_RE.match(s) or s.startswith('---'):
        return 'STRUCTURAL'
    return 'PARTY'


def _azure_find_blob_start(text: str) -> int:
    """
    Find the character index where the redistributable blob begins inside
    a blob-owner's full text.

    Two things can precede the blob:

    A) Structural headers — the serial/case-type line plus any embedded
       '--- Connected X.Y ---' sub-case blocks.  The blob starts at the
       first petitioner line immediately after the last structural block.
       (Walk backwards from first Versus to first structural/IA/ADVOCATE line.)

    B) Owner-content preamble — ADVOCATE/IA lines that belong to the blob
       owner's own case (e.g. respondent advocate + IA numbers for case 34
       that appear before the redistributable Versus blocks).
       (Scan forward past structural section and skip ADVOCATE/IA lines.)

    Returns max(A, B) so both patterns are handled correctly.
    """
    lines = text.split('\n')
    n = len(lines)
    tags = [_azure_tag_for_struct(l) for l in lines]

    # ── A: walk back from first Versus ───────────────────────────────────────
    first_versus = next((i for i, t in enumerate(tags) if t == 'VERSUS'), None)
    if first_versus is None:
        return len(text)

    pet_a = first_versus - 1
    while pet_a >= 0:
        t = tags[pet_a]
        if t == 'EMPTY':
            pet_a -= 1
            continue
        if t in ('STRUCTURAL', 'IA', 'ADVOCATE', 'VERSUS'):
            pet_a += 1
            while pet_a < first_versus and tags[pet_a] == 'EMPTY':
                pet_a += 1
            break
        pet_a -= 1
    else:
        pet_a = 0

    pos_a = sum(len(l) + 1 for l in lines[:pet_a])

    # ── B: scan forward past structural section, skip ADVOCATE/IA preamble ──
    struct_end = 0
    i = 0
    while i < n:
        if tags[i] in ('STRUCTURAL', 'EMPTY'):
            struct_end = i
            i += 1
        else:
            break

    preamble_end = struct_end
    j = struct_end + 1
    while j < n:
        if tags[j] in ('ADVOCATE', 'IA'):
            preamble_end = j
            j += 1
        elif tags[j] == 'EMPTY':
            j += 1
        else:
            break

    pos_b = (sum(len(l) + 1 for l in lines[:preamble_end + 1])
             if preamble_end > struct_end else 0)

    return max(pos_a, pos_b)


def _azure_redistribute_blobs(cases: dict[str, str]) -> dict[str, str]:
    """
    Detect cases whose text contains multiple Versus blocks (blob owners)
    that are preceded by stub cases (zero Versus occurrences), then
    redistribute the blob content back to those stub cases.

    A "stub" has zero Versus in its full text (including Connected sub-cases).
    A "blob owner" has ≥ 2 Versus blocks — it has swallowed content from
    neighbouring stubs.

    Redistribution
    --------------
    For a run of stubs [s1 … sN] immediately followed by blob_owner B:
      1. Identify the blob-carrying section: if the last Connected sub-section
         of B contains ≥ 2 Versus blocks, that sub-section is the blob.
         Otherwise the whole key text is the blob (original behaviour).
      2. Find the blob start using _azure_find_blob_start().
      3. Split the blob via _azure_split_blob() into M blocks.
      4. Assign blocks[0..N-1] to stubs s1..sN in order.
      5. Append blocks[N..] back to B's blob-carrying section.
         B retains its structural header + any excess blocks.
    """
    def count_versus(text: str) -> int:
        return len(re.findall(r'\bVersus\b', text))

    def is_stub(key: str) -> bool:
        return count_versus(result[key]) == 0

    all_keys = sorted(cases.keys(), key=lambda k: float(k))
    result = dict(cases)

    i = 0
    while i < len(all_keys):
        key = all_keys[i]

        if not is_stub(key):
            i += 1
            continue

        # Collect the run of consecutive stubs
        stub_run: list[str] = []
        j = i
        while j < len(all_keys) and is_stub(all_keys[j]):
            stub_run.append(all_keys[j])
            j += 1

        if j >= len(all_keys):
            i = j
            continue

        blob_owner_key = all_keys[j]
        blob_owner_text = result[blob_owner_key]

        # ── Determine which section of the blob owner actually carries the blob ──
        # Split on '--- Connected N.M ---' markers to get sections.
        # The last section with ≥ 2 Versus is the blob carrier.
        connected_split_re = re.compile(r'(?=\n--- Connected )')
        sections = connected_split_re.split(blob_owner_text)
        # sections[0] = parent content, sections[1..] = Connected sub-sections

        # Find the last section that has ≥ 2 Versus (the blob carrier)
        blob_section_idx = None
        for si in range(len(sections) - 1, -1, -1):
            if count_versus(sections[si]) >= 2:
                blob_section_idx = si
                break

        if blob_section_idx is None:
            # No section has ≥ 2 Versus — nothing to redistribute
            i = j + 1
            continue

        blob_section_text = sections[blob_section_idx]

        # Find the blob start within this section
        blob_start = _azure_find_blob_start(blob_section_text)
        structural_header = blob_section_text[:blob_start].rstrip()
        blob = blob_section_text[blob_start:]

        blob_blocks = _azure_split_blob(blob)
        if not blob_blocks:
            i = j + 1
            continue

        n_stubs = len(stub_run)

        # blocks[0..N-1] → stubs in order.
        # Insert content BEFORE any '--- Connected' sub-case blocks so the
        # party data appears at the top of the stub entry, not after sub-cases.
        for idx, stub_key in enumerate(stub_run):
            if idx >= len(blob_blocks):
                break
            stub_text = result[stub_key]
            connected_marker = '\n--- Connected'
            insert_at = stub_text.find(connected_marker)
            if insert_at != -1:
                result[stub_key] = (
                    stub_text[:insert_at].rstrip()
                    + '\n' + blob_blocks[idx]
                    + stub_text[insert_at:]
                )
            else:
                result[stub_key] = stub_text.rstrip() + '\n' + blob_blocks[idx]

        # blocks[N..] → back into the blob-carrying section of the blob owner
        owner_extra = blob_blocks[n_stubs:]
        if owner_extra:
            sections[blob_section_idx] = (
                structural_header + '\n' + '\n'.join(owner_extra)
            ).strip()
        else:
            sections[blob_section_idx] = structural_header.strip()

        result[blob_owner_key] = '\n'.join(s for s in sections if s.strip())

        i = j + 1

    return result


def segment_cases_azure(text: str) -> dict[str, str]:
    """
    Segment cases from Azure Document Intelligence output.

    Azure returns linearized, reading-order text — no column-dump artifacts.
    The same serial-boundary splitting used for Tesseract works directly here,
    without the column-dump reassembly pre-pass.

    After initial segmentation, _azure_redistribute_blobs() detects cases where
    Azure merged multiple cases' party/IA content into a single trailing blob and
    redistributes that content back to the preceding stub cases.

    Connected cases (e.g. 4.1, 5.8) are merged under their parent key.
    """
    # Strip page markers inserted by the extractor (=== PAGE N ===)
    text = re.sub(r'\n*=== PAGE \d+ ===\n*', '\n', text)

    # Split on inline serial boundaries (same regex as Tesseract)
    raw_blocks: list[str] = _TESSERACT_SPLIT_RE.split(text)

    # Classify each block
    classified: list[tuple[Optional[int], Optional[int], str]] = []
    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        parsed = _tesseract_parse_serial(block)
        if parsed is None:
            classified.append((None, None, block))
        else:
            classified.append((parsed[0], parsed[1], block))

    # Stitch orphans + merge sub-cases.
    # Key fix: when a parent block arrives after its sub-cases have already
    # initialised the key, prepend the parent content so that party/Versus
    # data always sits at the top — where _azure_find_blob_start and
    # _azure_split_blob expect it.
    cases: dict[str, str] = {}
    last_key: Optional[str] = None

    for main, sub, blk in classified:
        if main is None:
            if last_key:
                cases[last_key] += "\n\n" + blk
            continue

        key = str(main)

        if sub is not None:
            if key in cases:
                cases[key] += f"\n\n--- Connected {main}.{sub} ---\n{blk}"
            else:
                # Sub-case arrived before its parent — initialise with a
                # Connected marker so the parent can detect this later.
                cases[key] = f"--- Connected {main}.{sub} ---\n{blk}"
            last_key = key
        else:
            if key in cases:
                # Parent block arriving after sub-cases have already seeded
                # the key: prepend so party content is always at the top.
                if cases[key].startswith("--- Connected"):
                    cases[key] = blk + "\n\n" + cases[key]
                else:
                    cases[key] += "\n\n" + blk
            else:
                cases[key] = blk
            last_key = key

    # Redistribute multi-case blobs from blob owners back to stub cases
    cases = _azure_redistribute_blobs(cases)

    return cases


# ================================
# PADDLE SEGMENTATION (ROBUST)
# ================================

SERIAL_PATTERN = re.compile(
    r'^\s*(\d+(?:\.\d+)?)(?:\s*$|\s*Connected\b)',
    re.MULTILINE,
)

CASE_TYPE_PATTERN = re.compile(
    r'^(C\.A\. No\.|SLP\(C\) No\.|MA\s+\d+/\d+|Diary No\.)',
    re.MULTILINE
)


def segment_cases_paddle(text: str) -> dict[str, str]:
    """
    Segment cases from Paddle OCR output.
    Handles normal serial numbers, connected cases, and layout drift.
    """
    matches = list(SERIAL_PATTERN.finditer(text))
    if not matches:
        return {}

    cases = {}
    for i, match in enumerate(matches):
        serial = match.group(1)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()

        if "." in serial:
            parent_serial = serial.split(".")[0]
            if parent_serial in cases:
                cases[parent_serial] += f"\n\n--- Connected Case {serial} ---\n{block}"
            else:
                cases[parent_serial] = f"--- Connected Case {serial} ---\n{block}"
        else:
            cases[serial] = block

    return _repair_layout_drift(cases)


def _repair_layout_drift(cases: dict[str, str]) -> dict[str, str]:
    """
    Fix layout drift where the next case's case-type line appears inside
    the previous block due to OCR reading order.
    Only applies to top-level cases, not Connected sub-case content.
    """
    serials = sorted(cases.keys(), key=lambda x: float(x))

    for i in range(len(serials) - 1):
        current_serial = serials[i]
        next_serial = serials[i + 1]
        current_text = cases[current_serial]

        # Only scan the parent portion — stop before any Connected sub-case blocks
        connected_marker = '\n\n--- Connected Case'
        parent_end = current_text.find(connected_marker)
        parent_text = current_text[:parent_end] if parent_end != -1 else current_text

        matches = list(CASE_TYPE_PATTERN.finditer(parent_text))

        if not matches:
            continue

        last_match = matches[-1]
        if last_match.start() > len(parent_text) * 0.6:
            trailing = parent_text[last_match.start():].strip()
            cases[current_serial] = parent_text[:last_match.start()].strip()
            if parent_end != -1:
                cases[current_serial] += current_text[parent_end:]
            cases[next_serial] = trailing + "\n" + cases[next_serial]

    return cases


# ================================
# DISPATCHER
# ================================

def segment_cases(text: str, selected_engine: str) -> dict[str, str]:
    """
    Segment cases based on the OCR engine used.

    Args:
        text: Raw OCR text
        selected_engine: 'tesseract', 'azure', or 'paddle'

    Returns:
        Dictionary mapping case identifiers to case content

    Raises:
        ValueError: If engine is not supported
    """
    if selected_engine == "tesseract":
        return segment_cases_tesseract(text)
    elif selected_engine == "azure":
        return segment_cases_azure(text)
    elif selected_engine == "paddle":
        return segment_cases_paddle(text)
    else:
        raise ValueError(f"Unsupported OCR engine: {selected_engine}")