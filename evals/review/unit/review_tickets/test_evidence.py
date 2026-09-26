"""Evidence quotes must be the code at the reviewed commit."""
import evidence


def check(repo, location, code):
    return evidence.in_code({"location": location, "code": code}, str(repo["repo"]), repo["sha"])


def test_exact_quote_passes(repo):
    assert check(repo, "src/api.ts:3", '    const res = await fetch("/api/admin/users");')


def test_quote_with_other_whitespace_passes(repo):
    assert check(repo, "src/api.ts:3-4", 'const res = await fetch("/api/admin/users");\nif (!res.ok) return [];')


def test_ellipsis_elides(repo):
    assert check(repo, "src/api.ts:1-9", "export async function fetchUserList() {\n  ...\n    return [];")


def test_paraphrase_fails(repo):
    assert not check(repo, "src/api.ts:3", "fetch the admin users list")


def test_short_line_near_location_passes(repo):
    assert check(repo, "src/api.ts:2", "  try {")


def test_short_line_far_from_location_fails(repo):
    assert not check(repo, "src/api.ts:12", "  try {")


def test_multi_line_quote_cited_by_start_line(repo):
    # A 5-line quote cited only by its first line still has its closing lines in reach.
    code = "  try {\n    const res = await fetch(\"/api/admin/users\");\n    if (!res.ok) return [];\n    return (await res.json()).users ?? [];\n  } catch {"
    assert check(repo, "src/api.ts:2", code)


def test_missing_file_fails(repo):
    assert not check(repo, "src/nope.ts:1", "anything at all")


def test_location_without_line_fails(repo):
    assert not check(repo, "src/api.ts", "  try {")
